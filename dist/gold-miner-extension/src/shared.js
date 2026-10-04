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
      feedbackFailed: "反馈未保存，请重试",
      loading: "加载中…",
      cancel: "取消",
      cancelled: "已取消",
      busy: "已有任务正在处理，请稍后重试",
      rateLimited: "接口限流，请稍后再试",
      timeout: "超时。已发出的请求可能已计费。",
      modelUnavailable: "模型不可用，已降级为无模型搜索",
      modelOutputTruncated: "模型输出被 max_tokens 截断，已降级。请在设置页重新探测。",
      modelEmptyOutput: "模型返回空内容，已降级。请在设置页重新探测。",
      modelBadResponse: "模型响应格式异常，已降级。请在设置页重新探测。",
      invalidEndpoint: "端点无效，请在设置页检查。",
      endpointPermissionRequired: "缺少端点访问授权，请在设置页保存并授权。",
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
      feedbackFailed: "Feedback was not saved. Try again.",
      loading: "Loading…",
      cancel: "Cancel",
      cancelled: "Cancelled",
      busy: "Tasks are busy. Try again shortly.",
      rateLimited: "Rate limited. Try again later.",
      timeout: "Timed out. In-flight requests may already be billed.",
      modelUnavailable: "Model unavailable; fell back to rule-based search",
      modelOutputTruncated: "Model output was truncated at max_tokens; degraded. Re-probe in options.",
      modelEmptyOutput: "Model returned no usable content; degraded. Re-probe in options.",
      modelBadResponse: "Unexpected model response shape; degraded. Re-probe in options.",
      invalidEndpoint: "Invalid endpoint. Check it in options.",
      endpointPermissionRequired: "Endpoint access not granted. Save and grant it in options.",
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
    if (parts.length !== 2 || !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/.test(parts[0]) ||
        !/^[A-Za-z0-9_.-]{1,100}$/.test(parts[1]) || [".", ".."].includes(parts[1])) return "";
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
    const limit = Math.max(1, Math.min(20, ctx.limit || 5));
    const n = Math.min(limit - 1, Math.max(0, Math.round(limit * residual)));
    // Reserve slots for another source; do not concatenate the unchanged ranking.
    const primary = scored.slice(0, Math.max(1, limit - n));
    const sources = new Set(primary.map((x) => x.item.source));
    const diverse = scored.slice(primary.length).filter((x) => !sources.has(x.item.source));
    const selected = diverse.slice(0, n);
    const selectedItems = new Set(selected.map((x) => x.item));
    const mixed = ctx.personalization === false || !n ? scored :
      primary.concat(selected, scored.slice(primary.length).filter((x) => !selectedItems.has(x.item)));
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
      sanitizeRemoteText(parts.query || ""),
    ].map((x) => encodeURIComponent(x)).join("|");
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
    for (const c of (Array.isArray(list) ? list : []).slice(0, 200)) {
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
        html_url: "https://github.com/" + repo,
        source: sanitizeRemoteText(c.source || "unknown"),
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
    for (const exp of (Array.isArray(list) ? list : []).slice(0, 4)) {
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
    const entries = Array.isArray(bundle && bundle.entries) ? bundle.entries.slice(0, 100) : [];
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
        processing_mode: e.processing_mode === "model" ? "model" : "rules",
        created_at: e.created_at || "",
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
        processing_mode: e.processing_mode === "model" ? "model" : "rules",
        created_at: e.created_at || "",
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

  function buildExploreQueries(meta, lang, interests) {
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
    if (interests && interests.length) {
      const extra = interests.slice(0, 1).map((word) => ({query: sanitizeRemoteText(word), lang: lang || "en", source: SOURCE_KINDS.interest_query}));
      const bilingual = out.length ? expandQueries(out[0].query, "en", []).slice(1, 2) : [];
      out.splice(1, 0, ...extra, ...bilingual);
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

  // Reasoning models inline their chain of thought in <think>...</think> inside
  // the message content. Strip it explicitly instead of relying on indexOf("{"),
  // which can slice a wrong span when the prose itself contains braces.
  function stripReasoning(text) {
    let out = String(text == null ? "" : text);
    out = out.replace(/<think>[\s\S]*?<\/think>/gi, "");
    const open = out.search(/<think>/i);
    if (open >= 0) out = out.slice(0, open);
    return out.replace(/<\/?think>/gi, "").trim();
  }

  // A single source of truth for the model's output budget. Reasoning models
  // spend the whole budget thinking; 256 left no room for the JSON at all.
  const MODEL_MAX_TOKENS = 2048;

  // Validates one chat-completion payload and returns the usable answer text.
  // Throws a specific code so callers never report "ok" for a truncated reply.
  function readModelChoice(data) {
    const choice =
      data && data.choices && data.choices[0];
    if (!choice) throw new Error("model_bad_response");
    const finish = choice.finish_reason || choice.finishReason || "";
    const raw =
      (choice.message && choice.message.content) ||
      choice.text ||
      "";
    const content = stripReasoning(raw);
    if (String(finish).toLowerCase() === "length") throw new Error("model_output_truncated");
    if (!content) throw new Error("model_empty_output");
    return content;
  }

  function parseModelExpansions(payload, original, lang) {
    let data = payload;
    if (typeof payload === "string") {
      const trimmed = stripReasoning(payload);
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

  function endpointUrl(base) {
    try {
      const u = new URL(base);
      if (u.username || u.password || u.search || u.hash) return "";
      if (u.protocol !== "https:" && !(u.protocol === "http:" && u.hostname === "127.0.0.1")) return "";
      return u.href.replace(/\/$/, "");
    } catch { return ""; }
  }

  function isOptionsSender(sender, extensionId) {
    if (!sender || sender.id !== extensionId) return false;
    try {
      const url = new URL(sender.url || "");
      return url.protocol === "chrome-extension:" && url.hostname === extensionId &&
        url.pathname === "/src/options.html";
    } catch { return false; }
  }

  function allowedMessage(sender) {
    if (!sender || !sender.id) return false;
    if (root.chrome && root.chrome.runtime && sender.id !== root.chrome.runtime.id) return false;
    if (isOptionsSender(sender, root.chrome && root.chrome.runtime && root.chrome.runtime.id)) return true;
    if (sender.tab) {
      try { if (new URL(sender.url || sender.tab.url).origin !== "https://github.com") return false; }
      catch { return false; }
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
    stripReasoning,
    readModelChoice,
    MODEL_MAX_TOKENS,
    allowedMessage,
    isOptionsSender,
    endpointUrl,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
