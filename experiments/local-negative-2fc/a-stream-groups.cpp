#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <memory>
#include <string>
#include <string_view>
#include <thread>
#include <unordered_map>
#include <vector>
struct Group{std::vector<uint32_t> v;uint32_t errors=0;};
struct Endpoint{std::string name;std::array<Group,72> hours;explicit Endpoint(std::string_view s):name(s){}};
struct Shard {std::unordered_map<std::string_view,Endpoint*> lookup;std::vector<std::unique_ptr<Endpoint>> endpoints;std::array<std::string,72> names;bool error=false;};
static size_t boundary(const char* path,size_t offset,size_t size){if(!offset||offset>=size)return offset;FILE* f=std::fopen(path,"rb");if(!f){std::perror(path);std::exit(1);} if(fseeko(f,offset-1,SEEK_SET)!=0)std::exit(1);int c;while((c=std::fgetc(f))!=EOF&&c!='\n')++offset;std::fclose(f);return offset;}
static void ingest(Shard& shard,const char* path,size_t start,size_t stop){
 FILE* in=std::fopen(path,"rb");if(!in){shard.error=true;return;} if(fseeko(in,start,SEEK_SET)!=0){shard.error=true;std::fclose(in);return;}
 shard.lookup.reserve(2048); constexpr size_t chunk=1<<20;std::vector<char> buf(chunk+1024);size_t carried=0;size_t pos=start;
 while(pos<stop){size_t got=std::fread(buf.data()+carried,1,std::min(chunk,stop-pos),in);if(!got)break;pos+=got;char* end=buf.data()+carried+got;while(end>buf.data()&&end[-1]!='\n')--end;char* line=buf.data();
 while(line<end){int day=(line[8]-'0')*10+line[9]-'0';int days=line[6]=='0'?day-30:day+1;int hour=days*24+(line[11]-'0')*10+line[12]-'0'-18;
 if(shard.names[hour].empty())shard.names[hour]=std::string(line,13)+":00:00Z";char* p=line+28;while(*p!=' ')++p;const char* start_name=++p;while(*p!=' ')++p;std::string_view name(start_name,p-start_name);auto it=shard.lookup.find(name);Endpoint* ep;if(it==shard.lookup.end()){shard.endpoints.push_back(std::make_unique<Endpoint>(name));ep=shard.endpoints.back().get();shard.lookup.emplace(ep->name,ep);}else ep=it->second;
 Group& g=ep->hours[hour];g.errors+=p[1]=='5';p+=5;uint32_t v=0;while(*p>='0'&&*p<='9')v=v*10+(*p++-'0');g.v.push_back(v);line=p+1;}
 carried=buf.data()+carried+got-end;std::memmove(buf.data(),end,carried);
 }
 shard.error=std::ferror(in)||pos!=stop||carried!=0;std::fclose(in);
}
int main(int argc,char**argv){const char* input=argc>1?argv[1]:"/data/requests.log";const char* output=argc>2?argv[2]:"/out/summary.txt";constexpr int N=3;std::error_code ec;size_t bytes=std::filesystem::file_size(input,ec);if(ec){std::fprintf(stderr,"file_size: %s\n",ec.message().c_str());return 1;}
 std::array<size_t,N+1> bounds{};for(int i=0;i<=N;++i)bounds[i]=boundary(input,bytes*i/N,bytes);std::array<Shard,N> shards;std::vector<std::thread> threads;for(int i=0;i<N;++i)threads.emplace_back(ingest,std::ref(shards[i]),input,bounds[i],bounds[i+1]);for(auto& t:threads)t.join();

 for (auto& shard:shards) if(shard.error){std::fprintf(stderr,"read failed\n");return 1;}
 std::vector<std::string_view> names;
 for(auto& shard:shards) for(auto& e:shard.endpoints) names.push_back(e->name);
 std::sort(names.begin(),names.end());names.erase(std::unique(names.begin(),names.end()),names.end());
 FILE* out=std::fopen(output,"wb");if(!out){std::perror(output);return 1;}std::setvbuf(out,nullptr,_IOFBF,1<<20);
 std::string ob;ob.reserve(1<<20);auto num=[&](uint64_t x){char b[32];auto r=std::to_chars(b,b+sizeof(b),x);ob.append(b,r.ptr);};
 std::vector<uint32_t> vals;
 for(size_t h=0;h<72;++h){
  const std::string* hour=nullptr;for(auto& shard:shards)if(!shard.names[h].empty()){hour=&shard.names[h];break;}if(!hour)continue;
  for(auto name:names){vals.clear();uint32_t errors=0;
   for(auto& shard:shards){auto it=shard.lookup.find(name);if(it==shard.lookup.end())continue;auto& g=it->second->hours[h];errors+=g.errors; vals.insert(vals.end(),g.v.begin(),g.v.end());}
   size_t n=vals.size();if(!n)continue;auto rank=[n](size_t p){return(p*n+99)/100-1;};
   if(n<128)std::sort(vals.begin(),vals.end());else{auto a=rank(50),b=rank(95),c=rank(99);std::nth_element(vals.begin(),vals.begin()+a,vals.end());std::nth_element(vals.begin()+a+1,vals.begin()+b,vals.end());if(c>b)std::nth_element(vals.begin()+b+1,vals.begin()+c,vals.end());}
   ob.append(*hour);ob.push_back(' ');ob.append(name);ob.push_back(' ');num(n);ob.push_back(' ');num(vals[rank(50)]);ob.push_back(' ');num(vals[rank(95)]);ob.push_back(' ');num(vals[rank(99)]);ob.push_back(' ');num(errors);ob.push_back(' ');num(uint64_t(errors)*1000000/n);ob.push_back('\n');
   if(ob.size()>=(1<<20)){if(std::fwrite(ob.data(),1,ob.size(),out)!=ob.size())return 1;ob.clear();}
  }
 }
 if(std::fwrite(ob.data(),1,ob.size(),out)!=ob.size())return 1;return std::fclose(out)==0?0:1;
}
