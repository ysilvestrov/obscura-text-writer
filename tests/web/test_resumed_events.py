import shutil,subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('scenario',['events','terminal'])
def test_old_failure_event_cannot_disconnect_resumed_run(scenario):
 node=shutil.which('node')
 if not node:pytest.skip('Node required')
 root=Path(__file__).resolve().parents[2]
 result=subprocess.run([node,str(root/'tests/web/js/resumed_run_events.mjs'),scenario,str(root)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
 assert result.returncode==0,result.stderr


def _runs_follow(scenario):
 node=shutil.which('node')
 if not node:pytest.skip('Node required')
 root=Path(__file__).resolve().parents[2]
 result=subprocess.run([node,str(root/'tests/web/js/runs_follow.mjs'),scenario,str(root)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
 assert result.returncode==0,result.stderr


def test_short_run_open_story_keeps_controls_and_draws_only_the_full_run():_runs_follow('open')
def test_short_run_recovered_primary_keeps_controls_and_draws_only_the_full_run():_runs_follow('recover')
def test_short_run_latest_and_proposal_buttons_target_the_right_runs():_runs_follow('latest')
def test_short_run_keeps_state_when_the_detail_fetch_fails():_runs_follow('failure')
def test_review_session_picks_the_protocol_3_run_from_the_short_list():_runs_follow('review')
def test_server_event_refetch_does_not_join_an_older_run_request():_runs_follow('stale')
