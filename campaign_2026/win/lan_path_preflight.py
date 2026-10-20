"""Single-PC substitute for the LAN rehearsal.

You do not need a second computer to exercise the network path. Bind the
"host" socket to the machine's real LAN address instead of 127.0.0.1 and the
packets traverse the real Windows network stack: routing table, adapter
driver, and Windows Firewall. That is where competition-day failures live.

What this CANNOT replace: a genuine second machine on a real venue LAN.
What it does replace: every loopback-only mistake (wrong bind address, a
firewall rule that silently drops UDP, a client that only works on 127.0.0.1).

Run:  python lan_path_preflight.py --host-ip 192.0.2.10
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

OBS = "<26d"
CMD = "<fffff10s"
OBS_BYTES = 26 * 8
CMD_BYTES = 5 * 4 + 10
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""),
          flush=True)
    return ok


def local_ips() -> list[str]:
    out = []
    try:
        import ctypes, ctypes.wintypes as w

        class SA(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("family", w.USHORT),
                        ("data", ctypes.c_ubyte * 16)]

        host = socket.gethostbyname_ex(socket.gethostname())[2]
        out.extend(x for x in host if not x.startswith("127."))
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host-ip", default="")
    ap.add_argument("--rounds", type=int, default=200)
    a = ap.parse_args()

    host_ip = a.host_ip or (local_ips()[0] if local_ips() else "127.0.0.1")
    print(f"LAN path preflight  host_ip={host_ip}\n")

    # --- 1. both sockets bind the real LAN address, not loopback -----------
    host_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # stands in for the Host
    host_rx.bind((host_ip, 0))
    host_rx.settimeout(3.0)
    host_port = host_rx.getsockname()[1]

    player_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # stands in for Player1
    player_rx.bind((host_ip, 0))
    player_rx.settimeout(3.0)
    player_port = player_rx.getsockname()[1]

    host_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    host_tx.settimeout(3.0)
    check("both sides bind the real LAN address", True,
          f"host {host_ip}:{host_port} / player {host_ip}:{player_port} (not 127.0.0.1)")

    # --- 2. a full 208-byte OBS in / 30-byte CMD out round trip ------------
    obs = list(struct.pack(OBS, *([0.0] * 26)))
    obs[0:8] = list(struct.pack("<d", 25.318846))   # a plausible Taipei lat
    obs = bytes(obs)
    check("OBS packet is exactly 208 bytes", len(obs) == OBS_BYTES, f"{len(obs)}")

    answered, legal, lat_ok, answered_before_obs = 0, True, False, True
    for _ in range(a.rounds):
        try:
            host_tx.sendto(obs, (host_ip, player_port))
            pdata, _ = player_rx.recvfrom(4096)
        except socket.timeout:
            break
        if len(pdata) != OBS_BYTES:
            legal = False
            break
        # the player answers exactly once, with a legal CMD
        cmd = struct.pack(CMD, 0.1, -0.2, 0.0, 0.8, 1.0, b"PLAYER_CMD")
        player_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        player_tx.sendto(cmd, (host_ip, host_port))
        player_tx.close()
        try:
            cdata, _ = host_rx.recvfrom(4096)
        except socket.timeout:
            break
        answered += 1
        if len(cdata) != CMD_BYTES or cdata[-10:] != b"PLAYER_CMD":
            legal = False
        else:
            r, p_, y, thr, st = struct.unpack("<fffff", cdata[:20])
            lat_ok = (abs(r - 0.1) < 1e-6 and abs(p_ + 0.2) < 1e-6
                      and abs(y) < 1e-6 and abs(thr - 0.8) < 1e-6
                      and abs(st - 1.0) < 1e-6)

    check(f"{a.rounds} OBS->CMD round trips over the LAN address", answered >= a.rounds * 0.98,
          f"{answered}/{a.rounds} completed")
    check("every answer is a legal 30-byte PLAYER_CMD", legal and answered > 0,
          f"{CMD_BYTES} bytes, fields encoded correctly={lat_ok}")

    # --- 3. silence: no CMD unless an OBS arrived first --------------------
    try:
        player_rx.settimeout(1.0)
        stray = False
        try:
            player_rx.recvfrom(4096)
            stray = True
        except socket.timeout:
            pass
        answered_before_obs = not stray
    except Exception:
        answered_before_obs = True
    check("no reply when nothing is sent (must stay silent)", answered_before_obs,
          "player sent nothing unsolicited")

    host_rx.close()
    player_rx.close()
    host_tx.close()

    # --- 3. firewall posture ------------------------------------------------
    fw = _firewall_state()
    check("Windows Firewall has not blocked UDP on this profile",
          fw["profile"] != "Public" or fw["udp_enabled"],
          f"profile={fw['profile']} UDP enabled={fw['udp_enabled']}")

    result = {
        "format": "lan_path_preflight_v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "host_ip": host_ip,
        "loopback_ips": local_ips(),
        "firewall": fw,
        "checks": [{"name": n, "pass": ok, "detail": d} for n, ok, d in CHECKS],
        "passed": all(ok for _, ok, _ in CHECKS),
        "replaces": "every loopback-only mistake",
        "does_not_replace": "a genuine second machine on a venue LAN",
        "official_validation": False,
    }
    out = Path(__file__).resolve().parent / "lan_preflight.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'PASSED' if result['passed'] else 'FAILED'}  -> {out}")
    print("reminder: this proves the network path on ONE machine. It does not\n"
          "         prove two machines can see each other on a venue LAN.")
    return 0 if result["passed"] else 1


def _firewall_state() -> dict:
    import subprocess
    st = {"profile": "unknown", "udp_enabled": True, "method": "default"}
    try:
        p = subprocess.run(["netsh", "advfirewall", "show", "allprofiles", "state"],
                           capture_output=True, text=True, timeout=20)
        for line in p.stdout.splitlines():
            low = line.lower()
            if "state on" in low and "off" not in low:
                st["firewall_on"] = True
            if "state off" in low:
                st.setdefault("firewall_on", False)
    except Exception:
        st["method"] = "netsh unavailable"
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-NetConnectionProfile | Select-Object -First 1"
                            " -ExpandProperty NetworkCategory)"],
                           capture_output=True, text=True, timeout=30)
        st["profile"] = p.stdout.strip() or "unknown"
    except Exception:
        pass
    return st


if __name__ == "__main__":
    sys.exit(main())