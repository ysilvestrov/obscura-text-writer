import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const m=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/timeline-summaries.js'));

const blocks=[
  {key:'range:1-10',part:false,title:'',first_number:1,last_number:10,state:'none',reason:null,recommended:true,ready:true,ready_reason:null,text:null,version_id:null},
  {key:'range:11-20',part:false,title:'',first_number:11,last_number:20,state:'fresh',reason:null,recommended:false,ready:true,ready_reason:null,text:'Підсумок.',version_id:'v2'},
  {key:'part:p3',part:true,title:'Дорога',first_number:21,last_number:30,state:'stale',reason:'blocks_changed',recommended:true,ready:true,ready_reason:null,text:'Старий.',version_id:'v3'},
  {key:'part:p4',part:true,title:'',first_number:31,last_number:35,state:'none',reason:null,recommended:false,ready:false,ready_reason:'Сцена 33 «Х» ще не має пам’яті',text:null,version_id:null},
];
const rows=m.summaryRows(blocks);
assert.deepEqual(rows.map(r=>[r.key,r.action,r.highlighted,r.editable]),[
  ['range:1-10','create',true,false],['range:11-20','rebuild',false,true],['part:p3','rebuild',true,true],['part:p4',null,false,false]]);
assert.deepEqual(rows[0].label,{key:'summaries.range',params:{p0:1,p1:10}});
assert.deepEqual(rows[2].label,{key:'summaries.part',params:{p0:'Дорога',p1:21,p2:30}});
assert.equal(rows[2].reason,'summaries.reason.blocks_changed');
assert.equal(rows[3].reason,'Сцена 33 «Х» ще не має пам’яті');
assert.equal(rows[1].reason,null);
assert.deepEqual(m.summaryRows(undefined),[]);
console.log('ok');
