import assert from 'node:assert/strict';
import {stages, primaryAction, performPrimary,assertReadyDispatch,authorMode} from '../../../src/storygen/web/static/workspace-state.js';
import {createTextEditor} from '../../../src/storygen/web/static/text-editor.js';

assert.deepEqual(stages.map(s=>s.mode),['plan','brief','draft','review','prose','memory']);
const state={scene:{id:'c',heads:{}},mode:'draft',dirty:true,saving:false,bufferEpoch:1};
const calls=[];
const deps={state,save:async()=>{calls.push('save');state.dirty=false;state.scene.heads.draft='d'},run:async spec=>calls.push(spec),show:async mode=>calls.push(mode),accept:async()=>{},next:async()=>calls.push('next')};
await performPrimary(deps);
assert.equal(calls[0],'save');assert.equal(calls[1].editor_source_head,'draft');assert.equal(calls[1].editor_source_version_id,'d');
state.mode='prose';state.scene.heads.memory='m';
assert.match(primaryAction(state).label,/новий варіант пам/);
// R20-WORKSPACE: the repeat action on the draft tab is a short «Редагувати».
{const repeat={scene:{id:'c',heads:{draft:'d',prose:'p'}},mode:'draft',dirty:false};
assert.equal(primaryAction(repeat).label,'Редагувати');
// R20-WORKSPACE-S09: the review tab's primary action is «Прийняти правки».
assert.equal(primaryAction({scene:{id:'c',heads:{}},mode:'review',dirty:false}).label,'Прийняти правки');
assert.equal(primaryAction({...repeat,dirty:true}).label,'Зберегти й редагувати');
assert.equal(primaryAction({...repeat,scene:{id:'c',heads:{draft:'d'}}}).label,'Зберегти й редагувати');}
state.mode='draft';state.dirty=true;calls.length=0;
await assert.rejects(performPrimary({...deps,save:async()=>{throw Error('CAS')}}),/CAS/);assert.deepEqual(calls,[]);
await assert.rejects(performPrimary({...deps,save:async()=>{state.bufferEpoch++;state.dirty=false}}),/зміни/);assert.deepEqual(calls,[]);
state.dirty=false;state.mode='review';state.bufferOrigin='history';
await assert.rejects(performPrimary(deps),/історич/);
state.bufferOrigin='current';state.mode='memory';await performPrimary(deps);assert.equal(calls.at(-1),'next');
const field={value:'',readOnly:false,hidden:false,addEventListener(){},focus(){}};
const editor=createTextEditor(field);const markdown='**Жирний** і *курсив*\r\n\r\nОлена — 👩🏽‍💻';editor.write(markdown);assert.equal(editor.read(),markdown);
editor.readOnly(true);assert.equal(field.readOnly,true);
state.mode='draft';state.bufferOrigin='current';state.workspaceRuns=[{state:'queued'}];
assert.throws(()=>assertReadyDispatch(state,{sceneId:'c',epoch:state.bufferEpoch,mode:'draft'}),/запуск/);
state.workspaceRuns=[];assert.doesNotThrow(()=>assertReadyDispatch(state,{sceneId:'c',epoch:state.bufferEpoch,mode:'draft'}));
console.log('Workspace route and Markdown boundary regressions passed');
// R-49 (WRITING-MODE-S09): in a «Пишу сам» story the primary action never launches a prose run.
{const author={view:{story:{writing_mode:'author'}},scene:{id:'c',heads:{draft:'d'}},dirty:false,saving:false,bufferEpoch:1,bufferOrigin:'current'};
for(const mode of ['plan','brief'])assert.equal(primaryAction({...author,mode}).action,'write',mode);
assert.equal(primaryAction({...author,mode:'plan'}).label,'Писати прозу');
assert.equal(primaryAction({...author,mode:'draft'}).action,'use_draft');
assert.equal(primaryAction({...author,mode:'draft',scene:{id:'c',heads:{}}}).action,'write');
assert.equal(primaryAction({...author,mode:'prose'}).stage,'memory');
for(const mode of ['plan','brief','draft'])assert.equal(primaryAction({...author,mode}).mode,undefined,mode);
const seen=[];
await performPrimary({state:{...author,mode:'plan'},save:async()=>{},run:async spec=>seen.push(['run',spec]),show:async mode=>seen.push(['show',mode]),useDraft:async()=>seen.push(['use']),accept:async()=>{},next:async()=>{}});
await performPrimary({state:{...author,mode:'draft'},save:async()=>{},run:async spec=>seen.push(['run',spec]),show:async mode=>seen.push(['show',mode]),useDraft:async()=>seen.push(['use']),accept:async()=>{},next:async()=>{}});
assert.deepEqual(seen,[['show','prose'],['use']]);
assert.equal(authorMode(author),true);assert.equal(authorMode({view:{story:{writing_mode:'obscura'}}}),false);assert.equal(authorMode({}),false);}
