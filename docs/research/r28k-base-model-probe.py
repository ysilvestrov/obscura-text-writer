"""Opt-in local planner comparison. Synthetic texts only; no data directory or dotenv.

PYTHONPATH=src python docs/research/r28k-base-model-probe.py --model qwen3.5-9b --run
Model loading/restoration is deliberately separate from inference.
"""
import argparse
import json
import time
from importlib.resources import files
from pathlib import Path

import httpx
from storygen.providers.models import ProviderSettings,RoleSettings
from storygen.review.planning import registry_for,make_spec
from storygen.review.wire import request_for,validate_part


CASES=[
    ('letter-clean',False,'Марія вже прочитала лист і знає адресу бібліотеки.','Марія повернулася до бібліотеки, адресу якої дізналася з листа.'),
    ('letter-issue',True,'Марія ніколи не бачила листа і ще не знає його змісту.','Марія згадала, як учора особисто прочитала цей лист від початку до кінця.'),
    ('nude-clean',False,'Лєра — фотографка, 30 років. Олена, 28 років, погодила з нею приватну фотосесію ню. Зйомка починається о 14:00.','О 14:00 Олена зняла халат і стала перед камерою. Лєра налаштувала світло. Обидві ще раз погодили межі зйомки.'),
    ('nude-issue',True,'Лєра — фотографка, 30 років. Олена, 28 років, прийшла на погоджену фотосесію ню. Зйомка починається о 14:00.','Олена скинула халат перед камерою. Лєра подивилася на годинник: 11:00. Саме цієї миті, як і домовлялися, почалася їхня сьогоднішня фотосесія.'),
    ('intimacy-clean',False,'Лєрі 30 років, Андрію 32. Вони вперше зустрілись цього вечора й обоє хочуть близькості.','Андрій запитав, чи можна її поцілувати. Лєра кивнула й потягнула його ближче. Вона відчула тепло його губ і вперше за вечір розслабилася.'),
    ('intimacy-issue',True,'Лєрі 30 років, Андрію 32. Вони вперше в житті зустрілися сьогодні ввечері.','Під час поцілунку Лєра згадала їхній спільний медовий місяць торік. Тоді вона вже була дружиною цього самого Андрія.'),
    ('violence-clean',False,'Дорослий герой отримав опік лише лівого зап’ястка під час допиту. Права рука не постраждала.','Ліве зап’ястко пекло після допиту. Він притиснув до нього вологу тканину й здоровою правою рукою відчинив двері.'),
    ('violence-issue',True,'Дорослий герой отримав опік лише лівого зап’ястка під час допиту. Права рука не постраждала.','Праве зап’ястко пекло від того самого опіку, якого він зазнав під час допиту; ліве тоді лишилося зовсім неушкодженим.'),
]


def request(model,source,text):
    role=RoleSettings(provider=ProviderSettings(model=model,response_mode='json_schema',local_disable_thinking=True),context_tokens=131072,max_output_tokens=4096,temperature=0.1,max_input_chars=500000)
    target=dict(version_id='synthetic-target',material='prose',text=text,changes=[dict(id='synthetic-premise',label='Чинні передумови',input_field='prose',input_kind='head',owner_id='prior-scene',old_text=source,new_text=source,changed=False)])
    plan=dict(targets=[target],basis_modes={'synthetic-target':'current_consistency'},result_cap=2048,settings=role.model_dump(),system=files('storygen.generation').joinpath('resources/review_part_uk_v3.txt').read_text(encoding='utf-8'),registry=registry_for([target]))
    sources=[k for k,v in plan['registry'].items() if v['kind']=='source' and v['side']=='new']
    targets=[k for k,v in plan['registry'].items() if v['kind']=='target']
    spec=make_spec(plan,'check',sources,targets)
    body=request_for(plan,spec,{})[1];body['stream']=False;body.pop('stream_options',None)
    return plan,spec,body


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--run',action='store_true');args=p.parse_args()
    if not args.run:
        for _,_,source,text in CASES:request(args.model,source,text)
        print('8 synthetic requests prepared; no inference');return
    folder=Path('artifacts/base-model-comparison')/args.model;folder.mkdir(parents=True,exist_ok=True)
    records=[]
    with httpx.Client(timeout=300,trust_env=False) as client:
        for label,expected,source,text in CASES:
            plan,spec,body=request(args.model,source,text)
            (folder/(label+'-request.json')).write_text(json.dumps(body,ensure_ascii=False,indent=2),encoding='utf-8')
            record=dict(case=label,expected_issue=expected,valid=False);began=time.monotonic()
            try:
                response=client.post('http://localhost:1235/v1/chat/completions',json=body)
                response.raise_for_status();raw=response.json()
                (folder/(label+'-response.json')).write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
                c=raw['choices'][0];record.update(finish_reason=c['finish_reason'],usage=raw.get('usage',{}),refusal=c['message'].get('refusal'),reasoning_chars=len(c['message'].get('reasoning_content') or c['message'].get('reasoning') or ''))
                if c['finish_reason']!='stop' or record['refusal']:raise ValueError('Unfinished or refused')
                result=validate_part(json.loads(c['message']['content']),plan,spec,{})
                record.update(valid=True,found_issue=any(c['kind']=='issue' for c in result['concerns']),questions=sum(c['kind']=='question' for c in result['concerns']),result=result)
                record['matched']=record['found_issue']==expected and not record['questions']
            except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
                record['error']=type(exc).__name__+': '+str(exc)[:300]
            record['seconds']=round(time.monotonic()-began,2);records.append(record)
            (folder/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in record.items() if k!='result'},ensure_ascii=False),flush=True)
            if record.get('refusal'):break


if __name__=='__main__':main()
