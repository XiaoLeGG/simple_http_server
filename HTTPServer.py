import socket
import threading

class HTTPServer:



    def __init__(self, host="localhost", port=8080, parallel=5):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(parallel)

    def run(self):
        print(f"HTTP Server is running on {self.host}:{self.port}...")
        while True:
            conn, addr = self.socket.accept()
            threading.Thread(target=self.handle_connection, args=(conn, addr)).start()

    def handle_connection(self, conn, addr):
        print(f"Receive new connection from {addr[0]}:{addr[1]}")
        request = self.receive_request(conn)
        
        # conn.sendall(response)
        conn.close()

    def receive_request(self, conn):

        request = b""
        while True:
            data = conn.recv(1024)
            if not data:
                break
            request += data
            if data.endswith(b"\r\n\r\n"):
                break
        return request
    
if __name__ == "__main__":
    server = HTTPServer()
    server.run()