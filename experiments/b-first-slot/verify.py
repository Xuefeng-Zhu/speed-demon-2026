#!/usr/bin/env python3
"""Independent probe-focused reference cases; no timing measurements."""
import argparse,hashlib,importlib.util,json,os
from pathlib import Path
import platform,subprocess,tempfile
HERE=Path(__file__).resolve().parent

def token_hash(word):
    k=word.encode().ljust(16,b'\0')[:16];lo=int.from_bytes(k[:8],'little');hi=int.from_bytes(k[8:],'little')
    rot=((hi<<29)|(hi>>(64-29)))&((1<<64)-1)
    return (((lo^rot)*0x9e3779b97f4a7c15)&((1<<64)-1))>>40

def base36(n):
    chars='0123456789abcdefghijklmnopqrstuvwxyz';v=''
    while n:v=chars[n%36]+v;n//=36
    return v or '0'

def cases():
    longs=['a'*17,'a'*32,'abcdefghijklmnopq','abcdefgh'+'x'*24]
    yield 'long-only-empty-short-table',[('the '+w.upper()+' unknown '+v).encode() for w,v in zip(longs*20,(longs[1:]+longs[:1])*20)],['BOOL '+w for w in longs]+['PHRASE "'+u+' '+v+'"' for u,v in zip(longs,longs[1:])]
    yield 'unknown-none-and-empty-results',[b'the the and of',b'outside',b'',b'outside the',b'absentlongabcdefghijklmnopqrstuv'],['BOOL outside','BOOL absent','BOOL outside AND absent OR outside','PHRASE "outside outside"','PHRASE "the outside"']
    names=['abcdefgh','abcdefghi','abcdefghj','abcdefghijklmnop','abcdefghijklmnox','abcdefghijklmnopq','abcdefghijklmnopz','a'*32]
    texts=[]
    for i in range(257):texts.append((' '.join(names[i%len(names):]+names[:i%len(names)])+' abcdefghy unknown').upper().encode())
    queries=['BOOL '+w for w in names]+['PHRASE "'+u+' '+v+'"' for u,v in zip(names,names[1:])]
    queries+=['BOOL abcdefgh NOT abcdefghi OR abcdefghj','PHRASE "abcdefgh abcdefghi"']
    yield 'same-first-eight-full-key-and-long-tags',texts,queries
    # 24 fixed-width query keys share the last home bucket of the initial
    # 128-slot table; their linear cluster necessarily wraps through zero.
    colliders=[];n=0
    while len(colliders)<24:
        w='z'+base36(n).rjust(7,'0');n+=1
        if token_hash(w)&127==127:colliders.append(w)
    queries=['BOOL '+w for w in colliders]
    queries+=['PHRASE "'+colliders[i]+' '+colliders[i+1]+'"' for i in range(4)]
    qbytes=len(('\n'.join(queries)+'\n').encode());initial=1<<((qbytes//16|64)-1).bit_length()
    assert initial==128
    texts=[(' '.join(colliders[i:]+colliders[:i])+' unknown').upper().encode() for i in range(24)]
    yield 'real-hash-wrapped-home-cluster',texts,queries
    queries=[]
    for i in range(16000):
        ts=['v'+base36(i*6+j).rjust(4,'0') for j in range(6)]
        queries.append('BOOL '+ts[0]+''.join(op+t for op,t in zip([' OR ',' AND ',' NOT ',' OR ',' AND '],ts[1:])))
    queries+=['BOOL the OR v0000','PHRASE "the the"','PHRASE "v0000 the"']
    texts=[b'the the v0000 v0001',b'the v0002',b'outside',b'']
    texts+=[(' '.join('v'+base36(i*701+j).rjust(4,'0') for j in range(12))+' the').encode() for i in range(125)]
    yield '96000-distinct-bool-grow-remap-cap',texts,queries

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('binaries',nargs='*',type=Path);p.add_argument('--binary',action='append',type=Path,default=[]);p.add_argument('--repo',type=Path,default=Path(os.environ.get('B_TEST_REPO',HERE.parents[1])));p.add_argument('--threads',default='1,2,7,12');p.add_argument('--report',type=Path,default=HERE/'verification.json');a=p.parse_args()
    binaries=[b.resolve(strict=True) for b in a.binaries+a.binary];assert binaries
    path=a.repo/'official/reference/b_index.py';spec=importlib.util.spec_from_file_location('reference',path);ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    threads=[int(t) for t in a.threads.split(',')];rows=[]
    with tempfile.TemporaryDirectory(prefix='b-probe-reference-') as tmp:
        tmp=Path(tmp)
        for name,texts,queries in cases():
            data=tmp/name;data.mkdir();(data/'docs.txt').write_bytes(b''.join(str(i).encode()+b'\t'+t+b'\n' for i,t in enumerate(texts)));(data/'queries.txt').write_text('\n'.join(queries)+'\n')
            corpus,index=ref.load_corpus(str(data/'docs.txt'));expected=''.join(ref.answer(index,corpus,q.encode())+'\n' for q in queries).encode()
            for j,binary in enumerate(binaries):
                for n in threads:
                    out=data/f'out-{j}-{n}';r=subprocess.run([str(binary)],env={**os.environ,'SD_DATA':str(data),'SD_OUT':str(out),'SD_THREADS':str(n)},capture_output=True,timeout=90);assert r.returncode==0,(name,binary.name,n,r.stderr.decode());assert (out/'results.txt').read_bytes()==expected,(name,binary.name,n)
                    rows.append({'case':name,'binary':binary.name,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'threads':n,'docs':len(texts),'queries':len(queries),'passed':True})
            print('PASS '+name,flush=True)
    report={'platform':platform.platform(),'machine':platform.machine(),'comparisons':len(rows),'answers':sum(r['queries'] for r in rows),'threads':threads,'scope':'Independent reference equality only, no performance claim','rows':rows};a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))

if __name__=='__main__':main()
