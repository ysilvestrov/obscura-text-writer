import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {restoreSections,rememberSection,SECTIONS_KEY}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/tool-sections.js'));
const section=name=>({dataset:{section:name},open:false});
const memory=()=>{const data={};return {data,getItem:k=>data[k]??null,setItem:(k,v)=>{data[k]=String(v)}}};
// Restores the open sections that were saved; others stay closed.
let store=memory();store.setItem(SECTIONS_KEY,JSON.stringify({scene:true,evaluation:false}));
let items=[section('scene'),section('evaluation')];restoreSections(items,store);
assert.deepEqual(items.map(i=>i.open),[true,false]);
// A toggle is remembered without dropping the other section.
items[1].open=true;rememberSection(items[1],store);
assert.deepEqual(JSON.parse(store.data[SECTIONS_KEY]),{scene:true,evaluation:true});
// Broken JSON or storage that throws: everything stays closed, nothing throws.
store=memory();store.setItem(SECTIONS_KEY,'{not json');items=[section('scene')];restoreSections(items,store);assert.equal(items[0].open,false);
const throwing={getItem(){throw new Error('denied')},setItem(){throw new Error('denied')}};
items=[section('scene')];assert.doesNotThrow(()=>restoreSections(items,throwing));assert.equal(items[0].open,false);
items[0].open=true;assert.doesNotThrow(()=>rememberSection(items[0],throwing));
assert.doesNotThrow(()=>restoreSections([section('scene')],null));
