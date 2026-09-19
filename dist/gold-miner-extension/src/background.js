/* Gold Miner service worker. Secrets stay here, never sent to content scripts. */

importScripts("shared.js");

const S = self.GoldMinerShared;
const TRUSTED_TYPES = new Set([
  "SEARCH",
  "EXPLORE",
  "CANCEL",
  "FEEDBACK",
  "GET_PUBLIC_SETTINGS",
  "CLEAR_LOCAL",
  "EXPORT_CACHE",
  "IMPORT_CACHE",
]);

const inflight = new Map();
let persistReady = false;

async function lockStorage() {
  if (persistReady) return;
  if (chrome.storage && chrome.storage.setAccessLevel) {
    await chrome.storage.setAccessLevel({
      accessLevel: "TRUSTED_CONTEXTS",
    });
  }
  persistReady = true;
}

async function loadState() {
  await lockStorage();
  const data = await chrome.storage.local.get({
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
  return data;
}

function publicSettings(state) {
  return {
    readingLang: state.readingLang,
    interests: state.interests,
    personalization: state.personalization,
    historyEnabled: state.historyEnabled,
    hasModel: Boolean(state.byok && state.byok.apiKey),
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
    if (parts.length >= 2 && !["search", "topics", "settings", "orgs"].includes(parts[0])) {
      return parts[0] + "/" + parts[1];
    }
  } catch {
    /* ignore */
  }
  return "";
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
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "gold-miner-extension/0.1.0",
  };
  if (token) headers.Authorization = "Bearer " + token;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);
  try {
    const resp = await fetch(url, { headers, signal: ctrl.signal });
    if (resp.status === 429) return { code: "rate_limited", items: [] };
    if (!resp.ok) return { code: "bad_response", items: [] };
    const data = await resp.json();
    const items = (data.items || []).map((it) => ({
      repo: it.full_name,
      stars: it.stargazers_count || 0,
      description: S.sanitizeRemoteText(it.description || ""),
      html_url: it.html_url,
    }));
    return { code: "ok", items };
  } catch (err) {
    if (err && err.name === "AbortError") return { code: "timeout", items: [] };
    return { code: "network_error", items: [] };
  } finally {
    clearTimeout(timer);
  }
}

async function runJob(jobId, request) {
  const state = await loadState();
  const budget = new S.Budget(4);
  inflight.set(jobId, budget);
  const original = S.sanitizeRemoteText(request.originalQuery || "");
  const expansions = S.expandQueries(
    original,
    request.lang || state.readingLang,
    state.personalization ? state.interests : []
  );
  const collected = [];
  let degrade = "ok";
  for (const exp of expansions) {
    if (!budget.canStart()) break;
    budget.mark();
    const result = await githubSearch(exp.query, undefined);
    if (result.code === "rate_limited" || result.code === "timeout") {
      degrade = result.code;
      break;
    }
    for (const item of result.items) {
      collected.push(
        Object.assign({}, item, {
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
        })
      );
    }
  }
  inflight.delete(jobId);
  const ranked = S.rerank(collected, {
    interests: state.personalization ? state.interests : [],
    seen: state.seen,
    feedback: state.feedback,
    pageRepo: request.pageRepo || "",
    personalization: state.personalization,
    hideSeen: true,
    limit: request.limit || 5,
  });
  return {
    jobId,
    originalQuery: original,
    expansions: expansions.map((e) => ({
      query: e.query,
      lang: e.lang,
      source: e.source,
    })),
    candidates: ranked,
    code: degrade,
    hasModel: publicSettings(state).hasModel,
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!S.allowedMessage(sender)) {
    sendResponse({ code: "untrusted_input" });
    return false;
  }
  if (!message || !TRUSTED_TYPES.has(message.type)) {
    sendResponse({ code: "untrusted_input" });
    return false;
  }

  (async () => {
    await lockStorage();
    if (message.type === "GET_PUBLIC_SETTINGS") {
      sendResponse({ code: "ok", settings: publicSettings(await loadState()) });
      return;
    }
    if (message.type === "CANCEL") {
      const b = inflight.get(message.jobId);
      if (b) b.cancel();
      sendResponse({ code: "cancelled" });
      return;
    }
    if (message.type === "FEEDBACK") {
      const state = await loadState();
      const repo = S.canonicalRepo(message.repo || "");
      if (!repo) {
        sendResponse({ code: "bad_response" });
        return;
      }
      const fb = Object.assign({}, state.feedback);
      fb[repo] = message.action;
      const seen = new Set(state.seen);
      if (message.action === "seen" || message.action === "irrelevant") seen.add(repo);
      await chrome.storage.local.set({ feedback: fb, seen: Array.from(seen) });
      sendResponse({ code: "ok" });
      return;
    }
    if (message.type === "CLEAR_LOCAL") {
      await chrome.storage.local.set({
        seen: [],
        feedback: {},
        cache: {},
        pageHistory: [],
      });
      sendResponse({ code: "ok" });
      return;
    }
    if (message.type === "EXPORT_CACHE") {
      const state = await loadState();
      const bundle = S.sanitizeExport({
        exported_at: new Date().toISOString(),
        entries: Object.values(state.cache || {}),
      });
      sendResponse({ code: "ok", bundle });
      return;
    }
    if (message.type === "IMPORT_CACHE") {
      const incoming = S.sanitizeExport(message.bundle || {});
      const state = await loadState();
      const cache = Object.assign({}, state.cache);
      for (const e of incoming.entries) {
        const key = S.cacheKey({
          pageKind: "imported",
          contentVersion: e.content_version,
          language: e.language,
          processingMode: e.processing_mode,
          query: e.repo,
        });
        cache[key] = e;
      }
      await chrome.storage.local.set({ cache });
      sendResponse({ code: "ok", imported: incoming.entries.length });
      return;
    }
    if (message.type === "SEARCH" || message.type === "EXPLORE") {
      const jobId = message.jobId || String(Date.now());
      const pageRepo = parseRepoFromUrl(message.pageUrl || "");
      const originalQuery =
        message.originalQuery || parseQueryFromUrl(message.pageUrl || "") || pageRepo;
      const state = await loadState();
      const key = S.cacheKey({
        pageKind: message.type,
        contentVersion: message.contentVersion || "dom-1",
        language: state.readingLang,
        processingMode: state.byok && state.byok.apiKey ? "model" : "rules",
        query: originalQuery,
      });
      if (state.cache[key] && state.cache[key].candidates) {
        sendResponse({
          code: "ok",
          cached: true,
          jobId,
          originalQuery,
          candidates: state.cache[key].candidates,
          expansions: state.cache[key].expansions || [],
          hasModel: publicSettings(state).hasModel,
        });
        return;
      }
      const result = await runJob(jobId, {
        originalQuery,
        pageRepo,
        lang: state.readingLang,
        limit: message.limit || 5,
      });
      const cache = Object.assign({}, state.cache);
      cache[key] = {
        repo: pageRepo || "search",
        purpose: originalQuery,
        source: "bundle",
        language: state.readingLang,
        content_version: message.contentVersion || "dom-1",
        processing_mode: result.hasModel ? "model" : "rules",
        candidates: result.candidates,
        expansions: result.expansions,
      };
      await chrome.storage.local.set({ cache });
      if (state.historyEnabled && pageRepo) {
        const hist = (state.pageHistory || []).concat([pageRepo]).slice(-30);
        await chrome.storage.local.set({ pageHistory: hist });
      }
      sendResponse(result);
      return;
    }
    sendResponse({ code: "bad_response" });
  })().catch((err) => {
    sendResponse({ code: "bad_response", message: String(err && err.name) });
  });
  return true;
});

self.addEventListener("install", () => {
  lockStorage();
});
