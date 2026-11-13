import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const m=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/book-structure.js'));
const label=(key,n)=>`${key}:${n}`;

const book={kind:'structured',explicit:true,parts:[
  {id:'p1',title:'Дім',arcs:[{id:'a1',title:''},{id:'a2',title:'Сад'}]},
  {id:'p2',title:'',arcs:[{id:'b1',title:''}]}]};
const scenes=[{id:'s1',arc_id:'a1'},{id:'s2',arc_id:'a2'},{id:'s3',arc_id:'b1'},{id:'s4',arc_id:'b1'}];

// Flat book: scene rows only.
assert.deepEqual(m.groupScenes({kind:'flat',parts:[]},scenes,label).map(r=>r.type),['scene','scene','scene','scene']);
// Structured: part headings, arc headings only where a part has several arcs or the arc has a title.
const rows=m.groupScenes(book,scenes,label);
assert.deepEqual(rows.map(r=>r.type==='scene'?r.scene.id:`${r.type}:${r.title}`),
  ['part:Дім','arc:book.arc.untitled:1','s1','arc:Сад','s2','part:book.part.untitled:2','s3','s4']);

assert.deepEqual(m.arcOptions(book,label).map(o=>o.label),
  ['Дім › book.arc.untitled:1','Дім › Сад','book.part.untitled:2 › book.arc.untitled:1']);

// Buffer rules: a part or arc with scenes stays, the last arc of a part and the last part stay.
const buffer=m.createBuffer(book,scenes);
assert.equal(m.remove(buffer,0,1),'book.error.has_scenes');
assert.equal(m.remove(buffer,1,0),'book.error.last_arc');
m.addArc(buffer,1);
assert.equal(m.remove(buffer,1,1),null);
m.addPart(buffer);
assert.equal(buffer.parts.length,3);
assert.equal(m.remove(buffer,2),null);
assert.equal(m.remove(buffer,1),'book.error.has_scenes');
const single=m.createBuffer({kind:'flat',parts:[{id:'implicit-part',title:'',arcs:[{id:'implicit-arc',title:''}]}]},[]);
assert.equal(m.remove(single,0),'book.error.last_part');

// Moving and renaming, then the payload for PUT /structure.
m.rename(buffer,1,null,'Дорога');
m.move(buffer,0,0,1);
assert.deepEqual(buffer.parts[0].arcs.map(a=>a.id),['a2','a1']);
m.move(buffer,0,null,-1);
const body=m.payload(buffer,7);
assert.equal(body.expected_revision,7);
assert.deepEqual(body.parts.map(p=>p.title),['Дім','Дорога']);
assert.deepEqual(body.scene_arcs,{s1:'a1',s2:'a2',s3:'b1',s4:'b1'});
// New items carry client ids so scenes can be bound to them in the same request.
m.addPart(buffer);
assert.match(m.payload(buffer,7).parts[2].id,/^part-/);
// BOOK-LINEAGE-S04: an arc protagonist survives a save from the panel; an arc without one sends null.
const kept=m.createBuffer({kind:'structured',explicit:true,parts:[{id:'p1',title:'',arcs:[{id:'a1',title:'',protagonist_id:'B'},{id:'a2',title:''}]}]},[]);
assert.deepEqual(m.payload(kept,1).parts[0].arcs.map(a=>a.protagonist_id),['B',null]);
assert.equal(m.setProtagonist(kept,0,1,'A'),null);
assert.equal(m.setProtagonist(kept,0,0,''),null);
assert.deepEqual(m.payload(kept,1).parts[0].arcs.map(a=>a.protagonist_id),[null,'A']);
console.log('ok');

// MEMORY-MERGE harness H1: a meeting scene keeps all its arcs in the panel payload, and counts in each of its arcs.
{
  const meetingBook={kind:'structured',explicit:true,parts:[{id:'p1',title:'',arcs:[{id:'A',title:''},{id:'B',title:''}]}]};
  const meeting=m.createBuffer(meetingBook,[{id:'s1',arc_id:'A',arc_ids:['A']},{id:'s3',arc_id:'A',arc_ids:['A','B']}]);
  assert.deepEqual(m.payload(meeting,1).scene_arcs,{s1:'A',s3:['A','B']});
  assert.equal(m.remove(meeting,0,1),'book.error.has_scenes');
}

// MEMORY-MERGE harness H3: meeting options are the other arcs of the part of the scene's first arc.
assert.deepEqual(m.meetingOptions(book,['a1','a2'],label),[{value:'a2',label:'Сад',checked:true}]);
assert.deepEqual(m.meetingOptions(book,['a1'],label),[{value:'a2',label:'Сад',checked:false}]);
assert.deepEqual(m.meetingOptions(book,['b1'],label),[]);
assert.deepEqual(m.meetingOptions(book,[],label),[]);

// MEMORY-MERGE harness H4: scene rows carry the meeting and merge marks.
{
  const meetingBook={kind:'structured',explicit:true,parts:[{id:'p1',title:'',arcs:[{id:'A',title:''},{id:'B',title:''}]}]};
  const rows=m.groupScenes(meetingBook,[{id:'s1',arc_id:'A',arc_ids:['A']},{id:'s2',arc_id:'A',arc_ids:['A','B'],memory_merge:'required'}],label).filter(r=>r.type==='scene');
  assert.deepEqual(rows.map(r=>[r.meeting,r.merge]),[[false,null],[true,'required']]);
  assert.deepEqual(m.sceneMarks(rows[1]),['book.badge.meeting','book.badge.merge']);
  assert.deepEqual(m.sceneMarks({...rows[1],merge:'fresh'}),['book.badge.meeting']);
  assert.deepEqual(m.sceneMarks(rows[0]),[]);
}

// STORY-TIME-S07: a flashback (flag or «Початок:» mark) is marked in the scene status line.
{
  const flat={kind:'flat',explicit:false,parts:[{id:'p',title:'',arcs:[{id:'a',title:''}]}]};
  const rows=m.groupScenes(flat,[{id:'s1',flashback:true},{id:'s2',flashback_marked:true},{id:'s3'}],label).filter(r=>r.type==='scene');
  assert.deepEqual(rows.map(r=>m.sceneMarks(r)),[['book.badge.flashback'],['book.badge.flashback'],[]]);
}
