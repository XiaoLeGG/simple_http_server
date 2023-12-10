from HTTPServer import HTTPServer
from HTTPRequest import HTTPRequest
from HTTPResponse import HTTPResponse

if __name__ == "__main__":
    server = HTTPServer()
    server.run()