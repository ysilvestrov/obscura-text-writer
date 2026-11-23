// Mirror of storygen/roles.py (MODEL-001-S03); tests/test_roles.py keeps the two equal.
export const ROLES=Object.freeze(['planner','writer','editor','memory']);
export const ROLE_STAGE=Object.freeze({planner:'brief',writer:'draft',editor:'edit',memory:'memory'});
export const STAGE_ROLE=Object.freeze({prepare:'planner',brief:'planner',draft:'writer',edit:'editor',memory:'memory'});
// The role whose settings a failed or warned run points to; null for a run without one (MEMORY-CARRY uses no model).
export function runSettingsRole(run){
  if(!run?.request||run.request.mode==='memory_carry')return null;
  if(run.request.mode==='edit_loop')return 'editor';
  const task=run.tasks?.[run.cursor];
  return STAGE_ROLE[task?.stage||run.request.stage||run.request.mode]||null;
}
