import assert from 'node:assert/strict';
// MANUSCRIPT-IMPORT dialog: the pure logic of scene boundaries (spec §3.5, §4.4) — moving, adding and removing a boundary,
// the word counts after a move and the body of the import request.
const {toggleBoundary,sceneWords,applyBody,setFrontMatter,chapterSourceValue,MAX_FILE,MAX_SCENES}=await import('../../../src/storygen/web/static/manuscript-import.js');

assert.equal(MAX_FILE,20*1024*1024);assert.equal(MAX_SCENES,500);
// Paragraphs 0 title, 1 front matter, 2 heading, 3–6 prose (5 is a separator), 7 heading, 8–11 prose.
const roles=['title','front_matter','chapter_heading','prose','prose','separator','prose','chapter_heading','prose','prose','prose','prose'];
const paragraphs=roles.map((role,index)=>({index,text_head:'p'+index,words:role==='prose'?10*index:role==='front_matter'?4:0,heading_level:null,
  after_break:false,role,boundary_allowed:role==='prose'||role==='front_matter'}));
const scenes=[{start:3,end:4,title:'Пірс (1)',words:70,part_index:null,proposed:false,warnings:[]},
  {start:6,end:6,title:'Пірс (2)',words:60,part_index:null,proposed:false,warnings:[]},
  {start:8,end:11,title:'Шторм',words:380,part_index:null,proposed:true,warnings:['w']}];

// A boundary only on an allowed paragraph: a separator or a heading never starts a scene.
assert.deepEqual(toggleBoundary(scenes,5,paragraphs),scenes);
assert.deepEqual(toggleBoundary(scenes,7,paragraphs),scenes);
// The first boundary cannot be removed.
assert.deepEqual(toggleBoundary(scenes,3,paragraphs),scenes);
// Adding: the scene splits; the new scene is named after it.
const split=toggleBoundary(scenes,10,paragraphs);
assert.deepEqual(split.map(s=>[s.start,s.end,s.title]),[[3,4,'Пірс (1)'],[6,6,'Пірс (2)'],[8,9,'Шторм'],[10,11,'Шторм (2)']]);
assert.equal(split[3].proposed,false);
assert.deepEqual(scenes.map(s=>s.start),[3,6,8],'the input list is not changed');
// Removing: the scene joins the previous one.
const merged=toggleBoundary(split,10,paragraphs);
assert.deepEqual(merged.map(s=>[s.start,s.end,s.title]),[[3,4,'Пірс (1)'],[6,6,'Пірс (2)'],[8,11,'Шторм']]);
const chapters=toggleBoundary(scenes,6,paragraphs);  // a chapter or separator boundary can be removed too
assert.deepEqual(chapters.map(s=>[s.start,s.end]),[[3,6],[8,11]]);
// A taken suffix is skipped.
const twice=toggleBoundary(toggleBoundary(split,9,paragraphs),11,paragraphs);
assert.deepEqual(twice.map(s=>s.title),['Пірс (1)','Пірс (2)','Шторм','Шторм (3)','Шторм (2)','Шторм (4)']);
// A title that already ends in « (n)» is numbered from its base, never nested.
const numbered=[{...scenes[2],title:'Шторм (1)'}];
assert.deepEqual(toggleBoundary(numbered,10,paragraphs).map(s=>s.title),['Шторм (1)','Шторм (2)']);
assert.deepEqual(toggleBoundary([{...scenes[0],title:'Шторм (2)'},{...scenes[2],title:'Шторм (1)'}],10,paragraphs).map(s=>s.title),['Шторм (2)','Шторм (1)','Шторм (3)']);
assert.equal(toggleBoundary([{...scenes[2],title:'Розділ (без номера)'}],10,paragraphs)[1].title,'Розділ (без номера) (2)');

// The new title stays within 200 characters and keeps its suffix.
const long=[{...scenes[2],title:'я'.repeat(200)}];
const cut=toggleBoundary(long,10,paragraphs);
assert.equal(cut[1].title.length,200);assert.ok(cut[1].title.endsWith(' (2)'));

// Words: only imported paragraphs count (headings and separators inside a range do not); after a move they follow the boundary.
assert.deepEqual(sceneWords(scenes,paragraphs),[70,60,380]);
assert.deepEqual(sceneWords(split,paragraphs),[70,60,170,210]);
assert.deepEqual(sceneWords(chapters,paragraphs),[130,380]);
// A scene whose paragraphs were never loaded keeps the count it has.
assert.deepEqual(sceneWords(scenes,paragraphs.slice(0,7)),[70,60,380]);
const unloaded=toggleBoundary(scenes,8,paragraphs.slice(0,7));  // merging into a scene that was never expanded
assert.deepEqual(sceneWords(unloaded,paragraphs.slice(0,7)),[70,440]);

// The front matter joins the first scene and leaves it again, with any boundary placed inside it.
const withFront=setFrontMatter(scenes,[1],true,3);
assert.equal(withFront[0].start,1);
const inner=toggleBoundary(withFront,3,paragraphs);
assert.deepEqual(inner.map(s=>s.start),[1,3,6,8]);
assert.deepEqual(setFrontMatter(inner,[1],false,3).map(s=>[s.start,s.title]),[[3,'Пірс (1)'],[6,'Пірс (2)'],[8,'Шторм']]);
assert.deepEqual(setFrontMatter(scenes,[],true,3),scenes);

// The request body: only the fields the server accepts, scenes in ascending order. `edition` is the preview's field.
const FULL={parts_allowed:true,series_allowed:true,trial:{state:'none',kind:null,id:null,title:null}};
const body=applyBody({fingerprint:'f',title:'Маяк',language:'uk',content_rating:null,scenes:[split[3],split[0],split[2],split[1]],
  parts:[{index:0,paragraph:2,title:'Перша'}],include_front_matter:false,series:null,edition:FULL});
assert.deepEqual(body,{fingerprint:'f',title:'Маяк',language:'uk',content_rating:null,include_front_matter:false,
  scenes:[{start:3,title:'Пірс (1)'},{start:6,title:'Пірс (2)'},{start:8,title:'Шторм'},{start:10,title:'Шторм (2)'}],parts:[]});
const structured=applyBody({fingerprint:'f',title:' Маяк ',language:'en',content_rating:{sexual:0,violence:1,themes:0},
  scenes:[{...scenes[0],part_index:0},{...scenes[1],part_index:1}],parts:[{index:0,paragraph:2,title:'Перша'},{index:1,paragraph:7,title:''}],
  include_front_matter:true,front_matter:[1],series:{series_id:'s1',number:2},edition:FULL});
assert.deepEqual(structured,{fingerprint:'f',title:'Маяк',language:'en',content_rating:{sexual:0,violence:1,themes:0},include_front_matter:true,
  scenes:[{start:1,title:'Пірс (1)',part_index:0},{start:6,title:'Пірс (2)',part_index:1}],  // the front matter opens scene 1
  parts:[{index:0,title:'Перша'},{index:1,title:''}],series:{series_id:'s1',number:2}});
// LONG-PROSE-TRIAL-S07: without long prose parts go only with the trial checkbox (and trial: true) or into the trial
// series; a series only to the trial series; trial and series never together.
const PLAIN={start:3,title:'Пірс (1)'},PARTED={start:3,title:'Пірс (1)',part_index:0},PARTS=[{index:0,title:'Перша'}];
const storeBody=(edition,extra={})=>applyBody({fingerprint:'f',title:'Маяк',language:'uk',content_rating:null,scenes:[{...scenes[0],part_index:0}],
  parts:[{index:0,paragraph:2,title:'Перша'}],include_front_matter:false,series:null,edition,...extra});
const base={fingerprint:'f',title:'Маяк',language:'uk',content_rating:null,include_front_matter:false};
const available={parts_allowed:true,series_allowed:false,trial:{state:'available',kind:null,id:null,title:null}};
const onSeries={parts_allowed:true,series_allowed:true,trial:{state:'used',kind:'series',id:'s1',title:'Сага'}};
const onStory={parts_allowed:false,series_allowed:false,trial:{state:'used',kind:'story',id:'b1',title:'Маяк'}};
assert.deepEqual(storeBody(available),{...base,scenes:[PLAIN],parts:[]});
assert.deepEqual(storeBody(available,{series:{series_id:'s9',number:1}}),{...base,scenes:[PLAIN],parts:[]});
assert.deepEqual(storeBody(available,{trial_checked:true}),{...base,scenes:[PARTED],parts:PARTS,trial:true});
assert.deepEqual(storeBody(available,{trial_checked:true,series:{series_id:'s9',number:1}}),{...base,scenes:[PARTED],parts:PARTS,trial:true});
assert.deepEqual(storeBody(onSeries,{series:{series_id:'s1',number:3}}),{...base,scenes:[PARTED],parts:PARTS,series:{series_id:'s1',number:3}});
assert.deepEqual(storeBody(onSeries,{trial_checked:true}),{...base,scenes:[PLAIN],parts:[]});
assert.deepEqual(storeBody(onSeries),{...base,scenes:[PLAIN],parts:[]});
assert.deepEqual(storeBody(onStory,{series:{series_id:'s1',number:2},trial_checked:true}),{...base,scenes:[PLAIN],parts:[]});
// Without the preview's field (an older server) nothing beyond a flat book is sent.
assert.deepEqual(storeBody(undefined),{...base,scenes:[PLAIN],parts:[]});

// The author changed something only when a boundary or a title differs; the front matter moving the first start does not count.
const {authorEdits}=await import('../../../src/storygen/web/static/manuscript-import.js');
assert.equal(authorEdits(withFront,scenes),false);assert.equal(authorEdits(split,scenes),true);
assert.equal(authorEdits([{...scenes[0],title:'Інша'},...scenes.slice(1)],scenes),true);

// The detected chapter source as the request value.
assert.equal(chapterSourceValue('markers'),'markers');assert.equal(chapterSourceValue('level:2'),'2');assert.equal(chapterSourceValue('none'),'auto');
console.log('Manuscript import boundaries passed');
