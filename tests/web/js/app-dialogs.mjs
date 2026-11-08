import assert from 'node:assert/strict';
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.value='';this.isConnected=true;}
  append(...items){this.children.push(...items)}
  setAttribute(k,v){this[k]=v}
  addEventListener(k,fn){this.listeners[k]=fn}
  remove(){this.isConnected=false}
  focus(){document.activeElement=this}
  showModal(){this.open=true}
  close(){this.open=false;this.listeners.close?.()}
}
const body=new Element('body'),origin=new Element('button');
globalThis.document={body,activeElement:origin,createElement:tag=>new Element(tag)};
const {confirmDialog,promptDialog}=await import('../../../src/storygen/web/static/dialogs.js');
const pending=confirmDialog('Текст <b>');
const dialog=body.children.at(-1);
assert.equal(dialog.open,true);assert.equal(dialog.children[1].textContent,'Текст <b>');
assert.equal(await confirmDialog('Інше'),false,'Concurrent request must not be accepted');
dialog.children[2].children[0].onclick();assert.equal(await pending,false);await Promise.resolve();assert.equal(document.activeElement,origin);
const ok=confirmDialog('Підтвердити');body.children.at(-1).children[2].children[1].onclick();assert.equal(await ok,true);
const cancel=confirmDialog('Escape');body.children.at(-1).listeners.cancel({preventDefault(){}});assert.equal(await cancel,false);
const input=promptDialog('Назва');const box=body.children.at(-1);box.children[2].value='Сцена';box.children[3].children[1].onclick();assert.equal(await input,'Сцена');
console.log('dialog confirmation, cancellation, concurrency, input and focus passed');
