"""Derived sentence units; immutable proposal indices remain authoritative."""
import re


def sentence_context(text,start,end):
    left,right=0,len(text)
    for boundary in re.finditer(r'[.!?…]+[»”")\]]*(?=[ \t\r\n]|$)|[\r\n]+',text):
        if boundary.end()<start:left=boundary.end()
        elif boundary.start()>=end:
            right=boundary.start() if boundary.group()[0] in '\r\n' else boundary.end()
            break
    while left<start and text[left] in ' \t':left+=1
    return dict(context_before=text[left:start],context_after=text[end:right])


def sentence_groups(original,proposal):
    from .evidence import fragment_text
    fragments=None;units=[]
    for index,edit in enumerate(proposal.edits):
        if hasattr(edit,'start'):start,end=edit.start,edit.end;category='unclassified'
        else:
            if fragments is None:fragments={f.id:f for f in fragment_text(original)}
            fragment=fragments[edit.fragment_id]
            start=fragment.start+fragment.text.index(edit.original)
            end=start+len(edit.original);category=edit.category
        context=sentence_context(original,start,end)
        left=start-len(context['context_before']);right=end+len(context['context_after'])
        units.append(dict(index=index,start=start,end=end,left=left,right=right,replacement=edit.replacement,category=category))
    merged=[]
    for unit in sorted(units,key=lambda item:(item['left'],item['right'],item['start'])):
        if merged and unit['left']<merged[-1]['right']:
            merged[-1]['right']=max(merged[-1]['right'],unit['right'])
            merged[-1]['units'].append(unit)
        else:merged.append(dict(left=unit['left'],right=unit['right'],units=[unit]))
    groups=[]
    for group in merged:
        before=[];after=[];cursor=group['left']
        for unit in sorted(group['units'],key=lambda item:(item['start'],item['end'])):
            unchanged=original[cursor:unit['start']]
            if unchanged:
                before.append(dict(text=unchanged,changed=False));after.append(dict(text=unchanged,changed=False))
            before.append(dict(text=original[unit['start']:unit['end']],changed=True))
            after.append(dict(text=unit['replacement'],changed=True));cursor=unit['end']
        suffix=original[cursor:group['right']]
        if suffix:before.append(dict(text=suffix,changed=False));after.append(dict(text=suffix,changed=False))
        categories={item['category'] for item in group['units']}
        groups.append(dict(indices=sorted(item['index'] for item in group['units']),before_parts=before,after_parts=after,
                           category=next(iter(categories)) if len(categories)==1 else 'mixed'))
    return groups


def validate_group_selection(original,proposal,indices):
    selected=set(indices)
    for group in sentence_groups(original,proposal):
        members=set(group['indices'])
        if selected & members and not members<=selected:
            raise ValueError('Правки одного речення потрібно приймати або відхиляти разом; відкрийте перегляд знову')
