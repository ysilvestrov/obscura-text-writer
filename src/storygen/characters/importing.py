"""Lossless Markdown character sections to initial authoring payloads."""
import re

CONTAINERS={'персонажі','персонажи','characters','картки персонажів','описи персонажів'}
HEADING=re.compile(r'(?m)^[ \t]*(#{1,6})[ \t]+([^\r\n]+)(?:\r?\n|$)')


def heading_name(raw):
    return re.sub(r'[ \t]+#+[ \t]*$','',raw).replace('**','').replace('__','').strip().rstrip(':').strip()


def cards_from_markdown(text,source_version_id):
    headings=list(HEADING.finditer(text))
    candidates=[h for h in headings if heading_name(h[2]).casefold() not in CONTAINERS]
    if not candidates:return [],[]
    level=min(len(h[1]) for h in candidates)
    cards=[];warnings=[]
    for index,heading in enumerate(headings):
        name=heading_name(heading[2])
        if len(heading[1])!=level or not name or name.casefold() in CONTAINERS:continue
        following=next((h.start() for h in headings[index+1:] if len(h[1])<=level),len(text))
        body=text[heading.end():following].strip()
        if not body:continue
        cards.append({'id':None,'schema_version':2,'name':name,'entries':[{
            'id':None,'text':body,'availability':'unclassified','available_from_scene_id':None,
            'origin':'imported','sources':[{'version_id':source_version_id,'quote':body}]}]})
        if re.search('[A-Za-z]',name) and re.search('[А-Яа-яІіЇїЄєҐґ]',name):
            warnings.append(f'Ім’я «{name[:120]}» містить латинські й кириличні літери; перевірте написання для точного зіставлення зі сценами.')
    return cards,warnings
