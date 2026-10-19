# Desktop Operator

A persistent localhost service that gives an agent fast, structured control of a Windows desktop and browser.

Instead of starting a new Playwright CLI process for every click, Desktop Operator keeps Playwright, Windows UI Automation, screen capture, and OCR in one long-lived process. A command usually returns in **10-150 ms**.

Built for Codex-style local agents, but usable standalone from PowerShell.

[中文说明](README.zh-CN.md)

## Why

Typical GUI-agent loops are slow for three reasons:

- every action pays a process startup cost;
- full-page snapshots return hundreds of lines to find one button;
- a wrong selector blocks for 30 seconds.

Desktop Operator fixes the loop:

- one daemon, many commands;
- compact element queries with bounding boxes;
- multiple selector fallbacks and a 4-second default timeout;
- batch actions in one request;
- native windows and canvas/OCR fallback when the browser DOM is not enough.

## Features

- Browser control through Playwright with a dedicated Edge profile.
- Compact DOM queries: tag, text, id, name, role, visibility, box.
- Multi-selector click/fill, fast failure diagnostics.
- Batch actions in one HTTP call.
- CDP attach to an existing Edge started with `--remote-debugging-port`.
- Native Windows control through UI Automation: list windows, inspect control trees, click, type, send keys.
- Screen capture and Chinese OCR using the built-in Windows OCR engine.
- Text-based coordinate clicks for canvas/VNC interfaces.
- Capture click-triggered API responses as JSON.
- DPAPI-backed local secret storage.

## Requirements

- Windows 10 or 11.
- PowerShell 5.1+.
- Python 3.11-3.13 (3.12 recommended).
- Microsoft Edge.

## Quick start

```powershell
git clone https://github.com/gz2008/desktop-operator.git
cd desktop-operator
.\setup.ps1
.\op.ps1 system.info
.\op.ps1 browser.goto "url=https://example.com" "headed=true"
.\op.ps1 browser.text
```

The first command starts the daemon automatically. `system.shutdown` stops it; the next call restarts it.

## Commands

| Command | Purpose |
|---|---|
| `system.info` | Monitors, Python, profile, daemon state |
| `browser.goto url=... headed=true` | Open a page |
| `browser.query selector=... limit=10` | Compact element matches |
| `browser.find_text text=...` | Find elements by visible text |
| `browser.click selectors=[...]` | Try selectors in order, click the first match |
| `browser.fill selector=... value=...` | Fill a field |
| `browser.text` | Page text |
| `browser.capture_response ...` | Capture a click-triggered API response |
| `browser.attach cdp_url=...` | Attach to an existing Edge via CDP |
| `win.list` | Top-level windows |
| `win.tree title=... depth=4 limit=120` | Compact UI Automation tree |
| `win.click title=... name=...` | Click a native control |
| `win.type title=... text=...` | Paste text into the focused control |
| `win.keys keys={Ctrl}s` | Send keys |
| `screen.capture` | Capture the primary/virtual screen |
| `screen.ocr path=...` | OCR lines and boxes |
| `screen.find_text query=...` | Locate text on screen |
| `screen.click_text query=...` | Click the center of a text match |
| `mouse.click x=... y=...` | Coordinate click |
| `keyboard.type text=...` | Type arbitrary text via clipboard |
| `batch` | Run multiple actions in one request |

See [README.zh-CN.md](README.zh-CN.md) for more examples.

## Batch example

```powershell
.\op.ps1 call '{"cmd":"batch","actions":[{"cmd":"browser.fill","selector":"#user","value":"admin"},{"cmd":"browser.click","selector":"text=Next"}]}'
```

## CDP attach

```powershell
msedge.exe --remote-debugging-port=9222 --user-data-dir=D:\path\to\profile
.\op.ps1 browser.attach "cdp_url=http://127.0.0.1:9222"
```

`browser.close` disconnects from CDP without closing the browser process.

## Secrets

```powershell
.\secret.ps1 set lab-ecs
$pw = .\secret.ps1 get lab-ecs   # assign to a variable; do not echo
.\secret.ps1 list
.\secret.ps1 remove lab-ecs
```

Secrets are stored with Windows DPAPI under `secrets/`, which is git-ignored.

## Architecture

```text
op.ps1 / dop.py client
        |
        v
127.0.0.1:8765  (single-threaded daemon)
  |-- Playwright (persistent Edge profile or CDP)
  |-- UI Automation (native windows)
  |-- mss + Pillow (screen capture)
  `-- PowerShell + Windows.Media.Ocr (OCR)
```

The daemon is single-threaded on purpose: desktop actions are serialized, and UIA/COM stays on one thread.

## Measured latency

Windows 11, 2560x1600, warm daemon:

| Command | Average |
|---|---:|
| `system.info` | 27 ms |
| `win.list` | 41-81 ms |
| `browser.text` | 16 ms |
| `browser.query` | 11-24 ms |
| `screen.capture` | 180-242 ms |
| Chinese OCR | ~1.2 s |

Run `bench.py` after starting the browser once.

## Security

- Binds to `127.0.0.1` only.
- Uses a dedicated Edge profile; it does not copy your main browser profile.
- Secrets use DPAPI and `secrets/` is git-ignored.
- `.gitignore` excludes `profile/`, `shots/`, `secrets/`, `cdp-test/`, logs, and `.venv/`.
- This is a local automation tool, not a remote-control or credential-extraction tool.

## Limitations

- Windows only.
- Native control depends on an app exposing UI Automation; fully custom-drawn apps may need OCR or a dedicated adapter.
- OCR coordinates are physical pixels; the daemon enables per-monitor DPI awareness.
- The browser profile is separate from your daily browsing profile unless you use CDP attach.

## Docs

- [KooLabs acceleration playbook](docs/PLAYBOOK-huaweicloud-koolabs.md)
- [Postmortem: 2026-10-19 Huawei Cloud lab](docs/POSTMORTEM-2026-10-19.md)

## License

MIT
