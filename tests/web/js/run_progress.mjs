import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {progressText}=await import(pathToFileURL(root+'/src/storygen/web/static/run-progress.js'));

const book={id:'r',state:'running',request:{mode:'audit',audit_scope:'story'}};
const scenes=[{id:'s5',title:'Назва',position:4}];
const base={calls:{done:5,planned:23},spent_usd:'0.0200',spent_known:true,bound_usd:'2.1000',
  scene:{id:'s5',index:5,total:16},step:{link:'brief'},stopped:null};
let view=progressText(book,base,scenes);
assert.equal(view.title,'Валідація книги: сцена 5 з 16, «Назва»');
assert.equal(view.step,'завдання ↔ план');
assert.equal(view.counts,'Викликів: 5 / 23 · Витрачено: $0.02 з $2.10 (верхня межа)');
assert.ok(Math.abs(view.fraction-5/23)<1e-9);
assert.equal(progressText(book,{...base,scene:{id:'s5',index:17,total:16}},scenes).title,'Валідація книги: сцена 17, «Назва»');
assert.equal(progressText(book,{...base,scene:{id:'s5',index:5,total:null}},scenes).title,'Валідація книги: сцена 5, «Назва»');
assert.equal(progressText(book,{...base,scene:{id:null,index:0,total:16},step:null},scenes).title,'Валідація книги');
assert.equal(progressText(book,{...base,scene:{id:'gone',index:2,total:16}},scenes).title,'Валідація книги: сцена 2 з 16, «—»');
assert.equal(progressText(book,{...base,bound_usd:null},scenes).counts,'Викликів: 5 / 23 · Витрачено: $0.02');
assert.equal(progressText(book,{...base,spent_known:false},scenes).counts,'Викликів: 5 / 23 · Витрачено: $— з $2.10 (верхня межа)');
assert.equal(progressText(book,{...base,spent_usd:'0.0000',spent_known:false,bound_usd:null},scenes).counts,'Викликів: 5 / 23');  // Р5: local, no price
assert.equal(progressText(book,{...base,calls:{done:0,planned:23},spent_usd:'0.0000',spent_known:true,bound_usd:null},scenes).counts,'Викликів: 0 / 23');  // no «$0.0000» before the first call
assert.equal(progressText(book,{...base,spent_usd:'0.0100',spent_known:false,bound_usd:null},scenes).counts,'Викликів: 5 / 23 · Витрачено: $—');
assert.equal(progressText(book,{...base,calls:{done:0,planned:23},spent_usd:'0.0000'},scenes).counts,'Викликів: 0 / 23 · Витрачено: $0.0000 з $2.10 (верхня межа)');
const open=progressText(book,{...base,calls:{done:5,planned:null}},scenes);
assert.equal(open.fraction,null);assert.match(open.counts,/^Викликів: 5 · /);
assert.equal(progressText(book,{...base,calls:{done:30,planned:23}},scenes).fraction,1);
const sceneCheck={...book,request:{mode:'audit',audit_scope:'scene',scene_id:'s5'}};
assert.equal(progressText(sceneCheck,{...base,scene:{id:'s5',index:1,total:1},step:{link:'memory'}},scenes).step,"пам'ять ↔ проза");
assert.equal(progressText(sceneCheck,{...base,scene:{id:'s5',index:1,total:1}},scenes).title,'Перевірка сцени «Назва»');
const gen={id:'g',state:'running',request:{mode:'remaining'}};
view=progressText(gen,{...base,bound_usd:null,scene:{id:'s5',index:3,total:10},step:{stage:'draft'}},scenes);
assert.equal(view.title,'Сцена 3 з 10, етап: чернетка');assert.equal(view.step,'');
assert.equal(progressText(gen,{...base,scene:null,step:{stage:'prepare'}},scenes).title,'Етап: prepare');
assert.equal(progressText(gen,null,scenes),null);
// A progress without spent_usd or calls gives no «$NaN» and no NaN fraction.
const bare=progressText(book,{scene:{id:'s5',index:1,total:2},step:null,bound_usd:'1.0000'},scenes);
assert.ok(!bare.counts.includes('NaN'),bare.counts);assert.equal(bare.fraction,null);
assert.ok(!progressText(book,{...base,spent_usd:undefined},scenes).counts.includes('NaN'));
assert.ok(!progressText(book,{...base,spent_usd:'x',bound_usd:null},scenes).counts.includes('NaN'));
assert.equal(progressText(book,{...base,calls:{done:undefined,planned:4}},scenes).fraction,null);
