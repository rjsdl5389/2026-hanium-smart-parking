# v3 bridge changes for 2026-07-29 HW handover

- Mock ESP32 now matches firmware's 8-bit calibrated PWM profiles.
- Mock steering uses the five measured points: 30/60/86/112/122 degrees.
- Mock STATUS includes `encoder_count`.
- The bridge computes `encoder_delta` from consecutive STATUS messages and prints `enc` / `denc`.
- Added safe CLI presets: `straight`, `left weak`, `right weak`, `left strong`, `right strong`.
- Added calibration/status-size unit tests.
- No Django/backend/frontend files are included or modified.
