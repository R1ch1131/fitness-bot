import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync(new URL('./FitPulse Weight.js', import.meta.url), 'utf8');
const overviewSource = readFileSync(new URL('./FitPulse Overview.js', import.meta.url), 'utf8');
const snapshot = {status:'ok',source:'apple_health',current_weight:94.9,start_weight:103,goal_weight:80,lost_kg:8.1,remaining_kg:14.9,progress_percent:35.2,measured_on:'2026-10-26'};
const keyName='fitpulse.weight.health-token.v1', cachePath='/library/fitpulse-weight-v1.json';
async function run({ token='test-health-token-not-a-real-secret', cached=null, status=200, body=snapshot, fail=false, small=false, inApp=false, enteredToken='', overview=false, responses=null, refresh=false }={}) {
  const selectedCache = overview ? '/library/fitpulse-overview-v1.json' : cachePath;
  const keys=new Map(token?[[keyName,token]]:[]), files=new Map(cached?[[selectedCache,JSON.stringify({data:cached,savedAt:Date.now()})]]:[]);
  const texts=[],requests=[],draws=[],dates=[];let widget,alerts=0,complete=false;
  class Stack {addText(value){const t={value};texts.push(t);return t;} addDate(value){const d={value,applyRelativeStyle(){this.relative=true;}};dates.push(d);return d;} addSpacer(){} addImage(){return {};} addStack(){return new Stack();} centerAlignContent(){} layoutVertically(){} setPadding(){} async presentMedium(){} }
  class Drawing {setFillColor(){} fillRect(rect){draws.push(rect);} getImage(){return {};}}
  class Request {constructor(url){this.url=url;requests.push(this);} async loadString(){const result=responses ? responses[Math.min(requests.indexOf(this),responses.length-1)] : {status,body,fail};this.response={statusCode:result.status};if(result.fail)throw Error('offline');return JSON.stringify(result.body);}}
  class Alert {constructor(){alerts++; if(!inApp)throw Error('Widget must never prompt');} addAction(){} addCancelAction(){} addDestructiveAction(){} addSecureTextField(){} textFieldValue(){return enteredToken;} async presentAlert(){return 0;} async presentSheet(){return 0;} }
  const fileApi={joinPath:(a,b)=>a+'/'+b,libraryDirectory:()=>'/library',fileExists:p=>files.has(p),remove:p=>files.delete(p),readString:p=>files.get(p),writeString:(p,v)=>files.set(p,v)};
  const sandbox={args:{queryParameters:refresh?{refresh:'1'}:{}},config:{runsInApp:inApp,widgetFamily:small?'small':'medium'},FileManager:{local:()=>fileApi},Keychain:{contains:k=>keys.has(k),get:k=>keys.get(k),set:(k,v)=>keys.set(k,v),remove:k=>keys.delete(k)},ListWidget:Stack,DrawContext:Drawing,Size:class{constructor(w,h){this.width=w;this.height=h;}},Rect:class{constructor(x,y,w,h){this.x=x;this.y=y;this.width=w;this.height=h;}},Color:class{},Font:{systemFont:s=>s,boldSystemFont:s=>s},URLScheme:{forRunningScript:()=> 'scriptable:///run/FitPulse'},Alert,Request,Script:{setWidget:w=>widget=w,complete:()=>complete=true}};
  await vm.runInNewContext('(async()=>{'+(overview?overviewSource:source)+'})()',sandbox);
  return {texts,requests,draws,dates,widget,alerts,complete,keys,files};
}
test('fresh widget displays measured weight and progress; token only goes to own endpoint header',async()=>{
  const r=await run(); assert.ok(r.complete);assert.ok(r.texts.some(t=>t.value==='94,9 кг'));assert.ok(r.texts.some(t=>t.value==='35,2%'));assert.ok(r.texts.some(t=>t.value==='Осталось 14,9 кг'));
  assert.equal(r.requests.length,1);assert.equal(new URL(r.requests[0].url).pathname,'/api/widgets/weight');assert.ok(new URL(r.requests[0].url).searchParams.has('t')); assert.ok(r.requests[0].headers.Authorization.startsWith('Bearer '));assert.equal(r.requests[0].onRedirect(),null);assert.ok(r.files.has(cachePath));assert.equal(r.alerts,0);
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

const overviewSnapshot = {...snapshot, as_of:'2026-11-06T16:15:00+06:00',notifications:[
  {id:'3',title:'Третий push',body:'Последняя отправка',url:'/?tab=weekly',sent_at:'2026-11-06T16:10:00+06:00'},
  {id:'2',title:'Второй push',body:'Проверка питания',url:'/?tab=dashboard',sent_at:'2026-11-06T15:00:00+06:00'},
  {id:'1',title:'Первый push',body:'Вещи в зал',url:'/?tab=workouts',sent_at:'2026-11-06T13:00:00+06:00'}]};
test('medium overview displays weight, all three sends, relative freshness timer and 5-minute request',async()=>{
  const before=Date.now(),r=await run({overview:true,body:overviewSnapshot});
  for(const name of ['94,9 кг','Третий push','Второй push','Первый push'])assert.ok(r.texts.some(t=>t.value===name));
  assert.ok(r.texts.some(t=>t.value.startsWith('Данные обновлены ')));assert.ok(r.dates.some(d=>d.relative));
  assert.ok(r.widget.refreshAfterDate.getTime()>=before+5*60000);
  assert.equal(new URL(r.requests[0].url).pathname,'/api/widgets/overview');
  assert.ok(r.files.has('/library/fitpulse-overview-v1.json'));assert.ok(!r.files.has(cachePath));
});
test('overview offline keeps notifications and visibly marks cached data; 401 never reveals cache',async()=>{
  const offline=await run({overview:true,cached:overviewSnapshot,fail:true});
  assert.ok(offline.texts.some(t=>t.value==='Третий push'));assert.ok(offline.texts.some(t=>t.value.startsWith('Нет связи')));
  const denied=await run({overview:true,cached:overviewSnapshot,status:401});
  assert.ok(!denied.texts.some(t=>t.value==='Третий push'));assert.ok(!denied.files.has('/library/fitpulse-overview-v1.json'));
});
test('overview still displays notifications when weight has not been imported',async()=>{
  const r=await run({overview:true,body:{...overviewSnapshot,status:'empty',current_weight:null}});
  assert.ok(r.texts.some(t=>t.value==='Нет замера'));assert.ok(r.texts.some(t=>t.value==='Третий push'));
});
test('overview small family explains selecting the rectangular medium size',async()=>{
  const r=await run({overview:true,small:true,body:overviewSnapshot});assert.ok(r.texts.some(t=>t.value.includes('средний прямоугольный размер')));
});
test('overview empty history is explained instead of fabricating past sends',async()=>{
  const r=await run({overview:true,body:{...overviewSnapshot,notifications:[]}});assert.ok(r.texts.some(t=>t.value.includes('после обновления сервера')));
});

test('transient failure retries once and uses fresh notifications instead of stale cache',async()=>{
  const fresh={...overviewSnapshot,notifications:[{...overviewSnapshot.notifications[0],title:'Свежая отправка'}]};
  const r=await run({overview:true,cached:overviewSnapshot,responses:[{status:503,body:{}},{status:200,body:fresh}]});
  assert.equal(r.requests.length,2);assert.equal(r.requests[1].timeoutInterval,5);
  assert.ok(r.texts.some(t=>t.value==='Свежая отправка'));assert.ok(!r.texts.some(t=>t.value.startsWith('Нет связи')));
  assert.equal(r.requests[0].headers['Cache-Control'],'no-cache');
});
test('refresh link skips the menu and makes a new request in Scriptable',async()=>{
  const r=await run({overview:true,inApp:true,refresh:true,body:overviewSnapshot});
  assert.equal(r.alerts,0);assert.equal(r.requests.length,1);
  assert.ok(r.texts.some(t=>t.value==='↻' && t.url.endsWith('refresh=1')));
});
test('offline relative date stays anchored to old saved data rather than pretending it is new',async()=>{
  const r=await run({overview:true,cached:overviewSnapshot,fail:true});
  assert.equal(r.requests.length,2);assert.ok(r.dates[0].relative);
  assert.ok(r.texts.some(t=>t.value.startsWith('Нет связи · сохранено')));
});
