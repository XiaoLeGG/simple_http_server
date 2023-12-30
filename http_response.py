import os
import random
import socket
import enum
import utils
from http_connection import HTTPConnection
from typing import Union


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
        chunked : bool=False,
        is_head : bool=False,
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
        return cls(version=version, status_code=status_code, reason=reason, headers=headers, body=body, ranges=ranges, is_head=is_head, chunked=chunked)


    def __init__(self, version : str, status_code : int, reason : str, headers : dict, body : tuple, ranges : list, is_head : bool=False, chunked=False):
        self.status_code = status_code
        self.reason = reason
        self.headers = headers
        self.body = body
        self.version = version
        self.ranges = ranges
        self.is_head = is_head
        self.chunked = chunked

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

    
    def send(self, conn : Union[socket.socket, HTTPConnection]):
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

                self.headers["Accept-Ranges"] = "bytes"
                # range transfer
                if self.ranges:
                    self.status_code = 206
                    self.reason = "Partial Content"
                    boundary = "CS305v" + "{:05}".format(random.randint(0, 99999))
                    origin_content_type = self.headers["Content-Type"]
                    use_boundary = len(self.ranges) > 1
                    if use_boundary:
                        self.headers["Content-Type"] += f"multipart/byteranges; boundary={boundary}"
                    content_ranges = "bytes " + ",".join([f"{start}-{end}/{file_size}" for start, end in self.ranges])
                    self.headers["Content-Range"] = content_ranges
                    self.headers["Content-Length"] = self.ranges[0][1] - self.ranges[0][0] + 1
                    _content_length = 0
                    for start, end in self.ranges:
                        if use_boundary:
                            _content_length += len(b"--" + boundary.encode() + b"\r\n")
                            _content_length += len(b"Content-Type: " + origin_content_type.encode() + b"\r\n")
                            _content_length += len(b"Content-Range: bytes " + str(start).encode() + b"-" + str(end).encode() + b"/" + str(file_size).encode() + b"\r\n")
                            _content_length += len(b"Content-Length: " + str(end - start + 1).encode() + b"\r\n")
                            _content_length += len(b"\r\n")
                        _content_length += end - start + 1
                        _content_length += len(b'\r\n\r\n')
                    if use_boundary:
                        _content_length += len(b"--" + boundary.encode() + b"--")
                    self.headers["Content-Length"] = _content_length
                    conn.sendall(self._build_headers().encode())
                    if self.is_head:
                        return
                    for start, end in self.ranges:
                        if use_boundary:
                            conn.sendall(b"--" + boundary.encode() + b"\r\n")
                            conn.sendall(f"Content-Type: {origin_content_type}".encode() + b"\r\n")
                            conn.sendall(f"Content-Range: bytes {start}-{end}/{file_size}".encode() + b"\r\n")
                            conn.sendall(f"Content-Length: {end - start + 1}".encode() + b"\r\n")
                            conn.sendall(b"\r\n")
                        file.seek(start)
                        rest_data_len = end - start + 1
                        while rest_data_len > 0:
                            data = file.read(min(rest_data_len, DOWNLOAD_SPEED))
                            conn.sendall(data)
                            rest_data_len -= min(rest_data_len, DOWNLOAD_SPEED)
                        conn.sendall(b"\r\n\r\n")
                    if use_boundary:
                        conn.sendall(b"--" + boundary.encode() + b"--\r\n\r\n")
                    return
                else:
                    
                    # Transfer-Encoding
                    if self.chunked:
                        # response_builder.append(f"Content-Length: 0\r\n")
                        self.headers["Transfer-Encoding"] = "chunked"
                        headers_str = self._build_headers()
                        conn.sendall(headers_str.encode())
                        # print(headers_str)
                        if self.is_head:
                            return
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
                        if self.is_head:
                            return
                        file.seek(0)
                        rest_data_len = file_size
                        while rest_data_len > 0:
                            data = file.read(min(rest_data_len, DOWNLOAD_SPEED))
                            conn.sendall(data)
                            rest_data_len -= min(rest_data_len, DOWNLOAD_SPEED)
                        conn.sendall(b"\r\n\r\n")
                        return


