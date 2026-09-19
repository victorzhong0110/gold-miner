/* Gold Miner service worker. Secrets stay here, never sent to content scripts. */

if (typeof importScripts === "function") {
  importScripts("shared.js");
}

(function (root) {
  "use strict";

  const TRUSTED_TYPES = new Set([
    "SEARCH",
    "EXPLORE",
    "CANCEL",
    "FEEDBACK",
    "GET_PUBLIC_SETTINGS",
    "SAVE_SETTINGS",
    "CLEAR_LOCAL",
    "EXPORT_CACHE",
    "IMPORT_CACHE",
  ]);

  const SEARCH_FAIL = new Set([
    "rate_limited",
    "timeout",
    "bad_response",
    "network_error",
    "untrusted_input",
    "github_not_found",
  ]);

  function createBackground(opts) {
    opts = opts || {};
    const S = opts.shared || root.GoldMinerShared;
    const chromeApi = opts.chrome || root.chrome;
    const httpFetch =
      opts.fetch ||
      (typeof root.fetch === "function" ? root.fetch.bind(root) : null);
    const modelClient = opts.modelClient || null;
    const delay = opts.setTimeout || root.setTimeout;
    const clearDelay = opts.clearTimeout || root.clearTimeout;
    const inflight = new Map();
    let isolationState = "pending";

    function isolationOk() {
      return isolationState === "ok";
    }

    async function stripSecrets() {
      const data = await chromeApi.storage.local.get({ byok: {} });
      const byok = Object.assign({}, data.byok || {});
      if (byok.apiKey) {
        byok.apiKey = "";
        await chromeApi.storage.local.set({ byok: byok });
      }
    }

    async function lockStorage() {
      if (isolationState !== "pending") return isolationOk();
      const setter =
        chromeApi.storage &&
        chromeApi.storage.local &&
        chromeApi.storage.local.setAccessLevel;
      if (typeof setter !== "function") {
        isolationState = "failed";
        await stripSecrets();
        return false;
      }
      try {
        await setter.call(chromeApi.storage.local, {
          accessLevel: "TRUSTED_CONTEXTS",
        });
        isolationState = "ok";
        return true;
      } catch {
        isolationState = "failed";
        await stripSecrets();
        return false;
      }
    }

    async function loadState() {
      await lockStorage();
      return chromeApi.storage.local.get({
        readingLang: "zh",
        interests: [],
        personalization: true,
        historyEnabled: false,
        byok: { baseUrl: "", model: "", apiKey: "" },
        seen: [],
        feedback: {},
        cache: {},
        pageHistory: [],
      });
    }

    function publicSettings(state) {
      return {
        readingLang: state.readingLang,
        interests: state.interests,
        personalization: state.personalization,
        historyEnabled: state.historyEnabled,
        hasModel: false,
        storageIsolated: isolationOk(),
        seen: state.seen,
        feedback: state.feedback,
      };
    }

    function parseQueryFromUrl(url) {
      try {
        const u = new URL(url);
        return u.searchParams.get("q") || "";
      } catch {
        return "";
      }
    }

    function parseRepoFromUrl(url) {
      try {
        const u = new URL(url);
        const parts = u.pathname.split("/").filter(Boolean);
        if (
          parts.length >= 2 &&
          !["search", "topics", "settings", "orgs"].includes(parts[0])
        ) {
          return parts[0] + "/" + parts[1];
        }
      } catch {
        /* ignore */
      }
      return "";
    }

    function willAttemptModel(state) {
      if (typeof modelClient === "function") return true;
      const byok = (state && state.byok) || {};
      return Boolean(byok.apiKey && byok.baseUrl && byok.model);
    }

    async function githubJson(url, token, timeoutMs) {
      if (!httpFetch) return { code: "network_error", data: null };
      const headers = {
        Accept: "application/vnd.github+json",
        "User-Agent": "gold-miner-extension/0.1.0",
      };
      if (token) headers.Authorization = "Bearer " + token;
      const ctrl = new AbortController();
      const timer = delay(function () {
        ctrl.abort();
      }, timeoutMs || 12000);
      try {
        const resp = await httpFetch(url, { headers: headers, signal: ctrl.signal });
        if (resp.status === 429) return { code: "rate_limited", data: null };
        if (resp.status === 404) return { code: "github_not_found", data: null };
        if (!resp.ok) return { code: "bad_response", data: null, httpStatus: resp.status };
        const data = await resp.json();
        return { code: "ok", data: data };
      } catch (err) {
        if (err && err.name === "AbortError") return { code: "timeout", data: null };
        return { code: "network_error", data: null };
      } finally {
        clearDelay(timer);
      }
    }

    async function githubSearch(query, token) {
      const q = S.sanitizeRemoteText(query);
      if (!q || S.looksLikeInstruction(q)) {
        return { code: "untrusted_input", items: [] };
      }
      const url =
        "https://api.github.com/search/repositories?q=" +
        encodeURIComponent(q) +
        "&per_page=8";
      const packed = await githubJson(url, token, 12000);
      if (packed.code !== "ok") return { code: packed.code, items: [] };
      const items = ((packed.data && packed.data.items) || []).map(function (it) {
        return {
          repo: it.full_name,
          stars: it.stargazers_count || 0,
          description: S.sanitizeRemoteText(it.description || ""),
          html_url: it.html_url,
        };
      });
      return { code: "ok", items: items };
    }

    async function githubRepoMeta(fullName, token) {
      const repo = S.canonicalRepo(fullName);
      if (!repo) return { code: "untrusted_input", repo: null };
      const url = "https://api.github.com/repos/" + repo;
      const packed = await githubJson(url, token, 12000);
      if (packed.code !== "ok") return { code: packed.code, repo: null };
      const data = packed.data || {};
      return {
        code: "ok",
        repo: {
          full_name: data.full_name || repo,
          description: S.sanitizeRemoteText(data.description || ""),
          topics: (data.topics || [])
            .map(function (t) {
              return S.sanitizeRemoteText(String(t));
            })
            .filter(Boolean),
        },
      };
    }

    async function defaultModelHttp(byok, original, lang) {
      if (!httpFetch) throw new Error("network_error");
      const url = String(byok.baseUrl || "").replace(/\/$/, "") + "/chat/completions";
      const ctrl = new AbortController();
      const timer = delay(function () {
        ctrl.abort();
      }, 12000);
      try {
        const resp = await httpFetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + byok.apiKey,
          },
          body: JSON.stringify({
            model: byok.model,
            max_tokens: 256,
            messages: [
              {
                role: "system",
                content:
                  'Return only JSON {"zh":[],"en":[]} query expansions for GitHub search. No repos.',
              },
              { role: "user", content: original },
            ],
          }),
          signal: ctrl.signal,
        });
        if (!resp.ok) throw new Error("model_unavailable");
        const data = await resp.json();
        const content =
          data &&
          data.choices &&
          data.choices[0] &&
          data.choices[0].message &&
          data.choices[0].message.content;
        return S.parseModelExpansions(content || "", original, lang);
      } finally {
        clearDelay(timer);
      }
    }

    async function runModelExpansions(original, lang, interests, byok) {
      const fallback = S.expandQueries(original, lang, interests);
      if (typeof modelClient === "function") {
        try {
          const rows = await modelClient({
            original: original,
            lang: lang,
            byok: byok,
            interests: interests,
          });
          if (rows && rows.length) {
            return { usedModel: true, expansions: rows };
          }
        } catch {
          /* fall through */
        }
        return {
          usedModel: false,
          expansions: fallback,
          degrade: "model_unavailable",
        };
      }
      if (!byok || !byok.apiKey || !byok.baseUrl || !byok.model) {
        return { usedModel: false, expansions: fallback };
      }
      try {
        const rows = await defaultModelHttp(byok, original, lang);
        if (rows && rows.length) {
          return { usedModel: true, expansions: rows };
        }
      } catch {
        /* fall through */
      }
      return {
        usedModel: false,
        expansions: fallback,
        degrade: "model_unavailable",
      };
    }

    function cacheParts(state, pageKind, originalQuery, mode, contentVersion) {
      return {
        pageKind: pageKind,
        contentVersion: contentVersion || "dom-1",
        language: state.readingLang,
        processingMode: mode,
        query: originalQuery,
      };
    }

    function findCached(state, pageKind, originalQuery, attemptModel, contentVersion) {
      const modes = attemptModel ? ["model", "rules"] : ["rules"];
      for (let i = 0; i < modes.length; i++) {
        const mode = modes[i];
        const key = S.cacheKey(
          cacheParts(state, pageKind, originalQuery, mode, contentVersion)
        );
        const entry = state.cache && state.cache[key];
        if (entry && (entry.rawCandidates || entry.candidates)) {
          return { key: key, entry: entry, mode: mode };
        }
      }
      return null;
    }

    function rankForDisplay(raw, state, request) {
      return S.rerank(raw || [], {
        interests: state.personalization ? state.interests : [],
        seen: state.seen,
        feedback: state.feedback,
        pageRepo: request.pageRepo || "",
        personalization: state.personalization,
        hideSeen: true,
        limit: request.limit || 5,
      });
    }

    function collectFromSearch(items, exp, original) {
      return (items || []).map(function (item) {
        return Object.assign({}, item, {
          source: exp.source,
          purpose: item.description || "",
          why:
            "source=" +
            exp.source +
            "; query=" +
            exp.query +
            "; original=" +
            original,
          queryUsed: exp.query,
        });
      });
    }

    async function runJob(jobId, request) {
      const state = await loadState();
      const budget = new S.Budget(4);
      inflight.set(jobId, budget);
      const original = S.sanitizeRemoteText(request.originalQuery || "");
      const interests = state.personalization ? state.interests : [];
      let expansions = [];
      let usedModel = false;
      let degrade = "ok";

      if (request.kind === "EXPLORE" && request.pageRepo) {
        if (!budget.canStart()) {
          inflight.delete(jobId);
          return {
            jobId: jobId,
            originalQuery: original,
            expansions: [],
            candidates: [],
            rawCandidates: [],
            code: "budget_exhausted",
            hasModel: false,
          };
        }
        budget.mark();
        const meta = await githubRepoMeta(request.pageRepo, undefined);
        if (meta.code !== "ok") {
          inflight.delete(jobId);
          return {
            jobId: jobId,
            originalQuery: original,
            expansions: [],
            candidates: [],
            rawCandidates: [],
            code: meta.code,
            hasModel: false,
          };
        }
        expansions = S.buildExploreQueries(meta.repo, request.lang || state.readingLang);
      } else {
        const modelResult = await runModelExpansions(
          original,
          request.lang || state.readingLang,
          interests,
          state.byok
        );
        expansions = modelResult.expansions;
        usedModel = modelResult.usedModel;
        if (modelResult.degrade) degrade = modelResult.degrade;
      }

      const collected = [];
      for (let i = 0; i < expansions.length; i++) {
        const exp = expansions[i];
        if (!budget.canStart()) break;
        budget.mark();
        const result = await githubSearch(exp.query, undefined);
        if (result.code !== "ok") {
          if (SEARCH_FAIL.has(result.code)) {
            degrade = result.code;
            break;
          }
          degrade = result.code;
          break;
        }
        collected.push.apply(collected, collectFromSearch(result.items, exp, original));
      }
      inflight.delete(jobId);
      const ranked = rankForDisplay(collected, state, request);
      return {
        jobId: jobId,
        originalQuery: original,
        expansions: expansions.map(function (e) {
          return { query: e.query, lang: e.lang, source: e.source };
        }),
        candidates: ranked,
        rawCandidates: collected,
        code: degrade,
        hasModel: usedModel,
      };
    }

    async function persistCacheEntry(state, key, entry) {
      const cache = Object.assign({}, state.cache);
      cache[key] = entry;
      await chromeApi.storage.local.set({ cache: cache });
    }

    function makeCacheEntry(state, request, result, contentVersion) {
      return {
        repo: request.pageRepo || "",
        pageKind: request.kind,
        query: result.originalQuery,
        purpose: result.originalQuery,
        source: "bundle",
        language: state.readingLang,
        content_version: contentVersion || "dom-1",
        processing_mode: result.hasModel ? "model" : "rules",
        expansions: result.expansions,
        rawCandidates: result.rawCandidates || [],
      };
    }

    async function handleSearchOrExplore(message) {
      const jobId = message.jobId || String(Date.now());
      const pageRepo = parseRepoFromUrl(message.pageUrl || "");
      const originalQuery =
        message.originalQuery ||
        parseQueryFromUrl(message.pageUrl || "") ||
        pageRepo;
      const state = await loadState();
      const attemptModel = message.type === "SEARCH" && willAttemptModel(state);
      const hit = findCached(
        state,
        message.type,
        originalQuery,
        attemptModel,
        message.contentVersion
      );
      if (hit) {
        const ranked = rankForDisplay(hit.entry.rawCandidates || hit.entry.candidates, state, {
          pageRepo: pageRepo,
          limit: message.limit || 5,
        });
        return {
          code: "ok",
          cached: true,
          jobId: jobId,
          originalQuery: originalQuery,
          candidates: ranked,
          expansions: hit.entry.expansions || [],
          hasModel: hit.mode === "model",
        };
      }
      const result = await runJob(jobId, {
        kind: message.type,
        originalQuery: originalQuery,
        pageRepo: pageRepo,
        lang: state.readingLang,
        limit: message.limit || 5,
      });
      const searchFailed = SEARCH_FAIL.has(result.code);
      if (!searchFailed && result.code !== "budget_exhausted") {
        const mode = result.hasModel ? "model" : "rules";
        const key = S.cacheKey(
          cacheParts(state, message.type, originalQuery, mode, message.contentVersion)
        );
        await persistCacheEntry(
          state,
          key,
          makeCacheEntry(state, { kind: message.type, pageRepo: pageRepo }, result, message.contentVersion)
        );
        if (state.historyEnabled && pageRepo) {
          const hist = (state.pageHistory || []).concat([pageRepo]).slice(-30);
          await chromeApi.storage.local.set({ pageHistory: hist });
        }
      }
      return result;
    }

    async function dispatch(message, sender) {
      if (!S.allowedMessage(sender)) {
        return { code: "untrusted_input" };
      }
      if (!message || !TRUSTED_TYPES.has(message.type)) {
        return { code: "untrusted_input" };
      }
      await lockStorage();
      if (message.type === "GET_PUBLIC_SETTINGS") {
        return { code: "ok", settings: publicSettings(await loadState()) };
      }
      if (message.type === "SAVE_SETTINGS") {
        const isolated = await lockStorage();
        const incoming = (message.settings || {});
        const interests = Array.isArray(incoming.interests)
          ? incoming.interests
              .map(function (s) {
                return S.sanitizeRemoteText(String(s));
              })
              .filter(Boolean)
              .slice(0, 12)
          : [];
        const patch = {
          readingLang: incoming.readingLang === "en" ? "en" : "zh",
          interests: interests,
          personalization: incoming.personalization !== false,
          historyEnabled: Boolean(incoming.historyEnabled),
        };
        const byokIn = incoming.byok || {};
        const hasKey = Boolean(byokIn.apiKey);
        if (hasKey && !isolated) {
          await chromeApi.storage.local.set(patch);
          return { code: "storage_isolation_failed", isolated: false };
        }
        if (isolated) {
          patch.byok = {
            baseUrl: S.sanitizeRemoteText(byokIn.baseUrl || ""),
            model: S.sanitizeRemoteText(byokIn.model || ""),
            apiKey: String(byokIn.apiKey || ""),
          };
        }
        await chromeApi.storage.local.set(patch);
        return { code: "ok", isolated: isolated };
      }
      if (message.type === "CANCEL") {
        const b = inflight.get(message.jobId);
        if (b) b.cancel();
        return { code: "cancelled" };
      }
      if (message.type === "FEEDBACK") {
        const state = await loadState();
        const repo = S.canonicalRepo(message.repo || "");
        if (!repo) return { code: "bad_response" };
        const fb = Object.assign({}, state.feedback);
        fb[repo] = message.action;
        const seen = new Set(state.seen);
        if (message.action === "seen" || message.action === "irrelevant") seen.add(repo);
        await chromeApi.storage.local.set({
          feedback: fb,
          seen: Array.from(seen),
        });
        return { code: "ok" };
      }
      if (message.type === "CLEAR_LOCAL") {
        await chromeApi.storage.local.set({
          seen: [],
          feedback: {},
          cache: {},
          pageHistory: [],
        });
        return { code: "ok" };
      }
      if (message.type === "EXPORT_CACHE") {
        const state = await loadState();
        const bundle = S.sanitizeExport({
          exported_at: new Date().toISOString(),
          entries: Object.values(state.cache || {}),
        });
        return { code: "ok", bundle: bundle };
      }
      if (message.type === "IMPORT_CACHE") {
        const incoming = S.sanitizeExport(message.bundle || {});
        const state = await loadState();
        const cache = Object.assign({}, state.cache);
        let imported = 0;
        for (let i = 0; i < incoming.entries.length; i++) {
          const packed = S.importedCacheRecord(incoming.entries[i]);
          cache[packed.key] = packed.record;
          imported += 1;
        }
        await chromeApi.storage.local.set({ cache: cache });
        return { code: "ok", imported: imported };
      }
      if (message.type === "SEARCH" || message.type === "EXPLORE") {
        return handleSearchOrExplore(message);
      }
      return { code: "bad_response" };
    }

    function attachListeners() {
      chromeApi.runtime.onMessage.addListener(function (message, sender, sendResponse) {
        dispatch(message, sender)
          .then(sendResponse)
          .catch(function (err) {
            sendResponse({
              code: "bad_response",
              message: String(err && err.name),
            });
          });
        return true;
      });
    }

    return {
      dispatch: dispatch,
      attachListeners: attachListeners,
      lockStorage: lockStorage,
      isolationState: function () {
        return isolationState;
      },
    };
  }

  root.GoldMinerBackground = { createBackground: createBackground };

  if (
    !root.__GOLD_MINER_TEST__ &&
    root.chrome &&
    root.chrome.runtime &&
    root.chrome.runtime.onMessage
  ) {
    const svc = createBackground();
    svc.attachListeners();
    svc.lockStorage();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
