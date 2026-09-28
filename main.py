import mimetypes
import os.path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

hostName = "localhost"
serverPort = 8080

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "public_html")

print(TEMPLATES_DIR)

def read_template(filename:str) -> str:
    path = os.path.join(TEMPLATES_DIR, filename)
    try:
        with open(path, "r", encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Файл не найден</h1>"

def serve_static_file(path: str) -> tuple:
    full_path = os.path.join(STATIC_DIR, path.lstrip('/'))

    # Защита от выхода за пределы папки (чтобы нельзя было запросить ../../etc/passwd)
    if not os.path.commonpath([STATIC_DIR, full_path]) == STATIC_DIR:
        return None, 403

    if os.path.isfile(full_path):
        mime_type, _ = mimetypes.guess_type(full_path)
        with open(full_path, "rb") as f:
            return f.read(), mime_type or "application/octet-stream"
    return None, 404

class MyServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # ничего не делаем
    
    def _render_view(self, view_page) -> str:
        return read_template(f"{view_page}.html")

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Если путь начинается с /assets, пытаемся отдать файл
        if path != "/" and not path.startswith("/templates"):
            content, mime_type = serve_static_file(path)
            if content:
                self.send_response(200)
                self.send_header("Content-type", mime_type)
                self.end_headers()
                self.wfile.write(content)
                return
        route_key = path.strip("/")

        route_map = {
            "": "main",
            "catalog": "catalog",
            "category": "category",
            "contact": "contact"
        }

        view_page = route_map.get(route_key, "404")

        if view_page == "404":
            page_content = self._render_view(view_page)
            self.send_response(404)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(bytes(page_content, "utf-8"))
            return

        try:
            page_content = self._render_view(view_page)
            # Если read_template вернул заглушку "Файл не найден", считаем это ошибкой
            if "<h1>Файл не найден</h1>" in page_content:
                raise FileNotFoundError
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Page not found</h1>")
            return

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(bytes(page_content, "utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))

        post_data = self.rfile.read(content_length).decode('utf-8')
        data = parse_qs(post_data)

        username = data.get('username', [''])[0]
        email = data.get('email', [''])[0]
        message = data.get('message', [''])[0]

        print(f"Получено сообщение от: {username} ({email})")
        print(f"Текст: {message}")

        self.send_response(303)  # 303 See Other — стандарт для редиректа после POST
        self.send_header('Location', '/contact')
        self.end_headers()
        # self.wfile.write(response_body.encode('utf-8'))


if __name__ == "__main__":
    webServer = HTTPServer((hostName, serverPort), MyServer)
    print("Server started http://%s:%s" % (hostName, serverPort))
    print(f"Static files served from: {STATIC_DIR}")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")