
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os

class AESEncryptor:

    def __init__(self, key : bytes=None, iv : bytes=None):
        if key:
            self.key = key
        else:
            self.key = os.urandom(32)
        if iv:
            self.iv = iv
        else:
            self.iv = os.urandom(16)
        self.cipher = Cipher(
            algorithms.AES(self.key),
            modes.CFB(self.iv),
            backend=default_backend()
        )

    def get_key(self) -> bytes:
        return self.key
    
    def get_iv(self) -> bytes:
        return self.iv
    
    def encrypt(self, content : bytes) -> bytes:
        encryptor = self.cipher.encryptor()
        return encryptor.update(content)
    
    def encrypt_finallize(self):
        encryptor = self.cipher.encryptor()
        return encryptor.finalize()
    
    def decrypt(self, content : bytes) -> bytes:
        decryptor = self.cipher.decryptor()
        return decryptor.update(content)

    def decrypt_finallize(self):
        decryptor = self.cipher.decryptor()
        return decryptor.finalize()
    
    def get_cipher(self) -> Cipher:
        return self.cipher