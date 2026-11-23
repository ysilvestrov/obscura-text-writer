import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {invalidSceneCount,bookMenuState}=await import(pathToFileURL(root+'/src/storygen/web/static/book-validation-state.js'));
const {confirmationText,auditConfirmationText}=await import(pathToFileURL(root+'/src/storygen/web/static/run-readiness.js'));
const {runModeKey,stoppedAuditScene}=await import(pathToFileURL(root+'/src/storygen/web/static/run-summary.js'));

// R-44 book validation, design §12: the menu counts the scenes with a link in unchecked, discrepancy or unavailable
// (the rule of the server's book_pending and of the preview's invalid_scenes), whatever the scene's validity.
const status={
  a:{validity:'unchecked',links:{brief:{status:'unchecked'},prose:{status:'valid'}}},
  b:{validity:'discrepancy',links:{brief:{status:'discrepancy'}}},
  c:{validity:'valid',links:{brief:{status:'valid'},prose:{status:'valid'}}},
  d:{validity:'incomplete',links:{brief:{status:'unchecked'}}},      // brief-only scene with an unchecked brief link: counts
  e:{validity:'unchecked',links:{brief:{status:'valid'},prose:{status:'unavailable'}}},  // only unavailable: counts
  f:{validity:'incomplete',links:{}},                                // no links: does not count
  g:{validity:'incomplete'},                                         // no links key: does not count
  h:{validity:'unchecked',links:{brief:{status:'valid'},memory:{status:'missing'}}}};  // valid or missing only: does not count
assert.equal(invalidSceneCount(status),4);
assert.equal(invalidSceneCount({d:status.d}),1);
assert.equal(invalidSceneCount({e:status.e}),1);
assert.equal(invalidSceneCount({c:status.c,f:status.f,g:status.g,h:status.h}),0);
assert.equal(invalidSceneCount({}),0);
assert.equal(invalidSceneCount(undefined),0);
assert.deepEqual(bookMenuState(2),{key:'book_validation.menu_count',params:{p0:2},disabled:false});
// 0: the item says the book is valid and is inactive.
assert.deepEqual(bookMenuState(0),{key:'book_validation.valid',params:{},disabled:true});
// No view yet: the plain label, inactive until the counter is known.
assert.deepEqual(bookMenuState(null),{key:'book_validation.menu',params:{},disabled:true});

// The book preview: scenes, calls, the auditor model, the upper bound on cost and the caveat about edits during the run.
const book={ready:true,calls:4,invalid_scenes:2,roles:{auditor:{provider:'openrouter',model:'auditor-model'}},warnings:[],plan_fingerprint:'f'.repeat(64),
  links:[{scene_id:'s1',link:'brief',status:'unchecked'},{scene_id:'s2',link:'prose',status:'unchecked'}],
  cost:{per_call_usd:'0.0309',total_usd:'0.1234',reason:null}};
let text=auditConfirmationText(book);
assert.match(text,/Сцен до перевірки: 2\./);
assert.match(text,/До 4 викликів Ревізора/);
assert.match(text,/openrouter \/ auditor-model/);
assert.match(text,/\$0\.1234/);
assert.match(text,/верхня межа/);
assert.match(text,/правки під час перевірки/);
assert.doesNotMatch(text,/оцінки ціни немає/);
assert.doesNotMatch(text,/0\.0309/);  // the per-call price is never shown or multiplied in the page
// No sum: the server's reason, translated, and no dollars.
text=auditConfirmationText({...book,cost:{per_call_usd:null,total_usd:null,reason:'Ціна моделі застаріла; оновіть ціни в налаштуваннях'}});
assert.match(text,/Суму не пораховано: Ціна моделі застаріла/);
assert.doesNotMatch(text,/\$/);
// A local auditor: no USD line at all.
text=auditConfirmationText({...book,roles:{auditor:{provider:'local',model:'m'}},cost:{per_call_usd:null,total_usd:null,reason:null}});
assert.doesNotMatch(text,/\$|Суму не пораховано/);
assert.match(text,/Сцен до перевірки: 2\./);
// Warnings keep their header.
assert.match(auditConfirmationText({...book,warnings:['Увага']}),/Попередження:\nУвага/);

// The scene check goes through the same text: its links, the model and the sum when known.
const scene={ready:true,calls:2,roles:{auditor:{provider:'local',model:'synthetic-auditor'}},warnings:[],plan_fingerprint:'e'.repeat(64),
  links:[{link:'brief',status:'unchecked'},{link:'prose',status:'unchecked'}],cost:{per_call_usd:null,total_usd:null,reason:null}};
text=confirmationText(scene);
assert.match(text,/Зв’язки до перевірки: завдання, проза\./);
assert.match(text,/synthetic-auditor/);
assert.match(text,/До 2 викликів Ревізора/);
assert.doesNotMatch(text,/Сцен до перевірки/);
assert.doesNotMatch(text,/оцінки ціни немає/);
assert.match(confirmationText({...scene,cost:{per_call_usd:'0.01',total_usd:'0.0200',reason:null}}),/\$0\.0200/);
// A resumed book run (its readiness) reads as a book: counts, not a list of links without scenes.
assert.match(confirmationText(book),/Сцен до перевірки: 2\./);
// Other operations keep the usual text.
assert.match(confirmationText({calls:1,roles:{memory:{provider:'local',model:'memory-model'}}}),/оцінки ціни немає/);

// The run summary names a book run and leads from its stop to the scene.
assert.equal(runModeKey({request:{mode:'audit',audit_scope:'story'}}),'run.mode_audit_book');
assert.equal(runModeKey({request:{mode:'audit',audit_scope:'scene'}}),'run.mode_audit');
const scenes=[{id:'s1',position:0,title:'Ранок'},{id:'s2',position:1,title:'Вечір'}];
const stopped={state:'needs_review',request:{mode:'audit',audit_scope:'story'},checkpoint:{scene_id:'s2',link:'brief',phase:'awaiting_author'}};
assert.equal(stoppedAuditScene(stopped,scenes),scenes[1]);
assert.equal(stoppedAuditScene({...stopped,state:'running'},scenes),null);
assert.equal(stoppedAuditScene({...stopped,request:{mode:'audit',audit_scope:'scene'}},scenes),null);
assert.equal(stoppedAuditScene({...stopped,checkpoint:null},scenes),null);
assert.equal(stoppedAuditScene({...stopped,checkpoint:{scene_id:'gone'}},scenes),null);
assert.equal(stoppedAuditScene(stopped,undefined),null);
assert.equal(stoppedAuditScene(null,scenes),null);
console.log('Book validation helpers passed');
