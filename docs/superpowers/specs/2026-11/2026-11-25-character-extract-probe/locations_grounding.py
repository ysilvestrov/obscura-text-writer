"""R-51 spec 2, free check of probe 1 (no model calls): is each scene's proposed location named in that scene's prose?

Probe 1 (`probe1.py`) asked for characters, locations and the cast of each ≈1 000-word scene of «Тіні забутих предків»;
its raw outputs (`out-*.json`) and the text were kept in a scratch folder. This script reads them, matches every word of
the last path part with the project's mention rule (`memory.selection.name_stems` + `MentionIndex`) and, as a lenient
second rule, with the word minus one more letter (`name_stems` keeps four-letter words whole, so «хата» misses «хаті»).

Usage: python locations_grounding.py <folder with tini.txt and out-*.json>
"""
import json
import re
import sys
from pathlib import Path

from storygen.memory.selection import MentionIndex, name_stems

SCENE_WORDS = 1000
RUNS = ['out-deepse-5000.json', 'out-ds-5000.json', 'out-gemma--5000.json', 'out-gemma--10000.json']


def scenes_of(text):  # the chunking of probe1.py
    paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    scenes, cur, words = [], [], 0
    for p in paras:
        cur.append(p); words += len(p.split())
        if words >= SCENE_WORDS:
            scenes.append('\n\n'.join(cur)); cur, words = [], 0
    if cur: scenes.append('\n\n'.join(cur))
    return scenes


def lenient(stems):
    return tuple({s[:-1] if len(s) >= 4 else s for s in stems})


def main(folder):
    folder = Path(folder)
    scenes = scenes_of((folder/'text'/'tini.txt').read_text(encoding='utf-8'))
    report = []
    for name in RUNS:
        run = json.loads((folder/name).read_text(encoding='utf-8'))
        locs, cast = run['locations'], run['cast']
        rows = cast.items() if isinstance(cast, dict) else enumerate(cast)
        strict = loose = total = 0
        used, misses = set(), []
        for key, value in rows:
            lid = value.get('location') if isinstance(value, dict) else None
            if not lid or lid not in locs:
                continue
            used.add(lid); total += 1
            stems = name_stems(locs[lid].split('/')[-1])
            index = MentionIndex(scenes[int(key)])
            hit = index.first(stems) is not None
            hit_loose = hit or index.first(lenient(stems)) is not None
            strict += hit; loose += hit_loose
            if not hit_loose:
                misses.append([int(key), locs[lid]])
        report.append({'run': name, 'model': run['model'], 'group_words': run['group_words'], 'scenes': len(scenes),
                       'scenes_with_location': total, 'named_strict': strict, 'named_lenient': loose,
                       'cards': len(locs), 'cards_used_by_a_scene': len(used), 'not_named': misses})
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
