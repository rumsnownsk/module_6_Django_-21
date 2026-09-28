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
    """
    Считывает содержимое HTML-шаблона из папки шаблонов.

    Функция формирует полный путь к файлу, используя глобальную переменную TEMPLATES_DIR,
    и пытается прочитать его в кодировке UTF-8. Если файл не найден, вместо выброса
    исключения возвращается HTML-заглушка с сообщением об ошибке. Это позволяет серверу
    продолжить работу и отдать пользователю страницу 404 без аварийного завершения.
    """
    path = os.path.join(TEMPLATES_DIR, filename)
    try:
        with open(path, "r", encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Файл не найден</h1>"

def serve_static_file(path: str) -> tuple:
    """
    Обрабатывает запросы на получение статических файлов (CSS, JS, картинки и т.д.).

    Функция выполняет три ключевые задачи:
    1. Формирует безопасный абсолютный путь к запрашиваемому файлу внутри STATIC_DIR.
    2. Проверяет, не пытается ли пользователь выйти за пределы директории (защита от LFI-атак),
       используя os.path.commonpath.
    3. Определяет MIME-тип файла и возвращает его содержимое в бинарном виде вместе с типом.
    """
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
    """
    Кастомный обработчик HTTP-запросов для простого веб-сервера.

    Класс наследуется от BaseHTTPRequestHandler и переопределяет методы для:
    - Отключения стандартного логирования запросов в консоль.
    - Обработки GET-запросов (роутинг, отдача статики, рендеринг шаблонов).
    - Обработки POST-запросов (парсинг форм, сохранение данных, редирект).
    """
    def log_message(self, format, *args):
        pass  # ничего не делаем

    def _render_view(self, view_page) -> str:
        """
        Подготавливает имя файла шаблона и вызывает функцию его чтения.

        Метод добавляет расширение .html к имени страницы и делегирует чтение
        функции read_template. Является вспомогательным методом для do_GET.

        Args:
            view_page (str): Логическое имя страницы (без расширения), например "catalog".

        Returns:
            str: Строковое содержимое HTML-файла.
        """
        return read_template(f"{view_page}.html")

    def do_GET(self):
        """
        Обрабатывает входящие HTTP GET-запросы.

        Логика работы метода:
        1. Парсит URL запроса.
        2. Если запрос направлен на статику (и не является шаблоном), вызывает serve_static_file.
        3. Если запрос является маршрутом (например, "/", "/catalog"), сопоставляет его
           с ключом в словаре route_map и определяет нужный шаблон.
        4. Рендерит шаблон через _render_view. Если шаблон не найден или вернул заглушку,
           отправляет ответ с кодом 404.
        5. В случае успеха отправляет HTML-страницу с кодом 200.
        """
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
        """
        Обрабатывает входящие HTTP POST-запросы (отправка форм).

        Метод выполняет следующие действия:
        1. Считывает длину тела запроса и само тело.
        2. Парсит данные формы (формат application/x-www-form-urlencoded) в словарь.
        3. Извлекает значения полей username, email и message (с обработкой отсутствующих ключей).
        4. Выводит полученные данные в консоль (для отладки).
        5. Выполняет редирект (HTTP 303) на страницу "/contact", реализуя паттерн PRG
           (Post/Redirect/Get) для предотвращения повторной отправки формы при обновлении страницы.
        """
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


if __name__ == "__main__":
    """
    Точка входа в приложение. Инициализирует и запускает HTTP-сервер.

    Создает экземпляр HTTPServer, привязанный к hostName и serverPort,
    используя класс MyServer в качестве обработчика запросов.
    Запускает сервер в бесконечном цикле обработки соединений до тех пор,
    пока процесс не будет прерван пользователем (KeyboardInterrupt).
    Корректно закрывает сокеты сервера при остановке.
    """
    webServer = HTTPServer((hostName, serverPort), MyServer)
    print("Server started http://%s:%s" % (hostName, serverPort))
    print(f"Static files served from: {STATIC_DIR}")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")