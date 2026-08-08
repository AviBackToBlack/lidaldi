#!/usr/bin/env python3
"""ZAP baseline scan target (T13, D4): one origin combining both halves.

Serves the built frontend (a static directory) and reverse-proxies
/api/sync/* to a locally running sync_server, mirroring the production
nginx layout (static webroot + proxied sync API on one origin).

Usage: static_proxy.py <static_root> <upstream_base_url> <port>
"""

import sys
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HOP_BY_HOP = {"transfer-encoding", "connection", "keep-alive", "date", "server"}


class Handler(SimpleHTTPRequestHandler):
    upstream = None  # set in main()

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(self.upstream + self.path, data=body, method=method)
        if self.headers.get("Content-Type"):
            req.add_header("Content-Type", self.headers["Content-Type"])
        # nginx parity: pass the real client address to the sync server so
        # its per-IP rate limiting sees the actual client, not the proxy.
        req.add_header("X-Real-IP", self.client_address[0])
        try:
            # snyk:ignore:Server-Side Request Forgery (SSRF)  # false positive: this is a test proxy whose purpose is to forward /api/* to a local upstream
            resp = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            resp = e
        with resp:
            data = resp.read()
            self.send_response(resp.code)
            for k, v in resp.getheaders():
                if k.lower() not in HOP_BY_HOP:
                    self.send_header(k, v)
            self.end_headers()
            # snyk:ignore:Cross-site Scripting (XSS)  # false positive: test proxy writing the upstream response body back to the client
            self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy("POST")
        else:
            self.send_error(405)

    def do_OPTIONS(self):
        if self.path.startswith("/api/"):
            self._proxy("OPTIONS")
        else:
            self.send_error(405)

    def log_message(self, fmt, *args):
        return


def main():
    static_root, upstream, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
    Handler.upstream = upstream.rstrip("/")
    srv = ThreadingHTTPServer(("0.0.0.0", port), partial(Handler, directory=static_root))
    print(f"static_proxy: serving {static_root} + proxying /api/ -> {upstream} on :{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
