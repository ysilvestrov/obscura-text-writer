"""Public memory errors contain trusted rules/locations, never model values."""
import json
from pydantic import ValidationError

RULES = {
    'Scope дозволено лише для станів': 'character_ids можуть бути непорожніми лише для character_states',
    'Невідомий фрагмент підтвердження пам’яті': 'Невідомий фрагмент підтвердження пам’яті (evidence_id)',
    'Невідомий scope персонажа': 'character_ids містить персонажа поза дозволеним списком сцени',
    'Add не має target, update/retire потребують claim ID': 'Для add потрібен claim_id=null; update/retire потребують чинного claim_id',
    'До трьох add на категорію': 'Перевищено ліміт: до трьох add на категорію',
    'Claim не можна змінювати двічі за відповідь': 'Один claim змінено кілька разів за відповідь',
    'Невідомий, закритий або незмінний claim': 'Update/retire посилається на невідомий, закритий або незмінний claim',
    'Не можна змінювати категорію або scope claim': 'Update/retire змінює категорію або scope чинного claim',
    'Повтор JSON ключа': 'JSON містить повтор ключа',
    'Джерело пам’яті вже враховане': 'Поточне джерело прози вже враховане в попередній пам’яті',
    'Пам’ять повинна посилатися на всі поточні джерела прози': 'Пам’ять не містить очікуваного набору джерел прози',
    'Пам’ять повинна посилатися на всі поточні джерела прози у порядку сцен': 'Порушено набір або порядок джерел прози',
    'Нова пам’ять втратила попередні підтверджені записи': 'Нова пам’ять втратила попередні підтверджені записи',
    'Новий запис потребує підтвердження поточною прозою': 'Новий запис не підтверджений поточною прозою',
    'Запис пам’яті не має дослівного підтвердження у прозі': 'Цитату пам’яті не знайдено дослівно у вихідній прозі',
    'Нова пам’ять змінила журнал попередніх сцен': 'Відповідь змінила журнал попередніх сцен',
    'Немає єдиного зафіксованого джерела прози': 'У спробі немає єдиного зафіксованого джерела прози',
}
FIELDS = {'operations','schema_version','action','category','claim_id','text','character_ids','evidence_id',
          'source_prose_ids','source_version_id','quote','facts','character_states','open_threads','timeline'}
TYPES = {'missing':'Відсутнє обов’язкове поле', 'extra_forbidden':'Зайве поле у JSON',
         'literal_error':'Недопустиме значення поля', 'list_type':'Потрібен список',
         'string_type':'Потрібен текстовий рядок', 'string_too_short':'Порожнє обов’язкове поле',
         'too_long':'Перевищено дозволену кількість елементів'}


def memory_error(exc):
    if isinstance(exc,json.JSONDecodeError):
        return f'Некоректний JSON пам’яті: рядок {exc.lineno}, стовпець {exc.colno}'
    if isinstance(exc,ValidationError):
        messages=[]
        for error in exc.errors(include_input=False,include_url=False)[:3]:
            loc=error['loc'];prefix=''
            if len(loc)>1 and loc[0]=='operations' and type(loc[1]) is int:
                prefix=f'Операція {loc[1]+1}: '
            fields=[str(k) for k in loc if isinstance(k,str) and k in FIELDS and k!='operations']
            if fields:prefix+='.'.join(fields)+': '
            reason=RULES.get(str(error.get('ctx',{}).get('error',''))) or TYPES.get(error['type'],'Порушено правила схеми пам’яті')
            messages.append(prefix+reason)
        return '; '.join(messages) or 'Порушено схему пам’яті'
    return RULES.get(str(exc),'Результат не відповідає схемі, джерелам або правилам збереження пам’яті')
