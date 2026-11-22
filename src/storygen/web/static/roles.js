// Mirror of storygen/roles.py (MODEL-001-S03); tests/test_roles.py keeps the two equal.
export const ROLES=Object.freeze(['planner','writer','editor','memory']);
export const ROLE_STAGE=Object.freeze({planner:'brief',writer:'draft',editor:'edit',memory:'memory'});
export const STAGE_ROLE=Object.freeze({prepare:'planner',brief:'planner',draft:'writer',edit:'editor',memory:'memory'});
