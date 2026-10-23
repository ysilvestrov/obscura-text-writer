import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {installExportForm}=await import(pathToFileURL(root+'/src/storygen/web/static/export-form.js'));
class Element{
 constructor(){this.disabled=false;this.hidden=true;this.children=[];this.value='epub';this.checked=false;}
 setAttribute(k,v){this[k]=v;} focus(){this.focused=true;}
 append(n){this.children.push(n);} replaceChildren(...n){this.children=n;}
}
const nodes={};for(const id of ['export-story','export-form','export-submit','export-status','export-format','export-incomplete','export-cancel','publication-links'])nodes[id]=new Element();
const events={};const document={querySelector:s=>nodes[s.slice(1)],createElement:()=>new Element(),addEventListener:(k,f)=>events[k]=f};
const state={storyId:'story',dirty:false,saving:false,view:{scenes:[{heads:{prose:'id'}}]}};
let calls=0,body,fail=false,release;
installExportForm({state,document,notice(){},json:(method,b)=>b,api:async(url,b)=>{calls++;body=b;if(release)await release;if(fail)throw Error('FB2: оберіть автора');return{download_url:'/book.epub',manifest_url:'/book.manifest.json'};}});
const submit=()=>nodes['export-form'].onsubmit({preventDefault(){}});
assert.equal(nodes['export-story'].disabled,false);nodes['export-story'].onclick();assert.equal(nodes['export-form'].hidden,false);
nodes['export-cancel'].onclick();assert.equal(calls,0);assert.equal(nodes['export-form'].hidden,true);
await submit();assert.equal(calls,1);assert.deepEqual(body,{format:'epub',allow_incomplete:false});
const links=nodes['publication-links'].children;fail=true;await submit();assert.equal(nodes['publication-links'].children,links);assert.match(nodes['export-status'].textContent,/автора/);
state.dirty=true;events['editor-state-changed']();await submit();assert.equal(calls,2);assert.equal(nodes['export-story'].disabled,true);
state.dirty=false;state.saving=true;events['editor-state-changed']();assert.equal(nodes['export-submit'].disabled,true);
state.saving=false;events['editor-state-changed']();let done;release=new Promise(r=>done=r);const pending=submit();await submit();assert.equal(calls,3);done();await pending;
console.log('export explicit form, cancellation, dirty/saving, duplicate and failure preservation passed');
