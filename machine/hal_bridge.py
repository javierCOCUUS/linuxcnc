#!/usr/bin/env python3
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            return self._json({"service": "hal-bridge", "status": "online"})

        if parsed.path != "/hal/pins":
            return self._json({"error": "not_found"}, 404)

        query = parse_qs(parsed.query)
        needle = (query.get("filter", [""])[0] or "").lower().strip()

        try:
            result = subprocess.run(
                ["halcmd", "show", "pin"],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception as exc:
            return self._json({"error": "halcmd_failed", "detail": str(exc)}, 500)

        if result.returncode != 0:
            return self._json({
                "error": "halcmd_error",
                "stderr": result.stderr,
                "stdout": result.stdout,
            }, 500)

        pins = []
        for line in result.stdout.splitlines():
            raw = line.rstrip()
            if not raw.strip():
                continue
            if needle and needle not in raw.lower():
                continue

            parts = raw.split()
            pins.append({
                "raw": raw,
                "owner": parts[0] if len(parts) > 0 else "",
                "type": parts[1] if len(parts) > 1 else "",
                "direction": parts[2] if len(parts) > 2 else "",
                "value": parts[3] if len(parts) > 3 else "",
                "name": parts[4] if len(parts) > 4 else raw.strip(),
            })

        return self._json({
            "status": "ok",
            "filter": needle,
            "count": len(pins),
            "pins": pins,
        })


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8010), Handler)
    print("HAL bridge listening on http://0.0.0.0:8010")
    server.serve_forever()
