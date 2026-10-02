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
    let isolationPromise;
    let cacheWrites = Promise.resolve();
    let dataEpoch = 0;
    let githubBackoffUntil = 0;

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
      if (!isolationPromise) isolationPromise = isolateStorage();
      return isolationPromise;
    }

    async function isolateStorage() {
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
        modelRevision: 0,
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

    async function githubJson(url, token, timeoutMs, job) {
      if (Date.now() < githubBackoffUntil) return { code: "rate_limited", data: null };
      if (!httpFetch) return { code: "network_error", data: null };
      const headers = {
        Accept: "application/vnd.github+json",
        "User-Agent": "gold-miner-extension/0.1.0",
      };
      if (token) headers.Authorization = "Bearer " + token;
      const ctrl = new AbortController();
      const abort = () => ctrl.abort();
      if (job) job.controller.signal.addEventListener("abort", abort, { once: true });
      const timer = delay(abort, timeoutMs || 12000);
      try {
        if (job) job.githubRequests += 1;
        const resp = await httpFetch(url, { headers: headers, signal: ctrl.signal });
        const header = (name) => resp.headers && resp.headers.get ? resp.headers.get(name) : null;
        if (resp.status === 429 || (resp.status === 403 && header("x-ratelimit-remaining") === "0")) {
          const retry = Number(header("retry-after"));
          githubBackoffUntil = Date.now() + Math.max(60000, Math.min(3600000, (retry || 60) * 1000));
          return { code: "rate_limited", data: null };
        }
        if (resp.status === 404) return { code: "github_not_found", data: null };
        if (!resp.ok) return { code: "bad_response", data: null, httpStatus: resp.status };
        const data = await resp.json();
        return { code: "ok", data: data };
      } catch (err) {
        if (err && err.name === "AbortError") return { code: "timeout", data: null };
        return { code: "network_error", data: null };
      } finally {
        clearDelay(timer);
        if (job) job.controller.signal.removeEventListener("abort", abort);
      }
    }

    async function githubSearch(query, token, job) {
      const q = S.sanitizeRemoteText(query);
      if (!q || S.looksLikeInstruction(q)) {
        return { code: "untrusted_input", items: [] };
      }
      const url =
        "https://api.github.com/search/repositories?q=" +
        encodeURIComponent(q) +
        "&per_page=8";
      const packed = await githubJson(url, token, 12000, job);
      if (packed.code !== "ok") return { code: packed.code, items: [] };
      if (!packed.data || !Array.isArray(packed.data.items)) return {code: "bad_response", items: []};
      const items = packed.data.items.filter(it => it && typeof it === "object").map(function (it) {
        return {
          repo: it.full_name,
          stars: it.stargazers_count || 0,
          description: S.sanitizeRemoteText(it.description || ""),
          html_url: it.html_url,
        };
      });
      return { code: "ok", items: items };
    }

    async function githubRepoMeta(fullName, token, job) {
      const repo = S.canonicalRepo(fullName);
      if (!repo) return { code: "untrusted_input", repo: null };
      const url = "https://api.github.com/repos/" + repo;
      const packed = await githubJson(url, token, 12000, job);
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

    async function defaultModelHttp(byok, original, lang, job) {
      if (!httpFetch) throw new Error("network_error");
      const base = S.endpointUrl(byok.baseUrl);
      if (!base) throw new Error("invalid_endpoint");
      if (chromeApi.permissions && !await chromeApi.permissions.contains({origins: [new URL(base).origin + "/*"]})) throw new Error("endpoint_permission_required");
      const url = base + "/chat/completions";
      const ctrl = new AbortController();
      const abort = () => ctrl.abort();
      if (job) job.controller.signal.addEventListener("abort", abort, { once: true });
      const timer = delay(abort, 12000);
      try {
        const resp = await httpFetch(url, {
          method: "POST",
          redirect: "error",
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
        if (job) job.controller.signal.removeEventListener("abort", abort);
      }
    }

    async function runModelExpansions(original, lang, interests, byok, job) {
      const fallback = S.expandQueries(original, lang, interests);
      if (typeof modelClient === "function") {
        try {
          const rows = await modelClient({
            original: original,
            lang: lang,
            byok: byok,
            interests: interests,
            signal: job.controller.signal,
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
        const rows = await defaultModelHttp(byok, original, lang, job);
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
      const modes = attemptModel ? ["model"] : ["rules"];
      for (let i = 0; i < modes.length; i++) {
        const mode = modes[i];
        const key = S.cacheKey(
          cacheParts(state, pageKind, originalQuery, mode, contentVersion)
        );
        const entry = state.cache && state.cache[key];
        const age = entry && entry.created_at ? Date.now() - Date.parse(entry.created_at) : Infinity;
        if (entry && age >= 0 && age < 86400000 &&
            (mode !== "model" || entry.model_revision === state.modelRevision) &&
            (entry.rawCandidates || entry.candidates)) {
          return { key: key, entry: entry, mode: mode };
        }
      }
      return null;
    }

    function rankForDisplay(raw, state, request) {
      return S.rerank(S.sanitizeCandidateList(raw), {
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

    async function runJob(jobId, request, job) {
      const state = await loadState();
      const budget = job.budget;
      const cancelledResult = () => ({jobId, code: "cancelled", candidates: [], rawCandidates: [], expansions: [], hasModel: false});
      if (budget.cancelled) return cancelledResult();
      const original = S.sanitizeRemoteText(request.originalQuery || "");
      const interests = state.personalization ? state.interests : [];
      let expansions = [];
      let usedModel = false;
      let degrade = "ok";

      if (request.kind === "EXPLORE" && request.pageRepo) {
        if (!budget.canStart()) {
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
        const meta = await githubRepoMeta(request.pageRepo, undefined, job);
        if (budget.cancelled) return cancelledResult();
        if (meta.code !== "ok") {
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
        expansions = S.buildExploreQueries(meta.repo, request.lang || state.readingLang, interests);
      } else {
        job.modelRequests = willAttemptModel(state) ? 1 : 0;
        const modelResult = await runModelExpansions(
          original,
          request.lang || state.readingLang,
          interests,
          state.byok,
          job
        );
        if (budget.cancelled) return cancelledResult();
        expansions = modelResult.expansions;
        usedModel = modelResult.usedModel;
        if (modelResult.degrade) degrade = modelResult.degrade;
      }

      const collected = [];
      for (let i = 0; i < expansions.length; i++) {
        const exp = expansions[i];
        if (!budget.canStart()) break;
        budget.mark();
        const result = await githubSearch(exp.query, undefined, job);
        if (budget.cancelled) return cancelledResult();
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
      if (budget.cancelled) return cancelledResult();
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
        cost: {github_requests: job.githubRequests, model_requests: job.modelRequests, tokens: "unknown", fees: "unknown", elapsed_ms: Date.now() - job.startedAt},
      };
    }

    async function persistCacheEntry(state, key, entry, job) {
      const write = cacheWrites.then(async () => {
        if (job.budget.cancelled || job.epoch !== dataEpoch) return;
        const latest = await loadState();
        if (job.budget.cancelled || job.epoch !== dataEpoch) return;
        const cache = Object.assign({}, latest.cache);
        cache[key] = entry;
        const keys = Object.keys(cache);
        for (const old of keys.slice(0, Math.max(0, keys.length - 100))) delete cache[old];
        await chromeApi.storage.local.set({cache});
        if (job.budget.cancelled) {
          const current = await loadState();
          const cleaned = Object.assign({}, current.cache);
          if (JSON.stringify(cleaned[key]) === JSON.stringify(entry)) delete cleaned[key];
          await chromeApi.storage.local.set({cache: cleaned});
        }
      });
      cacheWrites = write.catch(() => {});
      await write;
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
        model_revision: state.modelRevision,
        created_at: new Date().toISOString(),
        expansions: result.expansions,
        rawCandidates: result.rawCandidates || [],
      };
    }

    async function handleSearchOrExplore(message, job) {
      const jobId = job.id;
      const pageRepo = parseRepoFromUrl(message.pageUrl || "");
      const originalQuery =
        message.originalQuery ||
        parseQueryFromUrl(message.pageUrl || "") ||
        pageRepo;
      const state = await loadState();
      if (job.budget.cancelled) return {code: "cancelled", jobId, candidates: []};
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
          cost: {github_requests: 0, model_requests: 0, cache_hits: 1},
        };
      }
      const result = await runJob(jobId, {
        kind: message.type,
        originalQuery: originalQuery,
        pageRepo: pageRepo,
        lang: state.readingLang,
        limit: message.limit || 5,
      }, job);
      const searchFailed = SEARCH_FAIL.has(result.code);
      if (!searchFailed && ["ok", "model_unavailable"].includes(result.code) && !job.budget.cancelled) {
        const mode = result.hasModel ? "model" : "rules";
        const key = S.cacheKey(
          cacheParts(state, message.type, originalQuery, mode, message.contentVersion)
        );
        await persistCacheEntry(
          state,
          key,
          makeCacheEntry(state, { kind: message.type, pageRepo: pageRepo }, result, message.contentVersion),
          job
        );
        if (state.historyEnabled && pageRepo) {
          const hist = (state.pageHistory || []).concat([pageRepo]).slice(-30);
          await chromeApi.storage.local.set({ pageHistory: hist });
        }
      }
      if (job.budget.cancelled) return {code: "cancelled", jobId, candidates: []};
      return result;
    }

    async function dispatch(message, sender) {
      if (!S.allowedMessage(sender)) {
        return { code: "untrusted_input" };
      }
      if (!message || !TRUSTED_TYPES.has(message.type)) {
        return { code: "untrusted_input" };
      }
      const privileged = ["SAVE_SETTINGS", "CLEAR_LOCAL", "EXPORT_CACHE", "IMPORT_CACHE"];
      if (privileged.includes(message.type) && !S.isOptionsSender(sender, chromeApi.runtime.id)) return {code: "untrusted_input"};
      if (message.type === "SEARCH" || message.type === "EXPLORE") {
        const id = sender.id + ":" + (sender.tab ? sender.tab.id : "options") + ":" + (message.jobId || Date.now());
        if (inflight.has(id) || inflight.size >= 2) return {code: "busy"};
        const job = {id: message.jobId || id, budget: new S.Budget(4), controller: new AbortController(), epoch: dataEpoch, githubRequests: 0, modelRequests: 0, startedAt: Date.now()};
        inflight.set(id, job);
        try { return await handleSearchOrExplore(message, job); }
        finally { inflight.delete(id); }
      }
      if (message.type === "CANCEL") {
        const id = sender.id + ":" + (sender.tab ? sender.tab.id : "options") + ":" + message.jobId;
        const job = inflight.get(id);
        if (job) { job.budget.cancel(); job.controller.abort(); }
        return {code: "cancelled"};
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
        if (byokIn.baseUrl && !S.endpointUrl(byokIn.baseUrl)) return {code: "invalid_endpoint"};
        const previous = await loadState();
        const changed = JSON.stringify(previous.byok) !== JSON.stringify(byokIn);
        patch.modelRevision = previous.modelRevision + (changed ? 1 : 0);
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
      if (message.type === "FEEDBACK") {
        const state = await loadState();
        const repo = S.canonicalRepo(message.repo || "");
        if (!repo || !["seen", "interested", "irrelevant"].includes(message.action)) return { code: "bad_response" };
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
        dataEpoch += 1;
        for (const job of inflight.values()) { job.budget.cancel(); job.controller.abort(); }
        await cacheWrites;
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
        if (!message.bundle || message.bundle.format !== "gold-miner-cache-v1" || !Array.isArray(message.bundle.entries) || message.bundle.entries.length > 100) return {code: "bad_response"};
        await cacheWrites;
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
    if (root.chrome.action && root.chrome.action.onClicked) {
      root.chrome.action.onClicked.addListener(() => root.chrome.runtime.openOptionsPage());
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
