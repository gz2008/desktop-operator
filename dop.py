from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import mss
import pyperclip
import uiautomation as auto
from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "profile"
SHOTS = ROOT / "shots"
LOG = ROOT / "operator.log"
HOST = "127.0.0.1"
PORT = 8765

SHOTS.mkdir(parents=True, exist_ok=True)


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def clamp_text(value, limit=4000):
    if not isinstance(value, str):
        return value
    return value if len(value) <= limit else value[:limit] + f"...[+{len(value) - limit}]"


def rect_dict(ctrl):
    try:
        r = ctrl.BoundingRectangle
        return [int(r.left), int(r.top), int(r.right), int(r.bottom)]
    except Exception:
        return None


class BrowserSession:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.headed = None
        self.attached = False

    def ensure(self, headed: bool = False, url: str | None = None):
        if self.ctx is not None and headed != self.headed:
            self.close()
        if self.ctx is None:
            self.pw = sync_playwright().start()
            self.ctx = self.pw.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE),
                channel="msedge",
                headless=not headed,
                viewport={"width": 1440, "height": 900},
                args=[
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                ],
            )
            self.headed = headed
            self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        if url:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return self.page

    def close(self):
        try:
            if self.attached:
                # Disconnect from CDP without closing the user's browser process.
                pass
            elif self.ctx is not None:
                self.ctx.close()
        finally:
            if self.pw is not None:
                self.pw.stop()
            self.pw = None
            self.browser = None
            self.ctx = None
            self.page = None
            self.headed = None
            self.attached = False

    def attach(self, cdp_url: str = "http://127.0.0.1:9222"):
        self.close()
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.connect_over_cdp(cdp_url)
        self.ctx = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.attached = True
        self.headed = True
        return self.page


BROWSER = BrowserSession()


JS_ELEMENT_INFO = """
e => {
  const r = e.getBoundingClientRect();
  const cs = getComputedStyle(e);
  return {
    tag: e.tagName.toLowerCase(),
    text: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim().slice(0, 160),
    id: e.id || '',
    name: e.getAttribute('name') || '',
    role: e.getAttribute('role') || '',
    aria: e.getAttribute('aria-label') || '',
    type: e.getAttribute('type') || '',
    cls: (typeof e.className === 'string' ? e.className : '').slice(0, 80),
    visible: !!(r.width && r.height && cs.visibility !== 'hidden' && cs.display !== 'none'),
    box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]
  };
}
"""


def bw_page(args):
    return BROWSER.ensure(bool(args.get("headed", False)), args.get("url"))


def browser_diag(page, selector=None):
    body = ""
    try:
        body = page.locator("body").inner_text(timeout=2000)[:600]
    except Exception:
        pass
    diag = {
        "url": page.url,
        "title": page.title(),
        "body": body,
    }
    if selector:
        try:
            loc = page.locator(selector)
            diag["count"] = loc.count()
            diag["visible"] = sum(
                1
                for i in range(min(loc.count(), 40))
                if loc.nth(i).is_visible(timeout=300)
            )
        except Exception as exc:
            diag["selector_error"] = str(exc)
    return diag


def resolve_locator(page, args):
    selectors = args.get("selectors") or [args.get("selector")]
    selectors = [s for s in selectors if s]
    if not selectors:
        raise ValueError("selector or selectors is required")
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                return selector, loc
        except Exception:
            continue
    return selectors[0], page.locator(selectors[0])


def cmd_browser(args):
    action = args["action"]
    if action == "close":
        BROWSER.close()
        return {"closed": True}
    if action == "attach":
        page = BROWSER.attach(args.get("cdp_url", "http://127.0.0.1:9222"))
        return {"attached": True, "url": page.url, "title": page.title()}

    page = bw_page(args)

    if action == "goto":
        page.goto(args["url"], wait_until=args.get("wait", "domcontentloaded"), timeout=args.get("timeout", 30000))
        return {"url": page.url, "title": page.title()}
    if action == "text":
        return {"url": page.url, "title": page.title(), "text": clamp_text(page.locator("body").inner_text(timeout=5000))}
    if action == "query":
        selector = args["selector"]
        limit = int(args.get("limit", 20))
        timeout = int(args.get("timeout", 5000))
        loc = page.locator(selector)
        count = loc.count()
        if count == 0 and args.get("wait", False):
            try:
                loc.first.wait_for(state="attached", timeout=timeout)
            except PlaywrightTimeout:
                pass
            count = loc.count()
        items = []
        for i in range(min(count, limit)):
            try:
                info = loc.nth(i).evaluate(JS_ELEMENT_INFO)
                info["index"] = i
                items.append(info)
            except Exception:
                continue
        return {"selector": selector, "count": count, "items": items}
    if action == "find_text":
        text = args["text"]
        loc = page.get_by_text(text, exact=bool(args.get("exact", False)))
        count = loc.count()
        items = []
        for i in range(min(count, int(args.get("limit", 20)))):
            try:
                info = loc.nth(i).evaluate(JS_ELEMENT_INFO)
                info["index"] = i
                items.append(info)
            except Exception:
                continue
        return {"text": text, "count": count, "items": items}
    if action in {"click", "dblclick", "fill", "check", "uncheck", "select_option"}:
        selector, loc_all = resolve_locator(page, args)
        index = int(args.get("index", 0))
        timeout = int(args.get("timeout", 4000))
        loc = loc_all.nth(index)
        try:
            if action == "click":
                loc.click(timeout=timeout)
            elif action == "dblclick":
                loc.dblclick(timeout=timeout)
            elif action == "fill":
                loc.fill(str(args.get("value", "")), timeout=timeout)
            elif action == "check":
                loc.check(timeout=timeout)
            elif action == "uncheck":
                loc.uncheck(timeout=timeout)
            else:
                loc.select_option(args.get("value"), timeout=timeout)
            return {"ok": True, "selector": selector, "index": index}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "diag": browser_diag(page, selector)}
    if action == "press":
        page.keyboard.press(args["key"])
        return {"ok": True}
    if action == "eval":
        value = page.evaluate(args["expr"])
        return {"value": clamp_text(value)}
    if action == "screenshot":
        path = Path(args.get("path") or (SHOTS / f"browser-{now_stamp()}.png"))
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=bool(args.get("full_page", False)), timeout=20000)
        return {"path": str(path), "bytes": path.stat().st_size}
    if action == "tabs":
        return {
            "tabs": [
                {"index": i, "url": p.url, "title": p.title()}
                for i, p in enumerate(BROWSER.ctx.pages)
            ]
        }
    if action == "tab":
        index = int(args["index"])
        BROWSER.page = BROWSER.ctx.pages[index]
        BROWSER.page.bring_to_front()
        return {"index": index, "url": BROWSER.page.url, "title": BROWSER.page.title()}
    if action == "new_tab":
        p = BROWSER.ctx.new_page()
        BROWSER.page = p
        if args.get("url"):
            p.goto(args["url"], wait_until="domcontentloaded", timeout=30000)
        return {"url": p.url, "title": p.title()}
    if action == "capture_response":
        if args.get("url"):
            page.goto(args["url"], wait_until="domcontentloaded", timeout=30000)
        match = args.get("match", "")
        timeout = int(args.get("timeout", 15000))
        with page.expect_response(lambda r: match in r.url, timeout=timeout) as info:
            if args.get("click_selector"):
                page.locator(args["click_selector"]).first.click(timeout=5000)
            elif args.get("reload", False):
                page.reload()
            else:
                page.wait_for_timeout(200)
        resp = info.value
        try:
            body = resp.json()
        except Exception:
            try:
                body = clamp_text(resp.text(), 4000)
            except Exception:
                body = None
        return {
            "status": resp.status,
            "url": resp.url,
            "location": resp.headers.get("location"),
            "body": body,
        }
    if action == "wait":
        if args.get("selector"):
            page.wait_for_selector(args["selector"], timeout=int(args.get("timeout", 5000)))
        else:
            page.wait_for_timeout(int(args.get("ms", 1000)))
        return {"ok": True}
    if action == "html":
        return {"html": clamp_text(page.content(), int(args.get("limit", 4000)))}
    raise ValueError(f"unknown browser action: {action}")


def find_window(title: str | None, exact: bool = False):
    root = auto.GetRootControl()
    for w in root.GetChildren():
        try:
            name = w.Name or ""
        except Exception:
            continue
        if not name:
            continue
        if title is None:
            return w
        if (name == title) if exact else (title.lower() in name.lower()):
            return w
    return None


def cmd_win(args):
    action = args["action"]
    if action == "list":
        root = auto.GetRootControl()
        items = []
        for w in root.GetChildren():
            try:
                name = w.Name or ""
                if not name:
                    continue
                items.append(
                    {
                        "title": name,
                        "type": w.ControlTypeName,
                        "class": w.ClassName,
                        "pid": w.ProcessId,
                        "rect": rect_dict(w),
                        "enabled": w.IsEnabled,
                        "offscreen": w.IsOffscreen,
                    }
                )
            except Exception:
                continue
        return {"windows": items}

    win = find_window(args.get("title"), bool(args.get("exact", False)))
    if win is None:
        return {"ok": False, "error": "window not found", "title": args.get("title")}
    if action in {"activate", "restore"}:
        hwnd = win.NativeWindowHandle
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.BringWindowToTop(hwnd)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        if action == "activate":
            win.SetFocus()
        return {"ok": True, "title": win.Name, "hwnd": hwnd}
    if action == "minimize":
        hwnd = win.NativeWindowHandle
        ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        return {"ok": True, "title": win.Name, "hwnd": hwnd}
    if action == "tree":
        depth = int(args.get("depth", 3))
        limit = int(args.get("limit", 200))
        out = []
        stack = [(win, 0)]
        while stack and len(out) < limit:
            ctrl, d = stack.pop()
            try:
                out.append(
                    {
                        "depth": d,
                        "type": ctrl.ControlTypeName,
                        "name": (ctrl.Name or "")[:120],
                        "automation_id": ctrl.AutomationId,
                        "class": ctrl.ClassName[:60],
                        "rect": rect_dict(ctrl),
                        "enabled": ctrl.IsEnabled,
                        "offscreen": ctrl.IsOffscreen,
                    }
                )
            except Exception:
                continue
            if d >= depth:
                continue
            try:
                children = ctrl.GetChildren()
            except Exception:
                continue
            for child in reversed(children[:60]):
                stack.append((child, d + 1))
        return {"title": win.Name, "count": len(out), "controls": out}
    if action in {"click", "type", "focus"}:
        name = args.get("name")
        control_type = args.get("control_type")
        limit = int(args.get("limit", 3000))
        candidates = []
        stack = [win]
        seen = 0
        while stack and seen < limit:
            ctrl = stack.pop()
            seen += 1
            try:
                cname = ctrl.Name or ""
                ctype = ctrl.ControlTypeName
                matched = True
                if name is not None:
                    matched = (cname == name) if args.get("exact", False) else (name.lower() in cname.lower())
                if control_type:
                    matched = matched and ctype.lower() == control_type.lower()
                if matched and (cname or control_type):
                    candidates.append(ctrl)
                stack.extend(reversed(ctrl.GetChildren()[:80]))
            except Exception:
                continue
        if not candidates:
            return {"ok": False, "error": "control not found", "name": name}
        ctrl = candidates[0]
        if action == "focus":
            ctrl.SetFocus()
        elif action == "click":
            ctrl.SetFocus()
            ctrl.Click(simulateMove=False, waitTime=0)
        else:
            ctrl.SetFocus()
            pyperclip.copy(str(args.get("text", "")))
            auto.SendKeys("{Ctrl}v", waitTime=0)
        return {
            "ok": True,
            "matched": len(candidates),
            "type": ctrl.ControlTypeName,
            "name": ctrl.Name,
            "rect": rect_dict(ctrl),
        }
    if action == "keys":
        auto.SendKeys(args["keys"], waitTime=0)
        return {"ok": True}
    if action == "close":
        try:
            win.GetWindowPattern().Close()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    raise ValueError(f"unknown win action: {action}")


def capture_screen(path: Path | None = None, region=None):
    path = Path(path or (SHOTS / f"screen-{now_stamp()}.png"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with mss.mss() as sct:
        mon = sct.monitors[0] if not region else region
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img.save(path)
    return {"path": str(path), "width": img.width, "height": img.height, "bytes": path.stat().st_size}


def run_ocr(path: str):
    ps = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    cmd = [str(ps), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "ocr.ps1"), "-Path", path]
    proc = subprocess.run(cmd, capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace") or "OCR failed")
    raw = proc.stdout.decode("utf-8", "replace").strip()
    return json.loads(raw)


def cmd_screen(args):
    action = args["action"]
    if action == "capture":
        return capture_screen(args.get("path"))
    if action == "monitors":
        with mss.mss() as sct:
            return {"monitors": sct.monitors}
    if action in {"ocr", "find_text", "click_text"}:
        path = args.get("path")
        if not path:
            path = capture_screen()["path"]
        data = run_ocr(path)
        lines = data.get("lines", [])
        compact = [
            {k: v for k, v in ln.items() if k != "words"}
            for ln in lines
        ]
        if action == "ocr":
            return {
                "path": path,
                "width": data.get("width"),
                "height": data.get("height"),
                "text": clamp_text(data.get("text", "")),
                "lines": (
                    lines if args.get("words", False) else compact
                )[: int(args.get("limit", 120))],
            }
        query = str(args.get("query", "")).replace(" ", "").lower()
        matches = [ln for ln in lines if query and query in str(ln.get("text", "")).replace(" ", "").lower()]
        if action == "find_text":
            return {
                "path": path,
                "query": args.get("query"),
                "count": len(matches),
                "matches": [
                    {k: v for k, v in ln.items() if k != "words"}
                    for ln in matches[:20]
                ],
            }
        if not matches:
            return {"ok": False, "error": "text not found", "query": args.get("query"), "path": path}
        index = int(args.get("index", 0))
        ln = matches[min(index, len(matches) - 1)]
        x = int(ln["x"] + ln["w"] / 2)
        y = int(ln["y"] + ln["h"] / 2)
        auto.Click(x, y, waitTime=0)
        return {"ok": True, "query": args.get("query"), "clicked": [x, y], "line": ln}
    raise ValueError(f"unknown screen action: {action}")


def cmd_mouse(args):
    action = args["action"]
    if action == "click":
        x, y = int(args["x"]), int(args["y"])
        if args.get("button") == "right":
            auto.RightClick(x, y, waitTime=0)
        else:
            auto.Click(x, y, waitTime=0)
        return {"ok": True, "x": x, "y": y}
    if action == "move":
        auto.SetCursorPos(int(args["x"]), int(args["y"]))
        return {"ok": True}
    if action == "wheel":
        delta = int(args.get("delta", -600))
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, delta, 0)
        return {"ok": True, "delta": delta}
    if action == "position":
        x, y = auto.GetCursorPos()
        return {"x": x, "y": y}
    raise ValueError(f"unknown mouse action: {action}")


def cmd_keyboard(args):
    action = args["action"]
    if action == "type":
        pyperclip.copy(str(args.get("text", "")))
        auto.SendKeys("{Ctrl}v", waitTime=0)
        return {"ok": True}
    if action == "keys":
        auto.SendKeys(args["keys"], waitTime=0)
        return {"ok": True}
    raise ValueError(f"unknown keyboard action: {action}")


def cmd_clipboard(args):
    if args["action"] == "get":
        return {"text": clamp_text(pyperclip.paste())}
    if args["action"] == "set":
        pyperclip.copy(str(args.get("text", "")))
        return {"ok": True}
    raise ValueError("unknown clipboard action")


def cmd_system(args):
    with mss.mss() as sct:
        monitors = sct.monitors
    return {
        "platform": sys.platform,
        "python": sys.version,
        "cwd": os.getcwd(),
        "profile": str(PROFILE),
        "monitors": monitors,
        "browser_running": BROWSER.ctx is not None,
        "headed": BROWSER.headed,
    }


def dispatch(payload):
    cmd = payload.get("cmd", "")
    if cmd == "batch":
        results = []
        for action in payload.get("actions", []):
            try:
                results.append({"ok": True, "data": dispatch(action)})
            except Exception as exc:
                results.append({"ok": False, "error": str(exc)})
                break
        return {"count": len(results), "results": results}
    if cmd == "system.shutdown":
        import threading

        threading.Timer(0.3, lambda: os._exit(0)).start()
        return {"ok": True, "message": "shutting down"}
    args = dict(payload)
    args["action"] = payload.get("action") or (cmd.split(".", 1)[1] if "." in cmd else "")
    if cmd.startswith("browser."):
        return cmd_browser(args)
    if cmd.startswith("win."):
        return cmd_win(args)
    if cmd.startswith("screen."):
        return cmd_screen(args)
    if cmd.startswith("mouse."):
        return cmd_mouse(args)
    if cmd.startswith("keyboard."):
        return cmd_keyboard(args)
    if cmd.startswith("clipboard."):
        return cmd_clipboard(args)
    if cmd == "system.info":
        return cmd_system(args)
    raise ValueError(f"unknown command: {cmd}")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "service": "desktop-operator"})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            started = time.time()
            result = dispatch(payload)
            self._send(200, {"ok": True, "data": result, "elapsed_ms": round((time.time() - started) * 1000)})
        except Exception as exc:
            self._send(
                200,
                {
                    "ok": False,
                    "error": str(exc),
                    "trace": traceback.format_exc()[-2000:],
                },
            )

    def log_message(self, fmt, *args):
        return


def serve():
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(f"\n[{datetime.now().isoformat()}] starting on {HOST}:{PORT}\n")
    HTTPServer((HOST, PORT), Handler).serve_forever()


def health(timeout=1.0):
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def ensure_server():
    if health():
        return True
    log = open(LOG, "ab", buffering=0)
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "serve"],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(50):
        if health(0.5):
            return True
        time.sleep(0.2)
    return False


def call(payload, timeout=180):
    if not ensure_server():
        raise RuntimeError("operator daemon failed to start; see operator.log")
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_value(raw: str):
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def main():
    parser = argparse.ArgumentParser(description="Persistent desktop/browser operator")
    parser.add_argument("command", nargs="?", default="health")
    parser.add_argument("pairs", nargs="*")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args()

    if ns.command == "serve":
        serve()
        return
    if ns.command == "health":
        print(json.dumps(health(2) or {"ok": False}, ensure_ascii=False))
        return
    if ns.command == "call":
        payload = json.loads(ns.pairs[0])
    else:
        payload = {"cmd": ns.command}
        for pair in ns.pairs:
            key, _, value = pair.partition("=")
            payload[key] = parse_value(value)
    result = call(payload)
    if ns.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
