from enum import Enum

class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    HEAD = "HEAD"
    PUT = "PUT"
    DELETE = "DELETE"


class HTTPRequest:

    @classmethod
    def build_by_headers(cls, headers : str, part_body : str, index : int=0):
        headers = headers.split("\r\n")
        line_0 = headers[0].split(" ")
        method = HTTPMethod(line_0[0].upper())
        uri = line_0[1]
        if (len(line_0) > 2):
            protocol = line_0[2]
        else:
            protocol = "HTTP/1.1"
        headers = headers[1:]
        headers = dict([header.split(": ") for header in headers])
        return cls(method, uri, protocol, headers, part_body, index)

    def __init__(self, method : HTTPMethod, uri : str, protocol : str, headers : dict, body, cursor : int):
        self.method = method
        self.uri = uri
        self.protocol = protocol
        self.headers = headers
        self.body = body
        self.cursor = cursor


    def get_method(self) -> HTTPMethod:
        return self.method

    def get_uri(self) -> str:
        return self.uri

    def get_protocol(self) -> str:
        return self.protocol

    def get_headers(self) -> dict:
        return self.headers

    def get_body(self):
        return self.body
    
    def __str__(self):
        return f"{self.method} {self.uri} {self.protocol}\r\n" + "\r\n".join([f"{key}: {value}" for key, value in self.headers.items()]) + "\r\n\r\n" + self.body

