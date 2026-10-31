#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

struct Group {
    std::vector<uint32_t> latencies;
    uint32_t errors = 0;
};
struct Endpoint {
    std::string name;
    std::array<Group, 72> hours;
    explicit Endpoint(std::string_view s) : name(s) {}
};

int main(int argc, char** argv) {
    const char* input = argc > 1 ? argv[1] : "/data/requests.log";
    const char* output = argc > 2 ? argv[2] : "/out/summary.txt";
    FILE* in = std::fopen(input, "rb");
    if (!in) { std::perror(input); return 1; }
    FILE* out = std::fopen(output, "wb");
    if (!out) { std::perror(output); return 1; }
    std::setvbuf(in, nullptr, _IOFBF, 1 << 20);
    std::setvbuf(out, nullptr, _IOFBF, 1 << 20);
    std::unordered_map<std::string_view, Endpoint*> lookup;
    lookup.reserve(2048);
    std::vector<std::unique_ptr<Endpoint>> endpoints;
    std::array<std::string, 72> hour_names;
    // Keep partial lines across reads; valid lines are less than 1024 bytes.
    constexpr size_t chunk_size = 1 << 20;
    std::vector<char> buffer(chunk_size + 1024);
    size_t carried = 0;
    for (;;) {
        size_t got = std::fread(buffer.data() + carried, 1, chunk_size, in);
        if (got == 0) break;
        char* end = buffer.data() + carried + got;
        while (end > buffer.data() && end[-1] != '\n') --end;
        char* line = buffer.data();
        while (line < end) {
            // The format guarantees this fixed 72-hour window, with 27-byte timestamps.
            int day = (line[8]-'0') * 10 + line[9]-'0';
            int days = line[6] == '0' ? day - 30 : day + 1;
            int hour = days * 24 + (line[11]-'0') * 10 + line[12]-'0' - 18;
            if (hour_names[hour].empty()) hour_names[hour] = std::string(line, 13) + ":00:00Z";
            char* p = line + 28;
            while (*p != ' ') ++p; // skip method
            const char* start = ++p;
            while (*p != ' ') ++p;
            std::string_view name(start, p-start);
            auto found = lookup.find(name);
            Endpoint* endpoint;
            if (found == lookup.end()) {
                endpoints.push_back(std::make_unique<Endpoint>(name));
                endpoint = endpoints.back().get();
                lookup.emplace(endpoint->name, endpoint);
            } else endpoint = found->second;
            Group& group = endpoint->hours[hour];
            group.errors += p[1] == '5';
            p += 5; // space, three status digits, space
            uint32_t latency = 0;
            while (*p >= '0' && *p <= '9') latency = latency * 10 + (*p++ - '0');
            group.latencies.push_back(latency);
            line = p + 1;
        }
        carried = buffer.data() + carried + got - end;
        std::memmove(buffer.data(), end, carried);
    }
    bool read_error = std::ferror(in);
    std::fclose(in);
    if (read_error) { std::perror("read"); return 1; }
    std::sort(endpoints.begin(), endpoints.end(), [](const auto& a, const auto& b) {
        return a->name < b->name;
    });
    for (size_t hour = 0; hour < 72; ++hour) {
        if (hour_names[hour].empty()) continue;
        for (auto& endpoint : endpoints) {
            auto& group = endpoint->hours[hour];
            auto& v = group.latencies;
            size_t n = v.size();
            if (!n) continue;
            // Tiny groups are cheaper to sort; select only needed ranks in larger groups.
            auto rank = [n](size_t p) { return (p*n + 99)/100 - 1; };
            if (n < 128) {
                std::sort(v.begin(), v.end());
            } else {
                const auto a = rank(50), b = rank(95), c = rank(99);
                std::nth_element(v.begin(), v.begin() + a, v.end());
                std::nth_element(v.begin() + a + 1, v.begin() + b, v.end());
                if (c > b) std::nth_element(v.begin() + b + 1, v.begin() + c, v.end());
            }
            std::fprintf(out, "%s %s %zu %u %u %u %u %llu\n", hour_names[hour].c_str(),
                endpoint->name.c_str(), n, v[rank(50)], v[rank(95)], v[rank(99)],
                group.errors, static_cast<unsigned long long>(uint64_t(group.errors)*1000000/n));
        }
    }
    return std::fclose(out) == 0 ? 0 : 1;
}
