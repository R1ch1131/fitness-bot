import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync(new URL('./FitPulse Weight.js', import.meta.url), 'utf8');
const snapshot = {status:'ok',source:'apple_health',current_weight:94.9,start_weight:103,goal_weight:80,lost_kg:8.1,remaining_kg:14.9,progress_percent:35.2,measured_on:'2026-10-26'};
const keyName='fitpulse.weight.health-token.v1', cachePath='/library/fitpulse-weight-v1.json';
async function run({ token='test-health-token-not-a-real-secret', cached=null, status=200, body=snapshot, fail=false, small=false, inApp=false, enteredToken='' }={}) {
  const keys=new Map(token?[[keyName,token]]:[]), files=new Map(cached?[[cachePath,JSON.stringify({data:cached,savedAt:Date.now()})]]:[]);
  const texts=[],requests=[],draws=[];let widget,alerts=0,complete=false;
  class Stack {addText(value){const t={value};texts.push(t);return t;} addSpacer(){} addImage(){return {};} addStack(){return new Stack();} centerAlignContent(){} layoutVertically(){} setPadding(){} async presentMedium(){} }
  class Drawing {setFillColor(){} fillRect(rect){draws.push(rect);} getImage(){return {};}}
  class Request {constructor(url){this.url=url;requests.push(this);} async loadString(){this.response={statusCode:status};if(fail)throw Error('offline');return JSON.stringify(body);}}
  class Alert {constructor(){alerts++; if(!inApp)throw Error('Widget must never prompt');} addAction(){} addCancelAction(){} addDestructiveAction(){} addSecureTextField(){} textFieldValue(){return enteredToken;} async presentAlert(){return 0;} async presentSheet(){return 0;} }
  const fileApi={joinPath:(a,b)=>a+'/'+b,libraryDirectory:()=>'/library',fileExists:p=>files.has(p),remove:p=>files.delete(p),readString:p=>files.get(p),writeString:(p,v)=>files.set(p,v)};
  const sandbox={config:{runsInApp:inApp,widgetFamily:small?'small':'medium'},FileManager:{local:()=>fileApi},Keychain:{contains:k=>keys.has(k),get:k=>keys.get(k),set:(k,v)=>keys.set(k,v),remove:k=>keys.delete(k)},ListWidget:Stack,DrawContext:Drawing,Size:class{constructor(w,h){this.width=w;this.height=h;}},Rect:class{constructor(x,y,w,h){this.x=x;this.y=y;this.width=w;this.height=h;}},Color:class{},Font:{systemFont:s=>s,boldSystemFont:s=>s},URLScheme:{forRunningScript:()=> 'scriptable:///run/FitPulse'},Alert,Request,Script:{setWidget:w=>widget=w,complete:()=>complete=true}};
  await vm.runInNewContext('(async()=>{'+source+'})()',sandbox);
  return {texts,requests,draws,widget,alerts,complete,keys,files};
}
test('fresh widget displays measured weight and progress; token only goes to own endpoint header',async()=>{
  const r=await run(); assert.ok(r.complete);assert.ok(r.texts.some(t=>t.value==='94,9 кг'));assert.ok(r.texts.some(t=>t.value==='35,2%'));assert.ok(r.texts.some(t=>t.value==='Осталось 14,9 кг'));
  assert.equal(r.requests.length,1);assert.equal(r.requests[0].url,'https://fitness-bot-9f8m.onrender.com/api/widgets/weight');assert.ok(r.requests[0].headers.Authorization.startsWith('Bearer '));assert.equal(r.requests[0].onRedirect(),null);assert.ok(r.files.has(cachePath));assert.equal(r.alerts,0);
});
test('offline widget keeps last saved reading with a visible warning',async()=>{
  const r=await run({fail:true,cached:snapshot});assert.ok(r.texts.some(t=>t.value==='94,9 кг'));assert.ok(r.texts.some(t=>t.value.includes('Нет связи')));
});
test('authentication error never reveals a previous cached weight',async()=>{
  for(const fail of [false,true]) {const r=await run({status:401,fail,cached:snapshot});assert.equal(r.files.has(cachePath),false);assert.ok(!r.texts.some(t=>t.value.includes('94,9')));}
});
test('missing key or missing records never show invented weights',async()=>{
  const missing=await run({token:null});assert.equal(missing.requests.length,0);assert.ok(missing.texts.some(t=>t.value.includes('введи ключ')));
  const empty=await run({body:{status:'empty',source:'apple_health',goal_weight:80,current_weight:null}});assert.ok(empty.texts.some(t=>t.value.includes('Пока нет веса')));assert.ok(!empty.texts.some(t=>t.value.includes('94,9')));
});
test('small widget includes progress and remaining kilos without prompting',async()=>{
  const r=await run({small:true});assert.ok(r.texts.some(t=>t.value==='35,2% · осталось 14,9 кг'));assert.equal(r.alerts,0);
});
test('first manual setup accepts Bearer prefix and stores the secret separately from script/cache',async()=>{
  const secret='a-test-key-longer-than-thirty-two-characters';const r=await run({token:null,inApp:true,enteredToken:'Bearer '+secret});assert.equal(r.keys.get(keyName),secret);assert.ok(!r.files.get(cachePath).includes(secret));assert.ok(!source.includes(secret));
});
