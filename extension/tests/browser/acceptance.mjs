import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'gold-miner-browser-'));
const ext = path.join(tmp, 'extension');
const results = [];
const contexts = [];
const errors = [];
const productionHashes = {};
async function check(name, fn) {
  await fn(); results.push({name, status:'passed', evidence_kind:'chromium-with-fixture-network'});
}
try {
  await fs.cp(path.join(root, 'extension'), ext, {recursive:true, filter: source => !source.includes(path.sep + 'tests')});
  for (const name of ['src/background.js','src/shared.js','src/content.js','src/options.js']) {
    const source = await fs.readFile(path.join(root,'extension',name));
    assert.deepEqual(await fs.readFile(path.join(ext,name)), source);
    productionHashes[name] = crypto.createHash('sha256').update(source).digest('hex');
  }
  await fs.copyFile(path.join(here,'fixture-network.js'), path.join(ext,'src/fixture-network.js'));
  await fs.copyFile(path.join(here,'storage-probe.js'), path.join(ext,'src/storage-probe.js'));
  await fs.writeFile(path.join(ext,'src/fixture-bootstrap.js'), "importScripts('fixture-network.js', 'background.js');\n");
  const manifest = JSON.parse(await fs.readFile(path.join(ext,'manifest.json')));
  manifest.background.service_worker = 'src/fixture-bootstrap.js';
  manifest.content_scripts[0].js.push('src/storage-probe.js');
  await fs.writeFile(path.join(ext,'manifest.json'), JSON.stringify(manifest));

  async function launch(label) {
    const context = await chromium.launchPersistentContext(path.join(tmp,label), {
      channel:'chromium', headless:process.env.GM_BROWSER_HEADLESS === '1',
      args:[`--disable-extensions-except=${ext}`, `--load-extension=${ext}`]
    });
    contexts.push(context);
    await context.route('https://github.com/**', r => {
      const url = r.request().url();
      if (url.includes('long-results')) {
        // S5: a realistic long result page, tall enough that a panel appended
        // at the very end would sit far below the fold.
        const rows = Array.from({length: 40}, (_, i) =>
          `<li class="fixture-row"><a href="/fixture/repo-${i}">fixture/repo-${i}</a></li>`).join('');
        return r.fulfill({contentType:'text/html', body:
          `<!doctype html><html><body><header>nav</header><main><h1>results</h1><ul>${rows}</ul></main></body></html>`});
      }
      return r.fulfill({contentType:'text/html',
        body:'<!doctype html><html><body><main><article class="markdown-body">Fixture README v1</article></main></body></html>'});
    });
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    const id = new URL(worker.url()).host;
    const options = await context.newPage();
    options.on('pageerror', e => errors.push(e.message));
    await options.goto(`chrome-extension://${id}/src/options.html`);
    await options.waitForFunction(() => typeof chrome?.runtime?.sendMessage === 'function');
    const publicReply = await options.evaluate(() => chrome.runtime.sendMessage({type:'GET_PUBLIC_SETTINGS'}));
    assert.equal(publicReply.code, 'ok', 'options context must reach worker');
    return {context, worker, options};
  }
  async function calls(worker) { return worker.evaluate(() => globalThis.__fixtureCalls.length); }
  const a = await launch('profile-a');
  const page = await a.context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  await check('options-save-and-language', async () => {
    await a.options.selectOption('#readingLang','en');
    await a.options.fill('#interests','clipboard, rss');
    await a.options.click('#save');
    await a.options.waitForFunction(() => document.querySelector('#status').textContent.length > 0);
    assert((await a.options.locator('#status').textContent()).includes('已保存'), 'settings UI response: ' + await a.options.locator('#status').textContent());
    const state = await a.worker.evaluate(() => chrome.storage.local.get(['readingLang','interests']));
    assert.equal(state.readingLang,'en'); assert.deepEqual(state.interests,['clipboard','rss']);
  });
  await check('search-real-content-and-canonical-links', async () => {
    await page.goto('https://github.com/search?q=clipboard&type=repositories');
    await page.locator('#gold-miner-root a').first().waitFor();
    const hrefs = await page.locator('#gold-miner-root a').evaluateAll(xs => xs.map(x => x.href));
    assert(hrefs.includes('https://github.com/fixture/clipboard'));
    assert(hrefs.every(x => /^https:\/\/github.com\/[^/]+\/[^/]+$/.test(x)));
    assert((await calls(a.worker)) > 0);
  });
  await check('actual-storage-isolation-and-message-boundary', async () => {
    await page.waitForFunction(() => document.documentElement.dataset.gmStorageProbe);
    assert.equal(await page.getAttribute('html','data-gm-storage-probe'),'denied');
    await page.waitForFunction(() => document.documentElement.dataset.gmPrivilegeProbe);
    assert.equal(await page.getAttribute('html','data-gm-privilege-probe'),'untrusted_input');
  });
  await check('feedback-removes-seen-candidate', async () => {
    const li = page.locator('#gold-miner-root li').filter({hasText:'fixture/clipboard'});
    await li.getByRole('button',{name:'Seen', exact:true}).click();
    await li.waitFor({state:'detached'});
    const state = await a.worker.evaluate(() => chrome.storage.local.get('seen'));
    assert(state.seen.includes('fixture/clipboard'));
  });
  await check('export-ui-no-secrets', async () => {
    await a.worker.evaluate(() => chrome.storage.local.set({byok:{apiKey:'fixture-secret-only',baseUrl:'',model:''}}));
    const downloaded = a.options.waitForEvent('download');
    await a.options.click('#export');
    const download = await downloaded;
    await download.saveAs(path.join(tmp,'cache.json'));
    const text = await fs.readFile(path.join(tmp,'cache.json'),'utf8');
    assert(!text.includes('fixture-secret-only')); assert(!text.includes('apiKey'));
    assert(JSON.parse(text).entries.length > 0);
  });
  const b = await launch('profile-b');
  await check('second-profile-import-and-cache-reuse', async () => {
    await b.options.selectOption('#readingLang','en'); await b.options.click('#save');
    await b.options.waitForFunction(() => document.querySelector('#status').textContent.includes('已保存'));
    await b.options.setInputFiles('#importFile',path.join(tmp,'cache.json'));
    await b.options.waitForFunction(() => document.querySelector('#status').textContent.includes('Imported entries'));
    const other = await b.context.newPage();
    await other.goto('https://github.com/search?q=clipboard&type=repositories');
    await other.locator('#gold-miner-root a').first().waitFor();
    assert.equal(await calls(b.worker),0);
    await other.evaluate(() => {
      document.querySelector('article').textContent = 'Fixture README v2 changed';
      document.dispatchEvent(new Event('pjax:end'));
    });
    await other.waitForFunction(() => document.querySelector('#gold-miner-root a'));
    assert((await calls(b.worker)) > 0, 'changed content must refetch');
  });
  await check('cancel-and-close-do-not-resurrect', async () => {
    await a.worker.evaluate(() => {globalThis.__fixtureDelay = 1500;});
    await page.goto('https://github.com/search?q=cancel-fixture');
    await page.locator('#gold-miner-root').getByRole('button',{name:'Cancel',exact:true}).click();
    await page.waitForTimeout(1800);
    assert.equal(await page.locator('#gold-miner-root a').count(),0);
    await page.locator('#gold-miner-root header button').click();
    await page.waitForTimeout(600);
    assert.equal(await page.locator('#gold-miner-root').count(),0);
    const cache = await a.worker.evaluate(() => chrome.storage.local.get('cache'));
    assert(!Object.values(cache.cache).some(x => x.query === 'cancel-fixture'));
    await a.worker.evaluate(() => {globalThis.__fixtureDelay = 0;});
  });
  await check('repository-explore-and-page-world-navigation', async () => {
    await page.goto('https://github.com/fixture/start');
    await page.locator('#gold-miner-root a').first().waitFor();
    await page.evaluate(() => history.pushState({},'', '/settings/profile'));
    await page.locator('#gold-miner-root').waitFor({state:'detached'});
  });
  await check('concurrent-feedback-import-and-clear-ordering', async () => {
    const reply = await a.options.evaluate(async () => {
      const send = message => chrome.runtime.sendMessage(message);
      const feedback = await Promise.all([
        send({type:'FEEDBACK',repo:'fixture/one',action:'seen'}),
        send({type:'FEEDBACK',repo:'fixture/two',action:'irrelevant'})
      ]);
      const state = await chrome.storage.local.get(['seen','feedback']);
      const base = {format:'gold-miner-cache-v1',entries:[]};
      const imported = await Promise.all(['fixture-import-one','fixture-import-two'].map(query =>
        send({type:'IMPORT_CACHE',bundle:{...base,entries:[{pageKind:'SEARCH',query,language:'en',
          content_version:'fixture-import-v1',processing_mode:'rules',created_at:new Date().toISOString(),rawCandidates:[]}]}})));
      const cache = await chrome.storage.local.get('cache');
      await Promise.all([send({type:'FEEDBACK',repo:'fixture/late',action:'seen'}),send({type:'CLEAR_LOCAL'})]);
      const cleared = await chrome.storage.local.get(['seen','feedback','cache','pageHistory']);
      return {feedback,state,imported,queries:Object.values(cache.cache).map(x=>x.query),cleared};
    });
    assert(reply.feedback.every(x=>x.code==='ok'));
    assert(reply.state.seen.includes('fixture/one') && reply.state.seen.includes('fixture/two'));
    assert(reply.imported.every(x=>x.code==='ok'));
    assert(reply.queries.includes('fixture-import-one') && reply.queries.includes('fixture-import-two'));
    assert.deepEqual(reply.cleared,{seen:[],feedback:{},cache:{},pageHistory:[]});
  });
  await check('panel-is-visible-without-scrolling-on-a-long-results-page', async () => {
    const long = await a.context.newPage();
    await long.goto('https://github.com/search?q=long-results&type=repositories');
    await long.locator('#gold-miner-root').waitFor();
    // S5: the panel used to be appended last, so it only appeared at the very
    // bottom of a 36-result page and read as "the feature does not exist".
    const box = await long.locator('#gold-miner-root').boundingBox();
    assert(box, 'panel has no layout box');
    const viewport = long.viewportSize() || {width:1280, height:720};
    assert(box.y < viewport.height, `panel starts at y=${box.y}, below the ${viewport.height}px fold`);
    const scrollY = await long.evaluate(() => window.scrollY);
    assert.equal(scrollY, 0, 'the check must hold without scrolling');
    await long.locator('#gold-miner-root a').first().waitFor();
    await long.close();
  });
  await check('probe-reads-the-input-box-not-stale-storage', async () => {
    // S1: storage holds a plausible config while the visible input does not.
    // The old probe read storage, so a wrong host still showed a green light.
    await a.worker.evaluate(() => chrome.storage.local.set({byok:{
      baseUrl:'https://api.minimaxi.com/v1', model:'MiniMax-M3', apiKey:'fixture-key-not-real'}}));
    await a.options.fill('#baseUrl', 'not-a-valid-endpoint');
    await a.options.fill('#model', 'MiniMax-M3');
    await a.options.fill('#apiKey', 'fixture-key-not-real');
    await a.options.click('#probe');
    await a.options.waitForFunction(() => document.querySelector('#status').textContent.length > 0);
    const status = await a.options.locator('#status').textContent();
    assert(status.includes('invalid_endpoint'),
      'probe ignored the visible input and reported: ' + status);
  });
  await check('editing-byok-clears-a-stale-success-light', async () => {
    // S1: a green light that survives an edit is a false success.
    await a.options.evaluate(() => {document.querySelector('#status').textContent = 'http 200 ok (api.minimaxi.com)';});
    await a.options.fill('#model', 'MiniMax-M3-changed');
    await a.options.waitForFunction(() =>
      !document.querySelector('#status').textContent.includes('http 200 ok'));
    const status = await a.options.locator('#status').textContent();
    assert(status.includes('重新探测') || status.includes('re-probe'), 'stale light survived an edit: ' + status);
  });
  assert.deepEqual(errors, [], 'no unhandled options/content errors');} catch(error) {
  results.push({name:'acceptance',status:'failed',message:error.stack});
  process.exitCode = 1;
} finally {
  for (const context of contexts) await context.close();
  const report = {evidence_kind:'chromium-with-fixture-network', paid_model_requests:0,
    live_github_requests:0, human_installation:'not-run', production_sha:process.env.GITHUB_SHA || null,
    production_files_sha256:productionHashes, results};
  await fs.writeFile(path.join(here,'browser-results.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
  await fs.rm(tmp,{recursive:true,force:true});
}
