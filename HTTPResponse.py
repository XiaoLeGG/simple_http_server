import os
import datetime
import random

class HTTPResponse:

    _chunked_file_size = 1024

    @classmethod
    def build(
        cls,
        version="1.1",
        status_code=200,
        reason="OK",
        body=("text", "Hello World!"),
        content_type="text/plain",
        keep_alive=True,
        timeout=5,
        max=1000,
        set_cookie=None,
        ranges=None,
        server="CS305 HTTP Server/1.0",
        **kwargs
        ) -> "HTTPResponse":

        headers = dict()
        headers["Content-Type"] = content_type
        headers["Connection"] = "keep-alive" if keep_alive else "close"
        headers["Server"] = server
        if keep_alive:
            headers["Keep-Alive"] = f"timeout={timeout}; max={max}"
        if set_cookie:
            headers["Set-Cookie"] = set_cookie
        return cls(version, status_code, reason, headers, body, range)


    def __init__(self, version, status_code, reason, headers, body, ranges):
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

    def set_status_code(self, status_code) -> None:
        self.status_code = status_code

    def set_reason(self, reason) -> None:
        self.reason = reason

    def set_headers(self, headers) -> None:
        self.headers = headers

    def set_body(self, body) -> None:
        self.body = body

    def send(self, conn) -> None:
        response_builder = []
        response_builder.append(f"HTTP/{self.version} {self.status_code} {self.reason}\r\n")
        
        for key, value in self.headers.items():
            response_builder.append(f"{key}: {value}\r\n")
        date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT  ")
        response_builder.append(f"Date: {date}\r\n")

        if (self.body[0] == "empty"):
            response_builder.append("Content-Length: 0\r\n")
            response_builder.append("\r\n")
            for line in response_builder:
                conn.sendall(line.encode())
            return
        
        if (self.body[0] == "text"):
            response_builder.append(f"Content-Length: {len(self.body[1])}\r\n")
            response_builder.append("\r\n")
            response_builder.append(self.body[1] + "\r\n")
            response_builder.append("\r\n")
            for line in response_builder:
                conn.sendall(line.encode())
            return

        if (self.body[0] == "file"):
            file_path = self.body[1]
            with open(file_path, "rb") as file:
                file_size = os.path.getsize(file_path)

                # range transfer
                if self.ranges:
                    response_builder.append("Accept-Ranges: bytes\r\n")
                    boundary = "CS305v" + "{:05}".format(random.randint(0, 99999))
                    for line in response_builder:
                        if line.startswith("Content-Type"):
                            conn.sendall(b"Content-Type: multipart/byteranges; boundary=" + boundary.encode() + "\r\n".encode())
                        else:
                            conn.sendall(line.encode())
                    conn.sendall(b"\r\n")
                    for start, end in self.ranges:
                        conn.sendall(b"--" + boundary.encode() + "\r\n".encode())
                        conn.sendall("Content-Type: {type}".format(type=self.headers["Content-Type"]).encode() + "\r\n".encode())
                        conn.sendall("Content-Range: bytes {start}-{end}/{size}".format(start=start, end=end, size=file_size).encode() + "\r\n".encode())
                        conn.sendall("Content-Length: {length}".format(length=end - start + 1).encode() + "\r\n".encode())                            
                        file.seek(start)
                        conn.sendall(b"\r\n")
                        data = file.read(end - start + 1)
                        conn.sendall(data)
                        conn.sendall(b"\r\n")
                    conn.sendall(b"--" + boundary.encode() + "--\r\n\r\n".encode())
                    return
                else:
                    
                    # Transfer-Encoding
                    if file_size > self._chunked_file_size:
                        response_builder.append("Transfer-Encoding: chunked\r\n")
                        for line in response_builder:
                            conn.sendall(line.encode())
                        conn.sendall(b"\r\n")
                        while True:
                            data = file.read(self._chunked_file_size)
                            if not data:
                                break
                            conn.sendall(f"{len(data)}\r\n".encode())
                            conn.sendall(data)
                            conn.sendall(b"\r\n")
                        conn.sendall(b"0\r\n\r\n")
                        return
                    else:

                        # Simple File Transfer
                        response_builder.append(f"Content-Length: {file_size}\r\n")
                        for line in response_builder:
                            conn.sendall(line.encode())
                        conn.sendall(b"\r\n")
                        conn.sendall(file.read())
                        conn.sendall(b"\r\n\r\n")
                        return


