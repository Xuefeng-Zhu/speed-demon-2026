#define main solution_main
#include "main.cpp"
#undef main
#include <cassert>
#include <random>
int main() {
 std::mt19937_64 rng(0x139a9f);
 std::unordered_map<std::string,int> ids;
 auto add=[&](const std::string &s) { if (!ids.count(s)) ids.emplace(s,ids.size()); };
 for (int n=1;n<=32;++n) {add(std::string(n,'a'));add(std::string(n,'0'));add(std::string(n-1,'a')+'0');add(std::string(n-1,'0')+'a');}
 while(ids.size()<250000) {int n=1+rng()%32;std::string s(n,'a');for(char &c:s)c="abcdefghijklmnopqrstuvwxyz0123456789"[rng()%36];add(s);}
 Dict dict(ids.size()); for(const auto &p:ids)dict.add(p.first,p.second);
 for(const auto &p:ids)assert(dict.get(p.first.data(),p.first.size())==p.second);
 for(int i=0;i<250000;i++){int n=1+rng()%32;std::string s(n,'0');for(char &c:s)c="abcdefghijklmnopqrstuvwxyz0123456789"[rng()%36];auto p=ids.find(s);int actual=dict.get(s.data(),s.size());assert(actual==(p==ids.end()?-1:p->second));}
 printf("PASS %zu unique keys and 250000 generated membership queries, all lengths 1..32\n",ids.size());
}
