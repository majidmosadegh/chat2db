#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'status': 'healthy', 'server': 'simple-http'}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        # Suppress default logging
        pass

def run_server():
    server_address = ('127.0.0.1', 8002)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Simple HTTP server running on port 8002...")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
