"""Offline verification of immutable review reports and author authority."""
import json
from ..review.store import load,prefix
from ..review.proofs import verify_report
from ..impact.models import fingerprint,TEXT_STAMP_EXCLUDE
from .integrity import contained_path


def check_reviews(db,report,stories,scenes,versions,root):
    owners={key.split(':')[1] for key, in db.execute("SELECT key FROM app_settings WHERE key LIKE 'review3:%' OR key LIKE 'review4:%' OR key LIKE 'review-authority:%'") if len(key.split(':'))>=2}
    for owner in owners:
        try:
            if owner not in stories:raise ValueError('Невідомий власник review')
            reports,acceptances,operations,proofs=load(db,owner)
            from .review_authority import load as load_authority
            policies,_=load_authority(db,owner)
            if any(scene_id not in scenes or scenes[scene_id].story_id!=owner for scene_id,material in policies):raise ValueError('Стороння область авторського пріоритету')
            def target(t):
                ref=versions[t.version_id]
                if ref.story_id!=owner or ref.scene_id!=t.scene_id or t.scene_id not in scenes or ref.sha256!=t.sha256 or not ref.complete:raise ValueError('Невідповідне джерело review')
                if fingerprint(t.model_dump(exclude=TEXT_STAMP_EXCLUDE))!=t.fingerprint:raise ValueError('Змінено snapshot review')
                if contained_path(root,ref.relative_path).read_bytes().decode('utf-8')!=t.text:raise ValueError('Текст review змінено')
                for id,sha in t.source_hashes.items():
                    if versions[id].story_id!=owner or versions[id].sha256!=sha:raise ValueError('Змінено source review')
            for r in reports.values():
                if scenes[r.scene_id].story_id!=owner:raise ValueError('Стороння сцена review')
                run=db.execute('SELECT payload FROM runs WHERE id=?',(r.run_id,)).fetchone()
                if not run or json.loads(run[0])['story_id']!=owner:raise ValueError('Сторонній run review')
                for t in r.targets:target(t)
                verify_report(r,proofs,lambda path:contained_path(root,path).read_bytes().decode('utf-8'))
            for a in acceptances:
                r=reports[a.report_id];target(a.target)
                if a.run_id!=r.run_id or a.scene_id!=r.scene_id:raise ValueError('Стороннє прийняття review')
                op=operations[a.operation_id]
                if not any(value==a.model_dump() for value in op['result']['acceptances']):raise ValueError('Прийняття без operation proof')
                if a.authority=='model_no_concerns' and r.concerns:raise ValueError('Автоматичне прийняття має зауваження')
                if a.authority=='author_rejected' and (set(op.get('dispositions',{}))!={c.id for c in r.concerns} or any(v!='reject' for v in op['dispositions'].values())):raise ValueError('Відхилення без авторських рішень')
        except (ValueError,KeyError,TypeError,OSError,IndexError):report.add('invalid_review',prefix(owner),'Некоректний звіт послідовного перегляду, джерела або підстава прийняття')
