from pathlib import Path
c=Path('candidate.rs').read_text();p=Path('classifier-property.rs').read_text()
a=c[c.index('#[target_feature(enable = "avx2")]'):c.index('\n#[inline]\nfn push_word')].strip()
b=p[p.index('#[target_feature(enable = "avx2")]'):p.index('\n#[cfg(not(target_arch')].strip().replace('pub unsafe fn classify_avx2','unsafe fn classify_avx2')
assert a==b, 'classifier test no longer matches candidate body'
print('PASS exact candidate AVX2 classifier body matches test')
