"""Story locations from the «Локація:» line of a scene plan (MEMORY-LOCATIONS); pure, no IO.

A line lists one or more locations; `/` nests them. Identity is the normalized full path, so «Маєток Джорджа» and
«Маєток Джорджа біля озера» are two locations until the author merges them."""
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


def _chunks(line: str) -> list[str]:
    """The value cut at every separator and at «та»/«and» outside quotes and brackets, judged on the whole value."""
    outside=_outside(line)
    cuts=sorted([m.span() for m in _SEPARATORS.finditer(line)]+
                [m.span() for m in _CONJUNCTION.finditer(line) if outside[m.start()]])
    pieces=[];start=0
    for begin,end in cuts:
        if begin<start:continue  # overlapping matches cannot happen today; skip defensively
        pieces.append(line[start:begin]);start=end
    return [*pieces,line[start:]]


def parse_locations(line: str) -> list[tuple[str,...]]:
    """Paths of a «Локація:» value in order; empty parts are dropped and repeats (by key) kept once."""
    found=[];keys=set()
    for chunk in _chunks(line or ''):
        parts=tuple(p for p in (_clean(x) for x in chunk.split('/')) if p)
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
