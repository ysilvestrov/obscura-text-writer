import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {sceneStatus,reviewNeedsAuthor}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/workspace-status.js'));
const scene=(heads,needs_review=false)=>({id:'s1',heads,needs_review});
const cases=[
  [scene({}),{},'not_started','Не почато'],
  [scene({},true),{},'not_started','Не почато'],
  [scene({brief:'b'}),{},'no_text','Немає тексту'],
  [scene({brief:'b',draft:'d'}),{},'draft','Є чернетка'],
  [scene({brief:'b',draft:'d'},true),{},'needs_review','Потребує перегляду'],
  [scene({draft:'d',prose:'p'}),{},'prose','Текст створено'],
  [scene({draft:'d',prose:'p'},true),{s1:{prose:'pending'}},'impact_pending','Вплив не перевірено'],
  [scene({draft:'d',prose:'p'}),{s1:{prose:'changes_required'}},'impact_changes','Потрібні зміни'],
  [scene({draft:'d',prose:'p'}),{s1:{prose:'no_impact'}},'impact_current','Узгоджено після перевірки'],
];
for(const [input,impact,key,label] of cases)assert.deepEqual(sceneStatus(input,impact),{key,label},JSON.stringify(input));
assert.deepEqual(sceneStatus(scene({brief:'b'}),undefined),{key:'no_text',label:'Немає тексту'});
// #89 final review #5: the workspace shows the review card only while the session actually waits for the author.
for(const state of ['needs_review','paused','pause_requested','failed','interrupted','alternative'])assert.equal(reviewNeedsAuthor({state}),true,state);
for(const state of ['queued','running','succeeded','cancelled','cancellation_requested'])assert.equal(reviewNeedsAuthor({state}),false,state);
assert.equal(reviewNeedsAuthor(null),false);
