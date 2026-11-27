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

// Merges follow the final target: a parent merged into its own child does not invert the tree, and a chain А→Б→В
// shows А and Б under В.
const inverted=m.locationRows({locations:[card('a','Маяк',{merged_into:'b',target_path:'Маяк / ліхтарна'}),card('b','Маяк / ліхтарна',{parent_id:'a'})]});
assert.deepEqual(inverted.map(r=>[r.id,r.depth]),[['b',0],['a',1]]);
const chain=m.locationRows({locations:[card('x','А',{merged_into:'y',target_path:'В'}),card('y','Б',{merged_into:'z',target_path:'В'}),card('z','В'),card('k','Б / кухня',{parent_id:'y'})]});
assert.deepEqual(chain.map(r=>[r.id,r.depth]),[['z',0],['k',1],['x',1],['y',1]]);
console.log('merge tree ok');

// R-51 (MEMORY-LOCATIONS-S08): an unmerged card offers to remove itself from scenes whose places a model gave.
const model=m.locationRows({locations:[
  card('pier','Пірс',{scenes:[{id:'s1',position:0,title:'Ранок',source:'plan'},{id:'s3',position:2,title:'Ніч',source:'model'}]}),
  card('typo','Пiрс',{merged_into:'pier',target_path:'Пірс',scenes:[{id:'s4',position:3,title:'Світанок',source:'model'}]}),
]});
assert.deepEqual(model.map(r=>[r.id,r.modelScenes]),[['pier',[{id:'s3',label:'3. Ніч'}]],['typo',[]]]);
assert.equal(model[0].scenes,'1. Ранок, 3. Ніч');
console.log('model places ok');

// MEMORY-LOCATIONS-S11: «Склеїти з…» offers the phrases of glue candidates that name the card; «Склеєні назви» lists glues.
const glueData={locations:[card('bar','Бар'),card('cafe','в якому пахне кавою'),card('glued','Бар, в якому пахне кавою')],
  glues:[{key:'місто, двір',phrase:'Місто, двір'}],
  glue_candidates:[{phrase:'Бар, в якому пахне кавою',key:'бар, в якому пахне кавою',card_ids:['bar','cafe'],scene_ids:['s1','s2']},
    {phrase:'Бар, в якому пахне кавою, вулиця',key:'бар, в якому пахне кавою, вулиця',card_ids:['glued','street'],scene_ids:['s3']},
    {phrase:'Бар, '+'х'.repeat(196),key:'long',card_ids:['bar'],scene_ids:['s4']}]};
assert.deepEqual(m.glueOptions(glueData,'bar'),[{key:'бар, в якому пахне кавою',phrase:'Бар, в якому пахне кавою',cardIds:['bar','cafe'],scenes:2}],
  'only candidates naming the card, phrases of 3–200 characters');
assert.deepEqual(m.glueOptions(glueData,'glued').map(o=>o.key),['бар, в якому пахне кавою, вулиця']);
assert.deepEqual(m.glueOptions(glueData,'nobody'),[]);
assert.deepEqual(m.glueOptions(undefined,'bar'),[]);
assert.deepEqual(m.glueRows(glueData),[{key:'місто, двір',phrase:'Місто, двір'}]);
assert.deepEqual(m.glueRows(undefined),[]);
console.log('glue ok');

// MEMORY-LOCATIONS-S12: the page asks before leaving with typed descriptions; the memory tab links to the page.
assert.equal(m.hasDrafts(new Map()),false);
assert.equal(m.hasDrafts(new Map([['loc_1','текст']])),true);
assert.equal(m.memoryLinkHref('s1',null,null),'/stories/s1/locations');
assert.equal(m.memoryLinkHref('s1','sc1',null),'/stories/s1/locations');
assert.equal(m.memoryLinkHref('s1','sc1','memory'),'/stories/s1/locations?scene=sc1&material=memory');
console.log('page ok');
