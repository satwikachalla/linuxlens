#!/usr/bin/env python3
"""LinuxLens - a cute little Linux system dashboard for your terminal.

Usage:
    python3 linuxlens.py                        # refresh every 2 seconds
    python3 linuxlens.py --interval 1           # refresh every second
    python3 linuxlens.py --top 8                # show 8 top processes
    python3 linuxlens.py --theme pastel         # soft pastel colors
    python3 linuxlens.py --alert-after 5        # alert after 5s of high usage
    python3 linuxlens.py --alert-threshold 70   # alert when CPU/RAM >= 70%
"""

import argparse
import os
import platform
import re
import shutil
import time
import unicodedata
from collections import deque
from datetime import datetime

import psutil

# ---------------------------------------------------------------- settings

WIDTH = 52            # inner width of the box (between the two │ borders)
BAR_WIDTH = 10        # number of hearts in each bar
HISTORY_LENGTH = 12   # points kept for the sparklines
ANIMATION_STEP = 0.5  # seconds between redraws (penguin animation speed)

RESET = "\033[0m"
REVERSE = "\033[7m"

# Color themes: "border", "good", "warn", "high" and "heart" (empty = no color)
THEMES = {
    "default": {
        "border": "\033[96m",
        "good": "\033[92m",
        "warn": "\033[93m",
        "high": "\033[91m",
        "heart": "",
    },
    "pastel": {
        "border": "\033[38;5;183m",   # lavender
        "good": "\033[38;5;121m",     # mint
        "warn": "\033[38;5;216m",     # peach
        "high": "\033[38;5;213m",     # pink
        "heart": "\033[38;5;218m",    # soft pink
    },
}
COLORS = dict(THEMES["default"])

SPARK_BLOCKS = "▁▂▃▄▅▆▇█"
ANSI_PATTERN = re.compile(r"\033\[[0-9;?]*[A-Za-z]")

# Penguin faces per mood: (cpu below this, animation frames, message)
# Frames cycle with every redraw, so faces blink and fidget.
PENGUIN_MOODS = [
    (30,  ["(◕‿◕)"] * 5 + ["(-‿-)"],                 "feeling great!"),
    (60,  ["(•‿•)"] * 3 + ["(-‿-)"],                 "working hard~"),
    (80,  ["(°▽°;)", "(°▽°;)", "(°o°;)", "(°▽°;)"],  "getting busy..."),
    (101, ["(>_<)", "(>_<;)", "(>_<)", "(>o<)"],     "help, so toasty!"),
]
PENGUIN_WORRIED = (["(;_;)", "(;_;)", "(T_T)"], "please take a look!")


# ---------------------------------------------------------------- helpers

def set_theme(name):
    COLORS.clear()
    COLORS.update(THEMES[name])


def paint(text, key):
    color = COLORS[key]
    return f"{color}{text}{RESET}" if color else text


def visible_len(text):
    """Width of text as it appears on screen (ignores colors, counts emoji as 2)."""
    text = ANSI_PATTERN.sub("", text)
    return sum(
        2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        for char in text
    )


def row(text=""):
    """One box row: left border, text padded to WIDTH, right border."""
    padding = max(WIDTH - visible_len(text), 0)
    return f"{paint('│', 'border')}{text}{' ' * padding}{paint('│', 'border')}"


def centered(text):
    total = max(WIDTH - visible_len(text), 0)
    left = total // 2
    return row(" " * left + text)


def heart_bar(value, width=BAR_WIDTH):
    filled = round(min(max(value, 0), 100) / 100 * width)
    return paint("♥" * filled + "♡" * (width - filled), "heart")


def sparkline(history):
    if not history:
        return ""
    top = len(SPARK_BLOCKS) - 1
    return "".join(
        SPARK_BLOCKS[min(int(min(max(v, 0), 100) / 100 * top + 0.5), top)]
        for v in history
    )


def get_status(value):
    """Colored label, always 7 characters wide so borders stay aligned."""
    if value < 60:
        return paint(f"{'GOOD':<7}", "good")
    if value < 80:
        return paint(f"{'WARNING':<7}", "warn")
    return paint(f"{'HIGH':<7}", "high")


def penguin_line(cpu, tick, alerting):
    """The penguin's face changes with CPU load, blinks, and worries on alerts."""
    if alerting:
        frames, message = PENGUIN_WORRIED
    else:
        for limit, frames, message in PENGUIN_MOODS:
            if cpu < limit:
                break
    face = frames[tick % len(frames)]
    return f"  🐧 {face}  {message}"


def active_alerts(stats):
    """Messages for CPU/RAM that have stayed above the threshold long enough."""
    now = time.time()
    messages = []
    for label, since in stats["high_since"].items():
        if since is not None and now - since >= stats["alert_after"]:
            messages.append(f"{label} high for {int(now - since)}s")
    return messages


def greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "good morning!"
    if hour < 18:
        return "good afternoon!"
    return "good evening!"


def format_bytes(bytes_value):
    return f"{bytes_value / (1024 ** 3):.1f} GB"


def format_speed(bytes_per_second):
    kb = bytes_per_second / 1024
    if kb < 1024:
        return f"{kb:6.1f} KB/s"
    return f"{kb / 1024:6.1f} MB/s"


def format_uptime(seconds):
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days:
        return f"awake for {days}d {hours}h {minutes}m"
    return f"awake for {hours}h {minutes}m"


# ---------------------------------------------------------------- data

def get_top_processes(limit):
    processes = []
    core_count = psutil.cpu_count(logical=True) or 1

    for process in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_percent"]
    ):
        try:
            info = process.info
            processes.append({
                "pid": info["pid"],
                "name": info["name"] or "Unknown",
                # cpu_percent is per-core, so divide to get a 0-100 number
                "cpu": (info["cpu_percent"] or 0) / core_count,
                "memory": info["memory_percent"] or 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    processes.sort(key=lambda p: p["cpu"], reverse=True)
    return processes[:limit]


def get_load_average():
    try:
        one, five, fifteen = os.getloadavg()
        return f"{one:.2f}  {five:.2f}  {fifteen:.2f}"
    except (AttributeError, OSError):
        return "n/a"


def is_online():
    """True if any real (non-loopback) network interface is up."""
    return any(
        stats.isup
        for name, stats in psutil.net_if_stats().items()
        if name != "lo"
    )


def update_high_since(state, label, value, threshold, now):
    """Remember when a value first went above the threshold (None if it didn't)."""
    if value >= threshold:
        if state["high_since"][label] is None:
            state["high_since"][label] = now
    else:
        state["high_since"][label] = None


def collect_stats(state, top_count, alert_threshold, alert_after):
    cpu = psutil.cpu_percent(interval=None)   # non-blocking
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    # network speed = difference since the last frame
    now = time.time()
    counters = psutil.net_io_counters()
    elapsed = max(now - state["last_time"], 0.001)
    download = (counters.bytes_recv - state["last_recv"]) / elapsed
    upload = (counters.bytes_sent - state["last_sent"]) / elapsed
    state["last_time"] = now
    state["last_recv"] = counters.bytes_recv
    state["last_sent"] = counters.bytes_sent

    state["cpu_history"].append(cpu)
    state["ram_history"].append(memory.percent)

    update_high_since(state, "CPU", cpu, alert_threshold, now)
    update_high_since(state, "RAM", memory.percent, alert_threshold, now)

    return {
        "cpu": cpu,
        "cores": psutil.cpu_count(logical=True),
        "ram_percent": memory.percent,
        "ram_used": memory.used,
        "ram_total": memory.total,
        "swap_percent": swap.percent,
        "swap_used": swap.used,
        "swap_total": swap.total,
        "disk_percent": disk.percent,
        "disk_free": disk.free,
        "uptime": time.time() - psutil.boot_time(),
        "load": get_load_average(),
        "online": is_online(),
        "download": download,
        "upload": upload,
        "processes": get_top_processes(top_count),
        "cpu_history": list(state["cpu_history"]),
        "ram_history": list(state["ram_history"]),
        "high_since": dict(state["high_since"]),
        "alert_after": alert_after,
    }


# ---------------------------------------------------------------- display

def bar_row(label, value, history=None):
    line = f"  {label:<6}{heart_bar(value)} {value:5.1f}%  {get_status(value)}"
    if history is not None:
        line += f" {sparkline(history)}"
    return row(line)


def alert_row(alerts, tick):
    """Always one row tall, so the layout never jumps when an alert appears."""
    if not alerts:
        return row("  🌸 all systems calm")
    text = "  🚨 " + " · ".join(alerts)
    style = REVERSE if tick % 2 == 0 else ""      # flashes while active
    return row(f"{style}{COLORS['high']}{text}{RESET}")


def render(stats, interval, tick=0, compact=False):
    lines = []

    def gap():
        # blank spacer rows are skipped in compact mode to save height
        if not compact:
            lines.append(row())

    alerts = active_alerts(stats)

    # header
    lines.append(paint(f"╭{'─' * WIDTH}╮", "border"))
    lines.append(centered("✦ 🐧 LINUXLENS ✦"))
    lines.append(centered(f"Linux System Dashboard · {greeting()}"))
    lines.append(paint(f"├{'─' * WIDTH}┤", "border"))
    gap()

    # penguin mood + alert banner
    lines.append(row(penguin_line(stats["cpu"], tick, bool(alerts))))
    lines.append(alert_row(alerts, tick))
    gap()

    # system
    lines.append(row("  💻 SYSTEM"))
    lines.append(row(f"  OS         {platform.system()}"))
    lines.append(row(f"  Version    {platform.release()[:34]}"))
    lines.append(row(f"  Hostname   {platform.node()[:34]}"))
    lines.append(row(f"  CPU Cores  {stats['cores']}"))
    lines.append(row(f"  Uptime     {format_uptime(stats['uptime'])}"))
    lines.append(row(f"  Load avg   {stats['load']}"))
    gap()

    # performance
    lines.append(row("  ⚡ PERFORMANCE"))
    lines.append(bar_row("CPU", stats["cpu"], stats["cpu_history"]))
    lines.append(bar_row("RAM", stats["ram_percent"], stats["ram_history"]))
    lines.append(bar_row("Swap", stats["swap_percent"]))
    lines.append(bar_row("Disk", stats["disk_percent"]))
    gap()

    # memory (hidden in compact mode)
    if not compact:
        lines.append(row("  💾 MEMORY"))
        lines.append(row(
            f"  RAM Used   {format_bytes(stats['ram_used'])} / "
            f"{format_bytes(stats['ram_total'])}"
        ))
        lines.append(row(
            f"  Swap Used  {format_bytes(stats['swap_used'])} / "
            f"{format_bytes(stats['swap_total'])}"
        ))
        lines.append(row(f"  Disk Free  {format_bytes(stats['disk_free'])}"))
        gap()

    # network
    lines.append(row("  🌐 NETWORK"))
    if stats["online"]:
        lines.append(row(f"  Status     {paint('● Online', 'good')}"))
    else:
        lines.append(row(f"  Status     {paint('● Offline', 'high')}"))
    lines.append(row(f"  Download   ↓ {format_speed(stats['download'])}"))
    lines.append(row(f"  Upload     ↑ {format_speed(stats['upload'])}"))
    gap()

    # processes
    lines.append(row("  📊 TOP PROCESSES"))
    gap()
    lines.append(row(f"  {'PID':<9}{'NAME':<19}{'CPU':<9}{'RAM':<6}"))
    lines.append(row("  " + "─" * (WIDTH - 4)))
    for process in stats["processes"]:
        pid = str(process["pid"]).ljust(9)
        name = process["name"][:17].ljust(19)
        cpu_text = f"{process['cpu']:.1f}%".ljust(9)
        ram_text = f"{process['memory']:.1f}%"
        lines.append(row(f"  {pid}{name}{cpu_text}{ram_text}"))
    gap()

    lines.append(paint(f"╰{'─' * WIDTH}╯", "border"))
    lines.append("")
    lines.append(f"   🔄 Refreshing every {interval:g} seconds...")
    lines.append("   Press Ctrl+C to quit")

    return "\n".join(lines)


# ---------------------------------------------------------------- main

def fit_to_terminal(stats, interval, tick):
    """Pick the biggest layout that fits, so the screen never scrolls."""
    rows = shutil.get_terminal_size((80, 24)).lines - 1
    frame = render(stats, interval, tick)
    if frame.count("\n") + 1 > rows:
        frame = render(stats, interval, tick, compact=True)
    lines = frame.split("\n")
    if len(lines) > rows:
        lines = lines[:rows]          # last resort: cut the bottom
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="LinuxLens - cute system dashboard")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="seconds between data refreshes (default: 2)")
    parser.add_argument("--top", type=int, default=5,
                        help="how many top processes to show (default: 5)")
    parser.add_argument("--theme", choices=sorted(THEMES), default="default",
                        help="color theme (default: default)")
    parser.add_argument("--alert-threshold", type=float, default=80.0,
                        help="CPU/RAM percent that counts as high (default: 80)")
    parser.add_argument("--alert-after", type=float, default=10.0,
                        help="seconds of high usage before alerting (default: 10)")
    return parser.parse_args()


def main():
    args = parse_args()
    interval = max(args.interval, 0.5)
    set_theme(args.theme)

    # prime the CPU counters so the very first frame is accurate
    psutil.cpu_percent(interval=None)
    for process in psutil.process_iter(["cpu_percent"]):
        pass

    counters = psutil.net_io_counters()
    state = {
        "last_time": time.time(),
        "last_recv": counters.bytes_recv,
        "last_sent": counters.bytes_sent,
        "cpu_history": deque(maxlen=HISTORY_LENGTH),
        "ram_history": deque(maxlen=HISTORY_LENGTH),
        "high_since": {"CPU": None, "RAM": None},
    }

    # data refreshes every `interval`; the screen redraws every 0.5s so the
    # penguin can blink and the alert banner can flash in between
    redraws_per_cycle = max(1, round(interval / ANIMATION_STEP))
    tick = 0

    print("\033[2J\033[?25l", end="")   # clear screen once, hide cursor
    try:
        time.sleep(0.5)
        while True:
            stats = collect_stats(
                state, args.top, args.alert_threshold, args.alert_after
            )
            for _ in range(redraws_per_cycle):
                frame = fit_to_terminal(stats, interval, tick)
                # move cursor home and redraw in one go (no flicker)
                print("\033[H" + frame + "\033[J", end="", flush=True)
                tick += 1
                time.sleep(ANIMATION_STEP)
    except KeyboardInterrupt:
        pass
    finally:
        print("\033[?25h", end="")      # show cursor again
        print("\033[2J\033[H", end="")
        print("🐧 see you soon! 🌸")


if __name__ == "__main__":
    main()