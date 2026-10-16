#!/usr/bin/env python3
"""Persist the BE200 driver's in-memory log ring to disk.

Run by launchd (~/Library/LaunchAgents/com.richard.itlwm-logd.plist) every
10 s. Reads the "itlwm-log" IORegistry property (same source as
~/hackintosh/wifi/readlog.sh) and appends lines that are newer than the last
saved one to ~/hackintosh/wifi/logs/itlwm-YYYY-MM-DD.log.

Ring lines carry a "[epoch.ms] " stamp (driver t17+). Lines without a stamp
inherit the previous one. Dedup state: last stamp + how many lines with that
stamp were already written (several lines share a millisecond).
On a new boot a marker line is written and the tail of `pmset -g log`
(covering the previous sleep/wake) is saved next to the logs.
"""
import datetime
import json
import os
import plistlib
import re
import subprocess
import time

LOGDIR = os.path.expanduser("~/hackintosh/wifi/logs")
STATE = os.path.join(LOGDIR, ".state.json")
KEEP_DAYS = 14
STAMP = re.compile(r"^\[(\d{9,11})\.(\d{3})\] ?(.*)$")
EFI_CONFIG = "/Volumes/OMARCHY/EFI/OC/config.plist"


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout).stdout
    except Exception:
        return b""


def read_ring():
    raw = run(["/usr/sbin/ioreg", "-a", "-l", "-w0", "-p", "IOService", "-n", "PXSX"])
    if not raw:
        return None
    try:
        tree = plistlib.loads(raw)
    except Exception:
        return None
    stack = [tree]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if "itlwm-log" in o:
                return o["itlwm-log"]
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
    return None


def boottime():
    out = run(["/usr/sbin/sysctl", "-n", "kern.boottime"]).decode(errors="replace")
    m = re.search(r"sec = (\d+)", out)
    return int(m.group(1)) if m else 0


def kext_label():
    try:
        with open(EFI_CONFIG, "rb") as f:
            d = plistlib.load(f)
        for k in d["Kernel"]["Add"]:
            if k.get("BundlePath") == "AirportItlwm.kext":
                return k.get("Comment", "?")
    except Exception:
        pass
    out = run(["/usr/bin/kmutil", "showloaded", "--list-only"]).decode(errors="replace")
    for line in out.splitlines():
        if "Itlwm" in line or "itlwm" in line:
            return " ".join(line.split()[-2:])
    return "unknown (EFI not mounted)"


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {"boottime": 0, "last_ms": 0, "n_at_last": 0}


def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f)
    os.replace(tmp, STATE)


def append(day, lines):
    with open(os.path.join(LOGDIR, f"itlwm-{day}.log"), "a") as f:
        f.write("".join(lines))


def on_new_boot(bt):
    when = datetime.datetime.fromtimestamp(bt)
    append(when.strftime("%Y-%m-%d"),
           [f"=== boot {when:%Y-%m-%d %H:%M:%S} | kext {kext_label()} ===\n"])
    pm = run(["/usr/bin/pmset", "-g", "log"], timeout=60).decode(errors="replace").splitlines()
    with open(os.path.join(LOGDIR, f"pmset-{when:%Y%m%d-%H%M%S}.txt"), "w") as f:
        f.write("\n".join(pm[-150:]) + "\n")


def prune():
    cutoff = time.time() - KEEP_DAYS * 86400
    for name in os.listdir(LOGDIR):
        p = os.path.join(LOGDIR, name)
        if name.startswith((".", "logd")) or not os.path.isfile(p):
            continue
        if os.path.getmtime(p) < cutoff:
            os.remove(p)


def main():
    os.makedirs(LOGDIR, exist_ok=True)
    st = load_state()
    bt = boottime()
    if bt and bt != st.get("boottime"):
        on_new_boot(bt)
        st = {"boottime": bt, "last_ms": 0, "n_at_last": 0}
        save_state(st)
        prune()

    ring = read_ring()
    if not ring:
        return

    last_ms, n_at_last = st["last_ms"], st["n_at_last"]
    cur_ms, seen_at_cur = None, 0
    out = {}
    for line in ring.splitlines():
        m = STAMP.match(line)
        if m:
            ms = int(m.group(1)) * 1000 + int(m.group(2))
            text = m.group(3)
        elif cur_ms is not None:
            ms, text = cur_ms, line          # continuation of a multi-line message
        else:
            continue                          # unstamped (pre-t17) lines
        if ms != cur_ms:
            cur_ms, seen_at_cur = ms, 0
        seen_at_cur += 1
        if ms < last_ms or (ms == last_ms and seen_at_cur <= n_at_last):
            continue
        t = datetime.datetime.fromtimestamp(ms / 1000)
        out.setdefault(t.strftime("%Y-%m-%d"), []).append(
            f"[{t:%H:%M:%S}.{ms % 1000:03d}] {text}\n")
        if ms > last_ms:
            last_ms, n_at_last = ms, 0
        n_at_last += 1

    if out:
        for day, lines in sorted(out.items()):
            append(day, lines)
        st["last_ms"], st["n_at_last"] = last_ms, n_at_last
        save_state(st)


if __name__ == "__main__":
    main()
