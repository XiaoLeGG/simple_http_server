import socket
import threading
from HTTPRequest import HTTPRequest, HTTPMethod
from HTTPResponse import HTTPResponse
import os
import base64
import utils

class HTTPServer:

    def __init__(self, host : str="localhost" , port : int=8080, parallel : int=5):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(parallel)
        utils.init_sql()

    def run(self):
        print(f"HTTP Server is running on {self.host}:{self.port}...")
        while True:
            conn, addr = self.socket.accept()
            threading.Thread(target=self.handle_connection, args=(conn, addr)).start()

    def handle_connection(self, conn : socket.socket, addr : tuple):
        print(f"Receive new connection from {addr[0]}:{addr[1]}")
        request = self.receive_request(conn)
        
        # conn.sendall(response)
        conn.close()

    def handle_request(self, conn : socket.socket):
        data = conn.recv(4096)
        if not data:
            return HTTPResponse.build(status_code=400, reason="Bad Request")
        request = data.decode("utf-8")
        index = request.find("\r\n\r\n")

        if not request or index == -1:
            return HTTPResponse.build(status_code=400, reason="Bad Request")
        request_headers = request[:index]
        request_body = request[index+4:]
        http_request = HTTPRequest.build_by_headers(request_headers, request_body, 4096)

        print(http_request)

        if http_request.get_method() == HTTPMethod.GET:
            return self.handle_request_get(conn, http_request)
        elif http_request.get_method() == HTTPMethod.POST:
            pass
        elif http_request.get_method() == HTTPMethod.HEAD:
            pass
        else:
            return HTTPResponse.build(status_code=405, reason="Method Not Allowed")
    

    def handle_connection(self, conn : socket.socket, addr : tuple):
        print(f"Receive new connection from {addr[0]}:{addr[1]}")
        
        # Process the request
        response = self.handle_request(conn)
        response.send(conn)
        conn.close()
        print(f"Connection from {addr[0]}:{addr[1]} closed.")


    def handle_request_get(self, conn : socket.socket, http_request : HTTPRequest, is_head : bool=False) -> HTTPResponse:
        if "Content-Length" in http_request.get_headers():
            content_length = int(http_request.get_headers()["Content-Length"])
            if content_length > 0:
                body = http_request.get_body()
                if len(body.encode("utf-8")) < content_length:
                    body += conn.recv(content_length - len(body.encode("utf-8"))).decode("utf-8")
        uri = http_request.get_uri()
        if uri == "/":
            # Get the current directory
            current_dir = os.getcwd()
            
            html = utils.file_explore_html(current_dir)
            
            # Create the HTTP response
            response = HTTPResponse.build(body=("text", html) if not is_head else ("empty", None), status_code=200, reason="OK", content_type="text/html" if not is_head else None)
            return response
        else:
            if uri.startswith("/"):
                uri = uri[1:]
            if uri.endswith("/"):
                uri = uri[:-1]
            index = uri.find("?")
            if index != -1:
                parameters = dict([parameter.split("=") for parameter in uri[index+1:].split("&")])
                uri = uri[:index]
            else:
                parameters = dict()
            root_dir = uri.split("/")[0]
            if not "Authorization" in http_request.get_headers():
                return HTTPResponse.build(status_code=401, reason="Unauthorized", headers={"WWW-Authenticate": "Basic realm=\"Authorization Required\""})
            auth = http_request.get_headers()["Authorization"]
            user_pass_base64 = auth.split(" ")[1]
            user_pass = base64.b64decode(user_pass_base64).decode()
            user = user_pass.split(":")[0]
            password = user_pass.split(":")[1]
            uuid = utils.get_user_by_name(user)
            if uuid is None:
                return HTTPResponse.build(status_code=401, reason="Unauthorized", headers={"WWW-Authenticate": "Basic realm=\"User not exists\""})
            verification = utils.verify_user(uuid, password)
            if not verification:
                return HTTPResponse.build(status_code=401, reason="Unauthorized", headers={"WWW-Authenticate": "Basic realm=\"Wrong password\""})
            html = utils.file_explore_html(os.getcwd() + "/data/" + uri)
        return HTTPResponse.build(status_code=404, reason="Not Found")
if __name__ == "__main__":
    server = HTTPServer()
    server.run()