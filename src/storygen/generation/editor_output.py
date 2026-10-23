"""Narrow response-envelope handling and trusted public editor diagnostics."""
import json
import re

from pydantic import ValidationError

from ..copyediting import CopyEdits,CopyEditAnchorError


class EditorProtocolError(ValueError):
    pass


def parse_editor_output(text,warnings=None):
    content=text.strip()
    warnings=warnings if warnings is not None else []
    fence=re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```',content,re.IGNORECASE|re.DOTALL)
    if fence:
        content=fence.group(1)
        warnings.append('Знято одну зовнішню Markdown-обгортку JSON редактора; оригінальну відповідь збережено без змін.')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:
                raise EditorProtocolError('duplicate_key')
            result[key]=value
        return result
    def invalid(_):
        raise EditorProtocolError('non_finite')
    try:
        payload=json.loads(content,object_pairs_hook=pairs,parse_constant=invalid)
    except RecursionError as exc:
        raise EditorProtocolError('too_deep') from exc
    return CopyEdits.model_validate(payload),warnings


GUARDS={
    'Редактура з diff не може вилучити всю сцену':'Редактор повернув порожній текст замість повної сцени',
    'Редактура з diff: текст перевищує 80000 символів; текст не обрізано':'Перевищено межу diff: 80000 символів; сирий текст збережено без обрізання',
    'Редактура з diff: перевищено 12000 одиниць порівняння; текст не обрізано':'Перевищено межу diff: 12000 одиниць порівняння; сирий текст збережено без обрізання',
    'Редактура з diff: понад 400 змін; потрібен менший фрагмент, текст не обрізано':'Понад 400 змін: потрібен менший фрагмент; сирий текст збережено без обрізання',
    'Редакторська правка не має однозначного дослівного оригіналу':'Неоднозначний або відсутній дослівний якір правки у вказаному фрагменті',
    'Точкова правка не може додавати абзаци':'Заміна додає перенос рядка; точкова правка не може створювати абзаци',
    'Точкова редактура змінила числовий факт':'Правка змінює числовий факт',
    'Точкова редактура змінила заперечення':'Правка змінює заперечення',
    'Точкова правка розширюється до переписування':'Одна правка надмірно розширює оригінал замість локальної заміни',
    'Редакторські правки перетинаються':'Редакторські правки перетинаються',
    'Правки охоплюють понад 35% тексту; потрібна окрема редакторська версія':'Правки охоплюють понад 35% тексту; використайте повну літературну редакцію',
    'Редактура не може вилучити всю сцену':'Редактура вилучає всю сцену',
    'Сукупність правок змінила числовий факт або заперечення':'Сукупність правок змінює числовий факт або заперечення',
}
FIELDS={'edits','fragment_id','original','replacement','category'}
TYPES={'missing':'відсутнє обов’язкове поле','extra_forbidden':'зайве поле',
       'literal_error':'недопустиме значення','list_type':'потрібен список','model_type':'потрібен JSON-об’єкт',
       'string_type':'потрібен текст','string_too_short':'порожнє обов’язкове поле',
       'string_too_long':'перевищено довжину поля','too_long':'перевищено допустиму кількість правок'}


def editor_failure(exc):
    if isinstance(exc,CopyEditAnchorError):
        cause={'fragment_missing':'Модель послалася на відсутній фрагмент',
            'original_missing':'Модель неточно скопіювала дослівний якір original: у фрагменті немає точного збігу',
            'original_ambiguous':'Дослівний якір original повторюється у фрагменті; місце заміни неоднозначне'}[exc.anchor_reason]
        location=f' ({exc.fragment_id})' if exc.fragment_id else ''
        message=f'Правка {exc.edit_index} із {exc.edit_count}{location}: {cause}. Увесь набір відхилено без застосування. Для цієї моделі можна обрати редактуру з diff замість JSON-правок'
        return {'category':'guard','message':message,'edit_index':exc.edit_index,'edit_count':exc.edit_count,
            'fragment_id':exc.fragment_id,'anchor_reason':exc.anchor_reason}
    if str(exc)=='Редактор не запропонував змін':
        return {'category':'no_changes','message':str(exc)+'; прийняття недоступне, поточний текст не змінено'}
    if isinstance(exc,json.JSONDecodeError):
        return {'category':'json','message':f'Некоректний JSON: рядок {exc.lineno}, стовпець {exc.colno}; потрібен один JSON-об’єкт без пояснень'}
    if isinstance(exc,EditorProtocolError):
        message={'duplicate_key':'JSON містить повтор ключа','non_finite':'JSON містить недопустиму числову константу',
                 'too_deep':'JSON має надмірну глибину вкладення; потрібна плоска схема правок'}.get(str(exc),'Порушено формат JSON')
        return {'category':'json','message':message}
    if isinstance(exc,ValidationError):
        messages=[]
        for error in exc.errors(include_input=False,include_url=False)[:3]:
            loc=error['loc'];prefix=''
            if len(loc)>1 and loc[0]=='edits' and type(loc[1]) is int:
                prefix=f'Правка {loc[1]+1}: '
            fields=[part for part in loc if isinstance(part,str) and part in FIELDS and part!='edits']
            if fields:prefix+='.'.join(fields)+': '
            messages.append(prefix+TYPES.get(error['type'],'порушено схему правок'))
        return {'category':'schema','message':'; '.join(messages) or 'Порушено схему правок'}
    if str(exc) in GUARDS:
        return {'category':'guard','message':GUARDS[str(exc)]}
    return {'category':'publication','message':'Не вдалося перевірити або зберегти редакторський результат; перевірте актуальність джерел і спробу'}
