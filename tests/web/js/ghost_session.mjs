import assert from 'node:assert/strict';
const root=new URL('../../../src/storygen/web/static/',import.meta.url);
const s=await import(new URL('ghost-session.js',root));

const long='Довгий абзац '+'слово '.repeat(30);
const text=`${long.trim()}\n\n***\n\n${long.trim()}`;
const session=s.createSession({sceneId:'s1',draftId:'d1',format:'markdown',text});
assert.deepEqual(session.blocks.map(b=>b.state),['reading','separator','reading']);
assert.equal(session.blocks[1].source,'***');
assert.equal(s.canSave(session),false);

// Tab on an untouched block does nothing: the AI text is already visible.
assert.equal(s.peekStart(session),false);
assert.equal(session.peeks,0);
// An empty input before typing keeps reading; the first change switches to writing for good.
assert.equal(s.input(session,''),false);
assert.equal(session.blocks[0].state,'reading');
assert.equal(s.input(session,'Мій текст.'),true);
assert.equal(session.blocks[0].state,'writing');
assert.equal(s.input(session,''),true);
assert.equal(session.blocks[0].state,'writing','erasing everything does not bring the AI text back');

// Peek only from writing; editing is locked while peeking; counters grow only on writing -> peek.
assert.equal(s.peekStart(session),true);
assert.equal(s.input(session,'під час проблиску'),false);
assert.equal(s.go(session,1),false,'no navigation during a peek');
assert.equal(s.peekEnd(session,1234.4),true);
assert.equal(s.peekEnd(session,50),false);
assert.deepEqual([session.peeks,session.peekMs],[1,1234]);

s.input(session,'Мій текст.');
assert.equal(s.canSave(session),false,'every text block must be written or skipped');
assert.equal(s.go(session,1),true);
assert.equal(s.go(session,1),true);
assert.equal(session.index,2);
assert.equal(s.skip(session),true);
assert.equal(s.canSave(session),true);
assert.equal(s.skippedCount(session),1);
assert.equal(s.resultText(session),'Мій текст.\n\n***');
assert.equal(s.unskip(session),true);
assert.equal(session.blocks[2].state,'reading','an untouched skipped block returns to reading');
s.input(session,'Другий.');
assert.equal(s.resultText(session),'Мій текст.\n\n***\n\nДругий.');
s.blockPasted(session);
assert.deepEqual(s.clientStats(session),{peeks:1,peek_ms:1234,pastes_blocked:1,blocks_skipped:0});

// All blocks skipped is not a rewrite.
const empty=s.createSession({sceneId:'s1',draftId:'d2',format:'plain',text:'Один короткий абзац.'});
s.skip(empty);
assert.equal(s.canSave(empty),false);

// Storage: a peek is never persisted; broken or foreign data is ignored; a throwing storage is tolerated.
const memory=new Map();
const storage={getItem:k=>memory.get(k)??null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k),get length(){return memory.size},key:i=>[...memory.keys()][i]};
s.peekStart(session);
assert.equal(s.saveSession(storage,session),true);
const restored=s.loadSession(storage,'s1','d1');
assert.equal(restored.blocks[2].state,'writing');
assert.equal(restored.blocks[0].text,'Мій текст.');
assert.equal(s.findSession(storage,'s1'),'d1');
assert.equal(s.loadSession(storage,'s1','other'),null);
memory.set(s.sessionKey('s1','bad'),'{');
assert.equal(s.loadSession(storage,'s1','bad'),null);
const broken={getItem(){throw new Error('denied')},setItem(){throw new Error('denied')},removeItem(){throw new Error('denied')},get length(){throw new Error('denied')}};
assert.equal(s.saveSession(broken,session),false);
assert.equal(s.loadSession(broken,'s1','d1'),null);
assert.equal(s.findSession(broken,'s1'),null);
s.dropSession(broken,'s1','d1');
s.dropSession(storage,'s1','d1');
assert.equal(s.loadSession(storage,'s1','d1'),null);

// Stats line: every field, overlap as a percentage, null overlap as a dash.
const t=(key,args)=>key+':'+Object.values(args).join('|');
assert.equal(s.ghostStatsText({blocks:12,blocks_written:11,blocks_skipped:1,overlap_4gram:0.0612,peeks:7,peek_ms:41200,pastes_blocked:2},t),'ghost.stats:11|12|1|6 %|7|41|2');
assert.equal(s.ghostStatsText({blocks:1,blocks_written:1,blocks_skipped:0,overlap_4gram:null,peeks:0,peek_ms:0,pastes_blocked:0},t),'ghost.stats:1|1|0|—|0|0|0');
assert.equal(s.ghostStatsText(null,t),'');
