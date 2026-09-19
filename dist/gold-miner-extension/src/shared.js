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
      noModel: "本次未走模型路径，仅使用规则扩展与公开搜索",
      close: "关闭",
      badResponse: "搜索失败，未写入成功缓存",
      networkError: "网络错误",
      storageIsolationFailed: "存储隔离失败，密钥未保存",
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
      noModel: "Model path did not run; using rules and public search only",
      close: "Close",
      badResponse: "Search failed; success cache was not written",
      networkError: "Network error",
      storageIsolationFailed: "Storage isolation failed; API key was not saved",
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

  function isSearchOrExploreKind(kind) {
    const k = String(kind || "").toUpperCase();
    return k === "SEARCH" || k === "EXPLORE";
  }

  function sanitizeCandidateList(list) {
    const out = [];
    for (const c of list || []) {
      if (!c || typeof c !== "object") continue;
      if (c.private_note || c.apiKey || c.token || c.OPENAI_API_KEY) continue;
      if (c.private === true) continue;
      const repo = canonicalRepo(c.repo || c.full_name || "");
      if (!repo || isPrivateName(repo)) continue;
      const purpose = rejectUntrustedDirective(c.purpose || c.description || "");
      const why = rejectUntrustedDirective(c.why || "");
      out.push({
        repo: c.repo || c.full_name,
        stars: Number(c.stars) || 0,
        description: purpose.text,
        html_url: typeof c.html_url === "string" ? c.html_url : "",
        source: c.source || "unknown",
        purpose: purpose.text,
        why: why.text,
        queryUsed: sanitizeRemoteText(c.queryUsed || ""),
      });
    }
    return out;
  }

  function sanitizeExpansions(list) {
    const out = [];
    const seen = new Set();
    for (const exp of list || []) {
      if (!exp) continue;
      const q = sanitizeRemoteText(exp.query || "");
      if (!q || looksLikeInstruction(q) || seen.has(q)) continue;
      seen.add(q);
      out.push({
        query: q,
        lang: exp.lang || "",
        source: exp.source || "",
      });
    }
    return out;
  }

  function normalizePageKind(kind, repo) {
    const k = String(kind || "").toUpperCase();
    if (k === "SEARCH" || k === "EXPLORE") return k;
    if (canonicalRepo(repo || "")) return "EXPLORE";
    return "SEARCH";
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
      if (e.private_note || e.apiKey || e.token || e.OPENAI_API_KEY) continue;
      if (e.private === true) continue;
      const repo = canonicalRepo(e.repo || "");
      if (repo && isPrivateName(repo)) continue;
      const pageKind = normalizePageKind(e.pageKind || e.page_kind, e.repo);
      const query = sanitizeRemoteText(e.query || e.purpose || (repo ? e.repo : ""));
      const searchLike = isSearchOrExploreKind(pageKind) && Boolean(query);
      if (!repo && !searchLike) continue;
      const purpose = rejectUntrustedDirective(e.purpose || e.description || query);
      out.entries.push({
        repo: repo ? e.repo : "",
        pageKind: pageKind,
        query: query,
        purpose: purpose.text,
        source: e.source || "unknown",
        language: e.language || "",
        content_version: e.content_version || "",
        processing_mode: e.processing_mode || "",
        expansions: sanitizeExpansions(e.expansions),
        rawCandidates: sanitizeCandidateList(e.rawCandidates || e.candidates),
      });
    }
    return out;
  }

  function importedCacheRecord(entry) {
    const e = entry || {};
    const pageKind = normalizePageKind(e.pageKind || e.page_kind, e.repo);
    const query = sanitizeRemoteText(e.query || e.purpose || e.repo || "");
    return {
      key: cacheKey({
        pageKind: pageKind,
        contentVersion: e.content_version,
        language: e.language,
        processingMode: e.processing_mode || "rules",
        query: query,
      }),
      record: {
        repo: canonicalRepo(e.repo || "") ? e.repo : "",
        pageKind: pageKind,
        query: query,
        purpose: e.purpose || query,
        source: e.source || "bundle",
        language: e.language || "",
        content_version: e.content_version || "",
        processing_mode: e.processing_mode || "rules",
        expansions: sanitizeExpansions(e.expansions),
        rawCandidates: sanitizeCandidateList(e.rawCandidates || e.candidates),
      },
    };
  }

  const EXPLORE_STOP = new Set([
    "the",
    "a",
    "an",
    "for",
    "and",
    "or",
    "to",
    "of",
    "on",
    "in",
    "with",
    "from",
    "this",
    "that",
    "is",
    "are",
    "was",
    "be",
    "as",
    "by",
    "it",
    "its",
    "into",
    "over",
    "your",
    "you",
    "lightweight",
    "simple",
    "一个",
    "的",
    "和",
    "与",
    "或",
    "在",
    "是",
  ]);

  function descriptionKeywords(description, limit) {
    const cap = limit || 2;
    const words = sanitizeRemoteText(description)
      .split(/[^\p{L}\p{N}+#.-]+/u)
      .map(function (w) {
        return w.trim();
      })
      .filter(function (w) {
        return w.length >= 3 && !EXPLORE_STOP.has(w.toLowerCase());
      });
    const seen = new Set();
    const out = [];
    for (const w of words) {
      const k = w.toLowerCase();
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(w);
      if (out.length >= cap) break;
    }
    return out;
  }

  function buildExploreQueries(meta, lang) {
    meta = meta || {};
    const out = [];
    for (const topic of (meta.topics || []).slice(0, 3)) {
      const q = sanitizeRemoteText(String(topic));
      if (q && !looksLikeInstruction(q)) {
        out.push({ query: q, lang: "en", source: SOURCE_KINDS.topic_related });
      }
    }
    for (const kw of descriptionKeywords(meta.description || "", 2)) {
      out.push({
        query: kw,
        lang: lang || "en",
        source: SOURCE_KINDS.github_search_default,
      });
    }
    const owner = String(meta.full_name || meta.repo || "").split("/")[0];
    if (owner && !looksLikeInstruction(owner)) {
      out.push({
        query: "user:" + owner,
        lang: "en",
        source: SOURCE_KINDS.same_owner,
      });
    }
    const seen = new Set();
    return out
      .filter(function (row) {
        if (!row.query || seen.has(row.query)) return false;
        seen.add(row.query);
        return true;
      })
      .slice(0, 4);
  }

  function parseModelExpansions(payload, original, lang) {
    let data = payload;
    if (typeof payload === "string") {
      const trimmed = payload.trim();
      const start = trimmed.indexOf("{");
      const end = trimmed.lastIndexOf("}");
      if (start < 0 || end <= start) return [];
      try {
        data = JSON.parse(trimmed.slice(start, end + 1));
      } catch {
        return [];
      }
    }
    if (!data || typeof data !== "object") return [];
    const rows = [];
    if (Array.isArray(data.variants)) {
      for (const v of data.variants) {
        const q = sanitizeRemoteText((v && (v.query || v.variant_query)) || "");
        if (q && !looksLikeInstruction(q)) {
          rows.push({
            query: q,
            lang: (v && (v.lang || v.variant_lang)) || lang || "en",
            source: SOURCE_KINDS.github_search_default,
          });
        }
      }
    } else {
      for (const q of (data.zh || []).slice(0, 2)) {
        const s = sanitizeRemoteText(q);
        if (s && !looksLikeInstruction(s)) {
          rows.push({ query: s, lang: "zh", source: SOURCE_KINDS.github_search_default });
        }
      }
      for (const q of (data.en || []).slice(0, 2)) {
        const s = sanitizeRemoteText(q);
        if (s && !looksLikeInstruction(s)) {
          rows.push({ query: s, lang: "en", source: SOURCE_KINDS.github_search_default });
        }
      }
      for (const q of (data.queries || []).slice(0, 3)) {
        const s = sanitizeRemoteText(q);
        if (s && !looksLikeInstruction(s)) {
          rows.push({
            query: s,
            lang: data.same_lang || lang || "en",
            source: SOURCE_KINDS.github_search_default,
          });
        }
      }
      if (data.query) {
        const s = sanitizeRemoteText(data.query);
        if (s && !looksLikeInstruction(s)) {
          rows.push({
            query: s,
            lang: data.other_lang || lang || "en",
            source: SOURCE_KINDS.github_search_default,
          });
        }
      }
    }
    const originalQ = sanitizeRemoteText(original);
    const out = [];
    if (originalQ) {
      out.push({ query: originalQ, lang: lang || "zh", source: SOURCE_KINDS.original_query });
    }
    const seen = new Set(out.map(function (r) {
      return r.query;
    }));
    for (const row of rows) {
      if (seen.has(row.query)) continue;
      seen.add(row.query);
      out.push(row);
      if (out.length >= 4) break;
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
    sanitizeCandidateList,
    sanitizeExpansions,
    importedCacheRecord,
    normalizePageKind,
    descriptionKeywords,
    buildExploreQueries,
    parseModelExpansions,
    allowedMessage,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
