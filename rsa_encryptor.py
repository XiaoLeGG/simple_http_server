from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes


class RSAEncryptor:

    def __init__(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self.public_key = self.private_key.public_key()

    def get_public_key(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def decode_content(self, content : bytes) -> bytes:
        return self.private_key.decrypt(
            content,
            padding.PKCS1v15()
        )
    
    @staticmethod
    def encrypt(content : bytes, public_key : bytes) -> bytes:
        public_key = serialization.load_pem_public_key(
            public_key,
            backend=None
        )
        
        return public_key.encrypt(
            content,
            padding.PKCS1v15()
        )