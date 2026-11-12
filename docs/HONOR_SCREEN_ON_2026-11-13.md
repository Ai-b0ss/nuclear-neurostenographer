# HONOR screen-on endurance QA — 2026-11-13

The owner explicitly prohibited turning off or locking the physical phone. Both physical short/long power tests now follow that instruction. They never send display power commands. PhysicalScreenOnQa requires the already unlocked, interactive device, launches the real QA Activity, waits for its RESUMED lifecycle stage and holds FLAG_KEEP_SCREEN_ON only on that Activity. The original window flag is restored on cleanup, including after other cleanup failures; global screen timeout/power settings are unchanged.

The same public 20m40s fixture and ordinary RC5 A3+C2 pipeline run in isolated Sol QA, with realtime compiled and global speaker linking OFF. Product code/APK/version are unchanged. The existing host guard retains all CPU/battery/OS limits and app-heartbeat aborts. Current run status: RUNNING, no physical endurance PASS claimed yet.

USB file-transfer mode restored ADB connectivity. Cool preflight passed. Initial processing was observed advancing at the C2 stage with display ON, battery34 C and CPU maximum59 C. These interim values are not the final peak or evidence of a completed transcript.

Local validation: corrected instrumentation compiled; the host watchdog's 17 tests remain applicable. Evidence will be added after the terminal run result. Earlier screen-off/headless investigation remains historical and must not be interpreted as the outcome of this screen-on test.
