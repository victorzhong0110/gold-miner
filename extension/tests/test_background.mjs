import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import test from "node:test";

const here = path.dirname(fileURLToPath(import.meta.url));
const sharedSrc = fs.readFileSync(path.join(here, "../src/shared.js"), "utf8");
const backgroundSrc = fs.readFileSync(path.join(here, "../src/background.js"), "utf8");
const exploreFixture = JSON.parse(
  fs.readFileSync(path.join(here, "fixtures/explore-p0deje-maccy.json"), "utf8")
);

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

function createMockChrome(options) {
  options = options || {};
  const events = [];
  let accessLevel = "TRUSTED_AND_UNTRUSTED_CONTEXTS";
  const store = Object.assign(
    {
      readingLang: "zh",
      interests: [],
      personalization: true,
      historyEnabled: false,
      byok: { baseUrl: "", model: "", apiKey: "" },
      seen: [],
      feedback: {},
      cache: {},
      pageHistory: [],
    },
    options.store || {}
  );
  const failIsolation = Boolean(options.failIsolation);
  const missingIsolationApi = Boolean(options.missingIsolationApi);

  const local = {
    accessLevel: () => accessLevel,
    events: () => events.slice(),
    store,
    async setAccessLevel(arg) {
      events.push({ op: "setAccessLevel", arg, at: events.length });
      if (failIsolation) throw new Error("setAccessLevel failed");
      accessLevel = arg.accessLevel;
    },
    async get(defaults) {
      const out = Object.assign({}, defaults || {});
      for (const k of Object.keys(out)) {
        if (Object.prototype.hasOwnProperty.call(store, k)) out[k] = store[k];
      }
      return out;
    },
    async set(obj) {
      events.push({ op: "set", keys: Object.keys(obj), at: events.length });
      Object.assign(store, obj);
    },
    readAsContentScript() {
      if (accessLevel === "TRUSTED_CONTEXTS") {
        return { denied: true, byok: undefined };
      }
      return { denied: false, byok: store.byok };
    },
  };
  if (missingIsolationApi) delete local.setAccessLevel;

  return {
    runtime: { id: "gold-miner-test", onMessage: { addListener() {} } },
    storage: { local },
  };
}

function defaultSearchItems(query) {
  const q = String(query || "").toLowerCase();
  if (exploreFixture.searches[q]) return exploreFixture.searches[q].items;
  if (q.includes("clipboard") || q.includes("剪贴板")) {
    return [
      {
        full_name: "p0deje/Maccy",
        stargazers_count: 21637,
        description: "clipboard history",
        html_url: "https://github.com/p0deje/Maccy",
      },
      {
        full_name: "EcoPasteHub/EcoPaste",
        stargazers_count: 100,
        description: "clipboard rss",
        html_url: "https://github.com/EcoPasteHub/EcoPaste",
      },
      {
        full_name: "hot/mega",
        stargazers_count: 80000,
        description: "generic tool",
        html_url: "https://github.com/hot/mega",
      },
    ];
  }
  if (q.includes("injected-model-term")) {
    return [
      {
        full_name: "model/hit",
        stargazers_count: 12,
        description: "from model expansion",
        html_url: "https://github.com/model/hit",
      },
    ];
  }
  return [
    {
      full_name: "example/one",
      stargazers_count: 3,
      description: "fixture",
      html_url: "https://github.com/example/one",
    },
  ];
}

function createFetchRecorder(handler) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url: String(url), init: init || {} });
    return handler(String(url), init || {}, calls);
  };
  fetchImpl.calls = calls;
  return fetchImpl;
}

function githubOkFetch() {
  return createFetchRecorder(async (url) => {
    if (url.includes("/repos/") && !url.includes("/search/")) {
      return jsonResponse(200, exploreFixture.repo);
    }
    const q = new URL(url).searchParams.get("q") || "";
    return jsonResponse(200, { items: defaultSearchItems(q) });
  });
}

function loadBackground(chrome, fetchImpl, extra) {
  extra = extra || {};
  const ctx = {
    chrome,
    fetch: fetchImpl,
    console,
    setTimeout,
    clearTimeout,
    AbortController,
    URL,
    Date,
    Map,
    Set,
    Object,
    Boolean,
    String,
    Number,
    Array,
    JSON,
    Promise,
    Error,
    TypeError,
    __GOLD_MINER_TEST__: true,
  };
  ctx.globalThis = ctx;
  ctx.self = ctx;
  vm.runInNewContext(sharedSrc, ctx);
  vm.runInNewContext(backgroundSrc, ctx);
  const svc = ctx.GoldMinerBackground.createBackground({
    chrome,
    fetch: fetchImpl,
    shared: ctx.GoldMinerShared,
    modelClient: extra.modelClient,
    setTimeout,
    clearTimeout,
  });
  return { ctx, svc, S: ctx.GoldMinerShared };
}

const sender = { id: "gold-miner-test" };

function searchMsg(overrides) {
  return Object.assign(
    {
      type: "SEARCH",
      jobId: "job-search",
      pageUrl: "https://github.com/search?q=clipboard",
      originalQuery: "clipboard",
      contentVersion: "dom-1",
      limit: 5,
    },
    overrides || {}
  );
}

test("P1-1 isolation API is invoked before API key persist", async () => {
  const chrome = createMockChrome();
  const { svc } = loadBackground(chrome, githubOkFetch());
  const resp = await svc.dispatch(
    {
      type: "SAVE_SETTINGS",
      settings: {
        readingLang: "zh",
        interests: [],
        personalization: true,
        historyEnabled: false,
        byok: {
          baseUrl: "https://example.test/v1",
          model: "mock-model",
          apiKey: "mock-key-not-real",
        },
      },
    },
    sender
  );
  assert.equal(resp.code, "ok");
  const events = chrome.storage.local.events();
  const iso = events.find((e) => e.op === "setAccessLevel");
  const persist = events.find((e) => e.op === "set" && e.keys.includes("byok"));
  assert.ok(iso, "setAccessLevel must be called");
  assert.equal(iso.arg.accessLevel, "TRUSTED_CONTEXTS");
  assert.ok(persist, "byok persist must happen");
  assert.ok(iso.at < persist.at, "isolation must run before persist");
  assert.equal(chrome.storage.local.store.byok.apiKey, "mock-key-not-real");
  const content = chrome.storage.local.readAsContentScript();
  assert.equal(content.denied, true);
  assert.equal(content.byok, undefined);
});

test("P1-1 fail-closed: isolation error does not save API key", async () => {
  const chrome = createMockChrome({ failIsolation: true });
  const { svc } = loadBackground(chrome, githubOkFetch());
  const resp = await svc.dispatch(
    {
      type: "SAVE_SETTINGS",
      settings: {
        readingLang: "en",
        interests: ["rss"],
        personalization: true,
        historyEnabled: false,
        byok: { baseUrl: "https://example.test/v1", model: "m", apiKey: "mock-key-not-real" },
      },
    },
    sender
  );
  assert.equal(resp.code, "storage_isolation_failed");
  assert.equal((chrome.storage.local.store.byok || {}).apiKey || "", "");
  assert.equal(chrome.storage.local.store.readingLang, "en");
  const content = chrome.storage.local.readAsContentScript();
  assert.equal(content.denied, false);
  assert.ok(!content.byok || !content.byok.apiKey);
});

test("P1-1 missing setAccessLevel on local denies key persist", async () => {
  const chrome = createMockChrome({ missingIsolationApi: true });
  const { svc } = loadBackground(chrome, githubOkFetch());
  const resp = await svc.dispatch(
    {
      type: "SAVE_SETTINGS",
      settings: {
        readingLang: "zh",
        interests: [],
        personalization: true,
        historyEnabled: false,
        byok: { baseUrl: "https://example.test/v1", model: "m", apiKey: "mock-key-not-real" },
      },
    },
    sender
  );
  assert.equal(resp.code, "storage_isolation_failed");
  assert.equal((chrome.storage.local.store.byok || {}).apiKey || "", "");
});

test("P1-2 injected model client expansions are used; hasModel only then", async () => {
  const chrome = createMockChrome();
  const fetchImpl = githubOkFetch();
  const { svc } = loadBackground(chrome, fetchImpl, {
    modelClient: async () => [
      { query: "injected-model-term", lang: "en", source: "github_search_default" },
    ],
  });
  const resp = await svc.dispatch(searchMsg(), sender);
  assert.equal(resp.code, "ok");
  assert.equal(resp.hasModel, true);
  assert.ok(resp.expansions.some((e) => e.query === "injected-model-term"));
  assert.ok(resp.candidates.some((c) => c.repo === "model/hit"));
  assert.ok(fetchImpl.calls.some((c) => c.url.includes("injected-model-term")));
  const cached = Object.values(chrome.storage.local.store.cache);
  assert.equal(cached[0].processing_mode, "model");
});

test("P1-2 without client stays rules-only and never claims hasModel", async () => {
  const chrome = createMockChrome();
  const fetchImpl = githubOkFetch();
  const { svc } = loadBackground(chrome, fetchImpl);
  const resp = await svc.dispatch(searchMsg({ originalQuery: "剪贴板" }), sender);
  assert.equal(resp.code, "ok");
  assert.equal(resp.hasModel, false);
  assert.ok(resp.expansions.some((e) => e.source === "original_query"));
  assert.ok(!resp.expansions.some((e) => e.query === "injected-model-term"));
  const cached = Object.values(chrome.storage.local.store.cache);
  assert.equal(cached[0].processing_mode, "rules");
  const pub = await svc.dispatch({ type: "GET_PUBLIC_SETTINGS" }, sender);
  assert.equal(pub.settings.hasModel, false);
});

test("P1-2 key present without a real model run does not set hasModel", async () => {
  const chrome = createMockChrome({
    store: {
      byok: { baseUrl: "https://example.test/v1", model: "mock-model", apiKey: "mock-key-not-real" },
    },
  });
  const fetchImpl = createFetchRecorder(async (url) => {
    if (url.includes("/chat/completions")) {
      return jsonResponse(500, { error: "nope" });
    }
    const q = new URL(url).searchParams.get("q") || "";
    return jsonResponse(200, { items: defaultSearchItems(q) });
  });
  const { svc } = loadBackground(chrome, fetchImpl);
  const resp = await svc.dispatch(searchMsg(), sender);
  assert.equal(resp.hasModel, false);
  assert.ok(resp.code === "ok" || resp.code === "model_unavailable");
});

test("P2-3 mocked HTTP 403 is not cached as success", async () => {
  const chrome = createMockChrome();
  const fetchImpl = createFetchRecorder(async () => jsonResponse(403, { message: "no" }));
  const { svc } = loadBackground(chrome, fetchImpl);
  const first = await svc.dispatch(searchMsg(), sender);
  assert.equal(first.code, "bad_response");
  assert.equal(first.cached, undefined);
  assert.deepEqual(Object.keys(chrome.storage.local.store.cache), []);
  const second = await svc.dispatch(searchMsg(), sender);
  assert.equal(second.cached, undefined);
  assert.equal(second.code, "bad_response");
  assert.ok(fetchImpl.calls.length >= 2);
});

test("P2-3 network_error is preserved and not written as success cache", async () => {
  const chrome = createMockChrome();
  const fetchImpl = createFetchRecorder(async () => {
    throw new TypeError("Failed to fetch");
  });
  const { svc } = loadBackground(chrome, fetchImpl);
  const resp = await svc.dispatch(searchMsg(), sender);
  assert.equal(resp.code, "network_error");
  assert.deepEqual(chrome.storage.local.store.cache, {});
});

test("P2-4 mark irrelevant reranks cached raw candidates without refetch", async () => {
  const chrome = createMockChrome();
  const fetchImpl = githubOkFetch();
  const { svc } = loadBackground(chrome, fetchImpl);
  const first = await svc.dispatch(searchMsg(), sender);
  assert.equal(first.code, "ok");
  assert.ok(first.candidates.some((c) => /ecopaste/i.test(c.repo)));
  const fetchesAfterFirst = fetchImpl.calls.length;
  await svc.dispatch(
    { type: "FEEDBACK", repo: "EcoPasteHub/EcoPaste", action: "irrelevant" },
    sender
  );
  const second = await svc.dispatch(searchMsg(), sender);
  assert.equal(second.cached, true);
  assert.ok(!second.candidates.some((c) => /ecopaste/i.test(c.repo)));
  assert.equal(fetchImpl.calls.length, fetchesAfterFirst);
});

test("P2-4 personalization toggle changes ranking without refetch", async () => {
  const chrome = createMockChrome({
    store: { personalization: true, interests: ["rss"] },
  });
  const fetchImpl = githubOkFetch();
  const { svc } = loadBackground(chrome, fetchImpl);
  const first = await svc.dispatch(searchMsg(), sender);
  assert.equal(first.code, "ok");
  await svc.dispatch(
    { type: "FEEDBACK", repo: "hot/mega", action: "interested" },
    sender
  );
  const withPersonal = await svc.dispatch(searchMsg(), sender);
  assert.equal(withPersonal.cached, true);
  assert.equal(withPersonal.candidates[0].repo.toLowerCase(), "hot/mega");
  const fetches = fetchImpl.calls.length;
  await svc.dispatch(
    {
      type: "SAVE_SETTINGS",
      settings: {
        readingLang: "zh",
        interests: ["rss"],
        personalization: false,
        historyEnabled: false,
        byok: { baseUrl: "", model: "", apiKey: "" },
      },
    },
    sender
  );
  const without = await svc.dispatch(searchMsg(), sender);
  assert.equal(without.cached, true);
  assert.equal(fetchImpl.calls.length, fetches);
  assert.notEqual(without.candidates[0].repo.toLowerCase(), "hot/mega");
});

test("P2-5 explore uses repo topics fixture and returns related candidates", async () => {
  const chrome = createMockChrome();
  const fetchImpl = githubOkFetch();
  const { svc, S } = loadBackground(chrome, fetchImpl);
  const planned = S.buildExploreQueries(exploreFixture.repo, "zh");
  assert.ok(planned.some((e) => e.source === S.SOURCE_KINDS.topic_related));
  assert.ok(planned.some((e) => e.query === "clipboard"));
  const resp = await svc.dispatch(
    {
      type: "EXPLORE",
      jobId: "job-explore",
      pageUrl: "https://github.com/p0deje/Maccy",
      originalQuery: "",
      contentVersion: "dom-1",
      limit: 3,
    },
    sender
  );
  assert.equal(resp.code, "ok");
  assert.ok(resp.candidates.length > 0, "explore must return related candidates");
  assert.ok(!resp.candidates.some((c) => S.canonicalRepo(c.repo) === "p0deje/maccy"));
  assert.ok(
    fetchImpl.calls.some((c) => c.url.includes("/repos/p0deje/maccy")),
    "must fetch repo metadata"
  );
  assert.ok(
    fetchImpl.calls.some(
      (c) => c.url.includes("/search/repositories") && c.url.includes("clipboard")
    )
  );
  assert.ok(resp.candidates.some((c) => /ecopaste|clipy/i.test(c.repo)));
});

test("P2-6 export import reuse hits cache and skips refetch", async () => {
  const chrome = createMockChrome();
  const fetchImpl = githubOkFetch();
  const { svc } = loadBackground(chrome, fetchImpl);
  const first = await svc.dispatch(searchMsg(), sender);
  assert.equal(first.code, "ok");
  assert.ok(first.candidates.length > 0);
  const exported = await svc.dispatch({ type: "EXPORT_CACHE" }, sender);
  assert.equal(exported.code, "ok");
  assert.ok(exported.bundle.entries.length >= 1);
  const searchEntry = exported.bundle.entries.find((e) => e.pageKind === "SEARCH");
  assert.ok(searchEntry, "search cache must be exported");
  assert.ok(searchEntry.rawCandidates && searchEntry.rawCandidates.length > 0);
  assert.ok(!JSON.stringify(exported.bundle).includes("mock-key"));
  await svc.dispatch({ type: "CLEAR_LOCAL" }, sender);
  assert.deepEqual(chrome.storage.local.store.cache, {});
  const imported = await svc.dispatch(
    { type: "IMPORT_CACHE", bundle: exported.bundle },
    sender
  );
  assert.equal(imported.code, "ok");
  assert.ok(imported.imported >= 1);
  const fetches = fetchImpl.calls.length;
  const reused = await svc.dispatch(searchMsg(), sender);
  assert.equal(reused.cached, true);
  assert.equal(reused.code, "ok");
  assert.ok(reused.candidates.length > 0);
  assert.equal(fetchImpl.calls.length, fetches);
});

test("message handlers reject unknown types", async () => {
  const chrome = createMockChrome();
  const { svc } = loadBackground(chrome, githubOkFetch());
  const resp = await svc.dispatch({ type: "NOT_A_TYPE" }, sender);
  assert.equal(resp.code, "untrusted_input");
});
