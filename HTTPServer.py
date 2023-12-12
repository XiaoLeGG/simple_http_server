import socket
import threading
import mimetypes
import os
import base64
import utils
import datetime
from HTTPRequest import HTTPRequest, HTTPMethod
from HTTPResponse import HTTPResponse, HTTPBodyType
from log import Log, LogLevel
import uuid as ud


class HTTPServer:

    def __init__(self, host : str = "localhost", port : int = 8080, parallel : int = 5, timeout : int = 10, cookie_persist_time : int=3600):
        self.log = Log(
            f"logs/log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
        self.host = host
        self.port = port
        self.timeout = timeout
        self.parallel = parallel
        self.cookie_persist_time = cookie_persist_time
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(self.parallel)

        utils.init_sql()

    def run(self):
        self.log.log(
            LogLevel.INFO, f"HTTP Server is running on {self.host}:{self.port}...")
        while True:
            conn, addr = self.socket.accept()
            new_thread = threading.Thread(
                target=self.handle_connection, args=(conn, addr))
            new_thread.daemon = True
            new_thread.start()

    def handle_request(self, conn: socket.socket) -> HTTPResponse:
        conn.settimeout(self.timeout)
        try:
            data = conn.recv(4096)
        except socket.timeout:
            self.log.log(
                LogLevel.INFO, f"Timeout from {conn.getpeername()[0]}:{conn.getpeername()[1]}")
            return HTTPResponse.build(status_code=200,
                                      reason="Timeout Closed",
                                      keep_alive=False)
        if not data:
            self.log.log(
                LogLevel.INFO, f"Empty Request from {conn.getpeername()[0]}:{conn.getpeername()[1]}")
            return HTTPResponse.build(status_code=400,
                                      reason="Bad Request",
                                      keep_alive=True)
        
        # bug here?
        index = data.find(b"\r\n\r\n")
        
        if index == -1:
            self.log.log(
                LogLevel.INFO, f"Bad Request from {conn.getpeername()[0]}:{conn.getpeername()[1]}")
            return HTTPResponse.build(status_code=400,
                                      reason="Bad Request",
                                      keep_alive=False)
        headers_data = data[:index]
        body_data = data[index+len(b"\r\n\r\n"):]

        request_headers = headers_data.decode("utf-8")
        http_request = HTTPRequest.build_by_headers(
            request_headers, body_data, 4096)

        keep_alive = False
        if "Connection" in http_request.get_headers():
            if http_request.get_headers()["Connection"].lower() == "keep-alive":
                keep_alive = True
            else:
                keep_alive = False

        self.log.log(
            LogLevel.INFO, f"Request from {conn.getpeername()[0]}:{conn.getpeername()[1]}: {http_request.get_method()} {http_request.get_uri()} {http_request.get_protocol()}, keep-alive: {http_request.get_headers()['Connection'].lower() == 'keep-alive' if 'Connection' in http_request.get_headers() else False}")

        # print(http_request)

        if http_request.get_method() == HTTPMethod.GET:
            response = self.handle_request_get(conn, http_request)
            response.headers["Connection"] = "Keep-Alive" if keep_alive else "Close"
            if keep_alive:
                response.headers["Keep-Alive"] = f"timeout={self.timeout}; max={self.parallel}"
            return response
        elif http_request.get_method() == HTTPMethod.POST:
            pass
        elif http_request.get_method() == HTTPMethod.HEAD:
            pass
        else:
            return HTTPResponse.build(status_code=405,
                                      reason="Method Not Allowed")

    def handle_connection(self, conn: socket.socket, addr: tuple):
        self.log.log(
            LogLevel.INFO, f"Receive new connection from {addr[0]}:{addr[1]}")

        while True:
            try:
                response = self.handle_request(conn)
                self.log.log(
                    LogLevel.INFO, f"Response to {conn.getpeername()[0]}:{conn.getpeername()[1]}: {response.get_status_code()} {response.get_reason()}")
                response.send(conn)
                if not response.get_headers()["Connection"].lower() == "keep-alive":
                    break
            except Exception as e:
                # import traceback
                # traceback.print_exc()
                self.log.log(LogLevel.ERROR, f"Error: {e}")
                break
        conn.close()
        self.log.log(
            LogLevel.INFO, f"Connection from {addr[0]}:{addr[1]} closed.")
    def _get_request_auth(self, headers: dict) -> (str, str, bool):
        if not "Authorization" in headers:
            if "Cookie" in headers:
                cookie = headers["Cookie"]
                cookie_dict = dict([ck.split("=")
                                    for ck in cookie.split("; ")])
                if "session-id" in cookie_dict:
                    try:
                        cookie_uuid = ud.UUID(cookie_dict["session-id"])
                    except Exception as e:
                        return (None, None, True)
                    user_uuid = utils.get_user_by_cookie(cookie_uuid)
                    if user_uuid is None:
                        return None, str(cookie_uuid), True
                    user = utils.get_user_name_by_uuid(user_uuid)
                    return (user, str(cookie_uuid), True)
        else:
            auth = headers["Authorization"]
            user_pass_base64 = auth.split(" ")[1]
            user_pass = base64.b64decode(user_pass_base64).decode()
            user = user_pass.split(":")[0]
            password = user_pass.split(":")[1]
            return (user, password, False)
        return (None, None, False)

    def _verify_auth(self, root_user: str, user: str, password: str, is_cookie: bool) -> (int, str, ud.UUID):
        
        if user is None:
            return (401, "Authorization Required" if not is_cookie else "Cookie invalid or expired", None)
        if is_cookie:
            return (200, "", ud.UUID(password))
        uuid = utils.get_user_by_name(user)
        if root_user != user:
            return (401, "No permissions of the folder", None)
        if uuid is None:
            return (401, "User not exists", None)
        verification = utils.verify_user(uuid, password)
        if not verification:
            return (401, "Wrong password", None)
        return (200, "", uuid)

    def handle_request_get(self, conn: socket.socket, http_request: HTTPRequest, is_head: bool = False) -> HTTPResponse:

        if "Content-Length" in http_request.get_headers():
            content_length = int(http_request.get_headers()["Content-Length"])
            if content_length > 0:
                body = http_request.get_body()
                if len(body) < content_length:
                    body += conn.recv(content_length -
                                      len(body))
        uri = http_request.get_uri()
        if uri == "/":
            current_dir = utils.get_root_dir()
            html = utils.file_explore_html(current_dir, "test", current_dir)
            response = HTTPResponse.build(body=(HTTPBodyType.TEXT, html) if not is_head else ("empty", None),
                                          status_code=200,
                                          reason="OK",
                                          content_type="text/html" if not is_head else None)
            return response
        else:
            if uri.startswith("/favicon.ico"):
                return HTTPResponse.build(status_code=404,
                                          reason="Not Found")
            if uri.startswith("/"):
                uri = uri[1:]
            if uri.endswith("/"):
                uri = uri[:-1]
            
            file_path = utils.normalize_and_validate_path("/", uri)
            root_user = file_path.split("/")[1]
            abs_file_path = utils.get_data_dir() + "/" + file_path
            user, password, is_cookie = self._get_request_auth(http_request.get_headers())
            auth_code, msg, uuid = self._verify_auth(root_user, user, password, is_cookie)
            
            if auth_code != 200:
                return HTTPResponse.build(status_code=auth_code,
                                          reason="Unauthorized",
                                          headers={"WWW-Authenticate": f"Basic realm=\"{ msg }\""})

            if is_cookie:
                cookie_uuid = ud.UUID(password)
                # utils.resign_cookie(cookie_uuid, self.cookie_persist_time)
            else:
                cookie_uuid = utils.get_cookie_by_user(uuid)
                if cookie_uuid is None:
                    cookie_uuid = utils.generate_cookie(uuid, self.cookie_persist_time)

            if os.path.isdir(abs_file_path):
                sustech_http = False
                if "SUSTech-HTTP" in http_request.parameters:
                    if http_request.parameters["SUSTech-HTTP"] == "1":
                        sustech_http = True
                html = utils.file_explore_html(
                    file_path, root_user, abs_file_path, sustech_http=sustech_http)
                return HTTPResponse.build(body=(HTTPBodyType.TEXT, html) if not is_head else ("empty", None),
                                          status_code=200,
                                          reason="OK",
                                          content_type="text/html" if not is_head else None,
                                          set_cookie="session-id=" + str(cookie_uuid))
            else:
                file_type = mimetypes.guess_type(abs_file_path)[0]
                if file_type is None:
                    file_type = "application/octet-stream"
                if "Range" in http_request.get_headers():
                    ranges = http_request.get_headers()["Range"]
                    if ranges.startswith("bytes="):
                        ranges = utils.parse_ranges(
                            ranges, os.path.getsize(abs_file_path))
                    else:
                        ranges = None
                    if ranges is None:
                        return HTTPResponse.build(status_code=416,
                                                  reason="Range Not Satisfiable")
                    return HTTPResponse.build(body=(HTTPBodyType.FILE, abs_file_path) if not is_head else ("empty", None),
                                              status_code=206,
                                              reason="Partial Content",
                                              content_type=file_type if not is_head else None,
                                              ranges=ranges,
                                              set_cookie="session-id=" + str(cookie_uuid))
                return HTTPResponse.build(body=(HTTPBodyType.FILE, abs_file_path) if not is_head else ("empty", None),
                                          status_code=200,
                                          reason="OK",
                                          content_type=file_type if not is_head else None,
                                          set_cookie="session-id=" + str(cookie_uuid))
        return HTTPResponse.build(status_code=404, reason="Not Found")


if __name__ == "__main__":
    server = HTTPServer()
    server.run()
