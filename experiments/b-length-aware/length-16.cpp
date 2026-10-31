#include <algorithm>
#include <array>
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
struct alignas(32) Key { uint64_t v[4]{}; };
static Key key_of(const char* p,size_t n) { Key k; memcpy(&k,p,n); return k; }
static uint64_t khash(const Key& k,size_t n){ uint64_t h=0x9e3779b97f4a7c15ULL; for(size_t j=0;j<(n+7)/8;++j){h^=k.v[j];h*=0xbf58476d1ce4e5b9ULL;h^=h>>29;}return h; }
struct Dict { vector<int> slots; vector<Key> keys; explicit Dict(size_t n):keys(n) { size_t cap=1; while(cap<n*2)cap*=2; slots.assign(cap,-1); } void add(const string& s,int id){Key k=key_of(s.data(),s.size());keys[id]=k;size_t i=(khash(k,s.size())>>32)&(slots.size()-1);while(slots[i]!=-1)i=(i+1)&(slots.size()-1);slots[i]=id;} int get(const char* p,size_t n) const {Key k=key_of(p,n);size_t i=(khash(k,n)>>32)&(slots.size()-1);while(slots[i]!=-1){int id=slots[i];if(!memcmp(&k,&keys[id],sizeof(k)))return id;i=(i+1)&(slots.size()-1);}return -1;} };
struct Query { bool phrase; vector<int> terms; vector<string> ops; };
struct PhraseStats { uint64_t sum=0; uint32_t count=0; int last=-1; array<int,10> first{}; };
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
 Dict lookup(ids.size());
 for (const auto& entry : ids) lookup.add(entry.first,entry.second);
 int fd=open(argv[1],O_RDONLY); if(fd<0){perror("open");return 1;}
 struct stat st; if(fstat(fd,&st)!=0){perror("fstat");return 1;}
 size_t bytes=st.st_size;
 vector<size_t> offsets{0};
 vector<char> scan(1<<20);
 for(size_t pos=0; pos<bytes;) {
  size_t len=min(scan.size(),bytes-pos); ssize_t got=pread(fd,scan.data(),len,pos);
  if(got<=0){perror("pread");return 1;}
  for(size_t i=0;i<size_t(got);i++)if(scan[i]=='\n')offsets.push_back(pos+i+1);
  pos+=size_t(got);
 }
 if(offsets.back()!=bytes)offsets.push_back(bytes);
 size_t n_docs=offsets.size()-1;
 // Query-driven phrase indexing: select a phrase bigram and index matching documents.
 vector<int> term_frequency(ids.size());
 vector<unsigned char> bool_terms(ids.size());
 for(const auto& q:qs)for(int id:q.terms){if(q.phrase)++term_frequency[id];else bool_terms[id]=1;}
 // Identical phrase queries share a single aggregate; never retain full result lists.
 unordered_map<string,int> phrase_cache;
 vector<int> phrase_group(qs.size(),-1), phrase_rep;
 for(int qid=0;qid<int(qs.size());++qid)if(qs[qid].phrase){
  const auto& v=qs[qid].terms;
  string key(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(int));
  auto [it,inserted]=phrase_cache.emplace(move(key),int(phrase_rep.size()));
  if(inserted)phrase_rep.push_back(qid);
  phrase_group[qid]=it->second;
 }
 unordered_map<uint64_t,vector<pair<int,int>>> phrase_pairs;
 vector<unsigned char> phrase_left(ids.size()), phrase_right(ids.size());
 auto pair_key=[](int a,int b){return (uint64_t(uint32_t(a))<<32)|uint32_t(b);};
 for(int group=0;group<int(phrase_rep.size());++group){
  const auto& terms=qs[phrase_rep[group]].terms; int anchor=0;
  for(int i=1;i+1<int(terms.size());++i)
   if(term_frequency[terms[i]]+term_frequency[terms[i+1]]<term_frequency[terms[anchor]]+term_frequency[terms[anchor+1]])anchor=i;
  phrase_left[terms[anchor]]=1;phrase_right[terms[anchor+1]]=1;
  phrase_pairs[pair_key(terms[anchor],terms[anchor+1])].emplace_back(group,anchor);
 }
 const auto& immutable_pairs=phrase_pairs;
 constexpr int n_workers=16;
 vector<vector<vector<int>>> local(n_workers, vector<vector<int>>(ids.size()));
 vector<vector<PhraseStats>> phrase_results(n_workers,vector<PhraseStats>(phrase_rep.size()));
 vector<thread> indexers;
 const auto& immutable_lookup=lookup;
 for(int worker=0;worker<n_workers;worker++) indexers.emplace_back([&,worker]{
  size_t doc=n_docs*worker/n_workers,last=n_docs*(worker+1)/n_workers;
  size_t pos=offsets[doc],stop=offsets[last]; auto& lists=local[worker];
  string pending; pending.reserve((1<<20)+4096); vector<char> buffer(1<<20); vector<int> seq;
  while(pos<stop){
   size_t len=min(buffer.size(),stop-pos); ssize_t got=pread(fd,buffer.data(),len,pos);
   if(got<=0){perror("pread");abort();} pos+=size_t(got); pending.append(buffer.data(),size_t(got));
   size_t start=0;
   while(start<pending.size()){
    size_t line_end=pending.find('\n',start);
    if(line_end==string::npos){if(pos<stop)break;line_end=pending.size();}
    seq.clear(); size_t i=pending.find('\t',start); if(i>=line_end)abort(); ++i;
    auto tokenchar=[](unsigned char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9');};
    while(i<line_end){
     while(i<line_end&&!tokenchar((unsigned char)pending[i]))++i;
     if(i==line_end)break;char word[32];size_t length=0;while(i<line_end&&tokenchar((unsigned char)pending[i])){unsigned char c=pending[i++];word[length++]=c>='A'&&c<='Z'?c+32:c;}
     int id=immutable_lookup.get(word,length);seq.push_back(id);
     if(id>=0&&bool_terms[id]){auto& p=lists[id];if(p.empty()||p.back()!=int(doc))p.push_back(int(doc));}
    }
    for(size_t pos=1;pos<seq.size();++pos){
     if(seq[pos-1]<0||seq[pos]<0||!phrase_left[seq[pos-1]]||!phrase_right[seq[pos]])continue;
     auto it=immutable_pairs.find(pair_key(seq[pos-1],seq[pos]));if(it==immutable_pairs.end())continue;
     for(auto [group,anchor]:it->second){
      if(pos-1<size_t(anchor))continue; size_t first=pos-1-anchor; const auto& terms=qs[phrase_rep[group]].terms;
      if(first+terms.size()>seq.size()||!equal(terms.begin(),terms.end(),seq.begin()+first))continue;
      auto& matches=phrase_results[worker][group];if(matches.last!=int(doc)){matches.last=int(doc);if(matches.count<10)matches.first[matches.count]=doc;++matches.count;matches.sum+=doc;}
     }
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
 for(int worker=0;worker<16;worker++) workers.emplace_back([&]{
 for(size_t n;(n=next.fetch_add(1,memory_order_relaxed))<qs.size();){const auto& q=qs[n];vector<int> result;
  if(!q.phrase){result=postings[q.terms[0]];for(size_t k=1;k<q.terms.size();++k){vector<int> next;auto& p=postings[q.terms[k]];if(q.ops[k-1]=="AND")set_intersection(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else if(q.ops[k-1]=="OR")set_union(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else set_difference(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));result.swap(next);}}
  ostringstream os;
  if(q.phrase){
   uint64_t sum=0,count=0; for(int w=0;w<n_workers;++w){const auto& p=phrase_results[w][phrase_group[n]];count+=p.count;sum+=p.sum;}
   os<<count<<' '<<sum;size_t written=0;
   for(int w=0;w<n_workers&&written<10;++w){const auto& p=phrase_results[w][phrase_group[n]];for(size_t i=0;i<min<size_t>(10,p.count)&&written<10;++i,++written)os<<' '<<p.first[i];}
  }else{
   uint64_t sum=0;for(int d:result)sum+=d;os<<result.size()<<' '<<sum;for(size_t i=0;i<min<size_t>(10,result.size());++i)os<<' '<<result[i];
  }
  os<<'\n';outputs[n]=os.str();
 } });
 for(auto& worker:workers)worker.join();
 for(const auto& line:outputs)out<<line;
 if(!out){cerr<<"Output write failed\n";return 1;}return 0;
}
