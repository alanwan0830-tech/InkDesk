#pragma once
#if __has_include("secrets.h")
#include "secrets.h"
#endif
#ifndef PAPER_BRIDGE_MDNS
#define PAPER_BRIDGE_MDNS ""
#endif
#ifndef PAPER_WIFI_SSID
#define PAPER_WIFI_SSID ""
#define PAPER_WIFI_PASSWORD ""
#define PAPER_FRAME_URL ""
#define PAPER_FRAME_TOKEN ""
#endif
// Minute clock, five-minute data retrieval. No playlist or rotation timer.
constexpr unsigned DATA_INTERVAL_MS = 300000;
// Provisional residue maintenance; validate with the actual panel.
constexpr unsigned FULL_REFRESH_INTERVAL_MS = 6UL * 60 * 60 * 1000;
