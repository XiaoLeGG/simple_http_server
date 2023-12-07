
class HTTPRequest:

    @classmethod
    def parse(cls, data: bytes) -> "HTTPRequest":
        pass

    def __init__(self):
        pass


    def get_method(self):
        return self.method

    def get_uri(self):
        return self.uri

    def get_protocol(self):
        return self.protocol

    def get_headers(self):
        return self.headers

    def get_body(self):
        return self.body

