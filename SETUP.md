# Windows local setup and chart files

For the full Prime dashboard restart, follow the single [current paper restart guide](docs/recovery/PRIME_AS_IS_RESTART.md). It pins the reviewed source, backs up the private state, captures current Main NQ inputs, applies the requested defaults, starts one paper engine, and verifies the dashboard routes. Leave its launcher window open.

Do not use archived per-panel commands or start a second engine alongside the current runtime. The standalone `start-plant.bat` launcher is for the separate local Plant utility; it is not the full Main/CC dashboard restart.

## Optional TradingView history CSV

Exporting chart history requires TradingView Plus or higher. In Supercharts, select `CME_MINI:NQ1!`, set the chart to 1 minute, and choose **Download chart data**. A typical filename is `CME_MINI_NQ1!, 1.csv`. Copy it into `C:\Users\tripl\Icarus\history\drop\` or leave it in Downloads; the local file workflow can pick up the registered symbols. This is historical input data and does not enable live order execution.

Older setup directions are preserved in [the 2026-10-23 archive](docs/recovery/archive/2026-10-23/main/SETUP.md) for provenance only. They include a different launch flow and are not the current full-restart procedure.
