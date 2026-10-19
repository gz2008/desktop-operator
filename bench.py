import json
import statistics
import time
import urllib.request


URL = "http://127.0.0.1:8765/"


def call(payload):
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body, (time.perf_counter() - started) * 1000


CASES = [
    ("system.info", {"cmd": "system.info"}),
    ("win.list", {"cmd": "win.list"}),
    ("browser.text", {"cmd": "browser.text"}),
    ("browser.query", {"cmd": "browser.query", "selector": "body", "limit": 1}),
    ("screen.capture", {"cmd": "screen.capture"}),
]


for name, payload in CASES:
    samples = []
    for _ in range(3):
        result, elapsed = call(payload)
        samples.append(elapsed)
        if not result.get("ok", False):
            print(name, "ERROR", result.get("error"))
            break
    if samples:
        print(
            f"{name:16s} avg={statistics.mean(samples):7.1f}ms "
            f"min={min(samples):7.1f}ms max={max(samples):7.1f}ms"
        )
