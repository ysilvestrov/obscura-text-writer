"""Read-only annotation checks, including immutable unpublished-source proofs."""
from ..authoring.comments import CommentSet,CommentPayload,validate_comment_set
from ..markdown_document import source_range_text
from .comment_store import proof_path
from .integrity import contained_path


def check_comments(db,report,stories,scenes,versions,verify_file,root):
    revisions={}
    for row in db.execute('SELECT id,story_id,scene_id,material_kind,revision,source_version_id,payload FROM authoring_comment_sets ORDER BY scene_id,revision'):
        try:
            notes=CommentSet.model_validate_json(row[-1])
            if tuple(getattr(notes,key) for key in ['id','story_id','scene_id','material_kind','revision','source_version_id'])!=tuple(row[:-1]):
                raise ValueError('Payload mismatch')
            source=versions.get(notes.source_version_id);scene=scenes.get(notes.scene_id)
            if not source or not scene or notes.story_id not in stories or scene.story_id!=notes.story_id:
                raise ValueError('Unknown owner/source')
            if (source.story_id,source.scene_id,source.kind,source.complete)!=(notes.story_id,notes.scene_id,'draft',True):
                raise ValueError('Source owner/kind')
            if (source.sha256,source.content_format)!=(notes.source_sha256,notes.content_format):raise ValueError('Source metadata')
            CommentPayload.model_validate({'general':notes.general,'comments':[comment.model_dump() for comment in notes.comments]})
            text=contained_path(root,source.relative_path).read_bytes().decode('utf-8')
            validate_comment_set(text,source.content_format,notes)
            for comment in notes.comments:
                anchor=comment.anchor
                if anchor.state!='needs_review':continue
                origin=anchor.origin
                if not origin:raise ValueError('Missing origin')
                if origin.version_id:
                    ref=versions.get(origin.version_id)
                    if not ref or (ref.story_id,ref.scene_id)!=(notes.story_id,notes.scene_id) or not ref.complete or ref.kind not in {'draft','manual','edited'}:
                        raise ValueError('Origin owner')
                    if (ref.sha256,ref.content_format)!=(origin.sha256,origin.content_format):raise ValueError('Origin metadata')
                    relative=ref.relative_path
                else:
                    relative=proof_path(notes.story_id,notes.scene_id,origin.sha256)
                    if origin.relative_path!=relative:raise ValueError('Origin path')
                    verify_file(relative,origin.sha256)
                original=contained_path(root,relative).read_bytes().decode('utf-8')
                if original[anchor.start:anchor.end]!=anchor.source_quote or source_range_text(original,anchor.start,anchor.end,origin.content_format)!=anchor.display_quote:
                    raise ValueError('Origin quote')
            revisions.setdefault(notes.scene_id,[]).append(notes.revision)
        except (ValueError,OSError,KeyError,TypeError):
            report.add('invalid_comment_set',row[0],'Некоректний набір коментарів або його джерело')
    for scene_id,values in revisions.items():
        if values!=list(range(1,max(values)+1)):report.add('comment_history_gap',scene_id,'Історія коментарів має пропущені ревізії')
