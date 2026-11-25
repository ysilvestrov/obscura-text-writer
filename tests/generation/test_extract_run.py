"""CHARACTER-EXTRACT (R-51): the queue run `character_extract` reads the book in groups (extract_run, Task 5)."""
import hashlib
import json

import pytest

from storygen.billing.models import BudgetError
from storygen.characters.extract import SKIP_CALLS_EXHAUSTED, SKIP_INPUT_LIMIT, SKIP_NO_ANSWER
from storygen.characters.extract_plan import EXTRACT_PLAN_CHANGED, EXTRACT_PROSE_CHANGED, EXTRACT_RUNNING, extract_plan
from storygen.domain import RevisionConflict
from storygen.generation import extract_run
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.worker import RunCoordinator
from storygen.providers.streaming import GenerationEvent
from storygen.run_models import RunRequest
from tests.characters.test_extract_plan import local_role
from tests.generation.test_audit_run import drive
from tests.generation.test_memory_build import written_book

OLYA = json.dumps({'new_cards': [{'key': 'n1', 'name': 'Оля', 'quotes': ['Оля пішла додому']}],
                   'scenes': [{'scene': 's1', 'participants': ['n1']}],
                   'protagonist_candidates': [{'id': 'n1', 'score': 0.6}]}, ensure_ascii=False)
EMPTY = '{}'
BAD = 'не JSON'
PROVIDER_DOWN = ('error', 'Провайдер недоступний')
FILTERED = ('content_filter',)  # the provider stops the answer for its content
REFUSED = ('refusal',)  # the model refuses in words: not JSON, flagged as a refusal


def prose(words, opening='Оля пішла додому.'):
    return opening + ' ' + ' '.join(['слово'] * words) + '.'


class Crash(BaseException):
    """The process dies inside a call: nothing below the worker catches it."""


class Script:
    """One reply per call, in order: a text (a `stop` answer), PROVIDER_DOWN (a provider error event) or an exception
    to raise; `during[i]` runs inside call i before the reply."""

    def __init__(self, *replies, during=None):
        self.replies, self.during, self.contexts = list(replies), during or {}, []

    def stream(self, context, cancel):
        index = len(self.contexts)
        self.contexts.append(context)
        if index in self.during:
            self.during[index]()
        reply = self.replies[min(index, len(self.replies) - 1)]
        if isinstance(reply, BaseException):
            raise reply
        if reply == PROVIDER_DOWN:
            yield GenerationEvent(type='error', message=reply[1], failure={'category': 'technical', 'message': reply[1]})
            return
        if reply == FILTERED:
            yield GenerationEvent(type='delta', text='{')
            yield GenerationEvent(type='terminal', finish_reason='content_filter')
            return
        if reply == REFUSED:
            yield GenerationEvent(type='delta', text='Не можу допомогти з цим.')
            yield GenerationEvent(type='terminal', finish_reason='stop', refusal=True)
            return
        yield GenerationEvent(type='delta', text=reply)
        yield GenerationEvent(type='terminal', finish_reason='stop')


def book(tmp_path, *words):
    """Scenes of `words` words each (the first opens with Оля); local memory role; nothing else."""
    texts = [prose(count) if i == 0 else prose(count, 'Тиша.') for i, count in enumerate(words)]
    return written_book(tmp_path, texts, memory_role=local_role())


def start(repo, story, gateway, group_words=1000, request_id='extract', fingerprint=True):
    worker = RunCoordinator(repo, gateway_factory=lambda _: gateway)
    seen = extract_plan(repo, story.id, group_words)['plan_fingerprint'] if fingerprint else None
    run = worker.enqueue(RunRequest(story_id=story.id, mode='character_extract', group_words=group_words,
                                    extract_plan_fingerprint=seen), request_id)
    return worker, run


def groups(gateway):
    return [json.loads(context.fragments['extract_scene_ids']) for context in gateway.contexts]


def proposal(run):
    assert run.checkpoint['phase'] == 'done', run.checkpoint
    return run.checkpoint['proposal']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_reads_groups_in_order_with_catalogue(tmp_path):
    repo, story, scenes = book(tmp_path, 600, 600)
    gateway = Script(OLYA, EMPTY)
    worker, run = start(repo, story, gateway)
    assert run.tasks == [] and run.checkpoint is None
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    assert groups(gateway) == [[scenes[0].id], [scenes[1].id]]
    assert 'c1: Оля' not in gateway.contexts[0].user_text and 'c1: Оля' in gateway.contexts[1].user_text
    result = proposal(run)
    assert [card['key'] for card in result['cards']] == ['new1'] and result['cards'][0]['name'] == 'Оля'
    assert result['cards'][0]['quotes'] == [{'version_id': scenes[0].heads['prose'], 'scene_id': scenes[0].id,
                                             'quote': 'Оля пішла додому'}]
    assert result['casts'] == [{'scene_id': scenes[0].id, 'mode': 'set', 'participants': ['new1']}]
    assert result['protagonist'] is None  # 0,6 is below the 1,0 threshold
    assert (result['partial'], result['calls'], result['skipped_scenes'], result['cost_usd']) == (False, 2, [], '0.0000')
    sha = {s.id: repo.get_version(s.heads['prose']).sha256 for s in scenes}
    assert result['source'] == {
        'scenes': {s.id: {'version_id': s.heads['prose'], 'sha256': sha[s.id]} for s in scenes},
        'start_cards_version_id': None, 'group_words': 1000}


@pytest.mark.req('CHARACTER-EXTRACT')
def test_existing_cards_seed_the_catalogue(tmp_path):
    from tests.generation.test_memory_build import with_cards
    repo, story, scenes = book(tmp_path, 600)
    story = with_cards(repo, story, 'Оля')
    update = json.dumps({'scenes': [{'scene': 's1', 'participants': ['c1']}]})
    gateway = Script(update)
    worker, run = start(repo, story, gateway)
    result = proposal(drive(worker, run.id))
    assert 'c1: Оля' in gateway.contexts[0].user_text
    assert result['cards'] == [] and result['source']['start_cards_version_id'] == story.characters_version_id
    assert result['casts'] == [{'scene_id': scenes[0].id, 'mode': 'set', 'participants': ['c0']}]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_retry_then_split_then_skip(tmp_path):
    repo, story, scenes = book(tmp_path, 300, 300, 600)  # groups [[s1, s2], [s3]]: calls bound 6
    gateway = Script(BAD, '', BAD, BAD, EMPTY, EMPTY)
    worker, run = start(repo, story, gateway)
    run = drive(worker, run.id)
    a, b, c = (s.id for s in scenes)
    assert run.state == 'completed', run.error
    assert groups(gateway) == [[a, b], [a, b], [a], [a], [b], [c]]
    result = proposal(run)
    assert result['skipped_scenes'] == [{'scene_id': a, 'reason': SKIP_NO_ANSWER}]
    assert (result['partial'], result['calls']) == (False, 6)
    assert set(result['source']['scenes']) == {b, c}  # the skipped scene was not read


@pytest.mark.req('CHARACTER-EXTRACT')
def test_bound_exhausted_completes_partial(tmp_path):
    repo, story, scenes = book(tmp_path, 600, 500, 400)  # groups [[s1], [s2, s3]]: calls bound 6
    gateway = Script(OLYA, BAD)
    worker, run = start(repo, story, gateway)
    run = drive(worker, run.id)
    a, b, c = (s.id for s in scenes)
    assert run.state == 'completed', run.error
    assert groups(gateway) == [[a], [b, c], [b, c], [b], [b], [c]]  # [c] would need its retry: a seventh call
    result = proposal(run)
    assert result['skipped_scenes'] == [{'scene_id': b, 'reason': SKIP_NO_ANSWER},
                                        {'scene_id': c, 'reason': SKIP_CALLS_EXHAUSTED}]
    assert (result['partial'], result['calls']) == (True, 6)
    assert [card['name'] for card in result['cards']] == ['Оля']  # the read groups still count


@pytest.mark.req('CHARACTER-EXTRACT')
def test_calls_never_exceed_bound(tmp_path):
    repo, story, scenes = book(tmp_path, 600)  # one group: calls bound 4
    gateway = Script(PROVIDER_DOWN)
    worker, run = start(repo, story, gateway)
    for _ in range(4):
        run = drive(worker, run.id)
        assert run.state == 'failed' and run.error == 'Провайдер недоступний'
        worker.resume(run.id)
    run = drive(worker, run.id)  # the fifth resume finds the bound spent and makes no call
    assert len(gateway.contexts) == 4 == extract_plan(repo, story.id, 1000)['calls_bound']
    assert run.state == 'completed'
    result = proposal(run)
    assert (result['partial'], result['calls']) == (True, 4)
    assert result['skipped_scenes'] == [{'scene_id': scenes[0].id, 'reason': SKIP_CALLS_EXHAUSTED}]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_interrupted_call_counts_toward_the_bound(tmp_path):
    repo, story, scenes = book(tmp_path, 600, 600)
    gateway = Script(OLYA, Crash(), EMPTY)
    worker, run = start(repo, story, gateway)
    with pytest.raises(Crash):
        drive(worker, run.id)
    assert worker.get_run(run.id).checkpoint['state']['calls'] == 2  # reserved before the call was sent
    worker.recover_interrupted()
    assert worker.get_run(run.id).state == 'interrupted'
    worker.resume(run.id)  # no explicit repeat decision: the group is read again within the bound
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    assert groups(gateway) == [[scenes[0].id], [scenes[1].id], [scenes[1].id]]
    assert proposal(run)['calls'] == 3


@pytest.mark.req('CHARACTER-EXTRACT')
def test_cancel_publishes_partial(tmp_path):
    repo, story, scenes = book(tmp_path, 600, 600)
    holder = {}
    gateway = Script(OLYA, EMPTY, during={1: lambda: holder['worker'].cancel(holder['run'])})
    worker, run = start(repo, story, gateway)
    holder.update(worker=worker, run=run.id)
    run = drive(worker, run.id)
    assert run.state == 'cancelled'
    result = proposal(run)
    assert (result['partial'], result['calls']) == (True, 2)
    assert [card['name'] for card in result['cards']] == ['Оля']
    assert set(result['source']['scenes']) == {scenes[0].id}
    with pytest.raises(ValueError):
        worker.resume(run.id)  # a published proposal ends the run


@pytest.mark.req('CHARACTER-EXTRACT')
def test_cancel_paused_run_publishes_partial(tmp_path):
    repo, story, scenes = book(tmp_path, 600, 600)
    holder = {}
    gateway = Script(OLYA, during={0: lambda: holder['worker'].pause(holder['run'])})
    worker, run = start(repo, story, gateway)
    holder.update(worker=worker, run=run.id)
    assert drive(worker, run.id).state == 'paused'
    run = worker.cancel(run.id)
    assert run.state == 'cancelled'
    result = proposal(worker.get_run(run.id))
    assert result['partial'] is True and [card['name'] for card in result['cards']] == ['Оля']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_pause_resume_continues_next_group(tmp_path):
    repo, story, scenes = book(tmp_path, 600, 600)
    holder = {}
    gateway = Script(OLYA, EMPTY, during={0: lambda: holder['worker'].pause(holder['run'])})
    worker, run = start(repo, story, gateway)
    holder.update(worker=worker, run=run.id)
    run = drive(worker, run.id)
    assert run.state == 'paused'
    assert run.checkpoint['phase'] == 'reading' and run.checkpoint['pending'] == [[scenes[1].id]]
    assert run.checkpoint['state']['calls'] == 1 and run.checkpoint['calls_bound'] == 6
    assert worker.run_readiness(run.id)['calls'] == 5  # what is left of the bound, not a fresh one
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    assert groups(gateway) == [[scenes[0].id], [scenes[1].id]]
    assert 'c1: Оля' in gateway.contexts[1].user_text and proposal(run)['calls'] == 2


def paused_after_first_group(tmp_path):
    repo, story, scenes = book(tmp_path, 600, 600)
    holder = {}
    gateway = Script(OLYA, EMPTY, during={0: lambda: holder['worker'].pause(holder['run'])})
    worker, run = start(repo, story, gateway)
    holder.update(worker=worker, run=run.id)
    assert drive(worker, run.id).state == 'paused'
    return repo, worker, run, scenes, gateway


@pytest.mark.req('CHARACTER-EXTRACT')
def test_resume_after_unread_prose_change_409(tmp_path):
    repo, worker, run, scenes, _ = paused_after_first_group(tmp_path / 'unread')
    save_manual_prose(repo, scenes[1].id, prose(600, 'Інше.'), repo.get_scene(scenes[1].id).revision)
    with pytest.raises(RevisionConflict, match=EXTRACT_PROSE_CHANGED):
        worker.resume(run.id)
    assert worker.get_run(run.id).state == 'paused'
    # A scene already read does not block: acceptance checks it (spec 4.3).
    repo, worker, run, scenes, gateway = paused_after_first_group(tmp_path / 'read')
    save_manual_prose(repo, scenes[0].id, prose(600, 'Інше.'), repo.get_scene(scenes[0].id).revision)
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'completed'
    assert proposal(run)['source']['scenes'][scenes[0].id]['version_id'] == scenes[0].heads['prose']  # what was read


@pytest.mark.req('CHARACTER-EXTRACT')
def test_provider_error_fails_resumable(tmp_path):
    repo, story, scenes = book(tmp_path, 600)
    gateway = Script(BudgetError('Ліміт бюджету вичерпано'), PROVIDER_DOWN, OLYA)
    worker, run = start(repo, story, gateway)
    run = drive(worker, run.id)
    assert (run.state, run.error) == ('failed', 'Ліміт бюджету вичерпано')
    assert run.checkpoint['phase'] == 'reading' and run.checkpoint['state']['skipped'] == []
    assert run.checkpoint['state']['calls'] == 0  # refused before sending: the call is given back to the bound
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert (run.state, run.error) == ('failed', 'Провайдер недоступний')  # not a retry: the scene is not skipped
    assert run.checkpoint['pending'] == [[scenes[0].id]] and run.checkpoint['state']['skipped'] == []
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'completed'
    assert proposal(run)['calls'] == 2 and [card['name'] for card in proposal(run)['cards']] == ['Оля']
    assert len(gateway.contexts) == 3


@pytest.mark.req('CHARACTER-EXTRACT')
@pytest.mark.parametrize('reply', [FILTERED, REFUSED], ids=['content_filter', 'terminal_refusal'])
def test_stream_refusal_splits_then_skips(tmp_path, reply):
    repo, story, scenes = book(tmp_path, 300, 300)  # one group [s1, s2]
    gateway = Script(reply, OLYA)
    worker, run = start(repo, story, gateway)
    run = drive(worker, run.id)
    a, b = (s.id for s in scenes)
    assert run.state == 'completed', run.error
    # The refusal is recorded for this rating: the halves are blocked before the call and spend nothing.
    assert groups(gateway) == [[a, b]]
    result = proposal(run)
    assert result['skipped_scenes'] == [{'scene_id': a, 'reason': SKIP_NO_ANSWER}, {'scene_id': b, 'reason': SKIP_NO_ANSWER}]
    assert result['calls'] == 1


@pytest.mark.req('CHARACTER-EXTRACT')
def test_policy_block_before_the_call_spends_nothing(tmp_path):
    from storygen.authoring.blueprints import get_role_settings
    from storygen.providers.policy import record_refusal
    repo, story, scenes = book(tmp_path, 600)
    gateway = Script(OLYA)
    worker, run = start(repo, story, gateway)
    record_refusal(repo, 'memory', get_role_settings(repo, story.id)['memory'].provider, (0, 0, 0), story_id=story.id,
                   scene_id=None, attempt_id='elsewhere', category='refusal_content')  # not a refusal of this run
    for _ in range(5):  # resuming again and again never spends the bound
        run = drive(worker, run.id)
        assert run.state == 'failed' and 'уже відмовила' in run.error
        assert run.checkpoint['phase'] == 'reading' and run.checkpoint['state']['calls'] == 0
        assert run.checkpoint['state']['skipped'] == [] and run.checkpoint['pending'] == [[scenes[0].id]]
        worker.resume(run.id)
    assert gateway.contexts == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_unfit_group_splits_then_skips_without_call(tmp_path, monkeypatch):
    repo, story, scenes = book(tmp_path, 300, 300)  # one group [s1, s2]
    real = extract_run.build_extract_context

    def narrow(repo_, story_id, settings, state, group, *args, **kwargs):
        if len(group) > 1 or group[0].scene_id == scenes[1].id:
            return SKIP_INPUT_LIMIT
        return real(repo_, story_id, settings, state, group, *args, **kwargs)
    gateway = Script(OLYA)
    worker, run = start(repo, story, gateway)
    monkeypatch.setattr(extract_run, 'build_extract_context', narrow)
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    assert groups(gateway) == [[scenes[0].id]]
    result = proposal(run)
    assert result['skipped_scenes'] == [{'scene_id': scenes[1].id, 'reason': SKIP_INPUT_LIMIT}]
    assert result['calls'] == 1


@pytest.mark.req('CHARACTER-EXTRACT')
def test_plan_changed_before_start_fails(tmp_path):
    repo, story, scenes = book(tmp_path, 600)
    gateway = Script(OLYA)
    worker, run = start(repo, story, gateway)
    save_manual_prose(repo, scenes[0].id, prose(600, 'Інше.'), repo.get_scene(scenes[0].id).revision)
    run = drive(worker, run.id)
    assert (run.state, run.error) == ('failed', EXTRACT_PLAN_CHANGED) and gateway.contexts == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_resume_next_to_active_extract_409(tmp_path):
    repo, worker, run, scenes, _ = paused_after_first_group(tmp_path)
    story = repo.get_story(run.story_id)
    other = worker.enqueue(RunRequest(story_id=story.id, mode='character_extract', group_words=1000), 'second')
    assert other.state == 'queued'  # a paused run does not block a new one
    with pytest.raises(RevisionConflict, match=EXTRACT_RUNNING):
        worker.resume(run.id)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_proposal_fingerprint_stable(tmp_path):
    repo, story, _ = book(tmp_path, 600, 600)
    worker, run = start(repo, story, Script(OLYA, EMPTY))
    result = proposal(drive(worker, run.id))
    body = {key: value for key, value in result.items() if key != 'fingerprint'}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    assert result['fingerprint'] == hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    assert extract_run.proposal_fingerprint(body) == result['fingerprint']
    assert proposal(worker.get_run(run.id))['fingerprint'] == result['fingerprint']
    assert extract_run.proposal_fingerprint({**body, 'calls': 3}) != result['fingerprint']
