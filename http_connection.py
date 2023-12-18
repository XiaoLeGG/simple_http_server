import socket
from aes_encryptor import AESEncryptor

class HTTPConnection:

    def __init__(self, conn : socket.socket, encryptor : AESEncryptor=None):
        self.conn = conn
        self.encryptor = encryptor
        
    def recv(self, size : int) -> bytes:
        data = self.conn.recv(size)
        if self.encryptor:
            data = self.encryptor.decrypt(data)
        return data
    
    def get_conn(self) -> socket.socket:
        return self.conn
    
    def getpeername(self):
        return self.conn.getpeername()
    
    def sendall(self, data : bytes):
        if self.encryptor:
            data = self.encryptor.encrypt(data)
        self.conn.sendall(data)

    def settimeout(self, timeout : float):
        self.conn.settimeout(timeout)

    def close(self):
        self.conn.close()

    def set_encryptor(self, encryptor : AESEncryptor):
        self.encryptor = encryptor
    