#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <string>
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
 vector<vector<int>> postings(ids.size()); vector<vector<int>> docs; ifstream di(argv[1]);if(!di){cerr<<"Cannot open docs\n";return 1;}
 while(getline(di,line)){
  int doc=docs.size();docs.emplace_back();auto& seq=docs.back();size_t i=line.find('\t');if(i==string::npos){cerr<<"Bad document\n";return 1;}++i;
  while(i<line.size()){
   auto tokenchar=[](unsigned char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9');};
   while(i<line.size()&&!tokenchar((unsigned char)line[i]))++i;
   if(i==line.size())break;string word;while(i<line.size()&&tokenchar((unsigned char)line[i])){unsigned char c=line[i++];word.push_back(c>='A'&&c<='Z'?c+32:c);}
   auto it=ids.find(word);int id=it==ids.end()?-1:it->second;seq.push_back(id);
   if(id>=0){auto& p=postings[id];if(p.empty()||p.back()!=doc)p.push_back(doc);}
  }
 }
 ofstream out(argv[3]);if(!out){cerr<<"Cannot open output\n";return 1;}
 for(const auto& q:qs){vector<int> result;
  if(!q.phrase){result=postings[q.terms[0]];for(size_t k=1;k<q.terms.size();++k){vector<int> next;auto& p=postings[q.terms[k]];if(q.ops[k-1]=="AND")set_intersection(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else if(q.ops[k-1]=="OR")set_union(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));else set_difference(result.begin(),result.end(),p.begin(),p.end(),back_inserter(next));result.swap(next);}}
  else {int anchor=q.terms[0];for(int t:q.terms)if(postings[t].size()<postings[anchor].size())anchor=t;for(int d:postings[anchor]){auto& seq=docs[d];if(search(seq.begin(),seq.end(),q.terms.begin(),q.terms.end())!=seq.end())result.push_back(d);}}
  uint64_t sum=0;for(int d:result)sum+=d;out<<result.size()<<' '<<sum;for(size_t i=0;i<min<size_t>(10,result.size());++i)out<<' '<<result[i];out<<'\n';
 }
 if(!out){cerr<<"Output write failed\n";return 1;}return 0;
}
