"""Append-only annotations and atomic draft/notes publication."""
import hashlib

from ..authoring.comments import CommentPayload,CommentSet,Comment,CommentOrigin,validate_comment_set,comment_fingerprint
from ..domain import RevisionConflict,VersionRef,new_id
from ..markdown_document import source_range_text


def proof_path(story_id,scene_id,digest):
    # Short, deterministic scene+source key; full SHA is always verified on read.
    # The full scene/SHA path plus atomic-write suffix exceeds Windows MAX_PATH.
    key=hashlib.sha256((scene_id+':'+digest).encode()).hexdigest()[:32]
    return f'stories/{story_id}/c/{key}.txt'


def _latest(db,scene_id,id=None):
    row=db.execute('SELECT payload FROM authoring_comment_sets WHERE scene_id=?'+(' AND id=?' if id else '')+' ORDER BY revision DESC LIMIT 1',
                   (scene_id,id) if id else (scene_id,)).fetchone()
    return CommentSet.model_validate_json(row[0]) if row else None


def get_comment_set(repo,scene_id,id=None):
    with repo.db.connection() as db:
        scene=repo._active_scene(db,scene_id);repo._active_story(db,scene.story_id)
        return _latest(db,scene_id,id)


def get_comment_state(repo,scene_id):
    with repo.db.connection() as db:
        db.execute('BEGIN')
        scene=repo._active_scene(db,scene_id);repo._active_story(db,scene.story_id)
        notes=_latest(db,scene_id);current=scene.heads.get('draft')
        ref=repo._get(db,'versions',current,VersionRef) if current else None
        matches=not notes or ref is not None and (notes.source_version_id,notes.source_sha256,notes.content_format)==(ref.id,ref.sha256,ref.content_format)
        source=repo._get(db,'versions',notes.source_version_id,VersionRef) if notes else None
        return {'scene':scene,'comment_set':notes,'expected_comments_revision':notes.revision if notes else 0,
                'source_version_id':current,'source_matches_current':matches,
                'comment_fingerprint':comment_fingerprint(notes,source) if notes else None}


def read_origin(repo,story_id,scene_id,origin):
    if origin.version_id:
        ref=repo.get_version(origin.version_id)
        if ref.story_id!=story_id or ref.scene_id!=scene_id or ref.kind not in {'draft','edited','manual'} or not ref.complete:
            raise ValueError('Джерело коментаря належить іншому матеріалу')
        if (ref.sha256,ref.content_format)!=(origin.sha256,origin.content_format):raise ValueError('Метадані джерела коментаря не збігаються')
        return repo.read_text(ref.id)
    if origin.relative_path!=proof_path(story_id,scene_id,origin.sha256):
        raise ValueError('Неприпустимий шлях джерела коментаря')
    return repo.files.read(origin.relative_path,origin.sha256).decode('utf-8')


def _resolve_comments(repo,scene,source_ref,payload):
    comments=[];proof_writes={}
    for comment in payload.comments:
        anchor=comment.anchor
        data=anchor.model_dump(exclude={'origin_source'})
        if anchor.state=='needs_review':
            if anchor.origin_source:
                proof=anchor.origin_source;raw=proof.text.encode('utf-8');digest=hashlib.sha256(raw).hexdigest()
                origin=CommentOrigin(relative_path=proof_path(scene.story_id,scene.id,digest),sha256=digest,content_format=proof.content_format)
                proof_writes[origin.relative_path]=(raw,digest)
                original=proof.text
            elif anchor.origin:
                origin=anchor.origin;original=read_origin(repo,scene.story_id,scene.id,origin)
            elif source_ref:
                origin=CommentOrigin(version_id=source_ref.id,sha256=source_ref.sha256,content_format=source_ref.content_format)
                original=repo.read_text(source_ref.id)
            else:raise ValueError('Потрібне початкове джерело зміненого коментаря')
            if original[anchor.start:anchor.end]!=anchor.source_quote or source_range_text(original,anchor.start,anchor.end,origin.content_format)!=anchor.display_quote:
                raise ValueError('Початкова цитата коментаря не відповідає джерелу')
            data['origin']=origin.model_dump()
        elif anchor.origin_source:
            raise ValueError('Чинний коментар не повинен мати історичне джерело')
        comments.append(Comment(id=comment.id,instruction=comment.instruction,anchor=data))
    for relative,(raw,digest) in proof_writes.items():
        path=repo.files.resolve(relative)
        if path.exists():repo.files.read(relative,digest)
        else:repo.files.write(relative,raw)
    return comments


def _insert_comment_set(db,notes):
    db.execute('INSERT INTO authoring_comment_sets VALUES(?,?,?,?,?,?,?)',
        (notes.id,notes.story_id,notes.scene_id,notes.material_kind,notes.revision,notes.source_version_id,notes.model_dump_json()))


def _same_notes(left,right):
    keys={'source_version_id','source_sha256','content_format','general','comments'}
    return left is not None and left.model_dump(include=keys)==right.model_dump(include=keys)


def save_draft_with_comments(repo,scene_id,text,content_format,expected_revision,expected_comments_revision,payload,*,expected_source_version_id):
    if not text.strip():raise ValueError('Чернетка не може бути порожньою')
    if content_format not in {'plain','markdown'}:raise ValueError('Невідомий формат авторського тексту')
    payload=CommentPayload.model_validate(payload.model_dump() if isinstance(payload,CommentPayload) else payload)
    if type(expected_comments_revision) is not int or expected_comments_revision<0:raise ValueError('Потрібна ревізія коментарів')
    scene=repo.get_scene(scene_id)
    if scene.revision!=expected_revision or scene.heads.get('draft')!=expected_source_version_id:
        raise RevisionConflict('Чернетку вже змінено; збережіть робочий текст окремо')
    previous_ref=repo.get_version(expected_source_version_id) if expected_source_version_id else None
    if previous_ref and (previous_ref.story_id!=scene.story_id or previous_ref.scene_id!=scene.id or previous_ref.kind!='draft' or not previous_ref.complete):
        raise ValueError('Неприпустиме джерело коментарів')
    validate_comment_set(text,content_format,payload)
    comments=_resolve_comments(repo,scene,previous_ref,payload)
    changed=not previous_ref or previous_ref.content_format!=content_format or repo.read_text(previous_ref.id)!=text
    ref=previous_ref
    if changed:
        from ..memory.forwarding import hidden_before
        policy=sorted(hidden_before(repo.context_view(scene.story_id),scene_id))
        id=new_id();raw=text.encode('utf-8')
        ref=VersionRef(id=id,story_id=scene.story_id,scene_id=scene_id,kind='draft',content_format=content_format,
            sha256=hashlib.sha256(raw).hexdigest(),relative_path=f'stories/{scene.story_id}/versions/{id}.txt',manual_projection_policy=policy)
        repo.files.write(ref.relative_path,raw)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current=repo._active_scene(db,scene_id);repo._active_story(db,current.story_id)
        latest=_latest(db,scene_id)
        if current.revision!=expected_revision or current.heads.get('draft')!=expected_source_version_id:
            raise RevisionConflict('Чернетку вже змінено; збережіть робочий текст окремо')
        if (latest.revision if latest else 0)!=expected_comments_revision:
            raise RevisionConflict('Коментарі змінено в іншій вкладці; оновіть їх перед збереженням')
        if changed:
            db.execute('INSERT INTO versions VALUES(?,?,?,?,?)',(ref.id,ref.story_id,ref.scene_id,ref.kind,ref.model_dump_json()))
            current.heads['draft']=ref.id;current.head_revisions['draft']=current.head_revisions.get('draft',0)+1;current.revision+=1
            repo._save_scene(db,current)
            if previous_ref:
                from .invalidation import invalidate_in_transaction
                invalidate_in_transaction(repo,db,[previous_ref.id],exclude=[ref.id])
            repo._touch_story(db,current.story_id)
        notes=CommentSet(story_id=scene.story_id,scene_id=scene.id,revision=expected_comments_revision+1,
            source_version_id=ref.id,source_sha256=ref.sha256,content_format=ref.content_format,general=payload.general,comments=comments)
        if _same_notes(latest,notes):notes=latest
        elif latest is None and not notes.general and not notes.comments:notes=None
        else:_insert_comment_set(db,notes)
    return {'scene':repo.get_scene(scene_id),'version':ref,'comment_set':notes}
