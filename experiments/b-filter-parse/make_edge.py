#!/usr/bin/env python3
"""Handcrafted Track B edge fixtures under $EDGE_ROOT/<name>/ (default /projects/sandbox/.data/edge).

Each fixture gets docs.txt, queries.txt and ref/results.txt from the official
reference. Run: python3 make_edge.py
"""
import os, random, subprocess, sys

ROOT = os.environ.get('EDGE_ROOT', '/projects/sandbox/.data/edge')
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'official', 'reference', 'b_index.py')


def write(name, docs, queries, docs_tail_lf=True, q_tail_lf=True):
    d = os.path.join(ROOT, name)
    os.makedirs(os.path.join(d, 'ref'), exist_ok=True)
    body = b''.join(b'%d\t' % i + t + b'\n' for i, t in enumerate(docs))
    if not docs_tail_lf:
        body = body[:-1]
    qb = b''.join(q.encode() + b'\n' for q in queries)
    if not q_tail_lf:
        qb = qb[:-1]
    open(os.path.join(d, 'docs.txt'), 'wb').write(body)
    open(os.path.join(d, 'queries.txt'), 'wb').write(qb)
    subprocess.run([sys.executable, REF, '--data', d, '--out', os.path.join(d, 'ref')], check=True)


def b(s):
    return s.encode('utf-8')


# 1. repeated terms in queries and documents
write('repeat', [b('bail bail bail bond'), b('bail bond bond'), b('bail'), b('bond bail bail'),
                 b('w w w w'), b('w w'), b('x')],
      ['BOOL bail AND bail', 'BOOL bail OR bail NOT bail', 'PHRASE "bail bail"', 'PHRASE "bail bail bail"',
       'PHRASE "bail bail bail bail"', 'PHRASE "w w w"', 'PHRASE "w w w w w"', 'PHRASE "bond bond"',
       'BOOL w', 'BOOL w AND w AND w', 'PHRASE "bail bond bail"', 'BOOL bond NOT bail', 'PHRASE "w w"'])

# 2. operator words as document tokens and inside phrases
write('opwords', [b('Smith AND Jones or NOT'), b('and or not'), b('AND'), b('this and that'),
                  b('Not Or And bool phrase'), b('BOOL PHRASE and'), b('nothing order andor')],
      ['BOOL and', 'BOOL or', 'BOOL not', 'BOOL and AND or', 'BOOL not OR and NOT or', 'BOOL and NOT and',
       'PHRASE "and or not"', 'PHRASE "and or"', 'PHRASE "or not"', 'PHRASE "not or and"',
       'BOOL bool AND phrase', 'PHRASE "bool phrase"', 'PHRASE "phrase and"', 'BOOL andor',
       'BOOL nothing OR order', 'PHRASE "smith and jones"', 'BOOL AND'.replace('BOOL AND', 'BOOL and OR not')])

# 3. non-ASCII bytes and punctuation as separators
write('nonascii', [b('Zürich café naïve'), b('İSTANBUL 273K'), b('ﬁduciary Straße'), b('bail\u00a0bond'),
                   b('habeas-corpus court’s U.S.C.'), b('§§ ¶'), b(''), b('𝔄ct Ñandú \u2014 x'),
                   b('a\u2014b c/d e(f)g'), b('z rich s o paulo')],
      ['BOOL z AND rich', 'BOOL zurich', 'BOOL cafe', 'BOOL caf', 'BOOL na OR ve', 'BOOL stanbul',
       'BOOL 273', 'BOOL 273k', 'BOOL duciary', 'BOOL stra AND e', 'PHRASE "bail bond"',
       'PHRASE "habeas corpus"', 'PHRASE "court s"', 'PHRASE "u s c"', 'BOOL ct', 'BOOL and',
       'BOOL ndu', 'PHRASE "a b"', 'PHRASE "c d e f g"', 'PHRASE "z rich"', 'PHRASE "s o paulo"',
       'PHRASE "rich caf"', 'BOOL x NOT ct', 'PHRASE "nd x"'])

# 4. absent terms and duplicate queries
write('absent_dup', [b('alpha beta gamma'), b('beta gamma delta'), b('gamma delta epsilon')],
      ['BOOL zzz', 'BOOL alpha AND zzz', 'BOOL alpha OR zzz', 'BOOL zzz OR alpha', 'BOOL zzz NOT alpha',
       'BOOL alpha NOT zzz', 'PHRASE "alpha zzz"', 'PHRASE "zzz alpha"', 'BOOL gamma', 'BOOL gamma',
       'BOOL gamma', 'PHRASE "beta gamma"', 'PHRASE "beta gamma"', 'BOOL zzz', 'BOOL alphabeta',
       'BOOL alph', 'BOOL alphaa', 'PHRASE "gamma delta"', 'BOOL beta AND gamma NOT delta',
       'BOOL beta AND gamma NOT delta'])

# 5. token lengths: 1, 7, 8, 9, 15, 16, 17, 24, 31, 32 and 16-byte shared prefixes
L = {n: ''.join('abcdefghijklmnopqrstuvwxyz0123456789'[i % 36] for i in range(n)) for n in
     (1, 7, 8, 9, 15, 16, 17, 24, 31, 32)}
p16 = 'abcdefghijklmnop'
longs = [p16 + 'q', p16 + 'r', p16 + 'qq', p16 + '0000000000000000', p16 + '00000000000000000',
         p16, p16[:8], p16[:8] + 'x', 'abcdefgh' + '\x00'.join([]) + 'ijklmnopq']
docs5 = [b(' '.join(L.values())), b(' '.join(longs)), b(L[16] + ' ' + L[17] + ' ' + L[16]),
         b((p16 + 'q ').upper() * 3), b(p16 + 'r ' + p16 + 'q'), b('00000000 0000000000000000 000000000000000000')]
q5 = ['BOOL ' + v for v in L.values()] + ['BOOL ' + v for v in longs] + [
    'PHRASE "%s %s"' % (L[16], L[17]), 'PHRASE "%s %s"' % (L[17], L[16]), 'PHRASE "%s %s"' % (p16 + 'r', p16 + 'q'),
    'PHRASE "%s %s"' % (p16 + 'q', p16 + 'q'), 'BOOL %s AND %s' % (p16 + 'q', p16 + 'r'),
    'BOOL %s NOT %s' % (p16, p16 + 'q'), 'BOOL ' + p16 + 's', 'BOOL ' + p16 + 'qqq', 'BOOL ' + 'a' * 32,
    'BOOL 00000000', 'BOOL 0000000000000000', 'BOOL 000000000000000000', 'BOOL 0', 'BOOL 00000000000000000',
    'PHRASE "%s %s %s"' % (L[31], L[32], L[1])]
write('lengths', docs5, q5)

# 6. uppercase / title case documents
write('upper', [b('THE COURT GRANTED BAIL'), b('The Court Granted Bail'), b('the court granted bail'),
                b('ThE CoUrT'), b('ABC123 DEF')],
      ['BOOL court', 'PHRASE "court granted"', 'BOOL abc123 OR def', 'PHRASE "the court"',
       'BOOL abc AND 123', 'PHRASE "abc123 def"'])

# 7. final lines without LF (docs and queries); spec guarantees LF but be robust
write('no_lf', [b('one two three'), b('two three four'), b('four five')],
      ['BOOL two', 'PHRASE "two three"', 'BOOL five'], docs_tail_lf=False, q_tail_lf=False)
write('no_lf_docs', [b('one two three'), b('two three four'), b('four five')],
      ['BOOL two', 'PHRASE "two three"', 'BOOL five'], docs_tail_lf=False)
write('no_lf_queries', [b('one two three'), b('two three four'), b('four five')],
      ['BOOL two', 'PHRASE "two three"', 'BOOL five'], q_tail_lf=False)

# 8. terms present only in queries of one kind
write('one_kind', [b('onlybool alpha'), b('onlyphrase beta gamma'), b('shared alpha beta'), b('filler')],
      ['BOOL onlybool', 'BOOL onlybool AND alpha', 'PHRASE "beta gamma"', 'PHRASE "onlyphrase beta"',
       'BOOL shared OR filler', 'PHRASE "shared alpha"', 'PHRASE "onlyphrase beta gamma"'])

# 9. many distinct query terms (several intern-table growths), random docs from a small alphabet
rng = random.Random(9)
words = sorted({''.join(rng.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(rng.choice(
    [1, 2, 3, 4, 5, 6, 7, 8, 8, 9, 12, 15, 16, 16, 17, 20, 25, 32]))) for _ in range(30000)})
dw = words[:20000]
seps = [' ', ' ', ' ', ', ', '-', '/', '\u00a0', '\u2014', '’s ', '. ']
docs9 = []
for i in range(3000):
    n = rng.randint(0, 60)
    t = ''
    for j in range(n):
        w = rng.choice(dw) if rng.random() < .7 else rng.choice(dw[:50])
        if rng.random() < .1:
            w = w.upper()
        t += w + (rng.choice(seps) if j + 1 < n else '')
    docs9.append(b(t))
q9 = []
for i in range(8000):
    if rng.random() < .6:
        k = rng.randint(1, 6)
        ts = [rng.choice(words) for _ in range(k)]
        q = 'BOOL ' + ts[0] + ''.join(' %s %s' % (rng.choice(['AND', 'OR', 'NOT']), t) for t in ts[1:])
    else:
        d = docs9[rng.randrange(len(docs9))].decode().lower()
        import re
        toks = re.findall(r'[a-z0-9]+', d)
        if len(toks) >= 2 and rng.random() < .8:
            k = min(len(toks), rng.randint(2, 8))
            s = rng.randint(0, len(toks) - k)
            ts = toks[s:s + k]
            if rng.random() < .2:
                ts = ts[::-1]
        else:
            ts = [rng.choice(words) for _ in range(rng.randint(2, 8))]
        q = 'PHRASE "' + ' '.join(ts) + '"'
    q9.append(q)
write('many_terms', docs9, q9)
print('ok')
