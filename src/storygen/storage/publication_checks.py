"""Readonly schema3 metadata and cover checks, including archived owners."""
from ..publication_models import CoverAsset, PublicationCard, PublicSignature


def check_publications(db,report,stories,verify_file,root):
    from .integrity import contained_path
    signatures={}; assets={}
    for id,revision,archived,payload in db.execute('SELECT id,revision,archived_at,payload FROM publication_signatures'):
        try:
            item=PublicSignature.model_validate_json(payload)
            if (item.id,item.revision,item.archived_at)!=(id,revision,archived):raise ValueError()
            signatures[id]=item
        except (ValueError,TypeError):report.add('invalid_publication',id,'Невірний публічний підпис або ревізія')
    for row in db.execute('SELECT id,story_id,sha256,relative_path,mime_type,width,height,payload FROM publication_assets'):
        try:
            item=CoverAsset.model_validate_json(row[-1])
            if tuple(item.model_dump()[key] for key in ['id','story_id','sha256','relative_path','mime_type','width','height'])!=tuple(row[:-1]) or item.story_id not in stories:
                raise ValueError()
            assets[item.id]=item
            verify_file(item.relative_path,item.sha256)
            from ..publication.covers import image_info
            try:
                info=image_info(contained_path(root,item.relative_path).read_bytes())
                if info!=(item.mime_type,item.width,item.height):raise ValueError('Невірні розміри/тип')
            except ValueError as exc:
                if 'Pillow' in str(exc):report.limitations.append('Обкладинки: не перевірено декодування без Pillow; хеші перевірені.')
                else:raise
        except (ValueError,TypeError,OSError):report.add('invalid_publication',str(row[0]),'Некоректний ресурс обкладинки')
    for story_id,revision,payload in db.execute('SELECT story_id,revision,payload FROM story_publications'):
        try:
            item=PublicationCard.model_validate_json(payload)
            if item.story_id!=story_id or item.revision!=revision or story_id not in stories:raise ValueError()
            if set(item.author_ids+item.translator_ids)-set(signatures):raise ValueError()
            if item.cover_id and (item.cover_id not in assets or assets[item.cover_id].story_id!=story_id):raise ValueError()
        except (ValueError,TypeError):report.add('invalid_publication',story_id,'Некоректна картка або власність її посилань')
