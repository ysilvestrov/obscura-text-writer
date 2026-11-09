"""Presentation locale; never translate author content or mutate domain state."""
from functools import lru_cache
from importlib.resources import files
import json
import re

SUPPORTED = {'uk', 'en'}


def choose_locale(preference=None, accept_language=''):
    if preference in SUPPORTED:
        return preference
    candidates=[]
    for index, item in enumerate((accept_language or '').split(',')):
        pieces=item.strip().lower().split(';')
        primary=pieces[0].split('-')[0]
        try:
            quality=next((float(p.strip()[2:]) for p in pieces[1:] if p.strip().startswith('q=')),1.0)
        except ValueError:
            continue
        if primary in SUPPORTED and 0 < quality <= 1:
            candidates.append((-quality,index,primary))
    return min(candidates)[2] if candidates else 'uk'


@lru_cache(maxsize=1)
def catalogs():
    return json.loads(files('storygen.web').joinpath('static','i18n.json').read_text(encoding='utf8'))


def translate(key, locale='uk', **params):
    messages=catalogs().get(locale,catalogs()['uk'])
    text=messages.get(key,catalogs()['uk'].get(key,key))
    import re
    return re.sub(r'{(p\d+)}',lambda match:str(params[match[1]]) if match[1] in params else match[0],text)


def request_locale(request):
    return choose_locale(request.cookies.get('obscura_locale'),request.headers.get('accept-language',''))


@lru_cache(maxsize=1)
def _diagnostic_catalog():
    import re
    exact={value:key for key,value in catalogs()['uk'].items() if not re.search(r'{p\d+}',value)}
    patterns=[]
    for key,value in catalogs()['uk'].items():
        names=re.findall(r'{(p\d+)}',value)
        if not names or len(re.sub(r'{p\d+}','',value))<8:
            continue
        parts=re.split(r'{p\d+}',value)
        pattern='^'+r'([\s\S]*?)'.join(re.escape(part) for part in parts)+'$'
        patterns.append((sum(map(len,parts)),re.compile(pattern),key,names))
    return exact,sorted(patterns,key=lambda row:-row[0])


# Catalog parameters that hold a "; "-joined list of other catalog diagnostics.
_LIST_PARAMS={'rating.guard.participants':('p1','; (?=персонаж «)')}


def diagnostic(text,locale='uk'):
    """Only call for application diagnostics, never author fields/documents."""
    if locale=='uk' or not isinstance(text,str):
        return text
    http=re.fullmatch(r'HTTP (\d{3}): ([\s\S]+) Автоматичного повтору немає\.',text) if len(text)<=6000 else None
    if http:return translate('generation.http_failure',locale,p0=http[1],p1=diagnostic(http[2],locale))
    retry=re.fullmatch(r'([\s\S]+) Автоматичного повтору немає\.',text) if len(text)<=6000 else None
    if retry:return translate('generation.no_retry',locale,p0=diagnostic(retry[1],locale))
    exact,patterns=_diagnostic_catalog()
    if text in exact:
        return translate(exact[text],locale)
    if len(text)<=6000:
        for _,pattern,key,names in patterns:
            match=pattern.fullmatch(text)
            if match:
                params=dict(zip(names,match.groups()))
                if key in _LIST_PARAMS:
                    # Application-built list of diagnostics; character names inside stay untranslated.
                    param,separator=_LIST_PARAMS[key]
                    params[param]='; '.join(diagnostic(item,locale) for item in re.split(separator,params[param]))
                return translate(key,locale,**params)
    for prefix,translated in [('Некоректні дані: ','Invalid data: '),('Помилка редактора: ','Editor error: '),('Помилка планувальника: ','Planner error: ')]:
        if text.startswith(prefix):
            return translated+diagnostic(text[len(prefix):],locale)
    return text
