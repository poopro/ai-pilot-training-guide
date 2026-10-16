# ASUS CPU Player setup result (2026-10-17)

Status: **LOCAL_READY; LAN_PENDING**.

The release asset `ai-pilot-cpu-player-win64-20261016.zip` was downloaded and its SHA-256 matched the value in the second-PC setup guide. The packaged helper hashes matched `HANDOFF_MANIFEST.json`. The bundled self-check passed and verified 2,115 package files.

On an ASUS Vivobook with 64-bit Windows 11 and an AMD Ryzen 7 5800H, the local synthetic CPU check ran 2,000 samples: p99 **0.412 ms**, maximum **0.737 ms**. The CPU margin check passed. No network service, flight simulation, training, or Player was started. These timings do not demonstrate real 60 Hz networking, combat performance, or competition compatibility.

The LAN launcher was checked for syntax and verified to stop when the LAN configuration is missing or lacks required fields. No LAN configuration or firewall rule was created. Cross-PC validation remains pending until the main PC supplies its Host IPv4, OBS output UDP port, CMD receive UDP port, and a supervised test window, and both PCs are confirmed to share the intended LAN.

Local machine identifiers, private IP addresses, absolute paths, process IDs, and the private runtime package are intentionally omitted. The ASUS-specific full handoff remains local.
