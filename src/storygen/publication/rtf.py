"""EXPORT-DOCX-S03: an RTF manuscript with the DOCX layout, for editors without Word; no import marks.

The file is pure ASCII: every character outside printable ASCII is a `\\uN?` escape (a surrogate pair
outside the BMP), and RTF control characters in author text are escaped.
"""
from .book import part_starts
from .docx import PROFILE,primary,valid_text
from .markup import chapter_paragraphs

LANG_ID={'uk':1058,'en':1033}


def encode(text):
    out=[]
    for c in valid_text(text).replace('\r\n','\n').replace('\r','\n'):
        if c in '\\{}':out.append('\\'+c)
        elif c=='\t':out.append('\\tab ')
        elif c=='\n':out.append('\\line ')
        elif 0x20<=ord(c)<0x80:out.append(c)
        else:
            data=c.encode('utf-16-le')
            for index in range(0,len(data),2):
                unit=int.from_bytes(data[index:index+2],'little')
                out.append(f'\\u{unit-65536 if unit>32767 else unit}?')
    return ''.join(out)


def _run(run):
    controls=('\\b' if run.bold else '')+('\\i' if run.italic else '')
    return '{'+controls+' '+encode(run.text)+'}' if controls else encode(run.text)


def _paragraph(content,controls):
    return '{\\pard'+controls+' '+content+'\\par}\n'


def render(book):
    p=PROFILE;publication=book.snapshot.publication;card=publication.card;story=book.snapshot.story
    document_language=primary(card.language)
    deflang=f'\\deflang{LANG_ID[document_language]}' if document_language in LANG_ID else ''
    body=f'\\fi{p["first_line_twips"]}\\sl{p["line_240ths"]}\\slmult1'
    centered=f'\\qc\\fi0\\sl{p["line_240ths"]}\\slmult1'
    heading=lambda level,size:f'\\s{level+1}\\outlinelevel{level}\\pagebb\\keepn\\fi0\\sa240\\b\\fs{size}'
    out=['{\\rtf1\\ansi\\ansicpg1252\\uc1\\deff0'+deflang,
        '{\\fonttbl{\\f0\\froman\\fcharset0 '+p['font']+';}}',
        '{\\stylesheet{\\s0 Normal;}{\\s1\\outlinelevel0\\b\\fs32 heading 1;}{\\s2\\outlinelevel1\\b\\fs28 heading 2;}}',
        f'\\paperw{p["width_twips"]}\\paperh{p["height_twips"]}'+''.join(f'\\marg{side}{p["margin_twips"]}' for side in 'lrtb'),
        '{\\footer\\pard\\qc\\fi0 \\chpgn\\par}',
        f'\\f0\\fs{p["font_half_points"]}\n']
    out.append(_paragraph(encode(book.title),centered+'\\sb2400\\sa480\\b\\fs36'))
    for person in publication.authors:out.append(_paragraph(encode(person.display_name),centered))
    if card.cycle_title:
        out.append(_paragraph(encode(card.cycle_title+(f' · {card.cycle_number}' if card.cycle_number is not None else '')),centered))
    words=sum(chapter.entry['word_count'] for chapter in book.chapters)
    out.append(_paragraph(encode(f'{"Words" if story.language=="en" else "Слів"}: {words}'),centered))
    starts=part_starts(book)
    for index,chapter in enumerate(book.chapters):
        if index in starts:out.append(_paragraph(encode(starts[index]),heading(0,32)))
        out.append(_paragraph(encode(chapter.title),heading(1,28)))
        lang=f'\\lang{LANG_ID[chapter.language]}' if chapter.language!=document_language and chapter.language in LANG_ID else ''
        paragraphs=list(chapter_paragraphs(chapter))
        while paragraphs and not paragraphs[-1]:paragraphs.pop()
        for runs in paragraphs:out.append(_paragraph(''.join(_run(run) for run in runs),body+lang))
    out.append('}\n')
    return ''.join(out).encode('ascii')
