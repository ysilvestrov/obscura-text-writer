import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const m=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/locations.js'));

// MEMORY-LOCATIONS-S07: rows of the «Locations» panel from GET /api/stories/{id}/locations (pure).
const card=(id,path,extra={})=>({id,path,parent_id:null,merged_into:null,target_path:null,description:'',scenes:[],...extra});
const data={story_revision:4,locations:[
  card('house','Дім'),
  card('yard','двір',{scenes:[{id:'s2',position:1,title:'Вечір'}]}),
  card('kitchen','Дім / кухня',{parent_id:'house',description:'Тісна.',scenes:[{id:'s1',position:0,title:'Ранок'},{id:'s2',position:1,title:'Вечір'}]}),
  card('pantry','Дім / кухня / комора',{parent_id:'kitchen'}),
  card('typo','Дiм',{merged_into:'house',target_path:'Дім'}),
],suggestions:[{a:'house',b:'yard',a_path:'Дім',b_path:'двір'}]};

const rows=m.locationRows(data);
assert.deepEqual(rows.map(r=>[r.id,r.depth]),[['house',0],['kitchen',1],['pantry',2],['typo',1],['yard',0]],
  'nested cards follow their parent; a merged card sits under its target');
assert.deepEqual(rows.map(r=>[r.id,r.merged,r.canMerge,r.canSplit,r.editable]),[
  ['house',false,true,false,true],['kitchen',false,true,false,true],['pantry',false,true,false,true],
  ['typo',true,false,true,false],['yard',false,true,false,true]]);
assert.equal(rows[1].scenes,'1. Ранок, 2. Вечір');
assert.equal(rows[0].scenes,'');
assert.equal(rows[3].targetPath,'Дім');
assert.equal(rows[1].description,'Тісна.');
assert.deepEqual(m.mergeTargets(data,'kitchen').map(t=>t.id),['house','pantry','yard'],'only unmerged cards, never itself');
assert.deepEqual(m.suggestionRows(data),[{a:'house',b:'yard',aPath:'Дім',bPath:'двір'}]);
assert.deepEqual(m.locationRows(undefined),[]);
assert.deepEqual(m.suggestionRows(undefined),[]);
// A broken parent chain (a parent that is not in the list) still shows the card at the top level once.
assert.deepEqual(m.locationRows({locations:[card('lost','Х / Y',{parent_id:'gone'})]}).map(r=>[r.id,r.depth]),[['lost',0]]);
console.log('ok');

const r=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/story-revision.js'));
const panels={a:{storyId:'s',rev:4},b:{storyId:'s',rev:3},c:{storyId:'other',rev:4}};
for(const p of Object.values(panels))r.followRevision(()=>({storyId:p.storyId,get:()=>p.rev,set:v=>{p.rev=v}}));
r.followRevision(()=>null);
r.announceRevision('s',5);
assert.deepEqual([panels.a.rev,panels.b.rev,panels.c.rev],[5,3,4],'only a panel one step behind on the same story follows');
console.log('revision ok');
