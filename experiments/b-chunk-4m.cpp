#include <algorithm>
#include <atomic>
#include <thread>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cstring>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>
using namespace std;
struct Query { bool phrase; vector<int> terms; vector<string> ops; };
int main(int argc,char**argv){
 if(argc!=4){cerr<<"Usage: index docs.txt queries.txt results.txt\n";return 1;}
 ifstream qi(argv[2]); if(!qi){cerr<<"Cannot open queries\n";return 1;}
 unordered_map<string,int> ids; vector<Query> qs; string line;
 auto term_id=[&](const string& s){auto it=ids.find(s);if(it!=ids.end())return it->second;int n=ids.size();ids.emplace(s,n);return n;};
 while(getline(qi,line)){
  istringstream in(line);string kind,s;in>>kind;Query q;q.phrase=kind=="PHRASE";
  if(q.phrase){while(in>>s){if(s.front()=='"')s.erase(s.begin());if(!s.empty()&&s.back()=='"')s.pop_back();q.terms.push_back(term_id(s));}}
  else {in>>s;q.terms.push_back(term_id(s));while(in>>s){q.ops.push_back(s);in>>s;q.terms.push_back(term_id(s));}}
  qs.push_back(move(q));
 }
 unordered_map<string_view,int> lookup; lookup.reserve(ids.size());
 for (const auto& entry : ids) lookup.emplace(entry.first, entry.second);
 int fd=open(argv[1],O_RDONLY); if(fd<0){perror("open");return 1;}
 struct stat st; if(fstat(fd,&st)!=0){perror("fstat");return 1;}
 size_t bytes=st.st_size;
 vector<size_t> offsets{0};
 vector<char> scan(1<<22);
 for(size_t pos=0; pos<bytes;) {
  size_t len=min(scan.size(),bytes-pos); ssize_t got=pread(fd,scan.data(),len,pos);
  if(got<=0){perror("pread");return 1;}
  for(size_t i=0;i<size_t(got);i++)if(scan[i]=='\n')offsets.push_back(pos+i+1);
  pos+=size_t(got);
 }
 if(offsets.back()!=bytes)offsets.push_back(bytes);
 size_t n_docs=offsets.size()-1;
 vector<vector<int>> docs(n_docs);
 constexpr int n_workers=6;
 vector<vector<vector<int>>> local(n_workers, vector<vector<int>>(ids.size()));
 vector<thread> indexers;
 const auto& immutable_lookup=lookup;
 for(int worker=0;worker<n_workers;worker++) indexers.emplace_back([&,worker]{
  size_t doc=n_docs*worker/n_workers,last=n_docs*(worker+1)/n_workers;
  size_t pos=offsets[doc],stop=offsets[last]; auto& lists=local[worker];
  string pending; pending.reserve((1<<22)+4096); vector<char> buffer(1<<22);
  while(pos<stop){
   size_t len=min(buffer.size(),stop-pos); ssize_t got=pread(fd,buffer.data(),len,pos);
   if(got<=0){perror("pread");abort();} pos+=size_t(got); pending.append(buffer.data(),size_t(got));
   size_t start=0;
   while(start<pending.size()){
    size_t line_end=pending.find('\n',start);
    if(line_end==string::npos){if(pos<stop)break;line_end=pending.size();}
    auto& seq=docs[doc]; size_t i=pending.find('\t',start); if(i>=line_end)abort(); ++i;
    auto tokenchar=[](unsigned char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9');};
    while(i<line_end){
     while(i<line_end&&!tokenchar((unsigned char)pending[i]))++i;
     if(i==line_end)break; size_t begin=i; bool upper=false; while(i<line_end&&tokenchar((unsigned char)pending[i])){unsigned char c=pending[i++];upper|=(c>='A'&&c<='Z');}
     string_view token(pending.data()+begin,i-begin);char word[32]; if(upper){for(size_t j=0;j<token.size();j++){unsigned char c=token[j];word[j]=c>='A'&&c<='Z'?c+32:c;}token=string_view(word,token.size());}
     auto it=immutable_lookup.find(token);int id=it==immutable_lookup.end()?-1:it->second;seq.push_back(id);
     if(id>=0){auto& p=lists[id];if(p.empty()||p.back()!=int(doc))p.push_back(int(doc));}
    }
    ++doc;start=line_end+(line_end<pending.size());
   }
   pending.erase(0,start);
  }
  if(doc!=last||!pending.empty())abort();
 });
 for(auto& worker:indexers)worker.join();
 close(fd);
 vector<vector<int>> postings(ids.size());
 for(size_t id=0;id<ids.size();id++){
  size_t size=0;for(int worker=0;worker<n_workers;worker++)size+=local[worker][id].size();
  postings[id].reserve(size);
  for(int worker=0;worker<n_workers;worker++){auto& p=local[worker][id];postings[id].insert(postings[id].end(),p.begin(),p.end());}
 }
 local.clear(); local.shrink_to_fit();
 ofstream out(argv[3]);if(!out){cerr<<"Cannot open output\n";return 1;}
 vector<string> outputs(qs.size()); atomic<size_t> next{0}; vector<thread> workers;
 for(int worker=0;worker<6;worker++) workers.emplace_back([&]{
 for(size_t n;(n=next.fetch_add(1,memory_order_relaxed))<qs.size();){const auto& q=qs[n];vector<int> result;
  if(!q.phrase){result=postings[q.terms[0]];for(size_t k=1;k<q.terms.size();++k){vector<int> next;auto& p=postings[q.terms[k]];if(q.ops[k-1]=="AND")set_intersection(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else if(q.ops[k-1]=="OR")set_union(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else set_difference(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));result.swap(next);}}
  else {int anchor=q.terms[0];for(int t:q.terms)if(postings[t].size()<postings[anchor].size())anchor=t;for(int d:postings[anchor]){auto& seq=docs[d];if(search(seq.begin(),seq.end(),q.terms.begin(),q.terms.end())!=seq.end())result.push_back(d);}}
  uint64_t sum=0;for(int d:result)sum+=d;ostringstream os;os<<result.size()<<' '<<sum;for(size_t i=0;i<min<size_t>(10,result.size());++i)os<<' '<<result[i];os<<'\n';outputs[n]=os.str();
 } });
 for(auto& worker:workers)worker.join();
 for(const auto& line:outputs)out<<line;
 if(!out){cerr<<"Output write failed\n";return 1;}return 0;
}
