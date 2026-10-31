from pathlib import Path
import random,subprocess,tempfile,os,sys
source=Path(sys.argv[1] if len(sys.argv)>1 else 'experiments/c-bounded-batch/candidate.rs').resolve().read_text(); ref=Path('official/reference/c_join.py').resolve(); needle='let n = thread::available_parallelism().map_or(1, |n| n.get());'; assert source.count(needle)==1
with tempfile.TemporaryDirectory(prefix='c-batch-cross-') as td:
 root=Path(td);data=root/'data';data.mkdir();refout=root/'ref';refout.mkdir()
 groups=130
 (data/'regions.csv').write_text('region_id,country\n'+''.join(f'{i+1},C{chr(65+i//26)}{chr(65+i%26)}\n' for i in range(groups)))
 with (data/'records.csv').open('w') as f:
  f.write('\ufeffid,name,note,region_id,amount\r\n')
  for i in range(70037):
   name=['', 'Alpha', 'Beta, Inc', 'A "Quote"', 'Name '+str(i%61)][i%5]; name='"'+name.replace('"','""')+'"'; note='"a\nb"' if i%11==0 else '"x"'; g=(i*17)%groups+1; f.write(f'{i+1},{name},{note},{g},{(-1 if i%2 else 1)*(i%100)}.25'+ ('\r\n' if i%3==0 or i==70036 else '\n'))
 subprocess.run([sys.executable,str(ref),'--data',str(data),'--out',str(refout)],check=True,stdout=subprocess.DEVNULL); expected=(refout/'aggregates.txt').read_bytes()
 for n in (1,2,3,7):
  for force in (False,True):
   text=source.replace(needle,f'let n = {n};')
   if force:
    assert text.count('        self.0 ^ self.0 >> 29\n')==1; text=text.replace('        self.0 ^ self.0 >> 29\n','        0\n')
   path=root/f's{n}-{force}.rs';path.write_text(text);exe=root/f'bin{n}-{force}';subprocess.run(['rustc','--edition=2021','-O','-C','overflow-checks=yes','-A','dead_code',str(path),'-o',str(exe)],check=True)
   out=root/f'out{n}-{force}';out.mkdir(); subprocess.run([str(exe)],env=dict(os.environ,SD_DATA=str(data),SD_OUT=str(out)),check=True);assert (out/'aggregates.txt').read_bytes()==expected,(n,force)
print('PASS 70,037 rows, 130 groups, 8 normal/forced hash × worker combinations')
