from fastapi import APIRouter, Request

from .. import build_edition
from ..build_manifest import project_version

router=APIRouter()


@router.get('/api/app-info')
def app_info(request: Request):
    # BUILD-EDITION-001-S05: build edition, its rating limit and interface links; never secrets or settings.
    edition=build_edition.current()
    return {'edition':edition.edition,'max_rating':edition.max_rating.model_dump(),'long_prose':edition.long_prose,'version':project_version(),
        'support_url':edition.support_url,'waitlist_url':edition.waitlist_url,'report_url':edition.report_url,
        'instance_id':request.app.state.instance_id}
