"""Read-only semantic journal checks against immutable captured provenance."""
from ..memory.journal import load_memory,validate_memory_journal


def check_memory_versions(report,root,versions):
    from .integrity import contained_path
    for ref in versions.values():
        if ref.kind!='memory':continue
        try:
            journal=load_memory(contained_path(root,ref.relative_path).read_text(encoding='utf-8'))
            sources={}
            owners=[]
            for id in journal.source_prose_ids:
                source=versions.get(id)
                if not source or source.story_id!=ref.story_id or source.kind not in {'manual','edited'} or not source.scene_id:
                    raise ValueError('Невірне джерело пам’яті')
                sources[id]=contained_path(root,source.relative_path).read_text(encoding='utf-8')
                owners.append(source.scene_id)
            if not owners or owners[-1]!=ref.scene_id or len(owners)!=len(set(owners)):
                raise ValueError('Пам’ять не закінчується своєю сценою або повторює сцену')
            validate_memory_journal(journal,sources)
            snapshot=ref.dependency_snapshot
            if snapshot and snapshot.scope=='memory':
                heads={s.owner_id:s.expected for s in snapshot.selectors if s.kind=='head' and s.field=='prose'}
                if owners!=snapshot.scene_order or journal.source_prose_ids!=[heads.get(id) for id in snapshot.scene_order]:
                    raise ValueError('Пам’ять порушує зафіксований префікс сцен')
            else:
                report.limitations.append(ref.id+': історичний порядок legacy-пам’яті без snapshot не доведений; джерела й цитати перевірені.')
        except (ValueError,KeyError,OSError,TypeError):
            report.add('invalid_memory',ref.id,'Некоректний журнал, префікс або доказ пам’яті')
