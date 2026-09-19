/**
 * Shared Gold Miner logic. Attaches to globalThis.GoldMinerShared.
 * Usable from content scripts and Node tests. No secrets here.
 */
(function (root) {
  "use strict";

  const STRINGS = {
    zh: {
      searchTitle: "跨语言候选",
      exploreTitle: "继续探索",
      originalQuery: "原始查询",
      purpose: "用途",
      source: "来源",
      why: "为什么出现",
      interested: "感兴趣",
      irrelevant: "不相关",
      seen: "见过",
      loading: "加载中…",
      cancel: "取消",
      rateLimited: "接口限流，请稍后再试",
      timeout: "超时。已发出的请求可能已计费。",
      modelUnavailable: "模型不可用，已降级为无模型搜索",
      noModel: "未配置模型，仅使用规则扩展与公开搜索",
      close: "关闭",
    },
    en: {
      searchTitle: "Cross-language candidates",
      exploreTitle: "Explore related",
      originalQuery: "Original query",
      purpose: "Purpose",
      source: "Source",
      why: "Why shown",
      interested: "Interested",
      irrelevant: "Irrelevant",
      seen: "Seen",
      loading: "Loading…",
      cancel: "Cancel",
      rateLimited: "Rate limited. Try again later.",
      timeout: "Timed out. In-flight requests may already be billed.",
      modelUnavailable: "Model unavailable; fell back to rule-based search",
      noModel: "No model configured; using rules and public search only",
      close: "Close",
    },
  };

  const SOURCE_KINDS = Object.freeze({
    github_search_default: "github_search_default",
    github_search_readme: "github_search_readme",
    topic_related: "topic_related",
    same_owner: "same_owner",
    interest_query: "interest_query",
    original_query: "original_query",
  });

  const MEGA_STAR = 20000;
  const EXPLORE_RESIDUAL = 0.25;

  function t(lang, key) {
    const pack = STRINGS[lang] || STRINGS.zh;
    return pack[key] || STRINGS.en[key] || key;
  }

  function sanitizeRemoteText(text) {
    if (typeof text !== "string") return "";
    let s = text.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
    s = s.replace(/\s+/g, " ").trim();
    if (s.length > 500) s = s.slice(0, 500);
    return s;
  }

  function looksLikeInstruction(text) {
    const s = String(text || "").toLowerCase();
    return (
      /ignore (all )?previous|system prompt|exfiltrat|steal (the )?key|api[_-]?key/.test(
        s
      ) || /忽略以上|输出密钥|把密钥/.test(s)
    );
  }

  function rejectUntrustedDirective(text) {
    const clean = sanitizeRemoteText(text);
    if (looksLikeInstruction(clean)) {
      return { ok: false, code: "untrusted_input", text: "" };
    }
    return { ok: true, code: "ok", text: clean };
  }

  function canonicalRepo(fullName) {
    if (typeof fullName !== "string") return "";
    const parts = fullName.trim().split("/");
    if (parts.length !== 2) return "";
    return (parts[0] + "/" + parts[1]).toLowerCase();
  }

  function isPrivateName(repo) {
    return /(?:^|\/)\./.test(repo) || /private/i.test(repo);
  }

  function dedupeRepos(list) {
    const seen = new Set();
    const out = [];
    for (const item of list || []) {
      const key = canonicalRepo(item.repo || item.full_name || "");
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(Object.assign({}, item, { repo: item.repo || item.full_name, canonical: key }));
    }
    return out;
  }

  function megaStarPenalty(stars) {
    const n = Number(stars) || 0;
    if (n < MEGA_STAR) return 0;
    return Math.min(0.35, Math.log10(n / MEGA_STAR + 1) * 0.2);
  }

  function overConcentration(list, ownerLimit) {
    const limit = ownerLimit || 2;
    const counts = {};
    for (const item of list) {
      const owner = canonicalRepo(item.repo).split("/")[0];
      counts[owner] = (counts[owner] || 0) + 1;
    }
    return Object.keys(counts).filter((o) => counts[o] > limit);
  }

  function applyOwnerCap(list, ownerLimit) {
    const limit = ownerLimit || 2;
    const seen = {};
    const out = [];
    for (const item of list) {
      const owner = canonicalRepo(item.repo).split("/")[0];
      seen[owner] = seen[owner] || 0;
      if (seen[owner] >= limit) continue;
      seen[owner] += 1;
      out.push(item);
    }
    return out;
  }

  function interestOverlap(text, interests) {
    const blob = String(text || "").toLowerCase();
    let hits = 0;
    for (const raw of interests || []) {
      const w = String(raw).trim().toLowerCase();
      if (w && blob.includes(w)) hits += 1;
    }
    return hits;
  }

  function scoreCandidate(item, ctx) {
    ctx = ctx || {};
    const interests = ctx.interests || [];
    const seen = new Set((ctx.seen || []).map((r) => canonicalRepo(r)));
    const feedback = ctx.feedback || {};
    const pageRepo = canonicalRepo(ctx.pageRepo || "");
    const key = canonicalRepo(item.repo);
    if (!key) return -999;
    if (seen.has(key) && ctx.hideSeen) return -500;
    if (key === pageRepo) return -400;
    const fb = feedback[key];
    if (fb === "irrelevant") return -300;
    let score = 1;
    if (fb === "interested") score += 1.2;
    score += 0.4 * interestOverlap(
      (item.description || "") + " " + (item.purpose || "") + " " + (item.why || ""),
      interests
    );
    if (item.source === SOURCE_KINDS.original_query) score += 0.2;
    if (item.source === SOURCE_KINDS.github_search_readme) score += 0.05;
    score -= megaStarPenalty(item.stars);
    if (ctx.personalization === false) {
      score = 1 - megaStarPenalty(item.stars);
    }
    return score;
  }

  function rerank(candidates, ctx) {
    ctx = ctx || {};
    const residual = ctx.explorationResidual == null ? EXPLORE_RESIDUAL : ctx.explorationResidual;
    const cleaned = dedupeRepos(candidates).filter((c) => !isPrivateName(c.repo || ""));
    const scored = cleaned
      .map((c) => ({ item: c, score: scoreCandidate(c, ctx) }))
      .filter((x) => x.score > -200)
      .sort((a, b) => b.score - a.score);
    const n = Math.max(1, Math.round(scored.length * residual));
    const head = scored.slice(0, Math.max(0, scored.length - n));
    const tail = scored.slice(Math.max(0, scored.length - n));
    const mixed = ctx.personalization === false ? scored : head.concat(tail);
    const capped = applyOwnerCap(
      mixed.map((x) =>
        Object.assign({}, x.item, {
          score: x.score,
          why:
            x.item.why ||
            "rule-score=" +
              x.score.toFixed(2) +
              "; source=" +
              (x.item.source || "unknown"),
        })
      ),
      2
    );
    return capped.slice(0, ctx.limit || 5);
  }

  function cacheKey(parts) {
    parts = parts || {};
    return [
      parts.pageKind || "unknown",
      parts.contentVersion || "none",
      parts.language || "zh",
      parts.processingMode || "rules",
      sanitizeRemoteText(parts.query || "").slice(0, 80),
    ].join("|");
  }

  function Budget(maxRequests) {
    this.max = maxRequests || 4;
    this.used = 0;
    this.cancelled = false;
  }
  Budget.prototype.canStart = function () {
    return !this.cancelled && this.used < this.max;
  };
  Budget.prototype.mark = function () {
    this.used += 1;
  };
  Budget.prototype.cancel = function () {
    this.cancelled = true;
  };

  function expandQueries(original, lang, interests) {
    const q = sanitizeRemoteText(original);
    if (!q) return [];
    const out = [{ query: q, lang: lang, source: SOURCE_KINDS.original_query }];
    const table = {
      "剪贴板": "clipboard history",
      "局域网": "lan file transfer",
      "订阅": "rss feed reader",
      "clipboard": "剪贴板 历史",
      "rss": "订阅 阅读器",
    };
    if (lang === "zh") {
      for (const k of Object.keys(table)) {
        if (q.includes(k) && /[\u4e00-\u9fff]/.test(k)) {
          out.push({
            query: table[k],
            lang: "en",
            source: SOURCE_KINDS.github_search_default,
          });
        }
      }
    } else {
      for (const k of Object.keys(table)) {
        if (q.toLowerCase().includes(k) && !/[\u4e00-\u9fff]/.test(k)) {
          out.push({
            query: table[k],
            lang: "zh",
            source: SOURCE_KINDS.github_search_default,
          });
        }
      }
    }
    for (const interest of (interests || []).slice(0, 2)) {
      const w = sanitizeRemoteText(interest);
      if (w) {
        out.push({
          query: q + " " + w,
          lang: lang,
          source: SOURCE_KINDS.interest_query,
        });
      }
    }
    const seen = new Set();
    return out.filter((row) => {
      if (seen.has(row.query)) return false;
      seen.add(row.query);
      return true;
    }).slice(0, 4);
  }

  function sanitizeExport(bundle) {
    const out = {
      format: "gold-miner-cache-v1",
      exported_at: bundle && bundle.exported_at,
      entries: [],
    };
    const entries = (bundle && bundle.entries) || [];
    for (const e of entries) {
      if (!e || typeof e !== "object") continue;
      const repo = canonicalRepo(e.repo || "");
      if (!repo || isPrivateName(repo) || e.private === true) continue;
      if (e.private_note || e.apiKey || e.token || e.OPENAI_API_KEY) continue;
      const purpose = rejectUntrustedDirective(e.purpose || e.description || "");
      out.entries.push({
        repo: e.repo,
        purpose: purpose.text,
        source: e.source || "unknown",
        language: e.language || "",
        content_version: e.content_version || "",
        processing_mode: e.processing_mode || "",
      });
    }
    return out;
  }

  function allowedMessage(sender) {
    if (!sender) return false;
    if (sender.id && root.chrome && root.chrome.runtime && sender.id !== root.chrome.runtime.id) {
      return false;
    }
    return true;
  }

  root.GoldMinerShared = {
    STRINGS,
    SOURCE_KINDS,
    MEGA_STAR,
    t,
    sanitizeRemoteText,
    looksLikeInstruction,
    rejectUntrustedDirective,
    canonicalRepo,
    isPrivateName,
    dedupeRepos,
    megaStarPenalty,
    overConcentration,
    applyOwnerCap,
    interestOverlap,
    scoreCandidate,
    rerank,
    cacheKey,
    Budget,
    expandQueries,
    sanitizeExport,
    allowedMessage,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
