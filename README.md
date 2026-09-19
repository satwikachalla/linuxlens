# 🐧 LinuxLens

A cute little system dashboard for your terminal, written in Python with [psutil](https://github.com/giampaolo/psutil). It shows live CPU, memory, swap, disk, network speed and top processes, and comes with a penguin who reacts to how hard your machine is working.

<!-- After you upload demo.gif to the repo, delete this line and the arrows around the next one:
![LinuxLens demo](demo.gif)
-->

## ✨ Features

- **Live stats** for CPU, RAM, swap and disk, drawn as heart bars (`♥♥♥♡♡♡♡♡♡♡`) with GOOD / WARNING / HIGH status
- **Sparkline history** (`▁▂▃▅▇`) showing recent CPU and RAM trends
- **Network monitor** with online status and live download / upload speed
- **Top processes** sorted by CPU usage
- **System info**: OS, kernel version, hostname, CPU cores, uptime and load average
- **Animated penguin** 🐧 that blinks, and whose face changes with CPU load
- **High-usage alerts**: a flashing banner appears when CPU or RAM stays high, and the penguin gets worried
- **Pastel theme** for softer colors
- **Fits your terminal**: switches to a compact layout automatically if the window is short
- **Flicker-free** redraws, with no scrolling and no screen clearing every frame

## 🚀 Getting started

**Requirements:** Python 3.8+ and a terminal with emoji support. Built and tested on Linux.

```bash
git clone https://github.com/satwikachalla/linuxlens.git
cd linuxlens
pip install -r requirements.txt
python3 linuxlens.py
```

Press `Ctrl+C` to quit.

## ⚙️ Options

| Option | Default | Description |
|---|---|---|
| `--interval SECONDS` | `2` | How often stats are refreshed |
| `--top N` | `5` | Number of top processes to show |
| `--theme {default,pastel}` | `default` | Color theme |
| `--alert-threshold PERCENT` | `80` | CPU/RAM percentage that counts as "high" |
| `--alert-after SECONDS` | `10` | How long usage must stay high before the alert shows |

Examples:

```bash
python3 linuxlens.py --interval 1 --top 8
python3 linuxlens.py --theme pastel
python3 linuxlens.py --alert-threshold 70 --alert-after 5
```

## 🐧 Meet the penguin

| CPU load | Mood |
|---|---|
| under 30% | `(◕‿◕)` feeling great! |
| 30-60% | `(•‿•)` working hard~ |
| 60-80% | `(°▽°;)` getting busy... |
| 80%+ | `(>_<)` help, so toasty! |
| alert active | `(;_;)` please take a look! |

## 🧠 How it works

- `psutil` provides the CPU, memory, disk, network and process data
- Network speed is calculated from the difference in byte counters between refreshes
- Every screen row is padded using the *visible* width of its text (ignoring color codes and counting emoji as two columns), so the box borders stay aligned
- Data refreshes every `--interval` seconds, while the screen redraws every 0.5 seconds so the penguin can animate between updates
- The frame is printed in one piece with ANSI cursor codes instead of clearing the screen, which avoids flicker

## 🛠️ Ideas for later

- Keyboard controls (quit, pause, change process sorting)
- Per-core CPU bars
- Temperature and battery info
- Disk read/write speed
- CSV logging for graphing usage over time

## 📄 License

Free to use and learn from. Add a license file if you plan to share it more widely.
