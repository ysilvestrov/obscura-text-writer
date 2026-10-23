"""Transactional publication metadata. No generation imports or prose mutations."""
import hashlib
from ..domain import RevisionConflict, StorageCorruption, new_id, now
from ..publication_models import (CoverAsset, PublicationCard, PublicationData,
    PublicationSnapshot, PublicationView, PublicSignature)


def signature(db,id):
    row=db.execute('SELECT payload FROM publication_signatures WHERE id=?',(id,)).fetchone()
    if not row:raise KeyError('Публічний підпис відсутній')
    return PublicSignature.model_validate_json(row[0])


def asset(db,story_id,id):
    row=db.execute('SELECT payload FROM publication_assets WHERE id=? AND story_id=?',(id,story_id)).fetchone()
    if not row:raise KeyError('Обкладинка відсутня або належить іншому твору')
    return CoverAsset.model_validate_json(row[0])


def card(db,story_id):
    row=db.execute('SELECT payload FROM story_publications WHERE story_id=?',(story_id,)).fetchone()
    return PublicationCard.model_validate_json(row[0]) if row else PublicationCard(story_id=story_id)


def view(db,story):
    item=card(db,story.id)
    return PublicationView(card=item,effective_title=item.title or story.title,
        authors=[signature(db,id) for id in item.author_ids],
        translators=[signature(db,id) for id in item.translator_ids],
        cover=asset(db,story.id,item.cover_id) if item.cover_id else None)


def publication_snapshot(repo,story_id):
    with repo.db.connection() as db:
        db.execute('BEGIN')
        return _publication_snapshot(repo,db,story_id)


def _publication_snapshot(repo,db,story_id):
    from .context_view import ContextView
    captured=ContextView(repo,db,story_id)
    return PublicationSnapshot(story=captured.story,publication=view(db,captured.story),
        scenes=[(captured.effective_scene(s.id),captured.get_version(s.heads['prose']) if s.heads.get('prose') else None)
                for s in captured.list_scenes(story_id)])


def operation(repo,action,**data):
    if action=='upload_cover':
        from ..publication.covers import image_info
        # Check owner before decoding; repeat under write lock before registration.
        repo.get_story(data['story_id'])
        content,mime,width,height=image_info(data['content'],normalize=True)
        id=new_id(); story_id=data['story_id']; suffix='png' if mime=='image/png' else 'jpg'
        item=CoverAsset(id=id,story_id=story_id,sha256=hashlib.sha256(content).hexdigest(),
            relative_path=f'stories/{story_id}/publication/covers/{id}.{suffix}',mime_type=mime,width=width,height=height)
        with repo.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            repo._active_story(db,story_id)
            repo.files.write(item.relative_path,content)
            db.execute('INSERT INTO publication_assets VALUES(?,?,?,?,?,?,?,?)',
                (id,story_id,item.sha256,item.relative_path,mime,width,height,item.model_dump_json()))
        return item
    with repo.db.connection() as db:
        write=action in {'create_signature','update_signature','save_card'}
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        if action=='list_signatures':
            clause='' if data.get('include_archived') else ' WHERE archived_at IS NULL'
            return [PublicSignature.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM publication_signatures'+clause+' ORDER BY rowid')]
        if action=='create_signature':
            item=PublicSignature(id=new_id(),display_name=data['display_name'])
            db.execute('INSERT INTO publication_signatures VALUES(?,?,?,?)',(item.id,item.revision,item.archived_at,item.model_dump_json()))
            return item
        if action=='update_signature':
            item=signature(db,data['id'])
            if item.revision!=data['expected_revision']:raise RevisionConflict('Підпис змінено в іншому вікні; оновіть довідник')
            payload=item.model_dump()
            if data.get('display_name') is not None:payload['display_name']=data['display_name']
            if data.get('archived') is not None:payload['archived_at']=now() if data['archived'] else None
            payload.update(revision=item.revision+1,updated_at=now())
            item=PublicSignature.model_validate(payload)
            db.execute('UPDATE publication_signatures SET revision=?,archived_at=?,payload=? WHERE id=?',
                (item.revision,item.archived_at,item.model_dump_json(),item.id))
            return item
        if action not in {'get_card','save_card','read_cover'}:raise ValueError('Невідома операція публікації')
        story=repo._active_story(db,data['story_id'])
        if action=='get_card':return view(db,story)
        if action=='read_cover':
            item=asset(db,story.id,data['id'])
            return repo.files.read(item.relative_path,item.sha256),item.mime_type
        current=card(db,story.id)
        if current.revision!=data['expected_revision']:raise RevisionConflict('Картку публікації змінено в іншому вікні; оновіть дані')
        incoming=data['data']
        if not isinstance(incoming,PublicationData):incoming=PublicationData.model_validate(incoming)
        if data.get('suggestion'):
            from ..publication_suggestions import SuggestionAcceptance,validate_acceptance
            from ..domain import StageAttempt
            from ..run_models import Run
            acceptance=SuggestionAcceptance.model_validate(data['suggestion'])
            attempt=repo._get(db,'stage_attempts',acceptance.attempt_id,StageAttempt)
            if attempt.run_id and repo._get(db,'runs',attempt.run_id,Run).state!='completed':
                raise RevisionConflict('Запуск пропозиції не завершено')
            validate_acceptance(attempt,_publication_snapshot(repo,db,story.id),current,incoming,acceptance)
        ids=set(incoming.author_ids+incoming.translator_ids)
        expected=data['expected_signature_revisions']
        if set(expected)!=ids:raise RevisionConflict('Оновіть вибрані публічні підписи')
        previous=set(current.author_ids+current.translator_ids)
        for id in ids:
            person=signature(db,id)
            if person.revision!=expected[id]:raise RevisionConflict('Вибраний підпис змінено; оновіть довідник')
            if person.archived_at and id not in previous:raise ValueError('Не можна додати новий архівований підпис')
        if incoming.cover_id:
            try:item=asset(db,story.id,incoming.cover_id)
            except KeyError:raise ValueError('Обкладинка не належить цьому твору') from None
            repo.files.read(item.relative_path,item.sha256)
        item=PublicationCard(**incoming.model_dump(),story_id=story.id,revision=current.revision+1)
        db.execute('INSERT INTO story_publications VALUES(?,?,?) ON CONFLICT(story_id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',
            (story.id,item.revision,item.model_dump_json()))
        return view(db,story)
