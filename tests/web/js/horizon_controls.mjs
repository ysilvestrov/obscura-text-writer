import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {mountHorizonControls}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/horizon-controls.js'));
class Element{
  constructor(tag){this.tag=tag;this.children=[];this.value='';this.listeners={};this.disabled=false}
  append(...nodes){this.children.push(...nodes)}
  addEventListener(type,fn){this.listeners[type]=fn}
}
globalThis.document={createElement:tag=>new Element(tag)};
function form(){const f=new Element('form');f.elements={edit_mode:new Element('select')};return f}
function find(root,name){return root.name===name?root:root.children.map(x=>find(x,name)).find(Boolean)}
const writer=form(),control=mountHorizonControls(writer,'writer',{});
const mode=find(writer,'future_plan_mode'),count=find(writer,'future_plan_count');
assert.equal(mode.value,'all');assert.equal(count.disabled,true);
mode.value='next_n';mode.listeners.change();assert.equal(count.disabled,false);
count.value='0';assert.deepEqual(control.read(),{future_plan_mode:'next_n',future_plan_count:0});
mode.value='current';mode.listeners.change();assert.equal(count.disabled,true);
const editor=form();editor.elements.edit_mode.value='diff';
mountHorizonControls(editor,'editor',{future_plan_mode:'current',future_plan_count:2});
assert.equal(find(editor,'future_plan_mode').disabled,true);
editor.elements.edit_mode.value='prose';editor.elements.edit_mode.listeners.change();
assert.equal(find(editor,'future_plan_mode').disabled,false);
const memory=form();mountHorizonControls(memory,'memory',{});assert.equal(find(memory,'future_plan_mode'),undefined);
console.log('Horizon controls: count, editor mode, memory isolation passed');
