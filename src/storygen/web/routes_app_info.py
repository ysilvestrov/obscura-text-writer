from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, Request

from .. import build_edition

router=APIRouter()


def _version() -> str:
    try:return version('storygen')
    except PackageNotFoundError:return '0.0.0'


@router.get('/api/app-info')
def app_info(request: Request):
    # BUILD-EDITION-001-S05: build edition, its rating limit and interface links; never secrets or settings.
    edition=build_edition.current()
    return {'edition':edition.edition,'max_rating':edition.max_rating.model_dump(),'version':_version(),
        'support_url':edition.support_url,'waitlist_url':edition.waitlist_url,'report_url':edition.report_url,
        'instance_id':request.app.state.instance_id}
