// Mirror of storygen/roles.py (MODEL-001-S03); tests/test_roles.py keeps the two equal.
export const ROLES=Object.freeze(['planner','writer','editor','memory','auditor']);
export const ROLE_STAGE=Object.freeze({planner:'brief',writer:'draft',editor:'edit',memory:'memory',auditor:'audit_prose'});
export const ROLE_STAGES=Object.freeze({planner:Object.freeze(['prepare','brief']),writer:Object.freeze(['draft']),editor:Object.freeze(['edit']),memory:Object.freeze(['memory']),auditor:Object.freeze(['audit_brief','audit_prose','audit_memory'])});
export const STAGE_ROLE=Object.freeze({prepare:'planner',brief:'planner',draft:'writer',edit:'editor',memory:'memory',audit_brief:'auditor',audit_prose:'auditor',audit_memory:'auditor'});
// The role of a refused workspace operation: a stage, or a mode without one (the scene check `audit`, the editor loop).
export function operationRole(stage){
  return ({...STAGE_ROLE,edit_loop:'editor',audit:'auditor'})[stage]||null;
}
// The role whose settings a failed or warned run points to; null for a run without one (MEMORY-CARRY uses no model).
export function runSettingsRole(run){
  if(!run?.request||run.request.mode==='memory_carry')return null;
  if(run.request.mode==='edit_loop')return 'editor';
  if(run.request.mode==='audit')return 'auditor';
  const task=run.tasks?.[run.cursor];
  return STAGE_ROLE[task?.stage||run.request.stage||run.request.mode]||null;
}
