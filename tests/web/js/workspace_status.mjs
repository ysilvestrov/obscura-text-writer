import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {sceneStatus,liveScene}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/workspace-status.js'));
const scene=(heads,needs_review=false)=>({id:'s1',heads,needs_review});
const cases=[
  [scene({}),{},'not_started','Не почато'],
  [scene({},true),{},'not_started','Не почато'],
  [scene({brief:'b'}),{},'no_text','Немає тексту'],
  [scene({brief:'b',draft:'d'}),{},'draft','Є чернетка'],
  [scene({brief:'b',draft:'d'},true),{},'needs_review','Потребує перегляду'],
  [scene({draft:'d',prose:'p'}),{},'prose','Текст створено'],
  [scene({draft:'d',prose:'p'},true),{s1:{prose:'pending'}},'needs_review','Потребує перегляду'],
  // R-44 PR 1: stale prose without the scene flag (an older version) also needs review; R-28 verdicts are gone.
  [scene({draft:'d',prose:'p'}),{s1:{prose:'pending'}},'needs_review','Потребує перегляду'],
  [scene({draft:'d',prose:'p'}),{s1:{prose:'current'}},'prose','Текст створено'],
];
for(const [input,impact,key,label] of cases)assert.deepEqual(sceneStatus(input,impact),{key,label},JSON.stringify(input));
assert.deepEqual(sceneStatus(scene({brief:'b'}),undefined),{key:'no_text',label:'Немає тексту'});
// Cross-review #3: the status row reads the refreshed scene metadata, not the scene object kept for the buffer.
const kept={id:'s1',heads:{}},fresh={id:'s1',heads:{draft:'d'}};
assert.equal(liveScene(kept,[fresh]),fresh);assert.equal(liveScene(kept,[]),kept);assert.equal(liveScene(null,[fresh]),null);
