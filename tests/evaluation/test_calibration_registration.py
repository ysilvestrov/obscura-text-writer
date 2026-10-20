from storygen.storage.repository import Repository
from storygen.evaluation.models import EvaluatorConfig,ScoringProfile
from storygen.evaluation.story_adapter import install_calibration
from storygen.evaluation.runner import evaluator_fingerprint
from storygen.evaluation.prompting import load_rubric


def test_eligible_calibration_registration_is_global_not_story_bound(tmp_path,monkeypatch):
 config=EvaluatorConfig(provider='codex_cli',model='test-judge',max_input_chars=100000)
 profile=ScoringProfile(version='candidate-v1')
 fingerprint=evaluator_fingerprint(config,load_rubric())
 class Outcome:
  metadata={'evaluator_fingerprint':fingerprint,'snapshots':{'profile':profile.model_dump()},'run_id':'test-run'}
  def model_dump(self):return {'metadata':self.metadata}
 monkeypatch.setattr('storygen.evaluation.calibration.calibrate',lambda *a,**kw:{'eligible':True})
 repo=Repository(tmp_path)
 installed=install_calibration(repo,config,[Outcome()])
 assert installed.calibrated and installed.evaluator_fingerprint==fingerprint
 with repo.db.connection() as db:
  assert db.execute('select count(*) from app_settings where key like ?',('calibration:%',)).fetchone()[0]==1


def test_switching_off_stops_remaining_evaluation_windows(tmp_path,monkeypatch):
 import json
 from storygen.domain import StoryCreate,SceneCreate
 from storygen.generation.dependencies import save_manual_prose
 from storygen.generation.worker import RunCoordinator,RunRequest
 from storygen.evaluation import story_adapter
 from storygen.evaluation.story_adapter import EvaluationSettings,save_evaluation_settings
 from storygen.evaluation.models import GatewayResult
 repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Вікна'));scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(2)]
 for scene in scenes:save_manual_prose(repo,scene.id,'Завершена проза.',scene.revision)
 settings=EvaluationSettings(config=EvaluatorConfig(provider='codex_cli',model='fake',max_input_chars=100000),context_tokens=128000)
 save_evaluation_settings(repo,story.id,settings)
 cases=[story_adapter.build_evaluation_case(repo,story.id,s.id,'scene') for s in scenes]
 monkeypatch.setattr(story_adapter,'plan_evaluation_windows',lambda *_:cases)
 calls=[]
 class Gateway:
  def complete(self,request):
   calls.append(request);settings.policy='off';save_evaluation_settings(repo,story.id,settings)
   data=json.loads(request.messages[1]['content'])
   report={'assessments':[{'criterion_id':k,'status':'assessed','score':4,'explanation':'Перевірено'} for k in data['required_criteria']],'findings':[],'checked_document_ids':[d['id'] for d in data['documents']],'limitations':[]}
   return GatewayResult(text=json.dumps(report),finish_reason='stop')
 worker=RunCoordinator(repo,evaluator_factory=lambda _:Gateway());run=worker.enqueue(RunRequest(story_id=story.id,mode='evaluate',evaluation_mode='story'),'off-between-windows')
 run.state='running';worker._save(run);worker._execute(run.id)
 assert len(calls)==1
 assert worker.get_run(run.id).state=='completed'
 assert any(e.type=='evaluation_skipped' for e in worker.list_events(run.id))
