import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
function options(fetchImpl) {
  const ids=['status','form','readingLang','interests','personalization','historyEnabled','baseUrl','model','apiKey','clear','export','importBtn','importFile','probe'];
  const els=Object.fromEntries(ids.map(id=>[id,{value:'',textContent:'',listeners:{},addEventListener(e,f){this.listeners[e]=f;}}]));
  const calls=[];
  const ctx={document:{getElementById:id=>els[id]},chrome:{storage:{local:{get:async()=>({readingLang:'en',byok:{baseUrl:'https://saved.example/v1',model:'saved',apiKey:'fixture-saved'}})}},permissions:{request:async()=>true},runtime:{sendMessage:(m,cb)=>{calls.push(m);cb?.({code:'ok'});}}},URL,AbortController,setTimeout,clearTimeout,fetch:fetchImpl};
  ctx.globalThis=ctx;
  for(const file of ['shared.js','options.js'])vm.runInNewContext(fs.readFileSync(new URL('../src/'+file,import.meta.url),'utf8'),ctx);
  return {els,calls};
}
const response=(content,finish_reason='stop',status=200)=>({status,json:async()=>({choices:[{message:{content},finish_reason}]})});
test('probe uses unsaved inputs, validates final answer and does not save credentials',async()=>{
  let request;const p=options(async(url,args)=>{request={url,args};return response('<think>{wrong}</think>pong');});
  await new Promise(setImmediate);Object.assign(p.els.baseUrl,{value:'https://current.example/v1'});p.els.model.value='current';p.els.apiKey.value='fixture-current';
  await p.els.probe.listeners.click();
  assert.equal(request.url,'https://current.example/v1/chat/completions');
  assert.equal(JSON.parse(request.args.body).max_tokens,2048);assert.equal(JSON.parse(request.args.body).model,'current');
  assert.match(p.els.status.textContent,/http 200 ok.*current.example/);assert(!p.calls.some(c=>c.type==='SAVE_SETTINGS'));
  p.els.model.listeners.input();assert.match(p.els.status.textContent,/not been tested/);
});
test('editing inputs prevents an old in-flight probe from restoring success',async()=>{
  let resolve;const p=options(()=>new Promise(r=>resolve=r));await new Promise(setImmediate);
  const task=p.els.probe.listeners.click();await new Promise(setImmediate);await new Promise(setImmediate);
  p.els.baseUrl.value='https://changed.example/v1';p.els.baseUrl.listeners.input();
  resolve(response('pong'));await task;assert.match(p.els.status.textContent,/not been tested/);
});
test('200 thinking-only and truncated responses never report ok; auth shows region hint',async()=>{
  for(const [resp,expected] of [[response('<think>still thinking'),/empty_model_output/],[response('pong','length'),/model_output_truncated/],[response('no','stop',401),/auth_rejected.*平台区域/]]){
    const p=options(async()=>resp);await new Promise(setImmediate);p.els.baseUrl.value='https://api.minimaxi.com/v1';await p.els.probe.listeners.click();assert.match(p.els.status.textContent,expected);assert(!p.els.status.textContent.includes('fixture-saved'));
  }
});
