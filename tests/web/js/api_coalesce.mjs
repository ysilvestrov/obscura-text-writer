import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2]||process.cwd();
const noop=()=>{};
globalThis.document={querySelector:()=>null,querySelectorAll:()=>[],addEventListener:noop,createElement:()=>({})};
globalThis.localStorage={getItem:()=>null,setItem:noop};
globalThis.sessionStorage=globalThis.localStorage;
const {api,APIError}=await import(pathToFileURL(root+'/src/storygen/web/static/api.js').href);
const realFetch=globalThis.fetch;
const body={items:[1,2],nested:{a:1}};
let calls=[];
const gates=[];
// each fetch waits for its own gate so the test controls completion order
function install(impl){calls=[];gates.length=0;globalThis.fetch=impl||(async(url,options={})=>{calls.push({url,options});await new Promise(r=>gates.push(r));return{ok:true,status:200,json:async()=>structuredClone(body)}})}
const flush=()=>new Promise(r=>setImmediate(r));
const releaseAll=async()=>{await flush();while(gates.length)gates.shift()();await flush()};
async function scenario(name,fn){install();try{await fn()}finally{globalThis.fetch=realFetch}}

await scenario('shared+copies',async()=>{const a=api('/x'),b=api('/x');await releaseAll();const [ra,rb]=await Promise.all([a,b]);
 assert.equal(calls.length,1);assert.deepEqual(ra,rb);assert.notEqual(ra,rb);
 ra.items.push(9);ra.nested.a=7;assert.deepEqual(rb,{items:[1,2],nested:{a:1}});});
await scenario('sequential',async()=>{const a=api('/x');await releaseAll();await a;const b=api('/x');await releaseAll();await b;assert.equal(calls.length,2);});
await scenario('post',async()=>{const a=api('/x',{method:'POST',body:'{}'}),b=api('/x',{method:'POST',body:'{}'});await releaseAll();await Promise.all([a,b]);assert.equal(calls.length,2);});
await scenario('lowercase get and null options',async()=>{const a=api('/l',{method:'get'}),b=api('/l',null),c=api('/l');await releaseAll();await Promise.all([a,b,c]);assert.equal(calls.length,1);});
await scenario('signal',async()=>{const ctl=new AbortController();
 const withSignal=api('/x',{signal:ctl.signal}),plain=api('/x');await flush();
 assert.equal(calls.length,2);assert.equal(calls[0].options.signal,ctl.signal);
 await releaseAll();assert.deepEqual(await withSignal,body);assert.deepEqual(await plain,body);});
await scenario('abort one does not reject other',async()=>{
 let release;const gate=new Promise(r=>{release=r});
 install(async(url,options={})=>{calls.push({url,options});if(options.signal)return new Promise((_,rej)=>options.signal.addEventListener('abort',()=>rej(new Error('aborted'))));await gate;return{ok:true,status:200,json:async()=>structuredClone(body)}});
 const c=new AbortController();const s=api('/y',{signal:c.signal}),p=api('/y');c.abort();
 await assert.rejects(s,/aborted/);release();assert.deepEqual(await p,body);});
await scenario('error',async()=>{
 install(async(url,options={})=>{calls.push({url,options});await new Promise(r=>gates.push(r));return{ok:false,status:500,json:async()=>structuredClone({detail:'boom',extra:{k:1}})}});
 const a=api('/e').catch(e=>e),b=api('/e').catch(e=>e);await releaseAll();
 const [ea,eb]=await Promise.all([a,b]);
 assert.equal(calls.length,1);
 for(const e of [ea,eb]){assert.ok(e instanceof APIError);assert.equal(e.status,500);assert.equal(e.message,'boom');}
 assert.notEqual(ea,eb);assert.notEqual(ea.data,eb.data);ea.data.extra.k=2;assert.equal(eb.data.extra.k,1);
 const c=api('/e').catch(()=>{});await releaseAll();await c;assert.equal(calls.length,2);});
await scenario('non-json body',async()=>{
 install(async(url,options={})=>{calls.push({url,options});await new Promise(r=>gates.push(r));return{ok:false,status:502,json:async()=>{throw new SyntaxError('x')}}});
 const a=api('/n').catch(e=>e),b=api('/n').catch(e=>e);await releaseAll();
 const [ea,eb]=await Promise.all([a,b]);
 assert.equal(calls.length,1);assert.ok(ea instanceof APIError&&eb instanceof APIError);
 assert.equal(ea.status,502);assert.equal(typeof ea.message,'string');assert.ok(ea.message.length>0);
 assert.notEqual(ea.data,eb.data);});
await scenario('network failure',async()=>{
 install(async(url,options={})=>{calls.push({url,options});await new Promise(r=>gates.push(r));throw new TypeError('network down')});
 const a=api('/f').catch(e=>e),b=api('/f').catch(e=>e);await releaseAll();
 const [ea,eb]=await Promise.all([a,b]);
 assert.equal(calls.length,1);assert.notEqual(ea,eb);
 for(const e of [ea,eb]){assert.equal(e.name,'TypeError');assert.equal(e.message,'network down');}});
await scenario('GET after mutation start does not join earlier GET',async()=>{
 const a=api('/s');await flush();const post=api('/s',{method:'POST',body:'{}'});await flush();const b=api('/s');await flush();
 assert.equal(calls.filter(c=>!c.options.method).length,2);
 await releaseAll();await Promise.all([a,post,b]);});
await scenario('GET after mutation completes does not join earlier GET',async()=>{
 const a=api('/s');await flush();const post=api('/s',{method:'POST',body:'{}'});await flush();
 gates.splice(1,1)[0]();await post;   // complete POST only; GET A still in flight
 const c=api('/s');await flush();
 assert.equal(calls.filter(x=>!x.options.method).length,2);
 await releaseAll();await Promise.all([a,c]);});
await scenario('two GETs after mutation still coalesce',async()=>{
 const post=api('/s',{method:'POST',body:'{}'});await flush();const b=api('/s'),c=api('/s');await flush();
 assert.equal(calls.filter(x=>!x.options.method).length,1);
 await releaseAll();await Promise.all([post,b,c]);});
console.log('ok');
