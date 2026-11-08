#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace paper {
constexpr int WIDTH = 800, HEIGHT = 480, STRIDE = WIDTH / 8;
constexpr size_t IMAGE_SIZE = STRIDE * HEIGHT, HEADER_SIZE = 24;
constexpr size_t PACKET_SIZE = HEADER_SIZE + IMAGE_SIZE;
struct Rect { int x, y, w, h; };
inline bool validRect(Rect r) {
    return r.x>=0 && r.y>=0 && r.w>0 && r.h>0 && r.x+r.w<=WIDTH && r.y+r.h<=HEIGHT && r.x%8==0 && r.w%8==0;
}
inline void windowBytes(Rect r,uint8_t* out) {
    int values[]={r.x,r.x+r.w-1,r.y,r.y+r.h-1};
    for(int i=0;i<4;++i){out[2*i]=values[i]>>8;out[2*i+1]=values[i]&255;}
    out[8]=1;
}
struct LocalClock {
    uint32_t epoch=0;
    int64_t started=0;
    void set(uint32_t value, int64_t micros) { epoch=value; started=micros; }
    uint32_t now(int64_t micros) const {
        return epoch ? epoch+uint32_t((micros-started)/1000000) : 0;
    }
};
constexpr Rect REGIONS[] = {
    {0,0,800,40}, {0,40,280,408}, {280,40,256,40},
    {280,80,256,128}, {280,208,256,240}, {536,40,264,408}, {0,448,800,32}
};
inline uint32_t u32(const uint8_t* p) {
    return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24;
}
inline uint32_t crcUpdate(uint32_t crc, const uint8_t* data, size_t size) {
    for (size_t i=0; i<size; ++i) {
        crc ^= data[i];
        for (int b=0; b<8; ++b) crc = (crc>>1) ^ (0xedb88320U & (0U-(crc&1)));
    }
    return crc;
}
inline bool validPacket(const uint8_t* p, size_t n) {
    if (n != PACKET_SIZE || memcmp(p,"PPR2",4) || p[4]!=0x20 || p[5]!=3 || p[6]!=0xe0 || p[7]!=1) return false;
    const uint32_t now=u32(p+8), source=u32(p+12);
    if (now<1704067200U || now>=2145916800U || !source || source>now+5 || u32(p+16)>1) return false;
    uint32_t crc=crcUpdate(0xffffffffU,p,20);
    crc=crcUpdate(crc,p+HEADER_SIZE,IMAGE_SIZE)^0xffffffffU;
    return crc==u32(p+20);
}
// Byte-aligned bounds inside a region; unchanged regions produce no panel command.
inline bool dirtyBounds(const uint8_t* before, const uint8_t* after, Rect region, Rect& out) {
    int left=WIDTH, right=-1, top=HEIGHT, bottom=-1;
    for (int y=region.y; y<region.y+region.h; ++y) {
        for (int b=region.x/8; b<(region.x+region.w)/8; ++b) {
            if (before[y*STRIDE+b] == after[y*STRIDE+b]) continue;
            if (b*8<left) left=b*8;
            if (b*8+7>right) right=b*8+7;
            if (y<top) top=y;
            if (y>bottom) bottom=y;
        }
    }
    if (right<0) return false;
    out={left,top,right-left+1,bottom-top+1};
    return true;
}
inline bool refreshAllowed(unsigned displayedPage, unsigned updatedPage) {
    return displayedPage==0 && updatedPage==0;
}
}
