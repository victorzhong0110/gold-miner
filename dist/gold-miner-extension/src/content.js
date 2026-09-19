/* Content script: GitHub DOM is untrusted. Never read keys. Never exec remote text. */

(function () {
  "use strict";
  const S = globalThis.GoldMinerShared;
  const ROOT_ID = "gold-miner-root";
  let navGen = 0;
  let attached = false;

  function pageKind() {
    const path = location.pathname;
    if (path === "/search" || path.startsWith("/search")) return "search";
    const parts = path.split("/").filter(Boolean);
    if (parts.length >= 2 && !["settings", "orgs", "topics", "notifications"].includes(parts[0])) {
      return "repo";
    }
    return "other";
  }

  function originalQuery() {
    const q = new URLSearchParams(location.search).get("q");
    return S.sanitizeRemoteText(q || "");
  }

  function repoFromPath() {
    const parts = location.pathname.split("/").filter(Boolean);
    if (parts.length >= 2) return parts[0] + "/" + parts[1];
    return "";
  }

  function contentVersion() {
    const about = document.querySelector("title");
    return S.sanitizeRemoteText((about && about.textContent) || location.pathname).slice(0, 80);
  }

  function langFromSettings(settings) {
    return settings && settings.readingLang === "en" ? "en" : "zh";
  }

  function ensureRoot() {
    let el = document.getElementById(ROOT_ID);
    if (el) return el;
    el = document.createElement("aside");
    el.id = ROOT_ID;
    el.setAttribute("data-gold-miner", "1");
    const host =
      document.querySelector("#js-pjax-container") ||
      document.querySelector("main") ||
      document.body;
    host.appendChild(el);
    return el;
  }

  function clearRoot() {
    const el = document.getElementById(ROOT_ID);
    if (el) el.remove();
  }

  function render(state) {
    const el = ensureRoot();
    el.textContent = "";
    const lang = state.lang;
    const box = document.createElement("section");
    box.className = "gm-panel";

    const h = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = S.t(lang, state.kind === "search" ? "searchTitle" : "exploreTitle");
    h.appendChild(title);
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = S.t(lang, "close");
    close.addEventListener("click", () => {
      el.remove();
    });
    h.appendChild(close);
    box.appendChild(h);

    if (state.status === "loading") {
      const p = document.createElement("p");
      p.textContent = S.t(lang, "loading");
      box.appendChild(p);
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.textContent = S.t(lang, "cancel");
      cancel.addEventListener("click", () => {
        chrome.runtime.sendMessage({ type: "CANCEL", jobId: state.jobId });
        state.status = "cancelled";
        render(state);
      });
      box.appendChild(cancel);
      el.appendChild(box);
      return;
    }

    if (state.code && state.code !== "ok") {
      const p = document.createElement("p");
      p.className = "gm-status";
      p.textContent = S.t(lang, state.code) || state.code;
      box.appendChild(p);
    }
    if (!state.hasModel) {
      const p = document.createElement("p");
      p.className = "gm-status";
      p.textContent = S.t(lang, "noModel");
      box.appendChild(p);
    }

    const oq = document.createElement("p");
    const oql = document.createElement("span");
    oql.textContent = S.t(lang, "originalQuery") + ": ";
    oq.appendChild(oql);
    oq.appendChild(document.createTextNode(state.originalQuery || ""));
    box.appendChild(oq);

    const list = document.createElement("ul");
    for (const c of state.candidates || []) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = c.html_url || "https://github.com/" + c.repo;
      a.textContent = c.repo;
      a.rel = "noreferrer noopener";
      li.appendChild(a);
      const meta = document.createElement("div");
      meta.className = "gm-meta";
      const purpose = S.rejectUntrustedDirective(c.purpose || c.description || "");
      meta.appendChild(document.createTextNode(S.t(lang, "purpose") + ": " + purpose.text));
      li.appendChild(meta);
      const src = document.createElement("div");
      src.className = "gm-meta";
      src.textContent = S.t(lang, "source") + ": " + (c.source || "unknown");
      li.appendChild(src);
      const why = document.createElement("div");
      why.className = "gm-meta";
      const whySafe = S.rejectUntrustedDirective(c.why || "");
      why.textContent = S.t(lang, "why") + ": " + whySafe.text;
      li.appendChild(why);
      const actions = document.createElement("div");
      ["interested", "irrelevant", "seen"].forEach((act) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = S.t(lang, act);
        btn.addEventListener("click", () => {
          chrome.runtime.sendMessage({ type: "FEEDBACK", repo: c.repo, action: act });
        });
        actions.appendChild(btn);
      });
      li.appendChild(actions);
      list.appendChild(li);
    }
    box.appendChild(list);
    el.appendChild(box);
  }

  function run(kind) {
    const myGen = ++navGen;
    const jobId = "job-" + myGen + "-" + Date.now();
    chrome.runtime.sendMessage({ type: "GET_PUBLIC_SETTINGS" }, (settingsResp) => {
      if (myGen !== navGen) return;
      const settings = (settingsResp && settingsResp.settings) || {};
      const lang = langFromSettings(settings);
      const state = {
        kind,
        lang,
        jobId,
        status: "loading",
        originalQuery: originalQuery() || repoFromPath(),
        candidates: [],
        hasModel: settings.hasModel,
        code: "ok",
      };
      render(state);
      const msg = {
        type: kind === "search" ? "SEARCH" : "EXPLORE",
        jobId,
        pageUrl: location.href,
        originalQuery: state.originalQuery,
        contentVersion: contentVersion(),
        limit: kind === "explore" ? 3 : 5,
      };
      chrome.runtime.sendMessage(msg, (resp) => {
        if (myGen !== navGen) return;
        if (chrome.runtime.lastError) {
          state.status = "error";
          state.code = "bad_response";
          render(state);
          return;
        }
        state.status = "ready";
        state.code = (resp && resp.code) || "bad_response";
        state.candidates = (resp && resp.candidates) || [];
        state.originalQuery = (resp && resp.originalQuery) || state.originalQuery;
        state.hasModel = resp && resp.hasModel;
        if (state.code === "rate_limited") state.code = "rateLimited";
        if (state.code === "timeout") state.code = "timeout";
        if (state.code === "model_unavailable") state.code = "modelUnavailable";
        render(state);
      });
    });
  }

  function onNavigate() {
    clearRoot();
    const kind = pageKind();
    if (kind === "other") return;
    run(kind);
  }

  function hookNav() {
    if (attached) return;
    attached = true;
    document.addEventListener("pjax:end", onNavigate);
    document.addEventListener("turbo:load", onNavigate);
    document.addEventListener("turbo:render", onNavigate);
    window.addEventListener("popstate", onNavigate);
    const push = history.pushState;
    history.pushState = function () {
      const ret = push.apply(this, arguments);
      onNavigate();
      return ret;
    };
    const replace = history.replaceState;
    history.replaceState = function () {
      const ret = replace.apply(this, arguments);
      onNavigate();
      return ret;
    };
  }

  hookNav();
  onNavigate();
})();
