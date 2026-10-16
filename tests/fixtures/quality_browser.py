"""中文：仅回环地址的浏览器验收夹具，拥有明确进程身份和有界生命周期。
English: Loopback browser fixture with explicit process ownership and a bounded lifetime.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Browser acceptance fixture</title>
<style>body{font:18px/1.5 system-ui,sans-serif;max-width:880px;margin:32px auto;padding:0 16px;color:#163049}
button{font:inherit;padding:8px 12px;margin:4px;border:1px solid #6b8494;border-radius:5px;background:#f5f8fa}
button:focus-visible{outline:3px solid #007782;outline-offset:3px}.panel{border:1px solid #bdcbd5;padding:16px;margin:16px 0}li{overflow-wrap:anywhere}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}</style>
<h1>Browser acceptance fixture</h1><p>Public synthetic data. No production records are used.</p>
<p id="identity">Service identity: __LABEL__ / __INSTANCE__</p><a href="/static">Open static page</a>
<section class="panel"><h2>Read-only requests</h2>
<button onclick="loadItems('normal')">Load items</button><button onclick="loadItems('empty')">Show empty</button>
<button onclick="loadItems('error')">Simulate error</button><button onclick="loadItems('slow')">Load slowly</button>
<button id="cancel" onclick="cancelLoad()" disabled>Cancel request</button>
<p id="status" role="status" aria-live="polite">Ready</p><ul id="items"></ul></section>
<section class="panel"><h2>Idempotent local write</h2><button id="save" onclick="saveRecord()">Create record</button>
<p id="saved" role="status" aria-live="polite">Created records: 0</p></section>
<script>
const api='__API__';let generation=0,controller=null;
const status=document.getElementById('status'),items=document.getElementById('items'),cancel=document.getElementById('cancel');
async function loadItems(mode){const mine=++generation;if(controller)controller.abort();controller=new AbortController();cancel.disabled=false;
status.textContent='Loading';items.replaceChildren();try{const response=await fetch(api+'/items?mode='+mode,{signal:controller.signal});
if(!response.ok)throw new Error('request');const data=await response.json();if(mine!==generation)return;
for(const item of data.items){const row=document.createElement('li');row.textContent=item;items.append(row)}
status.textContent=data.items.length?'Loaded '+data.items.length+' items':'No items found';
}catch(error){if(mine===generation)status.textContent=error.name==='AbortError'?'Cancelled':'Request failed; try again'}
finally{if(mine===generation){cancel.disabled=true;controller=null}}}
function cancelLoad(){++generation;if(controller)controller.abort();controller=null;cancel.disabled=true;items.replaceChildren();status.textContent='Cancelled'}
async function saveRecord(){const button=document.getElementById('save');if(button.disabled)return;button.disabled=true;
try{const response=await fetch(api+'/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idempotency_key:'browser-case-one'})});
if(!response.ok)throw new Error('request');const data=await response.json();document.getElementById('saved').textContent='Created records: '+data.created_count}
catch(error){document.getElementById('saved').textContent='Write failed'}finally{button.disabled=false}}
</script></html>"""


class Fixture:
    def __init__(self, label):
        self.label = label
        self.instance = secrets.token_hex(8)
        self.owner = secrets.token_urlsafe(24)
        self.stop = threading.Event()
        self.mutation_lock = threading.Lock()
        self.keys = set()
        self.api = ThreadingHTTPServer(("127.0.0.1", 0), self.handler("api"))
        try:
            self.front = ThreadingHTTPServer(("127.0.0.1", 0), self.handler("frontend"))
        except OSError:
            self.api.server_close()
            raise
        self.api_url = "http://127.0.0.1:" + str(self.api.server_port)
        self.front_url = "http://127.0.0.1:" + str(self.front.server_port)
        self.threads = []

    def identity(self, role):
        return {"fixture": "browser-quality/1", "instance": self.instance, "label": self.label,
                "pid": os.getpid(), "role": role}

    def handler(self, role):
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def send(self, value, code=200, html=False):
                raw = value.encode("utf-8") if html else json.dumps(value).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Access-Control-Allow-Origin", fixture.front_url)
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", fixture.front_url)
                self.send_header("Access-Control-Allow-Methods", "GET, POST")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def do_GET(self):
                parsed = urlsplit(self.path)
                if parsed.path == "/health":
                    return self.send(fixture.identity(role))
                if role == "frontend":
                    if parsed.path == "/static":
                        return self.send("<!doctype html><html lang=en><title>Static fixture</title><h1>Static fixture ready</h1><p>Public synthetic content.</p></html>", html=True)
                    if parsed.path == "/":
                        return self.send(PAGE.replace("__API__", fixture.api_url).replace("__LABEL__", fixture.label)
                                         .replace("__INSTANCE__", fixture.instance), html=True)
                elif parsed.path == "/items":
                    mode = parse_qs(parsed.query).get("mode", ["normal"])[0]
                    if mode not in {"normal", "empty", "error", "slow"}:
                        return self.send({"error": "INVALID_MODE"}, 400)
                    if mode == "slow":
                        fixture.stop.wait(2)
                    if mode == "error":
                        return self.send({"error": "SYNTHETIC_FAILURE"}, 503)
                    return self.send({"items": [] if mode == "empty" else ["Notebook", "Desk lamp"]})
                return self.send({"error": "NOT_FOUND"}, 404)

            def do_POST(self):
                if role != "api":
                    return self.send({"error": "NOT_FOUND"}, 404)
                if self.path == "/stop":
                    if self.headers.get("X-Fixture-Owner") != fixture.owner:
                        return self.send({"error": "NOT_AUTHORIZED"}, 403)
                    self.send(fixture.identity(role))
                    fixture.stop.set()
                    return
                if self.path != "/submit":
                    return self.send({"error": "NOT_FOUND"}, 404)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 256:
                        raise ValueError("bounded body")
                    self.connection.settimeout(2)
                    body = json.loads(self.rfile.read(length))
                    key = body["idempotency_key"]
                    if set(body) != {"idempotency_key"} or not isinstance(key, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", key):
                        raise ValueError("bounded key")
                except (ValueError, KeyError, TypeError, OSError):
                    return self.send({"error": "INVALID_ARGUMENT"}, 400)
                with fixture.mutation_lock:
                    if key not in fixture.keys and len(fixture.keys) >= 20:
                        return self.send({"error": "FIXTURE_LIMIT"}, 429)
                    fixture.keys.add(key)
                    return self.send({"created_count": len(fixture.keys)})
        return Handler

    def start(self):
        for server in (self.api, self.front):
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
            thread.start()
            self.threads.append(thread)

    def close(self):
        self.stop.set()
        for index, server in enumerate((self.api, self.front)):
            if index < len(self.threads) and self.threads[index].is_alive():
                server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=3)

    def lease(self):
        return {**self.identity("owner"), "frontend": self.front_url, "api": self.api_url, "owner_token": self.owner}


def stop_owned(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    url = value["api"]
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.path:
        raise ValueError("Not a loopback fixture lease")
    with urlopen(url + "/health", timeout=3) as response:
        health = json.load(response)
    if any(health.get(key) != value.get(key) for key in ("fixture", "instance", "pid", "label")) or health["role"] != "api":
        raise ValueError("Fixture owner identity changed")
    request = Request(url + "/stop", data=b"", headers={"X-Fixture-Owner": value["owner_token"]}, method="POST")
    with urlopen(request, timeout=3) as response:
        json.load(response)


def main():
    parser = argparse.ArgumentParser(description="Run or stop an explicitly owned loopback acceptance fixture.")
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--label", default="task-owned")
    parser.add_argument("--lifetime", type=int, default=600)
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if args.stop:
        stop_owned(args.lease)
        return 0
    if not 1 <= args.lifetime <= 1800 or not re.fullmatch(r"[a-z0-9-]{1,48}", args.label):
        raise ValueError("Bounded fixture parameters required")
    fixture = Fixture(args.label)
    try:
        with args.lease.open("x", encoding="utf-8") as stream:
            json.dump(fixture.lease(), stream)
        fixture.start()
        print(json.dumps({**fixture.identity("owner"), "frontend": fixture.front_url, "api": fixture.api_url}), flush=True)
        fixture.stop.wait(args.lifetime)
    finally:
        fixture.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
