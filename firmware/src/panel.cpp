#include <Arduino.h>
#include <TFT_eSPI.h> // Fixed vendor waveform tables; no vendor hardware calls.
#include "panel.h"

void PaperPanel::begin() {
    pinMode(10,OUTPUT);digitalWrite(10,HIGH);
    pinMode(11,OUTPUT);pinMode(12,OUTPUT);digitalWrite(12,HIGH);
    pinMode(13,INPUT);
    spi.begin(7,-1,9,10);
}
bool PaperPanel::ready() {
    const uint32_t start=millis();
    delay(10);
    while (!digitalRead(13)) {
        if (millis()-start>=20000) { Serial.println("Panel BUSY timeout; frame not committed");return false; }
        delay(5);
    }
    return true;
}
void PaperPanel::command(uint8_t c) {
    digitalWrite(11,LOW);digitalWrite(10,LOW);spi.transfer(c);digitalWrite(10,HIGH);
}
void PaperPanel::data(uint8_t d) {
    digitalWrite(11,HIGH);digitalWrite(10,LOW);spi.transfer(d);digitalWrite(10,HIGH);
}
void PaperPanel::bytes(const uint8_t* p,size_t n) {
    digitalWrite(11,HIGH);digitalWrite(10,LOW);spi.writeBytes(p,n);digitalWrite(10,HIGH);
}
bool PaperPanel::wake(bool partial) {
    digitalWrite(12,LOW);delay(10);digitalWrite(12,HIGH);delay(10);
    if (!ready()) return false;
    command(0x01);data(7);
    if (partial) { data(7);data(0x3f);data(0x3f); }
    else {
        for(int i=0;i<4;++i)data(CMD_USER[i]);
        command(0x30);data(CMD_USER[4]);command(0x82);data(CMD_USER[5]);
    }
    command(0x06);data(0x17);data(0x17);data(0x28);data(0x17);
    command(0x04);delay(100);if (!ready()) return false;
    command(0x00);data(partial?0x1f:0x3f);
    command(0x61);data(3);data(0x20);data(1);data(0xe0);
    command(0x15);data(0);
    command(0x50);data(0x10);data(7);
    if(partial) {
        command(0xe0);data(2);command(0xe5);data(0x6e);
    } else {
        const uint8_t* tables[]={LUT_VCOM,LUT_WW,LUT_KW,LUT_WK,LUT_KK};
        for(int i=0;i<5;++i){command(0x20+i);bytes(tables[i],42);}
    }
    return true;
}
void PaperPanel::pixels(uint8_t c,const uint8_t* image,paper::Rect r) {
    command(c);
    for(int y=r.y;y<r.y+r.h;++y)bytes(image+y*paper::STRIDE+r.x/8,r.w/8);
}
bool PaperPanel::refresh(const uint8_t* oldImage,const uint8_t* newImage,paper::Rect r,bool full) {
    if(!paper::validRect(r))return false;
    spi.beginTransaction(SPISettings(10000000,MSBFIRST,SPI_MODE0));
    bool ok=wake(!full);
    if(ok) {
        command(0x50);data(0xa9);data(7);
        command(0x91);command(0x90);
        uint8_t window[9];paper::windowBytes(r,window);bytes(window,9);
        pixels(0x10,oldImage,r);pixels(0x13,newImage,r);
        command(0x12);delay(1);ok=ready();
        if(ok) {
            command(0x92);
            command(0x50);data(0xf7);command(0x02);ok=ready();
        }
        if(ok){command(0x07);data(0xa5);}
    }
    spi.endTransaction();
    return ok;
}
