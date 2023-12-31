import socket
import threading
import mimetypes
import os
import base64
import utils
import datetime
from http_request import HTTPRequest, HTTPMethod
from http_response import HTTPResponse, HTTPBodyType
from http_connection import HTTPConnection
from rsa_encryptor import RSAEncryptor
from aes_encryptor import AESEncryptor
from log import Log, LogLevel
import uuid as ud
import tempfile
import time


class HTTPServer:

    def __init__(self, host: str = "localhost", port: int = 8080, parallel: int = 5, timeout: int = 10, cookie_persist_time: int = 3600, debug: bool = False, server: str = "CS305 HTTP Server/1.0", upload_chunk_size: int = 1024 * 1024 * 100):
        self.log = Log(
            f"logs{os.path.sep}log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
        self.host = host
        self.port = port
        self.debug = debug
        self.timeout = timeout
        self.parallel = parallel
        self.server = server
        self.upload_chunk_size = upload_chunk_size
        self.cookie_persist_time = cookie_persist_time
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(self.parallel)

        utils.init_sql()

    def run(self):
        self.log.log(
            LogLevel.INFO, f"{self.server} is running on {self.host}:{self.port}...")
        while True:
            conn, addr = self.socket.accept()
            new_thread = threading.Thread(
                target=self.handle_connection, args=(conn, addr))
            new_thread.daemon = True
            new_thread.start()

    def handle_request(self, conn: HTTPConnection) -> HTTPResponse:
        conn.settimeout(self.timeout)
        try:
            data = conn.recv(4096)
        except socket.timeout:
            self.log.log(
                LogLevel.INFO, f"Timeout from {conn.getpeername()[0]}:{conn.getpeername()[1]}")
            return HTTPResponse.build(server=self.server, status_code=200,
                                      reason="Timeout Closed",
                                      keep_alive=False), None
        if not data:
            self.log.log(
                LogLevel.INFO, f"Empty Request from {conn.getpeername()[0]}:{conn.getpeername()[1]}")
            return HTTPResponse.build(server=self.server, status_code=400,
                                      reason="Bad Request",
                                      keep_alive=True), None
        # bug here?
        index = data.find(b"\r\n\r\n")

        if index == -1:
            self.log.log(
                LogLevel.INFO, f"Bad Request from {conn.getpeername()[0]}:{conn.getpeername()[1]}")
            return HTTPResponse.build(server=self.server, status_code=400,
                                      reason="Bad Request",
                                      keep_alive=False), None
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
            LogLevel.INFO, f"Request from {conn.getpeername()[0]}:{conn.getpeername()[1]}: {http_request.get_method()} {http_request.get_uri()} {http_request.parameters} {http_request.get_protocol()}, keep-alive: {http_request.get_headers()['Connection'].lower() == 'keep-alive' if 'Connection' in http_request.get_headers() else False}")

        # print(http_request)
        aes_encryptor = None
        if http_request.get_method() == HTTPMethod.GET:
            response = self.handle_request_get(conn, http_request)
        elif http_request.get_method() == HTTPMethod.POST:
            response = self.handle_request_post(conn, http_request)
        elif http_request.get_method() == HTTPMethod.HEAD:
            response = self.handle_request_get(
                conn, http_request)
            response.is_head = True
        elif http_request.get_method() == HTTPMethod.ENCRYPT:
            response, aes_encryptor = self.hanlde_request_encrypt(
                conn, http_request
            )
        else:
            return HTTPResponse.build(server=self.server, status_code=405,
                                      reason="Method Not Allowed"), None
        response.headers["Connection"] = "Keep-Alive" if keep_alive and response.status_code < 300 else "Close"
        if keep_alive:
            response.headers["Keep-Alive"] = f"timeout={
                self.timeout}; max={self.parallel}"
        return response, aes_encryptor

    def handle_connection(self, conn: socket.socket, addr: tuple):
        self.log.log(
            LogLevel.INFO, f"Receive new connection from {addr[0]}:{addr[1]}")

        conn = HTTPConnection(conn)

        while True:
            try:
                response, aes_encryptor = self.handle_request(conn)
                self.log.log(
                    LogLevel.INFO, f"Response to {addr[0]}:{addr[1]}: {response.get_status_code()} {response.get_reason()}")
                response.send(conn)
                if not response.get_headers()["Connection"].lower() == "keep-alive":
                    break
                if aes_encryptor:
                    conn.set_encryptor(aes_encryptor)
            except Exception as e:
                if self.debug:
                    import traceback
                    traceback.print_exc()
                self.log.log(LogLevel.ERROR, f"Error: {e}")
                break
        try:
            time.sleep(1)
            conn.close()
        except Exception as e:
            pass
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

    def _normalize_uri_path(self, path: str):
        if path.startswith("/"):
            path = path[1:]
        if path.endswith("/"):
            path = path[:-1]

        file_path = utils.normalize_and_validate_path(os.path.sep, path)
        root_user = file_path.split(os.path.sep)[1]
        if file_path.startswith(os.path.sep):
            file_path = file_path[len(os.path.sep):]
        abs_file_path = os.path.join(utils.get_data_dir(), file_path)

        return file_path, root_user, abs_file_path

    def _verify_auth(self, root_user: str, user: str, password: str, is_cookie: bool, check_permission : bool = True) -> (int, str, ud.UUID):

        if user is None:
            return (401, "Authorization Required" if not is_cookie else "Cookie invalid or expired", None)
        uuid = utils.get_user_by_name(user)
        if uuid is None:
            return (401, "User not exists", None)
        if check_permission and root_user != user:
            return (403, "Forbidden", None)
        if is_cookie:
            cookie_uuid = ud.UUID(password)
        else:
            verification = utils.verify_user(uuid, password)
            if not verification:
                return (401, "Wrong password", None)
            cookie_uuid = utils.get_cookie_by_user(uuid)
            if cookie_uuid is None:
                cookie_uuid = utils.generate_cookie(
                    uuid, self.cookie_persist_time)
        utils.resign_cookie(cookie_uuid, self.cookie_persist_time)
        return (200, "", cookie_uuid)

    def hanlde_request_encrypt(self, conn: HTTPConnection, http_request: HTTPRequest) -> HTTPResponse:
        body = http_request.get_body()
        if "Content-Length" in http_request.get_headers():
            content_length = int(http_request.get_headers()["Content-Length"])
            if content_length > 0:
                _len = len(body)
                while _len < content_length:
                    _len += min(self.upload_chunk_size, content_length - _len)
                    body += conn.recv(min(self.upload_chunk_size, content_length -
                                      _len))
        aes_encryptor = AESEncryptor()
        data = RSAEncryptor.encrypt(
            aes_encryptor.get_key() + aes_encryptor.get_iv(), body)
        return HTTPResponse.build(server=self.server, status_code=200, reason="OK", body=(HTTPBodyType.TEXT, data), content_type="encryption/aes-key"), aes_encryptor

    def handle_request_post(self, conn: HTTPConnection, http_request: HTTPRequest) -> HTTPResponse:
        uri = http_request.get_uri()
        
        if uri.lower() == "/register":
            if "user" not in http_request.parameters or "password" not in http_request.parameters:
                return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
            user = http_request.parameters["user"]
            password = http_request.parameters["password"]
            if user is None or password is None or user == "" or password == "":
                return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
            try:
                uuid = utils.create_user(user, password)
            except Exception as e:
                return HTTPResponse.build(server=self.server, status_code=400, reason="User already exists")
            return HTTPResponse.build(server=self.server, status_code=200, reason="OK")
        
        if "path" not in http_request.parameters:
            return HTTPResponse.build(server=self.server, status_code=405, reason="Invalid Method")
        
        path = http_request.parameters["path"]
        file_path, root_user, abs_file_path = self._normalize_uri_path(path)
        user, password, is_cookie = self._get_request_auth(
            http_request.get_headers())
        auth_code, msg, uuid = self._verify_auth(
            root_user, user, password, is_cookie)
        if auth_code != 200:
            return HTTPResponse.build(server=self.server, status_code=auth_code,
                                      reason="Unauthorized" if auth_code != 403 else msg,
                                      headers={"WWW-Authenticate": f"Basic realm=\"{msg}\""} if auth_code != 403 else None)

        if not os.path.exists(abs_file_path):
            return HTTPResponse.build(server=self.server, status_code=404, reason="Not Found")

        if uri.lower() == "/upload":
            headers = http_request.get_headers()
            if "Rename" in headers:
                rename = headers["Rename"]
                while rename.endswith("/") or rename.endswith("\\"):
                    rename = rename[:-1]
                if "/" in rename:
                    rename = rename.split("/")[-1]
                if "\\" in rename:
                    rename = rename.split("\\")[-1]
                new_name = os.path.join(os.path.dirname(abs_file_path), rename)
                if new_name is None or new_name == "":
                    return HTTPResponse.build(server=self.server, status_code=400, reason="Invalid File Name")
                if os.path.exists(new_name):
                    return HTTPResponse.build(server=self.server, status_code=400, reason="File already exists")
                os.rename(abs_file_path, new_name)
                return HTTPResponse.build(server=self.server, status_code=200, reason="OK", set_cookie=f"session-id={str(uuid)}; Max-Age={self.cookie_persist_time}")
            if os.path.isfile(abs_file_path):
                return HTTPResponse.build(server=self.server, status_code=400, reason="You can not upload any thing to a file")
            if "Directory" in headers:
                dir_name = headers["Directory"]
                while dir_name.endswith("/") or dir_name.endswith("\\"):
                    dir_name = dir_name[:-1]
                if "/" in dir_name:
                    dir_name = dir_name.split("/")[-1]
                if "\\" in dir_name:
                    dir_name = dir_name.split("\\")[-1]
                if dir_name is None or dir_name == "":
                    return HTTPResponse.build(server=self.server, status_code=400, reason="Invalid Directory Name")
                abs_dir = os.path.join(abs_file_path, dir_name)
                if not os.path.exists(abs_dir):
                    os.makedirs(abs_dir)
                else:
                    return HTTPResponse.build(server=self.server, status_code=400, reason="Directory already exists")
                return HTTPResponse.build(server=self.server, status_code=200, reason="OK", set_cookie=f"session-id={str(uuid)}; Max-Age={self.cookie_persist_time}")
            if "Content-Type" in headers:
                if "boundary=" not in headers["Content-Type"]:
                    return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
                content_type_headers = dict(_header.split(
                    "=") for _header in headers["Content-Type"].split("; ")[1:])
                boundary = content_type_headers["boundary"]
                boundary = boundary.encode()
                body = http_request.get_body()
                if boundary not in body:
                    data = conn.recv(self.upload_chunk_size)
                    body += data if data else b""
                    if boundary not in body:
                        return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
                index = body.find(boundary)
                body = body[index:]
                while True:
                    with tempfile.TemporaryFile(mode="w+b") as tmp:
                        while True:
                            tmp.write(body)
                            if boundary + b"--" in body:
                                tmp.flush()
                                tmp.seek(0)
                                current_file = None
                                next_line = tmp.readline()
                                while True:
                                    line = next_line
                                    if not line:
                                        return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
                                    if line.startswith(b"--" + boundary + b"--"):
                                        if current_file:
                                            current_file.close()
                                            current_file = None
                                        break
                                    if line.startswith(boundary) or line.startswith(b"--" + boundary):
                                        if current_file:
                                            current_file.close()
                                            current_file = None
                                        filename = str(ud.uuid4()) + ".tmp"
                                        while True:
                                            line = tmp.readline()
                                            if line.startswith(b"Content-Disposition"):
                                                content_disposition = line.decode(
                                                    "utf-8").strip()
                                                if "filename" in content_disposition:
                                                    _headers = dict([header.split("=")
                                                                    for header in content_disposition.split("; ")[1:]])
                                                    if "filename" in _headers:
                                                        filename = _headers["filename"]
                                                        filename = filename[1:-1]
                                            if line == b"\r\n":
                                                break
                                        filename = os.path.basename(filename)
                                        upload_file_path = os.path.join(
                                            abs_file_path, filename)
                                        while os.path.exists(upload_file_path):
                                            index = filename.rfind(".")
                                            filename = filename[:index] + \
                                                " (1)" + filename[index:]
                                            upload_file_path = os.path.join(
                                                abs_file_path, filename)
                                        current_file = open(
                                            upload_file_path, "wb")
                                        next_line = tmp.readline()
                                        continue
                                    next_line = tmp.readline()
                                    if next_line and (next_line.startswith(boundary) or next_line.startswith(b"--" + boundary)):
                                        line = line[:-len(b'\r\n')]
                                    current_file.write(line)
                                return HTTPResponse.build(server=self.server, status_code=200, reason="OK", set_cookie=f"session-id={str(uuid)}; Max-Age={self.cookie_persist_time}")
                            body = conn.recv(self.upload_chunk_size)
                            if not body:
                                return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
                return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
            return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")
        elif uri.lower() == "/delete":
            if os.path.isdir(abs_file_path):
                return HTTPResponse.build(server=self.server, status_code=400, reason="You can not delete a directory")
            os.remove(abs_file_path)
            return HTTPResponse.build(server=self.server, status_code=200, reason="OK", set_cookie=f"session-id={str(uuid)}; Max-Age={self.cookie_persist_time}")
        else:
            return HTTPResponse.build(server=self.server, status_code=400, reason="Bad Request")

    def handle_request_get(self, conn: HTTPConnection, http_request: HTTPRequest) -> HTTPResponse:
        
        sustech_http = False

        if "SUSTech-HTTP" in http_request.parameters:
                if http_request.parameters["SUSTech-HTTP"] == "1":
                    sustech_http = True

        if "Content-Length" in http_request.get_headers():
            content_length = int(http_request.get_headers()["Content-Length"])
            if content_length > 0:
                body = http_request.get_body()
                _len = len(body)
                while _len < content_length:
                    _len += min(self.upload_chunk_size, content_length - _len)
                    conn.recv(min(self.upload_chunk_size, content_length -
                                  _len))
        uri = http_request.get_uri()
        if uri == "/" or uri == "":
            user, password, is_cookie = self._get_request_auth(
                http_request.get_headers())
            if not "Authorization" in http_request.get_headers() and user is None:
                if sustech_http:
                    return HTTPResponse.build(server=self.server, status_code=401,
                                          reason="Authorization Required")
                return HTTPResponse.build(server=self.server, status_code=200,
                                          reason="OK",
                                          content_type="text/html",
                                          body=(HTTPBodyType.TEXT, utils.login_html()))
            auth_code, msg, cookie_uuid = self._verify_auth(
                user, user, password, is_cookie)
            if auth_code != 200:
                if is_cookie:
                    return HTTPResponse.build(server=self.server, status_code=200,
                                          reason="OK",
                                          content_type="text/html",
                                          body=(HTTPBodyType.TEXT, utils.login_html()))
                return HTTPResponse.build(server=self.server, status_code=auth_code,
                                          reason="login failed")
            
            if sustech_http:
                return HTTPResponse.build(server=self.server, status_code=200,
                                              reason="OK",
                                              content_type="text/plain",
                                              body=(HTTPBodyType.TEXT, utils.file_explore_html(
                    None, None, utils.get_data_dir(), sustech_http=True)),
                    set_cookie=f"session-id={str(cookie_uuid)}; Max-Age={self.cookie_persist_time}")

            return HTTPResponse.build(server=self.server, status_code=302,
                                      reason="Found",
                                      headers={"Location": f"/{user}{"?" if http_request.parameters and len(http_request.parameters) > 0 else ""}{"&".join([f"{key}={value}" for key, value in http_request.parameters.items()])}"},
                                      set_cookie=f"session-id={str(cookie_uuid)}; Max-Age={self.cookie_persist_time}")

        else:
            file_path, root_user, abs_file_path = self._normalize_uri_path(uri)
            user, password, is_cookie = self._get_request_auth(
                http_request.get_headers())
            
            # special handling for SUSTech Project, do not check permission on get

            auth_code, msg, cookie_uuid = self._verify_auth(
                root_user, user, password, is_cookie, check_permission=False)

            if auth_code != 200:
                return HTTPResponse.build(server=self.server, status_code=auth_code,
                                          reason="Unauthorized" if auth_code != 403 else msg,
                                          headers={"WWW-Authenticate": f"Basic realm=\"{msg}\""} if auth_code != 403 else None)

            if not os.path.exists(abs_file_path):
                return HTTPResponse.build(server=self.server, status_code=404, reason="Not Found")

            if os.path.isdir(abs_file_path):
                html = utils.file_explore_html(
                    file_path, root_user, abs_file_path, sustech_http=sustech_http)
                return HTTPResponse.build(server=self.server, body=(HTTPBodyType.TEXT, html),
                                          status_code=200,
                                          reason="OK",
                                          content_type=(
                                              "text/html" if not sustech_http else "text/plain") + "; charset=utf-8",
                                          set_cookie=f"session-id={str(cookie_uuid)}; Max-Age={self.cookie_persist_time}")
            else:
                file_type = mimetypes.guess_type(abs_file_path)[0]
                if file_type is None:
                    file_type = "application/octet-stream"
                if "Range" in http_request.get_headers():
                    ranges = http_request.get_headers()["Range"]
                    ranges = utils.parse_ranges(
                        ranges, os.path.getsize(abs_file_path))
                    if ranges is None:
                        return HTTPResponse.build(server=self.server, status_code=416,
                                                  reason="Range Not Satisfiable")
                    return HTTPResponse.build(server=self.server, body=(HTTPBodyType.FILE, abs_file_path),
                                              status_code=206,
                                              reason="Partial Content",
                                              content_type=file_type,
                                              ranges=ranges,
                                              set_cookie=f"session-id={str(cookie_uuid)}; Max-Age={self.cookie_persist_time}")
                chunked = False
                if "chunked" in http_request.parameters:
                    if http_request.parameters["chunked"] == "1":
                        chunked = True
                return HTTPResponse.build(server=self.server, body=(HTTPBodyType.FILE, abs_file_path),
                                          status_code=200,
                                          reason="OK",
                                          content_type=file_type,
                                          set_cookie=f"session-id={str(cookie_uuid)}; Max-Age={self.cookie_persist_time}",
                                          chunked=chunked)
        return HTTPResponse.build(server=self.server, status_code=404, reason="Not Found")
