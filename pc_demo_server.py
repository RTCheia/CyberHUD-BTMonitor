import http.server
import json
import os
import socketserver
import sys
import threading
import time
import webbrowser

# 防止 Windows 控制台 GBK 编码报错
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pc_sender.hardware_monitor import HardwareMonitor

PORT = 8888
HTML_PATH = os.path.join(os.path.dirname(__file__), "preview_ui.html")

print("[INIT] 正在初始化硬件监控驱动 (LibreHardwareMonitor)...")
monitor = HardwareMonitor()
current_data = monitor.update()

def background_monitor_worker():
    global current_data
    while True:
        try:
            current_data = monitor.update()
        except Exception as e:
            print(f"[ERROR] 传感器更新异常: {e}")
        time.sleep(1)

class TelemetryHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(HTML_PATH, "rb") as f:
                self.wfile.write(f.read())
        elif self.path == "/api/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(current_data, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        pass

def run_server():
    t = threading.Thread(target=background_monitor_worker, daemon=True)
    t.start()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), TelemetryHandler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"\n=======================================================")
        print(f"[ONLINE] PC 硬件监控实时 Demo 服务已启动: {url}")
        print(f"[INFO] 正在打开浏览器实时预览...")
        print(f"=======================================================\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("[INFO] 正在关闭服务...")
        finally:
            monitor.close()

if __name__ == "__main__":
    run_server()
