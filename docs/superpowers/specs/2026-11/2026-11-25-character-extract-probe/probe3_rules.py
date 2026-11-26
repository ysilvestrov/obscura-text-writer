"""R-51 probe 3, free recount (no model calls): how many scene–place pairs of probe 3 each mention rule finds in the
prose of their scene. strict — `name_stems`; lenient — probe3.py (4+ letter stems also minus one letter); bounded — spec 2
§3.3 (a four-letter word minus one letter, matched only against words at most two letters longer). Reads the raw outputs
out3-*.json and the texts from the scratch folder C:/tmp/r51probe.
"""
import json, re, sys
sys.path.insert(0, r'C:\Projects\text-generator\.claude\worktrees\r51-loc\docs\superpowers\specs\2026-11\2026-11-25-character-extract-probe')
from probe3 import scenes_of
from storygen.memory.selection import name_stems, _WORD, _norm

books = {'tini2': 'tini2.txt', 'inst': 'inst.txt'}


def words_of(text):
    return set(_WORD.findall(_norm(text)))


def strict(path, words):
    return any(w.startswith(s) for s in name_stems(path.split('/')[-1]) for w in words)


def lenient(path, words):  # probe3: 4+ letter stems also minus one letter, any length
    stems = name_stems(path.split('/')[-1])
    return strict(path, words) or any(w.startswith(s[:-1]) for s in stems if len(s) >= 4 for w in words)


def bounded(path, words):  # 4-letter words: minus one letter, but only words at most 2 letters longer than that stem
    stems = name_stems(path.split('/')[-1])
    if strict(path, words): return True
    for s in stems:
        if len(s) == 4:
            short = s[:-1]
            if any(w.startswith(short) and len(w) <= len(short) + 2 for w in words): return True
    return False


for f in ['out3-ds-tini.json', 'out3-gm-tini.json', 'out3-ds-inst.json', 'out3-gm-inst.json']:
    r = json.load(open('C:/tmp/r51probe/' + f, encoding='utf-8'))
    scenes = scenes_of(open('C:/tmp/r51probe/text/' + books[r['book']], encoding='utf-8').read())
    tot = st = le = bo = 0
    for sid, v in r['places'].items():
        w = words_of(scenes[int(sid[1:]) - 1])
        for p in v['places']:
            tot += 1; st += strict(p['path'], w); le += lenient(p['path'], w); bo += bounded(p['path'], w)
    print(f, 'pairs', tot, 'strict', st, 'lenient', le, 'bounded', bo)
