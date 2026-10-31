#include <algorithm>
#include <atomic>
#include <thread>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using namespace std;

struct Group {
    string key;
    int64_t count=0, ids=0, sum=0, low=INT64_MAX, high=INT64_MIN, namebytes=0, notebytes=0;
    vector<string_view> names;
};
string readfile(const string& path) {
    ifstream in(path, ios::binary);
    if (!in) { cerr << "Cannot open " << path << '\n'; exit(1); }
    in.seekg(0, ios::end);
    string content(in.tellg(), '\0');
    in.seekg(0);
    if (!in.read(content.data(), content.size())) { cerr << "Cannot read " << path << '\n'; exit(1); }
    return content;
}
uint32_t number(const char*& p) {
    uint32_t n=0;
    while (*p >= '0' && *p <= '9') n=n*10+(*p++-'0');
    return n;
}
// Names are always quoted when nonempty. Their escaped byte sequence is a
// canonical representation, so distinct comparison can refer into the input.
struct Field { string_view encoded; size_t decoded_size; };
Field field(const char*& p) {
    if (*p != '"') {
        const char* start = p;
        while (*p != ',') ++p;
        auto len = static_cast<size_t>(p - start); ++p;
        return {string_view(start, len), len};
    }
    const char* start = ++p;
    size_t escapes = 0;
    while (true) {
        if (*p++ == '"') {
            if (*p != '"') break;
            ++escapes; ++p;
        }
    }
    size_t len = p - start - 1;
    ++p; // comma
    return {string_view(start, len), len - escapes};
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
        Field name=field(p), note=field(p);
        uint32_t region=number(p); ++p;
        bool neg=*p=='-'; if (neg) ++p;
        int64_t cents=number(p)*100; ++p; cents+=number(p); if (neg) cents=-cents;
        if (*p=='\r') ++p; if (*p=='\n') ++p;
        Group& g=groups[region<regions.size()?regions[region]:0];
        ++g.count; g.ids+=id; g.sum+=cents; g.low=min(g.low,cents); g.high=max(g.high,cents);
        g.namebytes+=name.decoded_size; g.notebytes+=note.decoded_size; g.names.push_back(name.encoded);
    }
    sort(groups.begin(),groups.end(),[](const Group& a,const Group& b){return a.key<b.key;});
    atomic<size_t> next{0};
    vector<thread> workers;
    for (int i=0;i<6;++i) workers.emplace_back([&] {
        size_t idx;
        while ((idx=next.fetch_add(1, memory_order_relaxed)) < groups.size()) {
            auto& names = groups[idx].names;
            sort(names.begin(), names.end());
            names.erase(unique(names.begin(), names.end()), names.end());
        }
    });
    for (auto& worker:workers) worker.join();
    ofstream result(out+"/aggregates.txt",ios::binary);
    if (!result) return 1;
    for(auto& g:groups) if(g.count) {
        result<<g.key<<' '<<g.count<<' '<<g.ids<<' '<<money(g.sum)<<' '<<money(g.low)<<' '<<money(g.high)<<' '<<g.names.size()<<' '<<g.namebytes<<' '<<g.notebytes<<'\n';
    }
}
