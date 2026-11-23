"""Registry of model roles (MODEL-001). Every role list and role/stage map imports from here.

`web/static/roles.js` mirrors ROLES, ROLE_STAGE, STAGE_ROLE and ROLE_STAGES for the browser; tests/test_roles.py keeps them equal.
"""

ROLES = ('planner', 'writer', 'editor', 'memory', 'auditor')
# For set arithmetic; membership checks and sorted() work on ROLES directly.
ROLE_SET = frozenset(ROLES)
# Role -> the scene stage whose prompt the role's settings carry (the auditor's main prompt is audit_prose).
ROLE_STAGE = {'planner': 'brief', 'writer': 'draft', 'editor': 'edit', 'memory': 'memory', 'auditor': 'audit_prose'}
# Role -> every stage whose prompt the role owns.
ROLE_STAGES = {'planner': ('prepare', 'brief'), 'writer': ('draft',), 'editor': ('edit',), 'memory': ('memory',),
               'auditor': ('audit_brief', 'audit_prose', 'audit_memory')}
# Scene pipeline stage -> role that runs it.
STAGE_ROLE = {'prepare': 'planner', 'brief': 'planner', 'draft': 'writer', 'edit': 'editor', 'memory': 'memory',
              'audit_brief': 'auditor', 'audit_prose': 'auditor', 'audit_memory': 'auditor'}
# UI catalog keys (i18n.json) for the role name on the settings role buttons.
ROLE_LABEL_KEYS = {'planner': 'm_38c94c25c4af', 'writer': 'm_75515c07207a', 'editor': 'm_65d42cf1679c', 'memory': 'm_aa1cfb48cc30',
                   'auditor': 'm_2a1a4e4b0a6f'}
ROLE_LABELS = {'planner': 'Планувальник', 'writer': 'Письменник', 'editor': 'Редактор', 'memory': 'Пам’ять', 'auditor': 'Ревізор'}
