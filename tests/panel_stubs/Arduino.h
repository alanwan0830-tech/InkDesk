#pragma once
#include <stdint.h>
#include <stddef.h>
#include <vector>
#define OUTPUT 1
#define INPUT 0
#define HIGH 1
#define LOW 0
extern uint32_t fakeMillis;
extern bool fakeBusy;
extern int fakeDC;
extern std::vector<int> transport;
inline uint32_t millis(){return fakeMillis;}
inline void delay(uint32_t n){fakeMillis+=n;}
inline void pinMode(int,int){}
inline void digitalWrite(int pin,int value){if(pin==11)fakeDC=value;}
inline int digitalRead(int){return fakeBusy ? 0 : 1;}
struct SerialMock{void println(const char*){}};
extern SerialMock Serial;
