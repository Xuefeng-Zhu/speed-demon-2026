#include <algorithm>
#include <atomic>
#include <thread>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
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
 const char* input=bytes?static_cast<const char*>(mmap(nullptr,bytes,PROT_READ,MAP_PRIVATE,fd,0)):nullptr;
 close(fd); if(bytes&&input==MAP_FAILED){perror("mmap");return 1;}
 vector<size_t> offsets; offsets.push_back(0);
 for(size_t i=0;i<bytes;i++)if(input[i]=='\n')offsets.push_back(i+1);
 if(offsets.back()!=bytes)offsets.push_back(bytes);
 size_t n_docs=offsets.size()-1;
 vector<vector<int>> docs(n_docs);
 constexpr int n_workers=6;
 vector<vector<vector<int>>> local(n_workers, vector<vector<int>>(ids.size()));
 vector<thread> indexers;
 const auto& immutable_lookup=lookup;
 for(int worker=0;worker<n_workers;worker++) indexers.emplace_back([&,worker]{
  size_t first=n_docs*worker/n_workers,last=n_docs*(worker+1)/n_workers;
  auto& lists=local[worker];
  for(size_t doc=first;doc<last;doc++){
   auto& seq=docs[doc];size_t i=offsets[doc],end=offsets[doc+1];
   while(i<end&&input[i]!='\t')++i; if(i==end)abort(); ++i;
   auto tokenchar=[](unsigned char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9');};
   while(i<end){
    while(i<end&&!tokenchar((unsigned char)input[i]))++i;
    if(i==end)break;char word[32];size_t len=0;while(i<end&&tokenchar((unsigned char)input[i])){unsigned char c=input[i++];word[len++]=c>='A'&&c<='Z'?c+32:c;}
    auto it=immutable_lookup.find(string_view(word,len));int id=it==immutable_lookup.end()?-1:it->second;seq.push_back(id);
    if(id>=0){auto& p=lists[id];if(p.empty()||p.back()!=int(doc))p.push_back(int(doc));}
   }
  }
 });
 for(auto& worker:indexers)worker.join();
 vector<vector<int>> postings(ids.size());
 for(size_t id=0;id<ids.size();id++){
  size_t size=0;for(int worker=0;worker<n_workers;worker++)size+=local[worker][id].size();
  postings[id].reserve(size);
  for(int worker=0;worker<n_workers;worker++){auto& p=local[worker][id];postings[id].insert(postings[id].end(),p.begin(),p.end());}
 }
 local.clear(); local.shrink_to_fit(); if(bytes)munmap(const_cast<char*>(input),bytes);
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
