"""Read-only presentation of pending inputs and current per-material conclusions."""
from ..storage.impact_validity import current_record


def scene_status(view):
    rows={}
    for scene in view.list_scenes(view.story.id):
        values={}
        for material in ['brief','prose']:
            id=scene.heads.get(material)
            record=current_record(view,id) if id else None
            values[material]=(record.verdict.verdict if record else 'pending' if id and (view.get_version(id).stale or material=='prose' and view.effective_scene(scene.id).needs_review) else 'current' if id else 'missing')
        id=scene.heads.get('memory')
        values['memory']='missing' if not id else 'needs_update' if view.get_version(id).stale else 'current'
        rows[scene.id]=values
    return rows


def public_record(record,current,memory_needs_update=False,delta=None,memory_check_current=False,memory_evidence_status='missing'):
    if record.schema_version==2 and delta:
        delta={'items':[{'explanation':delta['summary'],'evidence':delta.get('evidence',[])}],'uncertainty':delta.get('uncertainty')}
    sources={c.id+':'+side:dict(label=c.label,side=side,author_label=c.input_kind in {'scene','head'} or c.input_kind=='order' and c.owner_id!=record.story_id) for c in record.target.changes for side in ['old','new']}
    return dict(protocol=record.schema_version,proof_count=len(record.proof_attempt_ids),id=record.id,run_id=record.run_id,scene_id=record.target.scene_id,scene_title=record.target.scene_title,
        material=record.target.material,version_id=record.target.version_id,created_at=record.created_at,
        verdict=record.verdict.verdict,explanation=record.verdict.explanation,findings=[f.model_dump() for f in record.verdict.findings],
        sources=sources,delta=delta,current=current,memory_check_current=memory_check_current,memory_evidence_status=memory_evidence_status,memory_semantic_impact=record.memory_semantic_impact,
        memory_explanation=record.memory_explanation,memory_needs_update=memory_needs_update)
