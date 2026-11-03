"""Versioned author instructions, separate from prose and evidence memory."""
import hashlib
import json
from typing import Literal

from pydantic import Field,model_validator

from ..domain import DomainModel,new_id,now
from ..markdown_document import source_range_text


class OriginSource(DomainModel):
    text: str = Field(max_length=160000)
    content_format: Literal['plain','markdown'] = 'plain'


class CommentOrigin(DomainModel):
    version_id: str | None = Field(default=None,min_length=1,max_length=128)
    relative_path: str | None = Field(default=None,min_length=1,max_length=1000)
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    content_format: Literal['plain','markdown']

    @model_validator(mode='after')
    def one_source(self):
        if bool(self.version_id)==bool(self.relative_path):raise ValueError('Потрібне одне джерело коментаря')
        return self


class CommentAnchor(DomainModel):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    source_quote: str = Field(min_length=1,max_length=160000)
    display_quote: str = Field(min_length=1,max_length=160000)
    state: Literal['valid','needs_review'] = 'valid'
    reason: str | None = Field(default=None,max_length=1000)
    origin: CommentOrigin | None = None

    @model_validator(mode='after')
    def ordered(self):
        if self.end<=self.start:raise ValueError('Порожній або зворотний діапазон коментаря')
        if self.state=='valid' and self.origin:raise ValueError('Чинний коментар не повинен мати історичне джерело')
        return self


class InputAnchor(CommentAnchor):
    origin_source: OriginSource | None = None

    @model_validator(mode='after')
    def one_origin(self):
        if self.origin_source and self.origin:raise ValueError('Потрібне одне початкове джерело коментаря')
        if self.origin_source and self.state=='valid':raise ValueError('Чинний коментар не повинен мати історичне джерело')
        return self


class Comment(DomainModel):
    id: str = Field(min_length=1,max_length=128)
    instruction: str = Field(min_length=1,max_length=8000)
    anchor: CommentAnchor


class InputComment(Comment):
    anchor: InputAnchor


class CommentPayload(DomainModel):
    general: str = Field(default='',max_length=12000)
    comments: list[InputComment] = Field(default_factory=list,max_length=100)

    @model_validator(mode='after')
    def limits(self):
        if len(self.general)+sum(len(comment.instruction) for comment in self.comments)>50000:
            raise ValueError('Коментарі перевищують сумарний ліміт 50000 символів')
        if any(not comment.instruction.strip() for comment in self.comments):raise ValueError('Порожня вказівка коментаря')
        if len({comment.id for comment in self.comments})!=len(self.comments):raise ValueError('Повторний ID коментаря')
        proofs={comment.anchor.origin_source.text for comment in self.comments if comment.anchor.origin_source}
        if sum(map(len,proofs))>1000000:raise ValueError('Джерела коментарів перевищують сумарний ліміт')
        return self


class CommentSet(DomainModel):
    id: str = Field(default_factory=new_id)
    story_id: str
    scene_id: str
    material_kind: Literal['draft'] = 'draft'
    revision: int = Field(ge=1)
    source_version_id: str
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    content_format: Literal['plain','markdown']
    general: str = Field(default='',max_length=12000)
    comments: list[Comment] = Field(default_factory=list,max_length=100)
    created_at: str = Field(default_factory=now)


def validate_comment_set(source,content_format,notes):
    valid=[]
    for comment in notes.comments:
        anchor=comment.anchor
        if anchor.state!='valid':continue
        if not 0<=anchor.start<anchor.end<=len(source) or source[anchor.start:anchor.end]!=anchor.source_quote:
            raise ValueError('Цитата коментаря не відповідає джерелу')
        if source_range_text(source,anchor.start,anchor.end,content_format)!=anchor.display_quote:
            raise ValueError('Видимий текст коментаря не відповідає джерелу')
        valid.append((anchor.start,anchor.end))
    valid.sort()
    if any(right[0]<left[1] for left,right in zip(valid,valid[1:])):raise ValueError('Коментарі перетинаються')


def comment_fingerprint(notes,source_ref):
    if notes.source_version_id!=source_ref.id or notes.source_sha256!=source_ref.sha256 or notes.content_format!=source_ref.content_format:
        raise ValueError('Джерело коментарів змінилося')
    value={'notes':notes.model_dump(mode='json'),'source':{'id':source_ref.id,'sha256':source_ref.sha256,'content_format':source_ref.content_format}}
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
