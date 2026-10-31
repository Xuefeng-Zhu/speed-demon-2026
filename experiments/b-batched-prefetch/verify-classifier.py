from pathlib import Path
root=Path(__file__).resolve().parents[2]
c=(root/'experiments/b-batched-prefetch/candidate.rs').read_text()
p=(root/'experiments/b-avx2-token/classifier-property.rs').read_text()
a=c[c.index('#[target_feature(enable = "avx2")]'):c.index('\n#[inline]\nfn push_word')].strip()
b=p[p.index('#[target_feature(enable = "avx2")]'):p.index('\n#[cfg(not(target_arch')].strip().replace('pub unsafe fn classify_avx2','unsafe fn classify_avx2')
assert a==b, 'classifier test does not match candidate body'
print('PASS exact candidate AVX2 classifier body matches guard test')
