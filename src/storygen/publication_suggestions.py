"""Provider-independent proposal contracts and exact narrative source stamps."""
import hashlib
import json
import re
from typing import Literal
from pydantic import Field, model_validator
from .domain import DomainModel, RevisionConflict
from .publication_models import PublicationData

FIELDS=('title','annotation','genres','keywords')


class PublicationSuggestions(DomainModel):
    title: str | None = Field(default=None,max_length=300)
    annotation: str | None = Field(default=None,max_length=12000)
    genres: list[str] | None = Field(default=None,max_length=10)
    keywords: list[str] | None = Field(default=None,max_length=30)


class SuggestionAcceptance(DomainModel):
    attempt_id: str
    fingerprint: str
    fields: list[Literal['title','annotation','genres','keywords']] = Field(min_length=1,max_length=4)

    @model_validator(mode='after')
    def unique_fields(self):
        if len(set(self.fields))!=len(self.fields):raise ValueError('Поле пропозиції повторено')
        return self


def eligible_fields(view):
    return [key for key in FIELDS if not (view.effective_title.strip() if key=='title' else getattr(view.card,key))]


def source_stamp(snapshot):
    if not snapshot.scenes:raise ValueError('Немає готової прози для пропозиції')
    scenes=[]
    for scene,ref in snapshot.scenes:
        if ref is None or not ref.complete or ref.stale or scene.needs_review:
            raise ValueError('Для пропозиції потрібна повна актуальна проза всіх активних сцен')
        scenes.append({'scene_id':scene.id,'title':scene.title,'position':scene.position,'version_id':ref.id,'sha256':ref.sha256})
    return {'story_id':snapshot.story.id,'title':snapshot.story.title,'scenes':scenes}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def parse_suggestions(text,eligible,warnings=None):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Повторний ключ JSON')
            result[key]=value
        return result
    def invalid_constant(value):raise ValueError('Нечислова константа JSON')
    try:
        parsed=PublicationSuggestions.model_validate(json.loads(text,object_pairs_hook=pairs,parse_constant=invalid_constant))
        values=parsed.model_dump(exclude_none=True)
        normalized=PublicationData(**values)
        result={key:getattr(normalized,key) for key in values if getattr(normalized,key)}
        if set(result)-set(eligible):raise ValueError('Заповнено чужі поля')
    except (ValueError,TypeError,RecursionError) as exc:
        raise ValueError('Пропозиція метаданих не відповідає JSON, схемі або переліку порожніх полів; сирий текст збережено') from exc
    if not result:raise ValueError('Модель не запропонувала жодного непорожнього поля метаданих; сирий текст збережено')
    labels={'title':'Назва','annotation':'Анотація','genres':'Жанри','keywords':'Ключові слова'}
    if warnings is not None:
        for key in dict.fromkeys([*eligible,*values]):
            if key not in result:
                if key not in eligible:
                    warnings.append(f'Зайве порожнє поле «{labels[key]}» ({key}) пропущено; збережене значення не змінено.')
                else:
                    warnings.append(f'Модель не запропонувала непорожнє поле «{labels[key]}» ({key}); його пропущено. Заповніть його вручну за потреби.'+(' Для FB2 жанр обов’язковий.' if key=='genres' else ''))
    return result


def proposal_content(proposal):
    return {key:proposal[key] for key in ['source_stamp','eligible_fields','suggestions']}


def text_refusal(text):
    # Inspect only a failed model response, never source prose or valid JSON fields.
    from .evaluation.failures import is_text_refusal,refusal_detail
    normalized=re.sub(r"^\s*(?:I'm sorry|I am sorry|Sorry|Вибачте|Перепрошую)[,.!:\s]*(?:but\s+|але\s+)?",'',text,flags=re.I)
    denied=is_text_refusal(normalized) or bool(re.match(
        r"\s*(?:I (?:cannot|can't|am unable to) (?:generate|create|write|provide|suggest)|(?:Я )?не можу (?:створити|написати|згенерувати|запропонувати|надати))\b",normalized,re.I))
    if not denied:return None
    detail=refusal_detail(normalized).model_dump(mode='json')
    detail['message']=detail['message'].replace('Оцінювач','Планувальник')
    return detail


def validate_acceptance(attempt,snapshot,current,incoming,acceptance):
    acceptance=SuggestionAcceptance.model_validate(acceptance)
    proposal=attempt.context.get('publication_proposal')
    if attempt.story_id!=snapshot.story.id or attempt.stage!='publication_suggest' or attempt.state!='completed' or not proposal:
        raise RevisionConflict('Пропозиція не належить твору або не завершена')
    expected=fingerprint(proposal_content(proposal))
    if acceptance.fingerprint!=expected or proposal.get('fingerprint')!=expected:
        raise RevisionConflict('Пропозиція змінилася; перегляньте її знову')
    try:stamp=source_stamp(snapshot)
    except ValueError:raise RevisionConflict('Джерела пропозиції більше не актуальні') from None
    if stamp!=proposal['source_stamp']:raise RevisionConflict('Проза, назви або порядок сцен змінилися; пропозиція застаріла')
    allowed=set(proposal['eligible_fields'])&set(proposal['suggestions'])&set(eligible_fields(snapshot.publication))
    if set(acceptance.fields)-allowed:raise RevisionConflict('Пропозиція не може замінити заповнене поле або поле без поради')
    for key in acceptance.fields:
        if not getattr(incoming,key):raise ValueError('Прийняте поле пропозиції має бути непорожнім')
    return acceptance
