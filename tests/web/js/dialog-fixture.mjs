// Test-only DOM shim: answer the application dialog through each fixture's confirm callback.
export function installDialogFixture(doc){
  class Node {
    constructor(){this.children=[];this.listeners={};this.isConnected=true;}
    append(...items){this.children.push(...items)} setAttribute(){} addEventListener(name,fn){this.listeners[name]=fn}
    showModal(){queueMicrotask(()=>{const accepted=globalThis.confirm(this.children[1].textContent);const actions=this.children.at(-1);actions.children[accepted?1:0].onclick();})}
    close(){this.listeners.close?.()} remove(){this.isConnected=false} focus(){}
  }
  const create=doc.createElement?.bind(doc);let constructing=false;
  doc.body={append(){constructing=false}};
  doc.createElement=tag=>{if(tag==='dialog'){constructing=true;return new Node()}return constructing?new Node():create(tag)};
}
