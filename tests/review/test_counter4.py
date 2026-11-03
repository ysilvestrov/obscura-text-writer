from tests.review.test_runner import fixture
from storygen.review.readiness import readiness
from storygen.run_models import RunRequest
from tests.review.counter4 import activate_counter4


def test_new_local_prompt_requires_its_own_qualified_counter(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path)
    worker.cancel(run.id)
    request=RunRequest(story_id=story.id,mode='impact',impact_protocol=3,review_contract_version=4)
    before=readiness(repo,request)
    assert not before['ready'] and 'лічильник' in before['reason']
    profile=activate_counter4(repo,second.id)
    assert readiness(repo,request)['ready']
    (repo.root/'local_tokenizers'/profile['id']/'chat-template.txt').write_text('tampered',encoding='utf-8')
    assert not readiness(repo,request)['ready']
    assert not calls
