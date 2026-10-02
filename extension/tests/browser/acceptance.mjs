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
  await fs.cp(path.join(root, 'extension'), ext, {recursive:true});
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
    await context.route('https://github.com/**', r => r.fulfill({contentType:'text/html',
      body:'<!doctype html><html><body><main><article class="markdown-body">Fixture README v1</article></main></body></html>'}));
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
    const id = new URL(worker.url()).host;
    const options = await context.newPage();
    options.on('pageerror', e => errors.push(e.message));
    await options.goto(`chrome-extension://${id}/src/options.html`);
    await options.waitForFunction(() => typeof chrome?.runtime?.sendMessage === 'function');
    await options.evaluate(() => chrome.runtime.sendMessage({type:'GET_PUBLIC_SETTINGS'}));
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
    await a.options.waitForFunction(() => document.querySelector('#status').textContent.includes('已保存'));
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
  assert.deepEqual(errors, [], 'no unhandled options/content errors');
} catch(error) {
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
