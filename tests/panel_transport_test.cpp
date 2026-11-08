#include "panel.h"
#include <Arduino.h>
#include <cassert>
uint32_t fakeMillis=0;
bool fakeBusy=false;
int fakeDC=0;
std::vector<int> transport;
SerialMock Serial;
std::vector<uint8_t> payload(int command) {
    std::vector<uint8_t> result;
    bool found=false;
    for(int item:transport) {
        if(item<256){if(found)break;found=item==command;}
        else if(found)result.push_back(item&255);
    }
    return result;
}
int main() {
    PaperPanel panel;panel.begin();
    std::vector<uint8_t> before(paper::IMAGE_SIZE,0xaa),after(paper::IMAGE_SIZE,0x55);
    assert(panel.refresh(before.data(),after.data(),{792,479,8,1},false));
    assert(payload(0x90)==std::vector<uint8_t>({3,24,3,31,1,223,1,223,1}));
    assert(payload(0x10)==std::vector<uint8_t>({0xaa}));
    assert(payload(0x13)==std::vector<uint8_t>({0x55}));
    transport.clear();
    assert(panel.refresh(before.data(),after.data(),{0,0,800,480},true));
    assert(payload(0x90)==std::vector<uint8_t>({0,0,3,31,0,0,1,223,1}));
    assert(payload(0x10).size()==paper::IMAGE_SIZE);
    assert(payload(0x13).size()==paper::IMAGE_SIZE);
    fakeBusy=true;fakeMillis=0;transport.clear();
    assert(!panel.refresh(before.data(),after.data(),{0,0,8,1},false));
    assert(fakeMillis>=20000 && fakeMillis<21000);
    assert(payload(0x12).empty());
    assert(!panel.refresh(before.data(),after.data(),{799,0,8,1},false));
}
