#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using namespace std;

struct Group {
    string key;
    int64_t count=0, ids=0, sum=0, low=INT64_MAX, high=INT64_MIN, namebytes=0, notebytes=0;
    unordered_set<string> names;
};
string readfile(const string& path) {
    ifstream in(path, ios::binary);
    if (!in) { cerr << "Cannot open " << path << '\n'; exit(1); }
    return string(istreambuf_iterator<char>(in), {});
}
uint32_t number(const char*& p) {
    uint32_t n=0;
    while (*p >= '0' && *p <= '9') n=n*10+(*p++-'0');
    return n;
}
// Field syntax is the official generator's CSV grammar. Quotes inside a quoted
// field are doubled; the byte immediately after its closing quote is a comma.
string field(const char*& p) {
    string result;
    if (*p=='"') {
        ++p;
        while (true) {
            if (*p=='"') {
                ++p;
                if (*p!='"') break;
            }
            result.push_back(*p++);
        }
    } else {
        while (*p!=',') result.push_back(*p++);
    }
    ++p; // comma
    return result;
}
string money(int64_t cents) {
    bool neg=cents<0;
    if (neg) cents=-cents;
    return string(neg ? "-" : "")+to_string(cents/100)+'.'+char('0'+(cents%100)/10)+char('0'+cents%10);
}
int main(int argc,char** argv) {
    string data=argc>1?argv[1]:"/data", out=argc>2?argv[2]:"/out";
    string lookup=readfile(data+"/regions.csv"), records=readfile(data+"/records.csv");
    vector<uint16_t> regions(1000000, 0);
    vector<Group> groups(1); groups[0].key="_UNMATCHED";
    unordered_map<string,uint16_t> country;
    const char *p=lookup.c_str(); while (*p++!='\n') {}
    while (*p) {
        uint32_t id=number(p); ++p;
        string key(p,3); p+=4;
        auto it=country.find(key);
        if (it==country.end()) {
            uint16_t index=groups.size(); groups.emplace_back(); groups.back().key=key;
            it=country.emplace(key,index).first;
        }
        if(id<regions.size()) regions[id]=it->second;
    }
    p=records.c_str(); while (*p++!='\n') {}
    while (*p) {
        if ((unsigned char)*p==0xef) p+=3;
        uint32_t id=number(p); ++p;
        string name=field(p), note=field(p);
        uint32_t region=number(p); ++p;
        bool neg=*p=='-'; if (neg) ++p;
        int64_t cents=number(p)*100; ++p; cents+=number(p); if (neg) cents=-cents;
        if (*p=='\r') ++p; if (*p=='\n') ++p;
        Group& g=groups[region<regions.size()?regions[region]:0];
        ++g.count; g.ids+=id; g.sum+=cents; g.low=min(g.low,cents); g.high=max(g.high,cents);
        g.namebytes+=name.size(); g.notebytes+=note.size(); g.names.insert(std::move(name));
    }
    sort(groups.begin(),groups.end(),[](const Group& a,const Group& b){return a.key<b.key;});
    ofstream result(out+"/aggregates.txt",ios::binary);
    if (!result) return 1;
    for(const auto& g:groups) if(g.count) result<<g.key<<' '<<g.count<<' '<<g.ids<<' '<<money(g.sum)<<' '<<money(g.low)<<' '<<money(g.high)<<' '<<g.names.size()<<' '<<g.namebytes<<' '<<g.notebytes<<'\n';
}
