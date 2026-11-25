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


def sentence_groups(original,proposal,content_format='plain'):
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
    dependencies=[]
    if content_format=='markdown':
        from .markdown_document import format_dependency_groups
        candidate=original
        for unit in sorted(units,key=lambda item:item['start'],reverse=True):
            candidate=candidate[:unit['start']]+unit['replacement']+candidate[unit['end']:]
        dependencies=[set(dependency) for dependency in format_dependency_groups(original,candidate,units)]
        for dependency in dependencies:
            owners=[index for index,group in enumerate(merged) if dependency & {unit['index'] for unit in group['units']}]
            if len(owners)>1:
                first,last=min(owners),max(owners)
                selected=merged[first:last+1]
                merged[first:last+1]=[dict(left=min(g['left'] for g in selected),right=max(g['right'] for g in selected),
                                              units=[unit for group in selected for unit in group['units']])]
    groups=[]
    for group in merged:
        before=[];after=[];cursor=group['left']
        for unit in sorted(group['units'],key=lambda item:(item['start'],item['end'])):
            unchanged=original[cursor:unit['start']]
            if unchanged:
                before.append(dict(text=unchanged,changed=False));after.append(dict(text=unchanged,changed=False))
            before.append(dict(text=original[unit['start']:unit['end']],changed=True,index=unit['index']))
            after.append(dict(text=unit['replacement'],changed=True,index=unit['index']));cursor=unit['end']
        suffix=original[cursor:group['right']]
        if suffix:before.append(dict(text=suffix,changed=False));after.append(dict(text=suffix,changed=False))
        categories={item['category'] for item in group['units']}
        indices=sorted(item['index'] for item in group['units'])
        groups.append(dict(indices=indices,units=_units(indices,dependencies),before_parts=before,after_parts=after,
                           category=next(iter(categories)) if len(categories)==1 else 'mixed'))
    return groups


def _units(indices,dependencies):
    """EDIT-SENTENCE-GROUPS-S04: parts an author may accept apart. Each edit is a part; Markdown format dependencies
    (which may overlap, e.g. {1,2} and {0,2}) join their edits transitively into one part, so parts never share an edit."""
    parent={index:index for index in indices}
    def root(index):
        while parent[index]!=index:index=parent[index]
        return index
    for dependency in dependencies:
        members=[index for index in indices if index in dependency]
        for index in members[1:]:parent[root(index)]=root(members[0])
    parts={}
    for index in indices:parts.setdefault(root(index),[]).append(index)
    return sorted(parts.values(),key=lambda part:part[0])


SPLIT_ERROR='Розділити можна лише речення з кількома окремими правками; відкрийте перегляд знову'


def validate_group_selection(original,proposal,indices,content_format='plain',split=()):
    """Whole groups only, except a group the author split (its smallest index in `split`): there whole parts only."""
    selected=set(indices);groups=sentence_groups(original,proposal,content_format)
    splittable={group['indices'][0]:group for group in groups if len(group['units'])>1}
    if any(index not in splittable for index in split):raise ValueError(SPLIT_ERROR)
    for group in groups:
        for members in map(set,group['units'] if group['indices'][0] in split else [group['indices']]):
            if selected & members and not members<=selected:
                raise ValueError('Взаємозалежні правки речення або форматування потрібно приймати чи відхиляти разом; відкрийте перегляд знову')
