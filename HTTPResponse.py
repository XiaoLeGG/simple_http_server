import os
import random
import socket
import enum
import utils

DOWNLOAD_SPEED = 1024 * 1024 * 100

class HTTPBodyType(enum.Enum):
    EMPTY = "empty"
    TEXT = "text"
    FILE = "file"

class HTTPResponse:


    @classmethod
    def build(
        cls,
        version : str="1.1",
        status_code : int=200,
        reason : str="OK",
        body : tuple[HTTPBodyType,]=(HTTPBodyType.EMPTY, None),
        content_type : str=None,
        keep_alive : bool=False,
        timeout : int=20,
        max : int=1000,
        set_cookie : str=None,
        ranges : list=None,
        server : str="CS305 HTTP Server/1.0",
        headers : dict[str, str]=None,
        **kwargs
        ) -> "HTTPResponse":

        if headers is None:
            headers = dict()    

        headers["Connection"] = "Keep-Alive" if keep_alive else "Close"
        headers["Server"] = server
        if content_type:
            headers["Content-Type"] = content_type
        if keep_alive:
            headers["Keep-Alive"] = f"timeout={timeout}; max={max}"
        if set_cookie:
            headers["Set-Cookie"] = set_cookie
        return cls(version, status_code, reason, headers, body, ranges)


    def __init__(self, version : str, status_code : int, reason : str, headers : dict, body : tuple, ranges : list):
        self.status_code = status_code
        self.reason = reason
        self.headers = headers
        self.body = body
        self.version = version
        self.ranges = ranges

    def get_status_code(self) -> int:
        return self.status_code

    def get_reason(self) -> str:
        return self.reason

    def get_headers(self) -> dict:
        return self.headers

    def get_body(self) -> tuple:
        return self.body

    def set_status_code(self, status_code : int):
        self.status_code = status_code

    def set_reason(self, reason : str):
        self.reason = reason

    def set_headers(self, headers : dict):
        self.headers = headers

    def set_body(self, body : tuple):
        self.body = body

    
    def _build_headers(self) -> str:
        response_builder = []
        response_builder.append(f"HTTP/{self.version} {self.status_code} {self.reason}\r\n")
        
        for key, value in self.headers.items():
            response_builder.append(f"{key}: {value}\r\n")
        response_builder.append("\r\n")
        return "".join(response_builder)

    def send(self, conn : socket.socket):
        
        date = utils.get_current_time().strftime("%a, %d %b %Y %H:%M:%S GMT")
        self.headers["Date"] = date

        if (self.body[0] == HTTPBodyType.EMPTY):
            self.headers["Content-Length"] = 0
            conn.sendall(self._build_headers().encode())
            return
        
        if (self.body[0] == HTTPBodyType.TEXT):
            if isinstance(self.body[1], str):
                self.body = (self.body[0], self.body[1].encode())
            self.headers["Content-Length"] = len(self.body[1])
            conn.sendall(self._build_headers().encode())
            conn.sendall(self.body[1] + b"\r\n\r\n")

            return

        if (self.body[0] == HTTPBodyType.FILE):
            file_path = self.body[1]
            with open(file_path, "rb") as file:
                file_size = os.path.getsize(file_path)

                # range transfer
                if self.ranges:
                    self.status_code = 206
                    self.reason = "Partial Content"
                    self.headers["Accept-Ranges"] = "bytes"
                    boundary = "CS305v" + "{:05}".format(random.randint(0, 99999))
                    origin_content_type = self.headers["Content-Type"]
                    self.headers["Content-Type"] = "multipart/byteranges; boundary=" + boundary
                    conn.sendall(self._build_headers().encode())
                    for start, end in self.ranges:
                        conn.sendall(b"--" + boundary.encode() + b"\r\n")
                        conn.sendall(f"Content-Type: {origin_content_type}".encode() + b"\r\n")
                        conn.sendall(f"Content-Range: bytes {start}-{end}/{file_size}".encode() + b"\r\n")
                        conn.sendall(f"Content-Length: {end - start + 1}".encode() + b"\r\n")                            
                        file.seek(start)
                        conn.sendall(b"\r\n")
                        data = file.read(end - start + 1)
                        conn.sendall(data)
                        conn.sendall(b"\r\n\r\n")
                    conn.sendall(b"--" + boundary.encode() + b"--\r\n")
                    return
                else:
                    
                    # Transfer-Encoding
                    if file_size > DOWNLOAD_SPEED * 10:
                        # response_builder.append(f"Content-Length: 0\r\n")
                        self.headers["Transfer-Encoding"] = "chunked"
                        headers_str = self._build_headers()
                        conn.sendall(headers_str.encode())
                        # print(headers_str)
                        
                        while True:
                            data = file.read(DOWNLOAD_SPEED)
                            if not data:
                                break
                            conn.sendall(f"{len(data):X}\r\n".encode())
                            conn.sendall(data)
                            conn.sendall(b"\r\n")
                            if len(data) < DOWNLOAD_SPEED:
                                break
                        conn.sendall(b"0\r\n\r\n")
                        return
                    else:

                        # Simple File Transfer
                        self.headers["Content-Length"] = file_size
                        conn.sendall(self._build_headers().encode())
                        conn.sendall(file.read())
                        conn.sendall(b"\r\n\r\n")
                        return


