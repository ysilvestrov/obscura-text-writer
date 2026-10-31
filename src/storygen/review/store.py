"""Public domain facade; SQLite transactions belong to storage."""
from ..storage.review_store import prefix,load,latest,current_acceptance


def publish_scene(repo,run_id,report,authority,operation_id,**kwargs):
    return repo.review('publish_scene',run_id=run_id,report=report,authority=authority,operation_id=operation_id,**kwargs)


def save_report(repo,run,report):
    return repo.review('save_report',run=run,report=report)
