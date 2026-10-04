import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const source = name => fs.readFileSync(new URL('../src/' + name, import.meta.url), 'utf8');

function page(feedbackCode = 'ok') {
  const sent = [], callbacks = [], events = {};
  class Element {
    constructor(tag) {this.tag = tag; this.children = []; this.listeners = {}; this._text = ''; this.attrs = {};}
    set textContent(v) {this._text = v; this.children = [];}
    get textContent() {return this._text + this.children.map(c => c.textContent).join('');}
    appendChild(n) {n.parent = this; this.children.push(n); return n;}
    insertBefore(n, ref) {
      n.parent = this;
      const at = ref ? this.children.indexOf(ref) : -1;
      if (at < 0) this.children.push(n); else this.children.splice(at, 0, n);
      return n;
    }
    get firstChild() {return this.children[0] || null;}
    remove() {if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this);}
    setAttribute(k, v) {this.attrs[k] = v;}
    getAttribute(k) {return this.attrs[k];}
    addEventListener(name, fn) {this.listeners[name] = fn;}
  }
  const body = new Element('body');
  // Optional realistic page: <body><main><article/></main></body>
  let main = null;
  if (page.withMain) {
    main = new Element('main');
    main.attrs.id = page.withMain;
    main.appendChild(new Element('article'));
    body.appendChild(main);
  }
  const all = (root = body) => [root, ...root.children.flatMap(c => all(c))];
  const document = {
    body, createElement: t => new Element(t),
    createTextNode: t => {const n = new Element('text'); n.textContent = t; return n;},
    getElementById: id => all().find(n => n.id === id),
    querySelector: sel => (sel === 'main' || (main && sel === '#' + main.attrs.id)) ? main : null,
    querySelectorAll: () => [{textContent: document.readme || 'readme-v1'}],
    addEventListener: (name, cb) => {events[name] = cb;},
  };
  const location = {href: 'https://github.com/search?q=clipboard', pathname: '/search', search: '?q=clipboard'};
  const chrome = {runtime: {sendMessage(msg, cb) {sent.push(msg); if (msg.type === 'GET_PUBLIC_SETTINGS') cb({settings: {readingLang: 'en'}}); else if (msg.type === 'SEARCH' || msg.type === 'EXPLORE') callbacks.push(cb); else if (cb) cb({code: msg.type === 'FEEDBACK' ? feedbackCode : 'ok'});}}};
  const context = {document, location, chrome, URL, URLSearchParams, console, Date, Math, setInterval: cb => {events.poll = cb;}, history: {pushState() {}, replaceState() {}}, window: {addEventListener: (name, cb) => {events[name] = cb;}}};
  context.globalThis = context;
  vm.runInNewContext(source('shared.js'), context);
  vm.runInNewContext(source('content.js'), context);
  return {sent, callbacks, body, all, document, location, events, setFeedbackResponse: code => {feedbackCode = code;}};
}
const result = {code: 'ok', candidates: [{repo: 'safe/repo', html_url: 'javascript:alert(1)', description: 'fixture'}], hasModel: false};

test('cancelled UI ignores late callback', () => {
  const p = page();
  p.all().find(n => n.tag === 'button' && n.textContent === 'Cancel').listeners.click();
  p.callbacks[0](result);
  assert.match(p.body.textContent, /Cancelled/);
  assert.equal(p.all().filter(n => n.tag === 'a').length, 0);
  assert.ok(p.sent.some(m => m.type === 'CANCEL'));
});

test('close cancels and late callbacks do not recreate the panel', () => {
  const p = page();
  p.all().find(n => n.tag === 'button' && n.textContent === 'Close').listeners.click();
  p.callbacks[0](result);
  assert.equal(p.document.getElementById('gold-miner-root'), undefined);
});

test('navigation away invalidates pending task and duplicate events do not refetch', () => {
  const p = page();
  p.events['turbo:load'](); p.events['turbo:render']();
  assert.equal(p.callbacks.length, 1);
  p.location.href = 'https://github.com/settings/profile'; p.location.pathname = '/settings/profile';
  p.events.poll(); p.callbacks[0](result);
  assert.equal(p.document.getElementById('gold-miner-root'), undefined);
  assert.ok(p.sent.some(m => m.type === 'CANCEL'));
});

test('display derives safe links and feedback immediately hides the item', () => {
  const p = page(); p.callbacks[0](result);
  assert.equal(p.all().find(n => n.tag === 'a').href, 'https://github.com/safe/repo');
  p.all().find(n => n.tag === 'button' && n.textContent === 'Irrelevant').listeners.click();
  assert.equal(p.all().filter(n => n.tag === 'a').length, 0);
});

test('README changes alter contentVersion and refresh the task', () => {
  const p = page();
  const version = p.sent.find(m => m.type === 'SEARCH').contentVersion;
  p.document.readme = 'changed-readme-v2'; p.events['turbo:render']();
  const searches = p.sent.filter(m => m.type === 'SEARCH');
  assert.equal(searches.length, 2);
  assert.notEqual(searches[1].contentVersion, version);
});


test('failed feedback preserves candidate and a successful retry removes it', () => {
  const p = page('bad_response'); p.callbacks[0](result);
  const button = p.all().find(n => n.tag === 'button' && n.textContent === 'Seen');
  button.listeners.click();
  assert.equal(p.all().filter(n => n.tag === 'a').length,1);
  assert.equal(button.disabled,false);
  assert.match(p.body.textContent,/Feedback was not saved/);
  p.setFeedbackResponse('ok');button.listeners.click();
  assert.equal(p.all().filter(n => n.tag === 'a').length,0);
});

// --- S5 regressions: the panel was invisible until the page bottom ---

test('panel mounts at the top of the content host, not appended after the results', () => {
  page.withMain = 'js-pjax-container';
  const p = page();
  const root = p.document.getElementById('gold-miner-root');
  assert.ok(root, 'panel was not created');
  assert.equal(root.getAttribute('data-gm-mount'), 'inline');
  const main = p.all().find(n => n.tag === 'main');
  assert.equal(main.children[0], root, 'panel must be the first child so it is above the fold');
});

test('panel falls back to a visible floating mount when no content anchor exists', () => {
  page.withMain = null;
  const p = page();
  const root = p.document.getElementById('gold-miner-root');
  assert.ok(root);
  assert.equal(root.getAttribute('data-gm-mount'), 'floating');
  assert.equal(root.className, 'gm-floating');
});

test('a truncated model reply is shown as truncated, not as a generic model failure', () => {
  const p = page();
  p.callbacks[0]({code: 'model_output_truncated', candidates: [], hasModel: false});
  assert.match(p.body.textContent, /truncated at max_tokens/);
  assert.doesNotMatch(p.body.textContent, /Model unavailable/);
});
