#include "navigation.h"
#include <assert.h>
using namespace paper;
int main() {
    Navigation nav;
    assert(nav.shouldRender(false,false,false,false));
    nav.commit();
    assert(!nav.shouldRender(false,false,false,false));
    assert(nav.shouldRender(true,false,false,false));
    assert(nav.shouldRender(false,true,false,false));
    nav.press(1);assert(nav.selected==1 && nav.switching());nav.commit();
    // Network/minute/6h events never replace an archive, even over many days.
    for(int minute=0;minute<10000;++minute) {
        assert(!nav.shouldRender(minute%5==0,true,minute>=360,false));
        assert(nav.selected==1 && nav.displayed==1);
    }
    nav.press(1);assert(nav.selected==2);nav.commit();
    nav.press(1);assert(nav.selected==3);nav.commit();
    nav.press(1);assert(nav.selected==0);nav.commit();
    nav.press(-1);assert(nav.selected==3);nav.commit();
    nav.press(-1);assert(nav.selected==2);
    // A failed switch is not committed; retry keeps the requested destination.
    assert(nav.displayed==3 && nav.shouldRender(false,false,false,true));
    nav.commit();assert(nav.displayed==2);
    nav.press(0);assert(nav.selected==0 && nav.switching());nav.commit();
    assert(nav.shouldRender(false,false,true,false));
    DebouncedPress key;
    key.begin(false,0);
    assert(!key.sample(true,10));assert(!key.sample(false,20));
    assert(!key.sample(true,30));assert(!key.sample(true,69));
    assert(key.sample(true,70));
    for(unsigned t=80;t<10000;t+=10)assert(!key.sample(true,t));
    assert(!key.sample(false,10000));assert(!key.sample(false,10040));
    assert(!key.sample(true,10050));assert(key.sample(true,10090));
    key.begin(true,0); // Boot with held button: no accidental page advance.
    assert(!key.sample(true,100));
    assert(!key.sample(false,110));assert(!key.sample(false,150));
    assert(!key.sample(true,160));assert(key.sample(true,200));
    key.begin(false,0xfffffff0U);
    assert(!key.sample(true,0xfffffff5U));assert(!key.sample(true,20));
    assert(key.sample(true,29)); // Debounce across millis rollover.
}
