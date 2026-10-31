#include <algorithm>
#include <atomic>
#include <thread>
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
 vector<vector<int>> postings(ids.size()); vector<vector<int>> docs; ifstream di(argv[1]);if(!di){cerr<<"Cannot open docs\n";return 1;}
 while(getline(di,line)){
  int doc=docs.size();docs.emplace_back();auto& seq=docs.back();size_t i=line.find('\t');if(i==string::npos){cerr<<"Bad document\n";return 1;}++i;
  while(i<line.size()){
   auto tokenchar=[](unsigned char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9');};
   while(i<line.size()&&!tokenchar((unsigned char)line[i]))++i;
   if(i==line.size())break;char word[32];size_t len=0;while(i<line.size()&&tokenchar((unsigned char)line[i])){unsigned char c=line[i++];word[len++]=c>='A'&&c<='Z'?c+32:c;}
   auto it=lookup.find(string_view(word,len));int id=it==lookup.end()?-1:it->second;seq.push_back(id);
   if(id>=0){auto& p=postings[id];if(p.empty()||p.back()!=doc)p.push_back(doc);}
  }
 }
 ofstream out(argv[3]);if(!out){cerr<<"Cannot open output\n";return 1;}
 vector<string> outputs(qs.size()); atomic<size_t> next{0}; vector<thread> workers;
 for(int worker=0;worker<6;worker++) workers.emplace_back([&]{
 for(size_t n;(n=next.fetch_add(1,memory_order_relaxed))<qs.size();){const auto& q=qs[n];vector<int> result;
  if(!q.phrase){result=postings[q.terms[0]];for(size_t k=1;k<q.terms.size();++k){vector<int> next;auto& p=postings[q.terms[k]];if(q.ops[k-1]=="AND")set_intersection(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else if(q.ops[k-1]=="OR")set_union(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else set_difference(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));result.swap(next);}}
  else {
   vector<int> terms=q.terms;
   sort(terms.begin(),terms.end(),[&](int a,int b){return postings[a].size()<postings[b].size();});
   terms.erase(unique(terms.begin(),terms.end()),terms.end());
   vector<int> candidates=postings[terms[0]];
   for(size_t k=1;k<terms.size()&&!candidates.empty();++k){
    const auto& p=postings[terms[k]];vector<int> filtered;
    if(candidates.size()*8<p.size()) {
     auto it=p.begin();for(int d:candidates){it=lower_bound(it,p.end(),d);if(it==p.end())break;if(*it==d)filtered.push_back(d);}
    }else set_intersection(candidates.begin(),candidates.end(),p.begin(),p.end(),back_inserter(filtered));
    candidates.swap(filtered);
   }
   for(int d:candidates){auto& seq=docs[d];if(search(seq.begin(),seq.end(),q.terms.begin(),q.terms.end())!=seq.end())result.push_back(d);}
  }
  uint64_t sum=0;for(int d:result)sum+=d;ostringstream os;os<<result.size()<<' '<<sum;for(size_t i=0;i<min<size_t>(10,result.size());++i)os<<' '<<result[i];os<<'\n';outputs[n]=os.str();
 } });
 for(auto& worker:workers)worker.join();
 for(const auto& line:outputs)out<<line;
 if(!out){cerr<<"Output write failed\n";return 1;}return 0;
}
