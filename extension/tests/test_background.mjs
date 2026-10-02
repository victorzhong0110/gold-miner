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

const sender = { id: "gold-miner-test", url: "chrome-extension://gold-miner-test/src/options.html" };

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
  assert.equal(Object.keys(chrome.storage.local.store.cache || {}).length, 0);
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
  assert.equal(Object.keys(chrome.storage.local.store.cache || {}).length, 0);
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

function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; }
const modelSettings = (model = 'm') => ({type: 'SAVE_SETTINGS', settings: {readingLang: 'zh', byok: {baseUrl: 'https://example.test/v1', model, apiKey: 'mock-key-not-real'}}});

test('R1 rules cache does not suppress newly configured model or recovery', async () => {
  const chrome = createMockChrome();
  let modelCalls = 0, fail = true;
  const fetchImpl = createFetchRecorder(async url => {
    if (url.includes('/chat/completions')) {
      modelCalls++;
      return fail ? jsonResponse(500, {}) : jsonResponse(200, {choices: [{message: {content: '{"en":["injected-model-term"]}'}}]});
    }
    return jsonResponse(200, {items: defaultSearchItems(new URL(url).searchParams.get('q'))});
  });
  const {svc} = loadBackground(chrome, fetchImpl);
  await svc.dispatch(searchMsg(), sender);
  await svc.dispatch(modelSettings(), sender);
  const fallback = await svc.dispatch(searchMsg(), sender);
  assert.equal(fallback.hasModel, false);
  assert.equal(modelCalls, 1);
  fail = false;
  assert.equal((await svc.dispatch(searchMsg(), sender)).hasModel, true);
  assert.equal(modelCalls, 2);
  assert.equal((await svc.dispatch(searchMsg(), sender)).cached, true);
  await svc.dispatch(modelSettings('another-model'), sender);
  await svc.dispatch(searchMsg(), sender);
  assert.equal(modelCalls, 3);
});

test('R2 cancellation during search aborts and ignores a late successful response', async () => {
  const chrome = createMockChrome(), started = deferred(), late = deferred();
  let signal;
  const fetchImpl = createFetchRecorder(async (_, init) => {signal = init.signal; started.resolve(); return late.promise;});
  const {svc} = loadBackground(chrome, fetchImpl);
  const pending = svc.dispatch(searchMsg(), sender);
  await started.promise;
  await svc.dispatch({type: 'CANCEL', jobId: 'job-search'}, sender);
  assert.equal(signal.aborted, true);
  late.resolve(jsonResponse(200, {items: defaultSearchItems('clipboard')}));
  const result = await pending;
  assert.equal(result.code, 'cancelled');
  assert.equal(result.candidates.length, 0);
  assert.equal(fetchImpl.calls.length, 1);
  assert.equal(Object.keys(chrome.storage.local.store.cache).length, 0);
  assert.equal((await svc.dispatch(searchMsg({jobId: 'retry'}), sender)).code, 'ok');
});

test('R2 cancellation during model prevents all subsequent GitHub requests', async () => {
  const chrome = createMockChrome(), started = deferred(), late = deferred();
  const fetchImpl = githubOkFetch();
  const {svc} = loadBackground(chrome, fetchImpl, {modelClient: async ({signal}) => {started.resolve(signal); return late.promise;}});
  const pending = svc.dispatch(searchMsg(), sender);
  const signal = await started.promise;
  await svc.dispatch({type: 'CANCEL', jobId: 'job-search'}, sender);
  assert.equal(signal.aborted, true);
  late.resolve([{query: 'late', lang: 'en'}]);
  assert.equal((await pending).code, 'cancelled');
  assert.equal(fetchImpl.calls.length, 0);
  assert.equal(Object.keys(chrome.storage.local.store.cache).length, 0);
});

test('R3 imported candidate URLs are rebuilt and malformed repository names dropped', async () => {
  const chrome = createMockChrome(), fetchImpl = githubOkFetch();
  const {svc} = loadBackground(chrome, fetchImpl);
  await svc.dispatch(searchMsg(), sender);
  const exported = await svc.dispatch({type: 'EXPORT_CACHE'}, sender);
  exported.bundle.entries[0].rawCandidates[0].html_url = 'javascript:alert(1)';
  exported.bundle.entries[0].rawCandidates.push({repo: 'evil/../../payload', html_url: 'https://evil.test'});
  await svc.dispatch({type: 'CLEAR_LOCAL'}, sender);
  await svc.dispatch({type: 'IMPORT_CACHE', bundle: exported.bundle}, sender);
  const result = await svc.dispatch(searchMsg(), sender);
  assert.equal(result.cached, true);
  assert.ok(result.candidates.length);
  for (const c of result.candidates) assert.equal(c.html_url, 'https://github.com/' + c.repo.toLowerCase());
  assert.ok(!result.candidates.some(c => c.repo.includes('..')));
});

test('page messages cannot write settings, export cache or clear local data', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  const pageSender = {...sender, tab: {id: 4, url: 'https://github.com/example/one'}, url: 'https://github.com/example/one'};
  for (const type of ['SAVE_SETTINGS', 'EXPORT_CACHE', 'IMPORT_CACHE', 'CLEAR_LOCAL']) assert.equal((await svc.dispatch({type}, pageSender)).code, 'untrusted_input');
  assert.equal((await svc.dispatch({type: 'GET_PUBLIC_SETTINGS'}, {...pageSender, url: 'https://evil.test'})).code, 'untrusted_input');
  assert.equal((await svc.dispatch({type: 'GET_PUBLIC_SETTINGS'}, {})).code, 'untrusted_input');
});

test('two concurrent jobs preserve both cache entries and third request is bounded', async () => {
  const chrome = createMockChrome(), gate = deferred(), entered = deferred();
  let count = 0;
  const {svc} = loadBackground(chrome, createFetchRecorder(async () => {if (++count === 2) entered.resolve(); await gate.promise; return jsonResponse(200, {items: []});}));
  const a = svc.dispatch(searchMsg({jobId: 'a', originalQuery: 'alpha'}), sender);
  const b = svc.dispatch(searchMsg({jobId: 'b', originalQuery: 'beta'}), sender);
  await entered.promise;
  assert.equal((await svc.dispatch(searchMsg({jobId: 'c'}), sender)).code, 'busy');
  gate.resolve();
  await Promise.all([a, b]);
  assert.equal(Object.keys(chrome.storage.local.store.cache).length, 2);
});

test('clear data prevents pending requests from recreating cache', async () => {
  const chrome = createMockChrome(), gate = deferred(), started = deferred();
  const {svc} = loadBackground(chrome, createFetchRecorder(async () => {started.resolve(); await gate.promise; return jsonResponse(200, {items: []});}));
  const pending = svc.dispatch(searchMsg(), sender);
  await started.promise;
  await svc.dispatch({type: 'CLEAR_LOCAL'}, sender);
  gate.resolve();
  assert.equal((await pending).code, 'cancelled');
  assert.equal(Object.keys(chrome.storage.local.store.cache).length, 0);
});

test('expired cache is refreshed and content changes use a new cache', async () => {
  const chrome = createMockChrome(), fetchImpl = githubOkFetch(), {svc} = loadBackground(chrome, fetchImpl);
  await svc.dispatch(searchMsg(), sender);
  Object.values(chrome.storage.local.store.cache)[0].created_at = '2020-01-01T00:00:00Z';
  assert.equal((await svc.dispatch(searchMsg(), sender)).cached, undefined);
  assert.equal((await svc.dispatch(searchMsg({contentVersion: 'new-readme'}), sender)).cached, undefined);
});

test('invalid endpoint and malformed import do not change stored data', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  const message = modelSettings(); message.settings.byok.baseUrl = 'https://key:password@evil.test';
  assert.equal((await svc.dispatch(message, sender)).code, 'invalid_endpoint');
  assert.equal(chrome.storage.local.store.byok.apiKey, '');
  for (const bundle of [{entries: []}, {format: 'gold-miner-cache-v1', entries: 'not-array'}, null]) assert.equal((await svc.dispatch({type: 'IMPORT_CACHE', bundle}, sender)).code, 'bad_response');
});

test('rate-limit header applies backoff without additional HTTP calls', async () => {
  const chrome = createMockChrome();
  const fetchImpl = createFetchRecorder(async () => ({...jsonResponse(403, {}), headers: {get: key => key === 'x-ratelimit-remaining' ? '0' : null}}));
  const {svc} = loadBackground(chrome, fetchImpl);
  assert.equal((await svc.dispatch(searchMsg(), sender)).code, 'rate_limited');
  assert.equal((await svc.dispatch(searchMsg({jobId: 'new'}), sender)).code, 'rate_limited');
  assert.equal(fetchImpl.calls.length, 1);
  assert.equal(Object.keys(chrome.storage.local.store.cache).length, 0);
});

test('actual request counters separate cache hits and GitHub calls', async () => {
  const chrome = createMockChrome(), fetchImpl = githubOkFetch(), {svc} = loadBackground(chrome, fetchImpl);
  const result = await svc.dispatch(searchMsg(), sender);
  assert.equal(result.cost.github_requests, fetchImpl.calls.length);
  assert.equal(result.cost.model_requests, 0);
  const cached = await svc.dispatch(searchMsg(), sender);
  assert.equal(cached.cost.github_requests, 0);
  assert.equal(cached.cost.cache_hits, 1);
});


test('actual options tab can save/export/reset while other contexts cannot', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  const optionsTab = {...sender, tab: {id: 12, url: sender.url}};
  assert.equal((await svc.dispatch({type:'SAVE_SETTINGS', settings:{readingLang:'en', interests:['rss']}}, optionsTab)).code, 'ok');
  assert.equal(chrome.storage.local.store.readingLang, 'en');
  assert.equal((await svc.dispatch({type:'EXPORT_CACHE'}, optionsTab)).code, 'ok');
  assert.equal((await svc.dispatch({type:'CLEAR_LOCAL'}, optionsTab)).code, 'ok');
  for (const url of ['chrome-extension://other/src/options.html', 'chrome-extension://gold-miner-test/src/content.js', 'https://github.com/src/options.html', '']) {
    const rejected = {...sender, url};
    assert.equal((await svc.dispatch({type:'SAVE_SETTINGS', settings:{readingLang:'zh'}}, rejected)).code,'untrusted_input');
  }
  assert.equal(chrome.storage.local.store.readingLang, 'en');
});

test('concurrent feedback preserves both seen projects', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  await Promise.all([
    svc.dispatch({type:'FEEDBACK', repo:'owner/one', action:'seen'}, sender),
    svc.dispatch({type:'FEEDBACK', repo:'owner/two', action:'irrelevant'}, sender),
  ]);
  assert.deepEqual(JSON.parse(JSON.stringify(chrome.storage.local.store.feedback)), {'owner/one':'seen', 'owner/two':'irrelevant'});
  assert.deepEqual(new Set(chrome.storage.local.store.seen), new Set(['owner/one','owner/two']));
});

test('clear waits for an already accepted feedback write', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  const gate = deferred(), entered = deferred(), set = chrome.storage.local.set.bind(chrome.storage.local);
  let delayed = false;
  chrome.storage.local.set = async patch => {
    if (patch.feedback && Object.keys(patch.feedback).length && !delayed) {
      delayed = true; entered.resolve(); await gate.promise;
    }
    await set(patch);
  };
  const feedback = svc.dispatch({type:'FEEDBACK', repo:'owner/one', action:'seen'}, sender);
  await entered.promise;
  const clear = svc.dispatch({type:'CLEAR_LOCAL'}, sender);
  gate.resolve(); await Promise.all([feedback, clear]);
  assert.equal(chrome.storage.local.store.seen.length, 0);
  assert.equal(Object.keys(chrome.storage.local.store.feedback).length, 0);
});

test('two concurrent cache imports preserve both bundles', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  const bundle = query => ({format:'gold-miner-cache-v1', entries:[{
    pageKind:'SEARCH',query,purpose:query,language:'zh',content_version:'v1',
    processing_mode:'rules',created_at:new Date().toISOString(),rawCandidates:[]
  }]});
  await Promise.all(['one','two'].map(query => svc.dispatch({type:'IMPORT_CACHE',bundle:bundle(query)},sender)));
  assert.deepEqual(new Set(Object.values(chrome.storage.local.store.cache).map(x=>x.query)), new Set(['one','two']));
});

test('failed feedback write does not poison the next mutation', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  const set = chrome.storage.local.set.bind(chrome.storage.local); let fail = true;
  chrome.storage.local.set = async patch => {
    if (patch.feedback && fail) {fail = false; throw new Error('fixture storage failure');}
    await set(patch);
  };
  await assert.rejects(svc.dispatch({type:'FEEDBACK',repo:'owner/one',action:'seen'},sender));
  assert.equal((await svc.dispatch({type:'FEEDBACK',repo:'owner/two',action:'seen'},sender)).code,'ok');
  assert.deepEqual(chrome.storage.local.store.seen,['owner/two']);
});

test('concurrent exploration keeps both opted-in history records', async () => {
  const chrome = createMockChrome({store:{historyEnabled:true}}), {svc} = loadBackground(chrome, githubOkFetch());
  await Promise.all(['one','two'].map((name,i) => svc.dispatch({type:'EXPLORE',jobId:'history-'+i,
    pageUrl:'https://github.com/owner/'+name,contentVersion:'v1',limit:3},sender)));
  assert.deepEqual(new Set(chrome.storage.local.store.pageHistory),new Set(['owner/one','owner/two']));
});

test('repeated import never grows the cache past its 100-entry budget', async () => {
  const chrome = createMockChrome(), {svc} = loadBackground(chrome, githubOkFetch());
  const bundle = start => ({format:'gold-miner-cache-v1',entries:Array.from({length:100},(_,i)=>({
    pageKind:'SEARCH',query:'fixture-'+(start+i),language:'zh',content_version:'v1',
    processing_mode:'rules',created_at:new Date().toISOString(),rawCandidates:[]
  }))});
  await svc.dispatch({type:'IMPORT_CACHE',bundle:bundle(0)},sender);
  await svc.dispatch({type:'IMPORT_CACHE',bundle:bundle(100)},sender);
  assert.equal(Object.keys(chrome.storage.local.store.cache).length,100);
  assert.equal((await svc.dispatch({type:'EXPORT_CACHE'},sender)).bundle.entries.length,100);
});
