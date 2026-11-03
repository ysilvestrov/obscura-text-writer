import assert from 'node:assert/strict';
import {loadDocument,createCommentEditorState,commentAnnotations,replaceCommentAnnotations,undoTransaction,redoTransaction,schema,toDocumentRange,toSourceRange}
  from '../../../src/storygen/web/static/rich-editor-engine.js';

const loaded=loadDocument('Вона **знала**. Вона **знала**.','markdown');
const range={from:18,to:23};
const selection=toSourceRange(range,loaded.sourceMap);
assert.deepEqual(toDocumentRange(selection,loaded.sourceMap),range);
const annotation={id:'second',...range,state:'valid',origin:{doc:loaded.doc,...range,anchor:selection}};
const fresh=()=>createCommentEditorState(loaded.doc,[annotation]);
let state=fresh();
state=state.applyTransaction(state.tr.insertText('X',1)).state;
assert.equal(commentAnnotations(state)[0].from,19);
assert.equal(commentAnnotations(state)[0].state,'valid');
undoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].from,18);
assert.equal(commentAnnotations(state)[0].state,'valid');
redoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].from,19);

state=fresh();
state=state.applyTransaction(state.tr.insertText('!',19)).state;
assert.equal(commentAnnotations(state)[0].state,'needs_review');
undoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].state,'valid');
redoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].state,'needs_review');

state=fresh();
state=state.applyTransaction(state.tr.addMark(18,23,schema.marks.em.create())).state;
assert.equal(commentAnnotations(state)[0].state,'needs_review');
undoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].state,'valid');

for(const position of [18,23]){
  state=fresh();state=state.applyTransaction(state.tr.insertText('X',position)).state;
  assert.equal(commentAnnotations(state)[0].state,'valid','outer-boundary insertion is outside');
  assert.equal(state.doc.textBetween(commentAnnotations(state)[0].from,commentAnnotations(state)[0].to),'знала');
}
assert.throws(()=>{
  state=fresh();state.applyTransaction(replaceCommentAnnotations(state.tr,[annotation,{...annotation,id:'nested',from:19,to:22}]));
},/overlap/i);
state=fresh();state=state.applyTransaction(replaceCommentAnnotations(state.tr,[annotation,{...annotation,id:'adjacent',from:23,to:24}])).state;
assert.equal(commentAnnotations(state).length,2);

// A comment created after a text event has no geometry step in that older event.
state=createCommentEditorState(loaded.doc,[]);
state=state.applyTransaction(state.tr.insertText('XX',18)).state;
const later={id:'later',from:18,to:20,state:'valid',origin:{doc:state.doc,from:18,to:20,anchor:{display_quote:'XX'}}};
state=state.applyTransaction(replaceCommentAnnotations(state.tr,[later])).state;
undoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].state,'needs_review');
redoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].state,'valid');
assert.equal(state.doc.textBetween(commentAnnotations(state)[0].from,commentAnnotations(state)[0].to),'XX');

// Explicit note edits/deletion do not get resurrected by text undo.
state=fresh();state=state.applyTransaction(state.tr.insertText('!',19)).state;
state=state.applyTransaction(replaceCommentAnnotations(state.tr,commentAnnotations(state).map(item=>({...item,instruction:'new'})))).state;
undoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state)[0].instruction,'new');
assert.equal(commentAnnotations(state)[0].state,'valid');
state=fresh();state=state.applyTransaction(state.tr.insertText('!',19)).state;
state=state.applyTransaction(replaceCommentAnnotations(state.tr,[])).state;
undoTransaction(state,tr=>state=state.applyTransaction(tr).state);
assert.equal(commentAnnotations(state).length,0);

state=fresh();state=state.applyTransaction(state.tr.addMark(18,23,schema.marks.em.create())).state;
state=state.applyTransaction(state.tr.removeMark(18,23,schema.marks.em)).state;
assert.equal(commentAnnotations(state)[0].state,'needs_review','manual return is not history acceptance');
console.log('Annotation mapping/history/Unicode bridge/boundaries/overlap passed');


// An explicit reattachment starts a new binding, separate from the comment ID.
const simple=loadDocument('abc def ghi','markdown');
state=createCommentEditorState(simple.doc,[{id:'A',from:1,to:4,state:'valid',origin:{doc:simple.doc,from:1,to:4,anchor:{display_quote:'abc'}}}]);
state=state.applyTransaction(state.tr.insertText('X',2)).state;
const reattached={id:'A',from:10,to:13,state:'valid',origin:{doc:state.doc,from:10,to:13,anchor:{display_quote:'ghi'}}};
state=state.applyTransaction(replaceCommentAnnotations(state.tr,[reattached])).state;
state=state.applyTransaction(replaceCommentAnnotations(state.tr,[...commentAnnotations(state),{id:'B',from:3,to:5,state:'valid',origin:{doc:state.doc,from:3,to:5,anchor:{display_quote:'bc'}}}])).state;
undoTransaction(state,tr=>state=state.applyTransaction(tr).state);
const reattachedAfterUndo=commentAnnotations(state).find(c=>c.id==='A');
assert.equal(state.doc.textBetween(reattachedAfterUndo.from,reattachedAfterUndo.to),'ghi','Undo must not undo explicit attachment');
assert.equal(reattachedAfterUndo.state,'valid');
assert.ok(commentAnnotations(state).filter(c=>c.state==='valid').every((c,i,all)=>all.every(other=>other===c||c.to<=other.from||c.from>=other.to)));
