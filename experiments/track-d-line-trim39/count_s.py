import subprocess,sys,tempfile,os
def code_lines(t):
    n=0; block=False
    for l in t.split('\n'):
        s=l.strip()
        if block:
            if '*/' in s: block=False
            continue
        if not s or s.startswith('//'): continue
        if s.startswith('/*'):
            block='*/' not in s; continue
        n+=1
    return n
def count(src):
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,'main.rs'); open(p,'w').write(src)
        subprocess.run(['rustfmt','--edition','2021',p],check=True)
        return code_lines(open(p).read()), code_lines(src)
if __name__=='__main__':
    for rev in sys.argv[1:]:
        src=subprocess.run(['git','show',f'{rev}:track-d/src/main.rs'],capture_output=True,text=True,check=True).stdout
        dock=subprocess.run(['git','show',f'{rev}:track-d/Dockerfile'],capture_output=True,text=True,check=True).stdout
        f,r=count(src)
        print(f'{rev}: raw {r}, rustfmt {f}, Dockerfile non-blank {sum(1 for l in dock.splitlines() if l.strip())}')
