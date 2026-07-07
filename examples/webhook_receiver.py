"""Mock receiver boundary. FieldSight stores delivery logs locally; configure a signed external target in production."""
from http.server import BaseHTTPRequestHandler, HTTPServer

class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        print("Webhook event received:", self.rfile.read(int(self.headers.get("Content-Length", 0))))
        self.send_response(204); self.end_headers()

HTTPServer(("127.0.0.1", 8787), Receiver).serve_forever()
