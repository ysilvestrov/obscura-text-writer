import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2]||process.cwd();
const noop=()=>{};
globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener:noop,createElement:()=>({})};
globalThis.localStorage={getItem:()=>null,setItem:noop};
globalThis.sessionStorage=globalThis.localStorage;
const {api,APIError}=await import(pathToFileURL(root+'/src/storygen/web/static/api.js').href);
let calls=[],gate=null,status=200,body={items:[1,2],nested:{a:1}};
globalThis.fetch=async(url,options={})=>{
  calls.push({url,options});
  if(gate)await gate;
  return{ok:status<400,status,json:async()=>structuredClone(status<400?body:{detail:'boom',extra:{k:1}})};
};
const reset=()=>{calls=[];gate=null;status=200};
const hold=()=>{let release;gate=new Promise(r=>{release=r});return release};

// 1. concurrent GET shares one fetch, separate copies
{reset();const release=hold();const a=api('/x'),b=api('/x');release();const [ra,rb]=await Promise.all([a,b]);
 assert.equal(calls.length,1);assert.deepEqual(ra,rb);assert.notEqual(ra,rb);
 ra.items.push(9);ra.nested.a=7;assert.deepEqual(rb,{items:[1,2],nested:{a:1}});}
// 2. sequential GET is not cached
{reset();await api('/x');await api('/x');assert.equal(calls.length,2);}
// 3. concurrent POST are not shared
{reset();const release=hold();const a=api('/x',{method:'POST',body:'{}'}),b=api('/x',{method:'POST',body:'{}'});release();await Promise.all([a,b]);assert.equal(calls.length,2);}
// 4. signal requests are not shared; aborting one does not reject the other
{reset();const release=hold();const ctl=new AbortController();
 const withSignal=api('/x',{signal:ctl.signal}),plain=api('/x');
 assert.equal(calls.length,2);
 assert.equal(calls[0].options.signal,ctl.signal);
 release();const [r1,r2]=await Promise.all([withSignal,plain]);assert.deepEqual(r2,body);assert.deepEqual(r1,body);
 // abort of signalled request while plain pending
 reset();let rel2;gate=new Promise(r=>{rel2=r});
 globalThis.fetch=async(url,options={})=>{calls.push({url,options});if(options.signal){return new Promise((_,rej)=>options.signal.addEventListener('abort',()=>rej(new Error('aborted'))))}await gate;return{ok:true,status:200,json:async()=>structuredClone(body)}};
 const c2=new AbortController();const s=api('/y',{signal:c2.signal}),p=api('/y');c2.abort();
 await assert.rejects(s,/aborted/);rel2();assert.deepEqual(await p,body);}
// 5. error: both callers get APIError with same status, own data; next call fetches again
{globalThis.fetch=async(url,options={})=>{calls.push({url,options});if(gate)await gate;return{ok:false,status:500,json:async()=>structuredClone({detail:'boom',extra:{k:1}})}};
 reset();const release=hold();const a=api('/e'),b=api('/e');release();
 const [ea,eb]=await Promise.all([a.catch(e=>e),b.catch(e=>e)]);
 assert.equal(calls.length,1);
 for(const e of [ea,eb]){assert.ok(e instanceof APIError);assert.equal(e.status,500);assert.equal(e.message,'boom');}
 assert.notEqual(ea,eb);assert.notEqual(ea.data,eb.data);ea.data.extra.k=2;assert.equal(eb.data.extra.k,1);
 await api('/e').catch(()=>{});assert.equal(calls.length,2);}
console.log('ok');
