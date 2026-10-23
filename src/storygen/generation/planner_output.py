"""Narrow planner response envelope and trusted, value-free diagnostics."""
import json
import re
from pydantic import ValidationError
from .models import WritersBrief,StoryBlueprint


class PlannerProtocolError(ValueError):pass


def parse_planner_output(text,stage,warnings):
    content=text.strip()
    fence=re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```',content,re.I|re.S)
    if fence:
        content=fence.group(1)
        warnings.append('Знято одну зовнішню Markdown-обгортку JSON планувальника; оригінальну відповідь збережено без змін.')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise PlannerProtocolError('duplicate_key')
            result[key]=value
        return result
    def invalid(value):raise PlannerProtocolError('non_finite')
    try:json.loads(content,object_pairs_hook=pairs,parse_constant=invalid)
    except RecursionError as exc:raise PlannerProtocolError('too_deep') from exc
    model={'brief':WritersBrief,'prepare':StoryBlueprint}[stage]
    return model.model_validate_json(content),content


FIELDS={'objective','beats','constraints','proposed_changes','canon','characters','scenes','warnings',
        'id','name','description','sources','version_id','quote','title','position','target_words','character_ids'}
TYPES={'json_invalid':'Некоректний JSON','missing':'Відсутнє обов’язкове поле','extra_forbidden':'Зайве поле у JSON','list_type':'Потрібен список',
       'model_type':'Потрібен JSON-об’єкт','string_type':'Потрібен текст','too_short':'Замало елементів',
       'string_too_short':'Порожнє обов’язкове поле','string_too_long':'Перевищено довжину поля',
       'int_type':'Потрібне ціле число','greater_than_equal':'Значення нижче дозволеної межі',
       'less_than_equal':'Значення вище дозволеної межі'}


def planner_failure(exc):
    if isinstance(exc,json.JSONDecodeError):
        return {'category':'json','message':f'Некоректний JSON: рядок {exc.lineno}, стовпець {exc.colno}; потрібен один JSON-об’єкт без пояснень'}
    if isinstance(exc,PlannerProtocolError):
        message={'duplicate_key':'JSON містить повтор ключа','non_finite':'JSON містить недопустиму числову константу',
                 'too_deep':'JSON має надмірну глибину вкладення'}.get(str(exc),'Порушено формат JSON')
        return {'category':'json','message':message}
    if isinstance(exc,ValidationError):
        messages=[]
        for error in exc.errors(include_input=False,include_url=False)[:3]:
            parts=[]
            for part in error['loc']:
                if isinstance(part,str) and part in FIELDS:parts.append(part)
                elif type(part) is int and parts:parts[-1]+=f'[{part+1}]'
            prefix='.'.join(parts)
            messages.append((prefix+': ' if prefix else '')+TYPES.get(error['type'],'Порушено схему планувальника'))
        return {'category':'schema','message':'; '.join(messages) or 'Порушено схему планувальника'}
    return {'category':'publication','message':'Не вдалося перевірити або зберегти результат планувальника; перевірте актуальність джерел і збережену спробу'}
