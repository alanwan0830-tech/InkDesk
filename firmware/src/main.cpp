#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <Wire.h>
#include <RtcPCF8563.h>
#include <TFT_eSPI.h>
#include <esp_timer.h>
#include <esp_wifi.h>
#include <esp32s3/rom/miniz.h>
#include <time.h>
#include "settings.h"
#include "paper_core.h"
#include "clock_glyphs.h"
#include "panel.h"
#include "navigation.h"
#include "archived_pages.h"

using namespace paper;
EPaper screen;
PaperPanel panel;
RtcPCF8563<TwoWire> rtc(Wire);
Preferences prefs;
String wifiSSID, wifiPassword, frameURL, frameToken;
QueueHandle_t inbox, buttons, vehicleRequests;
uint8_t* vehicleImage=nullptr;
bool haveVehicle=false, vehicleFailed=false;
uint32_t vehicleVisit=0;
Navigation navigation;
uint8_t *baseImage=nullptr, *shown=nullptr;
uint32_t sourceAt=0, lastFull=0, lastSaved=0, sourceFlags=0, lastDisplayTry=0;
LocalClock localClock;
bool haveImage=false, initialized=false, rtcReady=false, prefsReady=false;
bool panelSynced=false, displayFailed=false;
struct FrameMessage { uint8_t* packet; int64_t receivedAt; uint32_t visit; bool vehicle; };
// Sample independently so short presses during an e-paper refresh are retained.
void buttonTask(void*) {
    const int pins[]={PREVIOUS_BUTTON,NEXT_BUTTON,HOME_BUTTON};
    const int directions[]={-1,1,0};
    DebouncedPress keys[3];
    for(int i=0;i<3;++i) {
        pinMode(pins[i],INPUT);
        keys[i].begin(digitalRead(pins[i])==LOW,millis());
    }
    for(;;) {
        for(int i=0;i<3;++i) {
            if(keys[i].sample(digitalRead(pins[i])==LOW,millis())) {
                const int direction=directions[i];
                if(xQueueSend(buttons,&direction,0)!=pdTRUE)
                    Serial.println("Button queue full; press again after refresh");
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

uint32_t currentTime() {
    return localClock.now(esp_timer_get_time());
}

void setClock(uint32_t epoch) {
    localClock.set(epoch,esp_timer_get_time());
    if (!rtcReady) return;
    RtcDateTime value;
    value.InitWithUnix32Time(epoch);
    rtc.SetDateTime(value);
    if (rtc.LastError()) return;
    rtc.SetIsRunning(true);
    if (!rtc.LastError() && prefsReady && !prefs.getBool("rtcUTC",false)) prefs.putBool("rtcUTC",true);
}

bool download(uint8_t* packet, bool vehicle) {
    HTTPClient http;
    http.setConnectTimeout(5000);
    http.setTimeout(vehicle ? 20000 : 5000);
    String url=frameURL;
    if(vehicle){if(!url.endsWith("/frame"))return false;url.remove(url.length()-5);url+="vehicle";}
    if (!http.begin(url)) return false;
    http.addHeader("Authorization", String("Bearer ")+frameToken);
    const char* headers[]={"Content-Encoding"};
    http.useHTTP10(true);
    http.addHeader("Accept-Encoding","deflate");
    http.collectHeaders(headers,1);
    const char* route=vehicle ? "vehicle" : "home";
    uint32_t requested=millis();
    int status=http.GET(), length=http.getSize();
    String encoding=http.header("Content-Encoding");
    bool compressed=encoding=="deflate";
    bool supported=compressed ? length>0 && length<int(PACKET_SIZE) :
                                encoding.isEmpty() && length==int(PACKET_SIZE);
    Serial.printf("Frame RX %s http=%d length=%d compressed=%d header_ms=%lu rssi=%d\n",
                  route,status,length,compressed,millis()-requested,int(WiFi.RSSI()));
    bool ok=false;
    if (status==200 && supported) {
        uint8_t* body=compressed ? static_cast<uint8_t*>(ps_malloc(length)) : packet;
        WiFiClient* stream=http.getStreamPtr();
        size_t received=0;
        uint32_t started=millis();
        while (body && stream && received<size_t(length) && millis()-started<20000) {
            int available=stream->available();
            if (available>0) {
                size_t amount=min(size_t(available),size_t(length)-received);
                int got=stream->read(body+received,amount);
                if (got<=0) break;
                received+=size_t(got);
            } else if (!http.connected()) break;
            else vTaskDelay(pdMS_TO_TICKS(10));
        }
        const char* result=body ? (millis()-started>=20000 ? "timeout" : "closed") : "allocation";
        if (received==size_t(length)) {
            size_t decoded=received;
            if (compressed) {
                auto* inflater=static_cast<tinfl_decompressor*>(ps_malloc(sizeof(tinfl_decompressor)));
                decoded=0;
                if (inflater) {
                    tinfl_init(inflater);
                    size_t input=received, output=PACKET_SIZE;
                    int flags=TINFL_FLAG_PARSE_ZLIB_HEADER | TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF;
                    if (tinfl_decompress(inflater,body,&input,packet,packet,&output,flags)==TINFL_STATUS_DONE &&
                        input==received) decoded=output;
                    free(inflater);
                }
            }
            ok=validPacket(packet,decoded,vehicle ? "VEH1" : "PPR2");
            result=ok ? "valid" : decoded==PACKET_SIZE ? "invalid-packet" : "decode";
        }
        Serial.printf("Frame RX %s result=%s received=%u body_ms=%lu offline=%d\n",
                      route,result,unsigned(received),millis()-started,ok ? int(u32(packet+16)) : -1);
        if (compressed) free(body);
    }
    http.end();
    return ok;
}

void fetchTask(void*) {
    uint32_t homeDue=millis(), lastVisit=0;
    HourlyVehicleRefresh hourly{homeDue};
    for (;;) {
        bool vehicle=false;
        // An overdue home request has a turn even during rapid manual navigation.
        for (;;) {
            uint32_t now=millis();
            int32_t homeWait=int32_t(homeDue-now);
            if (homeWait<=0) break;
            uint32_t wait=min(uint32_t(homeWait),hourly.remaining(now));
            uint32_t visit;
            bool manual=xQueueReceive(vehicleRequests,&visit,pdMS_TO_TICKS(wait))==pdTRUE;
            if (manual) lastVisit=visit;
            bool scheduled=hourly.consume(millis());
            if (scheduled || manual) {
                vehicle=true;
                Serial.println(scheduled ? "Vehicle hourly refresh" : "Vehicle manual refresh");
                break;
            }
        }
        bool delivered=false;
        if (frameURL.length() && frameToken.length()>=32) {
            WiFi.mode(WIFI_STA);
            // Load existing ESP Wi-Fi credentials, then prevent further flash writes.
            esp_wifi_set_storage(WIFI_STORAGE_RAM);
            if(wifiSSID.length()) WiFi.begin(wifiSSID.c_str(),wifiPassword.c_str());
            else WiFi.begin();
            uint32_t start=millis();
            while (WiFi.status()!=WL_CONNECTED && millis()-start<15000) vTaskDelay(pdMS_TO_TICKS(100));
            if (WiFi.status()==WL_CONNECTED) {
                Serial.println("Wi-Fi connected");
                if(strlen(PAPER_BRIDGE_MDNS) && MDNS.begin("paper-e1001")) {
                    IPAddress address=MDNS.queryHost(PAPER_BRIDGE_MDNS,1500);
                    if(address!=IPAddress(0,0,0,0))frameURL="http://"+address.toString()+":8767/frame";
                    MDNS.end();
                }
                uint8_t* packet=(uint8_t*)ps_malloc(PACKET_SIZE);
                if (packet) {
                    if (download(packet,vehicle)) {
                        FrameMessage message{packet,esp_timer_get_time(),lastVisit,vehicle};
                        delivered=xQueueSend(inbox,&message,portMAX_DELAY)==pdTRUE;
                    }
                    if (!delivered) free(packet);
                }
            } else Serial.println("Wi-Fi connection timed out");
            WiFi.disconnect(false,false); // Never erase saved Wi-Fi settings.
            WiFi.mode(WIFI_OFF);
        }
        if(vehicle){
            if(!delivered){
                FrameMessage failure{nullptr,0,lastVisit,true};
                xQueueSend(inbox,&failure,portMAX_DELAY);
            }
            Serial.println(delivered ? "Vehicle frame received" : "Vehicle request failed");
        } else {
            Serial.println(delivered ? "First-screen data accepted" : "Keeping cached frame; local clock continues");
            homeDue=millis()+(delivered ? DATA_INTERVAL_MS : 60000);
        }
    }
}

void localTime(uint32_t epoch, tm& result) {
    time_t beijing=time_t(epoch)+8*3600;
    gmtime_r(&beijing,&result);
}

void drawLocal(uint32_t now) {
    screen.fillRect(296,80,224,128,TFT_WHITE);
    screen.setTextColor(TFT_BLACK,TFT_WHITE);
    char clockText[6]="--:--";
    tm local={};
    if (now) {
        localTime(now,local);
        snprintf(clockText,sizeof(clockText),"%02d:%02d",local.tm_hour,local.tm_min);
    }
    float x=298;
    for (char c: clockText) {
        if (!c) break;
        int index=(c==':') ? 10 : (c=='-' ? 11 : c-'0');
        int width=(c==':') ? 2 : 8;
        for (int y=0;y<12;++y) for (int col=0;col<width;++col) {
            if (CLOCK_GLYPHS[index][y] & (1U<<(width-col-1)))
                screen.fillRect(int(x+col*5.65f+0.5f),int(85+y*6.6f+0.5f),4,5,TFT_BLACK);
        }
        x+=(width+1)*5.65f;
    }
    char date[30]="TIME NOT SET";
    if (now) strftime(date,sizeof(date),"%d %b %Y  %a",&local);
    screen.drawString(date,298,179,2);
    screen.fillRect(16,450,428,30,TFT_WHITE);
    char status[64]="NO DATA / waiting for local feed";
    if (haveImage) {
        tm fetched={};localTime(sourceAt,fetched);
        char stamp[20];strftime(stamp,sizeof(stamp),"%m/%d %H:%M",&fetched);
        const bool cached=!now || now<sourceAt || now-sourceAt>600;
        snprintf(status,sizeof(status),"DATA %s%s%s",stamp,cached ? " / CACHED" : "",sourceFlags ? " / OFFLINE" : "");
    }
    screen.drawString(status,18,452,2);
}

void render(uint32_t now) {
    if(displayFailed && millis()-lastDisplayTry<60000)return;
    lastDisplayTry=millis();
    uint8_t* pixels=(uint8_t*)screen.getPointer();
    if(navigation.selected==1){
        if(haveVehicle)memcpy(pixels,vehicleImage,IMAGE_SIZE);
        else {
            screen.fillScreen(TFT_WHITE);
            screen.setTextColor(TFT_BLACK,TFT_WHITE);
            screen.drawString(vehicleFailed ? "Vehicle data unavailable" : "Loading vehicle data...",36,180,4);
        }
        if(haveVehicle && vehicleFailed){
            screen.setTextColor(TFT_BLACK,TFT_WHITE);
            screen.drawString("OFFLINE / cached",360,24,2);
        }
    }
    else if (navigation.selected>=2) memcpy(pixels,ARCHIVED_PAGES[navigation.selected-2],IMAGE_SIZE);
    else if (haveImage) memcpy(pixels,baseImage,IMAGE_SIZE);
    else {
        screen.fillScreen(TFT_WHITE);
        screen.setTextColor(TFT_BLACK,TFT_WHITE);
        screen.drawString("PAPER / waiting for first-screen data",18,18,2);
    }
    if(navigation.selected==0) drawLocal(now);
    bool ok=true;
    uint32_t started=millis();
    if (!panelSynced || navigation.switching() || millis()-lastFull>=FULL_REFRESH_INTERVAL_MS) {
        ok=panel.refresh(pixels,pixels,{0,0,WIDTH,HEIGHT},true);
        if(ok){lastFull=millis();panelSynced=true;Serial.println("Full refresh complete");}
    } else {
        for (const auto& region:REGIONS) {
            Rect changed;
            if (dirtyBounds(shown,pixels,region,changed)) {
                ok=panel.refresh(shown,pixels,changed,false);
                if(!ok)break;
                Serial.printf("Partial complete x=%d y=%d w=%d h=%d\n",changed.x,changed.y,changed.w,changed.h);
            }
        }
    }
    displayFailed=!ok;
    if(ok){navigation.commit();memcpy(shown,pixels,IMAGE_SIZE);Serial.printf("Frame committed in %lu ms\n",(unsigned long)(millis()-started));}
    else {panelSynced=false;Serial.println("Display failed; retry after 60s; clock/network continue");}
}

void setup() {
    Serial.begin(115200);
    Serial.println("Paper firmware 0.4 / local clock / manual pages / no autoplay");
    if (!psramFound()) { Serial.println("PSRAM unavailable; display unchanged"); return; }
    baseImage=(uint8_t*)ps_malloc(IMAGE_SIZE);
    shown=(uint8_t*)ps_malloc(IMAGE_SIZE);
    vehicleImage=(uint8_t*)ps_malloc(IMAGE_SIZE);
    vehicleRequests=xQueueCreate(1,sizeof(uint32_t));
    inbox=xQueueCreate(3,sizeof(FrameMessage));
    buttons=xQueueCreate(8,sizeof(int));
    if (!vehicleImage || !vehicleRequests || !baseImage || !shown || !inbox || !buttons || !screen.getPointer()) {
        Serial.println("Memory unavailable; display unchanged");return;
    }
    prefsReady=prefs.begin("paper-v1",false);
    wifiSSID=PAPER_WIFI_SSID;
    wifiPassword=PAPER_WIFI_PASSWORD;
    frameURL=PAPER_FRAME_URL;
    frameToken=PAPER_FRAME_TOKEN;
    rtcReady=Wire.begin(19,20);
    Wire.setTimeOut(100);
    if (rtcReady) {
        rtc.Begin();
        // Stock RTC timezone is not assumed; only trust our own UTC marker.
        if (prefsReady && prefs.getBool("rtcUTC",false) && rtc.IsDateTimeValid() && rtc.GetIsRunning()) {
            RtcDateTime value=rtc.GetDateTime();
            if (!rtc.LastError() && value.Year()>=2024 && value.Year()<2100) {
                localClock.set(value.Unix32Time(),esp_timer_get_time());
            }
        }
    }
    if (prefsReady && prefs.getBytesLength("frame")==PACKET_SIZE) {
        uint8_t* stored=(uint8_t*)ps_malloc(PACKET_SIZE);
        if (stored) {
            if (prefs.getBytes("frame",stored,PACKET_SIZE)==PACKET_SIZE && validPacket(stored,PACKET_SIZE)) {
                memcpy(baseImage,stored+HEADER_SIZE,IMAGE_SIZE);
                sourceAt=u32(stored+12);sourceFlags=u32(stored+16);haveImage=true;
            }
            free(stored);
        }
    }
    if(prefsReady && prefs.getBytesLength("vehicle")==PACKET_SIZE){
        auto cached=(uint8_t*)ps_malloc(PACKET_SIZE);
        if(cached && prefs.getBytes("vehicle",cached,PACKET_SIZE)==PACKET_SIZE && validPacket(cached,PACKET_SIZE,"VEH1")){
            memcpy(vehicleImage,cached+HEADER_SIZE,IMAGE_SIZE);
            haveVehicle=true;
        }
        free(cached);
    }
    // Use the vendor sprite/font engine only; all hardware access is bounded.
    screen.setBitmapColor(1,0);screen.setTextFont(1);
    screen.setRotation(0);
    panel.begin();
    if (xTaskCreatePinnedToCore(buttonTask,"paper-buttons",2048,nullptr,1,nullptr,1)!=pdPASS)
        Serial.println("Button task unavailable");
    initialized=true;
    render(currentTime());
    if (xTaskCreatePinnedToCore(fetchTask,"paper-fetch",8192,nullptr,1,nullptr,0)!=pdPASS)
        Serial.println("Network task unavailable; local clock continues");
}

void loop() {
    if (!initialized) { delay(1000);return; }
    bool changed=false, vehicleChanged=false;
    int direction;
    if(xQueueReceive(buttons,&direction,0)==pdTRUE) {
        navigation.press(direction);
        if(navigation.selected==1){
            if(++vehicleVisit==0)++vehicleVisit;
            xQueueOverwrite(vehicleRequests,&vehicleVisit);
        }
        Serial.printf("Manual page selected: %u\n",navigation.selected+1);
    }
    FrameMessage message{};
    if (xQueueReceive(inbox,&message,0)==pdTRUE) {
        uint8_t* packet=message.packet;
        // Validate again before touching the live frame or RTC.
        if(message.vehicle){
            bool valid=packet && validPacket(packet,PACKET_SIZE,"VEH1");
            bool latest=vehicleVisit==message.visit;
            bool active=navigation.selected==1 && latest;
            if(valid){
                bool different=!haveVehicle || memcmp(vehicleImage,packet+HEADER_SIZE,IMAGE_SIZE)!=0;
                static uint32_t savedAt=0;
                if(different && prefsReady && (!savedAt || millis()-savedAt>=3600000)){
                    if(prefs.putBytes("vehicle",packet,PACKET_SIZE)==PACKET_SIZE)savedAt=millis();
                }
                memcpy(vehicleImage,packet+HEADER_SIZE,IMAGE_SIZE);
                haveVehicle=true;
                vehicleChanged=active && (vehicleFailed || memcmp(shown,vehicleImage,IMAGE_SIZE)!=0);
            } else if(active){
                vehicleChanged=!vehicleFailed;
            }
            if(latest)vehicleFailed=!valid;
            if(active)Serial.println(valid ? "Vehicle visit updated" : "Vehicle visit offline");
        } else if (packet && validPacket(packet,PACKET_SIZE)) {
            memcpy(baseImage,packet+HEADER_SIZE,IMAGE_SIZE);
            sourceAt=u32(packet+12);sourceFlags=u32(packet+16);
            setClock(u32(packet+8)+uint32_t((esp_timer_get_time()-message.receivedAt)/1000000));
            if (prefsReady && (!haveImage || millis()-lastSaved>=3600000)) {
                if (prefs.putBytes("frame",packet,PACKET_SIZE)==PACKET_SIZE) lastSaved=millis();
            }
            haveImage=true;changed=true;
        }
        free(packet);
    }
    static uint32_t lastMinute=UINT32_MAX;
    const uint32_t now=currentTime();
    if (vehicleChanged || navigation.shouldRender(changed,now/60!=lastMinute,millis()-lastFull>=FULL_REFRESH_INTERVAL_MS,displayFailed)) {
        render(now);lastMinute=now/60;
    }
    delay(20);
}
