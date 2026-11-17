#pragma once
#include <SPI.h>
#include "paper_core.h"

// UC8179 command sequence follows Seeed_GFX 24c5094; transport is bounded,
// supplies old AND new pixels after wake, and uses inclusive window endpoints.
class PaperPanel {
    SPIClass spi{HSPI};
    bool ready();
    void command(uint8_t c);
    void data(uint8_t d);
    void bytes(const uint8_t* data,size_t size);
    bool wake(bool partial);
    void pixels(uint8_t command,const uint8_t* image,paper::Rect r);
public:
    void begin();
    bool refresh(const uint8_t* oldImage,const uint8_t* newImage,paper::Rect r,bool full);
};
