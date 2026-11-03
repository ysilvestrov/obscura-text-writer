"""Structural audit only; human review is still required for all gold labels."""
from collections import Counter


def validate_dataset(cases: list[dict]) -> dict:
    counts=Counter(total=len(cases));ids=set();groups={}
    families={'A':3,'B':3,'C':2,'D':2,'E':2}
    for row in cases:
        template=row['template'];family=row['family'];variant=row['variant'];context=row['context']
        if row['id'] in ids:raise ValueError('Duplicate case ID')
        ids.add(row['id'])
        if family not in families or template not in {f'{family}{i}' for i in range(1,families[family]+1)}:
            raise ValueError('Unknown template')
        if variant not in {'a','b'} or context not in {'neutral','adult'}:raise ValueError('Unknown variant/context')
        key=(context,variant)
        if key in groups.setdefault(template,set()):raise ValueError('Duplicate template variant')
        groups[template].add(key)
        if not row['sources'] or not all(isinstance(t,str) and t.strip() for t in row['sources']) or not row['target'].strip():
            raise ValueError('Empty input')
        if context=='adult':
            ages=row['ages']
            if not ages or any(type(a) is not int or a<18 for a in ages):raise ValueError('Adult ages must be explicit')
            if any(str(a) not in '\n'.join(row['sources'])+'\n'+row['target'] for a in ages):raise ValueError('Age not present in model input')
        gold=row['gold'];verdict=gold['verdict']
        expected=('question' if variant=='a' else 'clean') if family=='D' else 'issue' if family=='E' or variant=='b' else 'clean'
        if verdict!=expected:raise ValueError('Wrong family verdict')
        n=2 if family=='E' and variant=='a' else 1 if verdict=='issue' else 0
        facts=gold['contradictions']
        if len(facts)!=n or len({f['id'] for f in facts})!=n:raise ValueError('Wrong contradiction count/IDs')
        for fact in facts:
            if not fact['source_indices'] or any(type(i) is not int or not 0<=i<len(row['sources']) for i in fact['source_indices']):raise ValueError('Unknown gold source')
            if not fact['target_quote'] or fact['target_quote'] not in row['target']:raise ValueError('Gold quote missing')
            if not fact['type'] or fact['severity'] not in {'minor','major','critical'}:raise ValueError('Incomplete gold label')
        if verdict=='clean' and not gold['clean_reason'].strip():raise ValueError('Missing clean explanation')
        if verdict=='question' and not gold['question_reason'].strip():raise ValueError('Missing ambiguity explanation')
        counts[verdict]+=1;counts[context]+=1;counts['contradictions']+=n
    expected=dict(total=48,clean=20,issue=24,question=4,contradictions=28,adult=24,neutral=24)
    if dict(counts)!=expected or len(groups)!=12 or any(len(g)!=4 for g in groups.values()):raise ValueError('Dataset must match 12 × 4 design')
    # Each context must have the same gold distribution, not merely 24 total inputs.
    for context in ['neutral','adult']:
        rows=[r for r in cases if r['context']==context]
        if Counter(r['gold']['verdict'] for r in rows)!=dict(clean=10,issue=12,question=2):raise ValueError('Unbalanced context labels')
    return expected
