#pragma once
#include "Arduino.h"
#define HSPI 1
#define MSBFIRST 1
#define SPI_MODE0 0
struct SPISettings{SPISettings(int,int,int){}};
struct SPIClass {
    SPIClass(int){}
    void begin(int,int,int,int){}
    void beginTransaction(SPISettings){}
    void endTransaction(){}
    void transfer(uint8_t b){transport.push_back((fakeDC?0x100:0)|b);}
    void writeBytes(const uint8_t* p,size_t n){for(size_t i=0;i<n;++i)transfer(p[i]);}
};
