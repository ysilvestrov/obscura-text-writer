"""Story locations from the «Локація:» line of a scene plan (MEMORY-LOCATIONS); pure, no IO.

A line lists one or more locations; `/` nests them. Identity is the normalized full path, so «Маєток Джорджа» and
«Маєток Джорджа біля озера» are two locations until the author merges them."""
import functools
import hashlib
import re
import unicodedata
from typing import Mapping, NamedTuple

# Separators between locations: punctuation and whole sequence words. «і» lives inside names.
_SEPARATORS=re.compile(r'[,;→]|(?<![\w’ʼ\'])(?:потім|далі|згодом|then|later)(?![\w’ʼ\'])',re.IGNORECASE)
# «та» and «and» separate too, but not inside quotes or brackets: «Ніч та день», "Bed and Breakfast", (кухня та комора).
_CONJUNCTION=re.compile(r'(?<![\w’ʼ\'])(?:та|and)(?![\w’ʼ\'])',re.IGNORECASE)
_PAIRS={'«':'»','“':'”','„':'“','(':')','[':']'}
_QUOTES='"«»“”„\'‘’'
_FINAL='.!?…:'
DESCRIPTION_LIMIT=2000


class Place(NamedTuple):
    """What the location graph needs of a card: its parent (by id) and the card it was merged into."""
    id: str
    parent_id: str | None
    merged_into: str | None


def _clean(part: str) -> str:
    return ' '.join(unicodedata.normalize('NFC',part).split()).strip(_QUOTES+' ').rstrip(_FINAL).strip(_QUOTES+' ')


def normalize(parts) -> str:
    """The identity key of a path: lower case, single spaces, no edge quotes or final punctuation."""
    return ' / '.join(_clean(p).lower() for p in parts)


def _outside(text: str) -> list[bool]:
    """For every character: whether it stands outside quotes and brackets. An unclosed one runs to the end."""
    flags=[];closers=[];straight=False
    for char in text:
        if straight:straight=char!='"';flags.append(False);continue
        if closers and char==closers[-1]:closers.pop();flags.append(False);continue
        if char in _PAIRS:closers.append(_PAIRS[char]);flags.append(False);continue
        if char=='"' and not closers:straight=True;flags.append(False);continue
        flags.append(not closers)
    return flags


_APOS="’ʼ'"
_TOKEN=re.compile(r"[\w’ʼ']+|[^\w\s’ʼ']")
_AFTER_SPACE=',;:.!?…'


def _tokens(phrase: str) -> list[str]:
    return _TOKEN.findall(unicodedata.normalize('NFC',phrase))


def glue_key(phrase: str) -> str:
    """The identity of a glued phrase: NFC, lower case, one apostrophe, single spaces between words and after
    punctuation, none before punctuation or after an opening mark."""
    out=''
    tokens=[t.lower().translate({ord(c):"'" for c in _APOS}) for t in _tokens(phrase)]
    for prev,token in zip(['']+tokens,tokens):
        word=token[0].isalnum() or token[0]=="'" or token[0]=='_'
        if prev and word and (prev[-1].isalnum() or prev[-1] in "'_" or prev in _AFTER_SPACE):out+=' '
        out+=token
    return out


@functools.lru_cache(maxsize=8192)
def _glue_pattern(phrase: str):
    """(compiled pattern, needle) of a glued phrase: any case, any of ’ ʼ ', spaces between words (at least one) and
    around punctuation (any), whole words at both ends. The needle — the longest apostrophe-free word, case-folded —
    lets a value without it skip the pattern (500 glues × 500 scenes stay within the spec's second)."""
    parts=[];prev_word=False;words=[]
    for token in _tokens(phrase):
        word=bool(re.match(r"[\w’ʼ']",token))
        if word:words+=[w for w in re.split(r"[’ʼ']",token) if w]
        if parts:parts.append(r'\s+' if word and prev_word else r'\s*')
        parts.append(''.join(f'[{_APOS}]' if c in _APOS else re.escape(c) for c in token));prev_word=word
    if not parts:return None
    return (re.compile(r"(?<![\w’ʼ'])"+''.join(parts)+r"(?![\w’ʼ'])",re.IGNORECASE),
            _fold(max(words,key=len)) if words else '')


def _fold(text: str) -> str:
    """Case-folded text without combining marks: a superset test for what re.IGNORECASE matches («İ» folds to «i̇»)."""
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def _glued_spans(line: str, glued) -> list[tuple[int,int]]:
    """Every occurrence of every glued phrase, overlapping ones too (a search restarts one character after a match)."""
    folded=None;spans=[]
    for compiled in filter(None,map(_glue_pattern,glued)):
        pattern,needle=compiled
        if folded is None:folded=_fold(line)
        if needle not in folded:continue
        found=pattern.search(line)
        while found:
            spans.append(found.span());found=pattern.search(line,found.start()+1)
    return spans


def _cuts(line: str, glued=()) -> list[tuple[int,int]]:
    """Separator spans of a value outside glued phrases; «та»/«and» also outside quotes and brackets."""
    outside=_outside(line)
    spans=_glued_spans(line,glued)
    inside=lambda pos:any(a<pos<b for a,b in spans)
    cuts=sorted([m.span() for m in _SEPARATORS.finditer(line) if not inside(m.start())]+
                [m.span() for m in _CONJUNCTION.finditer(line) if outside[m.start()] and not inside(m.start())])
    kept=[];start=0
    for begin,end in cuts:
        if begin<start:continue  # overlapping matches cannot happen today; skip defensively
        kept.append((begin,end));start=end
    return kept


def _pieces(line: str, cuts) -> list[tuple[int,int]]:
    bounds=[];start=0
    for begin,end in cuts:
        bounds.append((start,begin));start=end
    return [*bounds,(start,len(line))]


def _chunks(line: str, glued=()) -> list[str]:
    """The value cut at every separator and at «та»/«and» outside quotes and brackets, judged on the whole value; a
    glued phrase is never cut."""
    return [line[a:b] for a,b in _pieces(line,_cuts(line,glued))]


def _path(chunk: str) -> tuple[str,...]:
    return tuple(p for p in (_clean(x) for x in chunk.split('/')) if p)


def glue_cuts(line: str, glued=()) -> list[tuple[str,tuple[str,...],tuple[str,...]]]:
    """(phrase, left path, right path) for every cut between two pieces whose facing parts are not empty: the phrase is
    the raw text from the start of the left piece's last part to the end of the right piece's first part."""
    line=unicodedata.normalize('NFC',line or '')
    pieces=_pieces(line,_cuts(line,glued));found=[]
    for (la,lb),(ra,rb) in zip(pieces,pieces[1:]):
        left=line[la:lb];right=line[ra:rb]
        tail=left.rsplit('/',1)[-1];head=right.split('/',1)[0]
        if not tail.strip() or not head.strip() or not _path(left) or not _path(right):continue
        start=lb-len(tail)+(len(tail)-len(tail.lstrip()));end=ra+len(head.rstrip())
        found.append((' '.join(line[start:end].split()),_path(left),_path(right)))
    return found


def parse_locations(line: str, glued=()) -> list[tuple[str,...]]:
    """Paths of a «Локація:» value in order; glued phrases of the story stay whole, empty parts are dropped and repeats
    (by key) kept once."""
    found=[];keys=set()
    for chunk in _chunks(unicodedata.normalize('NFC',line or ''),glued):
        parts=_path(chunk)
        if not parts:continue
        key=normalize(parts)
        if key in keys:continue
        keys.add(key);found.append(parts)
    return found


def prefixes(parts) -> list[tuple[str,...]]:
    return [tuple(parts[:n]) for n in range(1,len(parts)+1)]


def location_id(story_id: str, key: str) -> str:
    return 'loc_'+hashlib.sha256(f'{story_id}\n{key}'.encode()).hexdigest()[:16]


def _distance(a: str, b: str) -> int:
    row=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        prev,row[0]=row[0],i
        for j,cb in enumerate(b,1):
            prev,row[j]=row[j],min(row[j]+1,row[j-1]+1,prev+(ca!=cb))
    return row[-1]


def similar(a_path: str, b_path: str) -> bool:
    """A merge hint: the same last part, all words of one name in the other, or an edit distance within 20 %."""
    a=normalize(a_path.split('/'));b=normalize(b_path.split('/'))
    if a==b:return False
    if a.rsplit(' / ',1)[-1]==b.rsplit(' / ',1)[-1]:return True
    wa=set(re.findall(r'\w+',a));wb=set(re.findall(r'\w+',b))
    if wa and wb and (wa<=wb or wb<=wa):return True
    return _distance(a,b)<=0.2*max(len(a),len(b))


def canonical(merged: Mapping[str,str|None], id: str) -> str:
    """The card an id stands for after merges; a cycle (never written, but read defensively) stops where it repeats."""
    seen=set()
    while merged.get(id) and id not in seen:
        seen.add(id);id=merged[id]
    return id


def neighbourhood(places: Mapping[str,Place], scene_ids) -> list[str]:
    """Every id whose card is a scene location, one of their ancestors or descendants (after merges), sorted."""
    merged={p.id:p.merged_into for p in places.values()}
    canon=lambda id:canonical(merged,id)
    def parent(id):
        place=places.get(id)
        return canon(place.parent_id) if place and place.parent_id else None
    def chain(id):
        out=[];id=canon(id)
        while id and id not in out:
            out.append(id);id=parent(id)
        return out
    core={canon(id) for id in scene_ids}
    if not core:return []
    near=set()
    for id in core:near.update(chain(id))
    for id in places:
        if core & set(chain(id)):near.add(canon(id))
    return sorted(id for id in set(places)|set(scene_ids) if canon(id) in near)
