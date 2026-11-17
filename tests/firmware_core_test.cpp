#include "paper_core.h"
#include <assert.h>
#include <fstream>
#include <iterator>
#include <vector>
using namespace paper;
int main(int argc, char** argv) {
    if (argc==2) {
        std::ifstream file(argv[1],std::ios::binary);
        std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});
        return validPacket(bytes.data(),bytes.size()) ? 0 : 2;
    }
    std::vector<uint8_t> before(IMAGE_SIZE,255), after=before;
    LocalClock clock;
    assert(clock.now(100000000)==0); // No fabricated compile-time clock.
    clock.set(1794132000,5000000);
    assert(clock.now(65000000)==1794132060); // Offline minute, no network event.
    assert(clock.now(3605000000LL)==1794135600); // Offline hour.
    assert(clock.now(5000000LL+5000000000000LL)==1799132000); // Beyond millis wrap.
    const uint8_t known[]="123456789";
    assert((crcUpdate(0xffffffffU,known,9)^0xffffffffU)==0xcbf43926U);
    Rect bounds;
    assert(!dirtyBounds(before.data(),after.data(),REGIONS[3],bounds));
    after[100*STRIDE+400/8]=0;
    for (unsigned i=0;i<7;++i) {
        bool changed=dirtyBounds(before.data(),after.data(),REGIONS[i],bounds);
        assert(changed==(i==3));
        if(changed) assert(bounds.x==400 && bounds.y==100 && bounds.w==8 && bounds.h==1);
    }
    // All screen pixels, including edges and dividers, belong to exactly one region.
    for(int y=0;y<HEIGHT;++y) for(int x=0;x<WIDTH;++x) {
        int count=0;
        for(const auto& r:REGIONS) count+=x>=r.x && x<r.x+r.w && y>=r.y && y<r.y+r.h;
        assert(count==1);
    }
    assert(refreshAllowed(0,0));
    for(unsigned page=1;page<4;++page) {
        assert(!refreshAllowed(page,0));
        assert(!refreshAllowed(0,page));
        assert(!refreshAllowed(page,page));
    }
    // Exercise every byte on all four edges and representative interior rows.
    for(int y: {0,39,40,79,80,207,208,447,448,479}) {
        for(int b=0;b<STRIDE;++b) {
            after=before;after[y*STRIDE+b]^=0x80;
            int matches=0;
            for(const auto& region:REGIONS) {
                Rect changed;
                if(dirtyBounds(before.data(),after.data(),region,changed)) {
                    ++matches;
                    assert(validRect(changed));
                    assert(changed.x==b*8 && changed.y==y && changed.w==8 && changed.h==1);
                }
            }
            assert(matches==1);
        }
    }
}
