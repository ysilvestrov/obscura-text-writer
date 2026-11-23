import assert from 'node:assert/strict';
import {runJumpVisible,jumpTarget,installRunJump} from '../../../src/storygen/web/static/run-jump.js';
// Only run states that wait for the author show the link; active runs do not.
for(const s of ['needs_review','alternative','paused','failed','interrupted'])assert.equal(runJumpVisible(s,false),true,s);
for(const s of ['queued','running','pause_requested','cancellation_requested','completed','cancelled',undefined,null])assert.equal(runJumpVisible(s,false),false,String(s));
// Minimal DOM stand-ins.
const el=(props={})=>({hidden:false,disabled:false,focused:0,scrolled:0,focus(){this.focused++},scrollIntoView(){this.scrolled++},...props});
function doc({buttons=[]}={}){
  const row=el(),link=el({hidden:true,listeners:{},addEventListener(t,f){this.listeners[t]=f}});
  const nodes={'#workspace-status-row':row,'#run-jump':link};
  return {row,link,buttons,querySelector:q=>nodes[q]||null,querySelectorAll:q=>q==='#run-actions button'?buttons:[]};
}
// An enabled run action wins: scroll to the status row, focus the first enabled button.
let d=doc({buttons:[el({disabled:true}),el(),el()]});
let target=jumpTarget(d);assert.equal(target.scroll,d.row);assert.equal(target.focus,d.buttons[1]);
// Hidden buttons are skipped too.
d=doc({buttons:[el({hidden:true}),el()]});assert.equal(jumpTarget(d).focus,d.buttons[1]);
// Nothing usable: scroll to the status row and focus the run summary.
d=doc({buttons:[el({disabled:true})]});const summary=el();d.row.querySelector=q=>q==='.run-summary'?summary:null;
target=jumpTarget(d);assert.equal(target.scroll,d.row);assert.equal(target.focus,summary);
d=doc();let run=null;
const update=installRunJump(d,()=>run);
update();assert.equal(d.link.hidden,true);
run='needs_review';update();assert.equal(d.link.hidden,false);
// Clicking jumps without following the anchor.
let prevented=false;d.buttons.push(el());d.link.listeners.click({preventDefault(){prevented=true}});
assert.equal(prevented,true);assert.equal(d.row.scrolled,1);assert.equal(d.buttons[0].focused,1);
console.log('Run jump link passed');
