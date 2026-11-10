import assert from 'node:assert/strict';
let failShow=false;
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.value='';this.isConnected=true;}
  append(...items){this.children.push(...items)}
  setAttribute(k,v){this[k]=v}
  addEventListener(k,fn){this.listeners[k]=fn}
  remove(){this.isConnected=false}
  focus(){document.activeElement=this}
  showModal(){if(failShow)throw Error('show failed');this.open=true}
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
const cancelledInput=promptDialog('Назва');body.children.at(-1).children[3].children[0].onclick();assert.equal(await cancelledInput,null);
const escapedInput=promptDialog('Назва');body.children.at(-1).listeners.cancel({preventDefault(){}});assert.equal(await escapedInput,null);
const entered=promptDialog('Назва');const enteredBox=body.children.at(-1);enteredBox.children[2].value='Друга';enteredBox.children[2].listeners.keydown({key:'Enter',preventDefault(){}});assert.equal(await entered,'Друга');
const empty=promptDialog('Назва');body.children.at(-1).children[3].children[1].onclick();assert.equal(await empty,'');
failShow=true;assert.equal(await confirmDialog('Помилка'),false);failShow=false;
const afterFailure=confirmDialog('Працює');body.children.at(-1).children[2].children[1].onclick();assert.equal(await afterFailure,true,'A failed open does not block later dialogs');
const named=confirmDialog('Вийти?',{accept:'Видалити написане',cancel:'Продовжити писати'});const namedBox=body.children.at(-1);
assert.deepEqual(namedBox.children[2].children.map(b=>b.textContent),['Продовжити писати','Видалити написане'],'Named actions replace the generic labels');
namedBox.children[2].children[0].onclick();assert.equal(await named,false);
console.log('dialog named actions, cancellation, input, Enter, failure recovery and focus passed');
