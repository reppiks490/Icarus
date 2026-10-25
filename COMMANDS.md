# Current Icarus commands

Use the single [current Prime as-is restart guide](docs/recovery/PRIME_AS_IS_RESTART.md) for the complete Windows/Git Bash restart. It pins the release, backs up private state, captures and applies Main NQ defaults, installs the editable package with the Python 3.10/3.11 distutils workaround, starts one paper runtime, and verifies `warm:true` plus Main, public status, CC1–CC4, and Connections.

Do not use the PowerShell `py -m icarus_plant stop/start` commands from the superseded version of this file. They do not perform the current full restart/default migration. The prior contents are preserved in [the command archive](docs/recovery/archive/restarts/2026-10-25/pre-final/COMMANDS.md).

Mobile gateway instructions are separate: [Windows gateway setup](docs/icarus/MOBILE_WINDOWS.md). The desktop restart does not start the gateway, and phone pairing requires the owner's device and Expo setup.