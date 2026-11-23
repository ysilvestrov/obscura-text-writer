// Visible run progress: pure rules that turn the server's run.progress into the texts of the run line. runs.js only renders them.
import {t} from './i18n.js';
import {dollars} from './run-summary.js';

const STAGES=new Set(['brief','draft','edit','memory','evaluate']);
const LINKS=new Set(['brief','prose','memory']);
const stageLabel=stage=>STAGES.has(stage)?t(`run_progress.stage_${stage}`):String(stage??'');

function titleOf(run,progress,scenes){
  const scene=progress.scene,mode=run?.request?.mode,scope=run?.request?.audit_scope;
  const name=(scene?.id&&(scenes||[]).find(item=>item.id===scene.id)?.title)||'—';
  if(mode==='audit'&&scope==='story'){
    if(!scene?.id||scene.index===0)return t('run.mode_audit_book');
    if(Number.isInteger(scene.total)&&scene.index<=scene.total)return t('run_progress.book_scene',{p0:scene.index,p1:scene.total,p2:name});
    return t('run_progress.book_scene_open',{p0:scene.index,p1:name});
  }
  if(mode==='audit')return t('run_progress.scene_audit',{p0:name});
  const stage=progress.step?.stage;
  if(scene?.id)return t('run_progress.generation',{p0:scene.index,p1:scene.total,p2:stageLabel(stage)});
  return t('run_progress.stage_only',{p0:stageLabel(stage)});
}

function countsOf(progress){
  const {calls,spent_usd,spent_known,bound_usd}=progress;
  const parts=[calls?.planned==null?t('run_progress.calls_open',{p0:calls?.done??0}):t('run_progress.calls',{p0:calls.done,p1:calls.planned})];
  const spent=spent_known===false?'$—':dollars(Number(spent_usd));
  if(bound_usd!=null)parts.push(t('run_progress.spent_bound',{p0:spent,p1:dollars(Number(bound_usd))}));
  else if(spent_usd!=='0.0000')parts.push(t('run_progress.spent',{p0:spent}));
  return parts.join(' · ');
}

// null when the server sent no progress (memory_carry, an old run). fraction is null while the call plan is open.
export function progressText(run,progress,scenes){
  if(progress==null)return null;
  const link=progress.step?.link,done=progress.calls?.done,planned=progress.calls?.planned;
  return {
    title:titleOf(run,progress,scenes),
    step:run?.request?.mode==='audit'&&LINKS.has(link)?t(`run_progress.link_${link}`):'',
    counts:countsOf(progress),
    fraction:planned>0?Math.min(1,Math.max(0,done/planned)):null};
}
