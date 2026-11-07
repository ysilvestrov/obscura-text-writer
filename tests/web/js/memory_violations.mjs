import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
class Element{
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
  append(...items){this.children.push(...items);}
  set innerHTML(_){throw Error('Untrusted text may not become HTML');}
}
globalThis.document={createElement:tag=>new Element(tag)};
const {violationDetails}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/memory-violations.js'));
const uk={'memory.violation.path.response':'Відповідь','memory.violation.path.operation':'Операція {p0}','memory.violation.path.element':'{p0}, елемент {p1}'};
const en={'memory.violation.path.response':'Response','memory.violation.path.operation':'Operation {p0}','memory.violation.path.element':'{p0}, element {p1}'};
const dict={...uk,'memory.violations.title':'Порушення ({p0})','memory.violations.more':'ще {p0}','memory.violation.evidence_unknown':'невідомий доказ','memory.violation.add_limit':'забагато додавань'};
const t=(key,params={})=>(dict[key]??key).replace(/{(p\d+)}/g,(w,n)=>params[n]??w);
assert.equal(violationDetails(undefined,{t}),null);
assert.equal(violationDetails(null,{t}),null);
assert.equal(violationDetails({items:[],total:0},{t}),null);
const items=[{operation:'operations[1]',code:'evidence_unknown'},{operation:'$',code:'add_limit'},{operation:'facts.add[0]',code:'brand_new_code'}];
const box=violationDetails({items,total:3},{t});
assert.equal(box.tag,'details');
const list=box.children.find(c=>c.tag==='ul'),lis=list.children;
assert.equal(lis.length,3);
assert.deepEqual(lis.map(li=>li.textContent),['Операція 2 · невідомий доказ','Відповідь · забагато додавань','facts.add, елемент 1 · brand_new_code']);
const tEn=(key,params={})=>({...dict,...en}[key]??key).replace(/{(p\d+)}/g,(w,n)=>params[n]??w);
const enBox=violationDetails({items:[...items,{operation:'character_states.update[2]',code:'add_limit'},{operation:'weird path',code:'add_limit'}],total:5},{t:tEn});
assert.deepEqual(enBox.children.find(c=>c.tag==='ul').children.map(li=>li.textContent),['Operation 2 · невідомий доказ','Response · забагато додавань','facts.add, element 1 · brand_new_code','character_states.update, element 3 · забагато додавань','weird path · забагато додавань']);
assert.equal(box.children.find(c=>c.tag==='summary').textContent,'Порушення (3)');
const many=Array.from({length:50},(_,i)=>({operation:`operations[${i}]`,code:'add_limit'}));
const big=violationDetails({items:many,total:57},{t}),rows=big.children.find(c=>c.tag==='ul').children;
assert.equal(rows.length,51);assert.equal(rows.at(-1).textContent,'ще 7');
assert.equal(violationDetails({items:many,total:50},{t}).children.find(c=>c.tag==='ul').children.length,50);
console.log('memory violations details passed');
