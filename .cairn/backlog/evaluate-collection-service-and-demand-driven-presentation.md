# Evaluate collection service and demand-driven presentation

Surfaced from: PERF-001
Captured: 2026-09-08T14:10:20.623Z

Developer raised a service during Mac performance work. Collection already runs on a background thread. Guarded native profiles show 858/873 ms collector CPU and 283/576 ms main-thread CPU in tray/Summary over separate 15-second samples. Investigate lifecycle isolation and avoiding hidden display preparation. Any service acceptance must count combined UI and service CPU, preserve one-second readings and continuous history, and include crash/reconnect and shutdown behavior. Discussion is not authorization to build or change the current performance contract.
