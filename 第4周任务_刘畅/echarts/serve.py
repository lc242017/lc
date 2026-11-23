# -*- coding: utf-8 -*-
"""启动大屏 HTTP 服务（在线版 index.html 用 fetch 加载 data/*.json）"""
import http.server
import os
import socketserver

PORT = 8090
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print(f"大屏已启动: http://localhost:{PORT}/index.html")
    httpd.serve_forever()
