// LONG-PROSE-TRIAL-S07: the trial helpers of the Obscura window.
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const m=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/long-prose-trial.js'));

assert.deepEqual(m.trialState({}),{state:'none',kind:null,id:null,title:null});
assert.deepEqual(m.trialState({long_prose_trial:{state:'available',kind:null,id:null,title:null}}).state,'available');
assert.equal(m.usedText({state:'used',title:'Маяк'}),'Пробу використано на «Маяк»');
assert.equal(m.usedText({state:'used',title:null}),'Пробу вже використано');
assert.equal(m.usedText({state:'used',title:''}),'Пробу вже використано');
assert.deepEqual(m.claimBody({series_id:'s1'}),{series_id:'s1',confirm:true});
assert.deepEqual(m.claimBody({story_id:'b1'}),{story_id:'b1',confirm:true});

function deps(answer,fail=null){
  const calls={api:[],reload:0,notices:[],asked:[]};
  return {calls,deps:{
    api:async(url,options)=>{calls.api.push([url,JSON.parse(options.body)]);if(fail)throw new Error(fail);return {state:'used'}},
    json:(method,body)=>({method,body:JSON.stringify(body)}),
    confirmDialog:async message=>{calls.asked.push(message);return answer},
    notice:(text,kind)=>calls.notices.push([text,kind]),
    location:{reload:()=>{calls.reload++}}}};
}
let run=deps(false);
assert.equal(await m.claimTrial(run.deps,{story_id:'b1'},'Маяк'),false);
assert.equal(run.calls.api.length,0);assert.equal(run.calls.reload,0);
assert.match(run.calls.asked[0],/«Маяк»/);
run=deps(true);
assert.equal(await m.claimTrial(run.deps,{series_id:'s1'},'Сага'),true);
assert.deepEqual(run.calls.api,[['/api/long-prose-trial',{series_id:'s1',confirm:true}]]);
assert.equal(run.calls.reload,1);
run=deps(true,'Пробу довгої прози вже використано');
assert.equal(await m.claimTrial(run.deps,{story_id:'b1'},'Маяк'),false);
assert.equal(run.calls.reload,0);
assert.deepEqual(run.calls.notices,[['Пробу довгої прози вже використано','error']]);
