#pragma once
#include <stdint.h>

namespace paper {
constexpr unsigned PAGE_COUNT=5;
constexpr int PREVIOUS_BUTTON=5, NEXT_BUTTON=4, HOME_BUTTON=3;

// One event per stable press, including across millis() wrap. Boot-held keys
// must be released first. No repeat timer can turn this into a slideshow.
struct DebouncedPress {
    bool raw=false, stable=false;
    uint32_t since=0;
    void begin(bool pressed,uint32_t now) { raw=stable=pressed;since=now; }
    bool sample(bool pressed,uint32_t now) {
        if(pressed!=raw){raw=pressed;since=now;}
        if(raw==stable || uint32_t(now-since)<40)return false;
        stable=raw;
        return stable;
    }
};

// Monotonic cadence from boot; manual visits between deadlines do not postpone it.
struct HourlyVehicleRefresh {
    static constexpr uint32_t interval=3600000U;
    uint32_t last;
    uint32_t remaining(uint32_t now) const {
        uint32_t elapsed=now-last;
        return elapsed>=interval ? 0 : interval-elapsed;
    }
    bool consume(uint32_t now) {
        if (remaining(now)) return false;
        last=now-(now-last)%interval;
        return true;
    }
};

struct Navigation {
    unsigned selected=0, displayed=PAGE_COUNT;
    void press(int direction) {
        if(direction==0)selected=0;
        else if(direction<0)selected=(selected+PAGE_COUNT-1)%PAGE_COUNT;
        else selected=(selected+1)%PAGE_COUNT;
    }
    bool switching() const { return selected!=displayed; }
    bool shouldRender(bool dataChanged,bool minuteChanged,bool fullDue,bool failed) const {
        return switching() || failed || (selected==0 && (dataChanged || minuteChanged || fullDue));
    }
    void commit() { displayed=selected; }
};
}
