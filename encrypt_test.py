import socket
from aes_encryptor import AESEncryptor
from rsa_encryptor import RSAEncryptor
import base64


def prepare_request(method, uri, protocol, headers, body):
    data = method + " " + uri + " " + protocol + "\r\n"
    for header, value in headers.items():
        data += header + ": " + value + "\r\n"
    data += "\r\n"
    data = data.encode()
    if body:
        data += body + b"\r\n\r\n"
    return data

def send_and_receive(send_packet : bytes, conn : socket.socket, send_aes_en : AESEncryptor=None, recv_aes_en : AESEncryptor=None, debug : bool=False):
    if send_aes_en:
        if debug:
            print("Original Data:", send_packet)
        send_packet = send_aes_en.encrypt(send_packet)
        if debug:
            print("Encrypted Data:", send_packet)
    conn.sendall(send_packet)
    data = conn.recv(4096)
    if recv_aes_en:
        if debug:
            print("Encrypted Data:", data)
        data = recv_aes_en.decrypt(data)
        if debug:
            print("Decrypted Data:", data)
    data = data.split(b"\r\n\r\n")
    headers = data[0].decode("utf-8").split("\r\n")
    status_line = headers[0].split(" ")
    headers = dict([header.split(": ") for header in headers[1:]])
    body = data[1]
    if len(body) < int(headers["Content-Length"]):
        data = conn.recv(int(headers["Content-Length"]) - len(body) + len(b'\r\n\r\n'))[:-len(b'\r\n\r\n')]
        if recv_aes_en:
            if debug:
                print("Encrypted Data:", data)
            data = recv_aes_en.decrypt(data)
            if debug:
                print("Decrypted Data:", data)
        body += data
    return status_line, headers, body

rsa_en = RSAEncryptor()

conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
conn.connect(("localhost", 8080))

# send encrypt request packet
encrypt_packet = prepare_request("ENCRYPT", "/", "HTTP/1.1", {"Connection": "keep-alive", "Content-Length": str(len(rsa_en.get_public_key()))}, rsa_en.get_public_key())

# receive encrypt response by asymmetric encryption
status_line, headers, body = send_and_receive(encrypt_packet, conn)
print("==========Encrypt Response==========")
print(status_line)
for key, value in headers.items():
    print(key, value)
print()
print("Encrypted Message:", body)
# decrypt response by asymmetric encryption
encrypt_response = rsa_en.decode_content(body)
print("Decrypted Message:", encrypt_response)
aes_en = AESEncryptor(encrypt_response[:32], encrypt_response[32:])
print("Decrypted AES Key:", aes_en.get_key())
print("Decrypted AES IV:", aes_en.get_iv())
print("====================================")


# send encrypted packet by symmetric encryption
get_packet = prepare_request("GET", "/", "HTTP/1.1", {"Connection": "Keep-Alive", "Content-Length": "0"}, None)

# streamly receive encrypted response by symmetric encryption
status_line, headers, body = send_and_receive(get_packet, conn, aes_en, aes_en)
    
get_response = body.decode()
print("==========GET Response==============")
print(status_line)
for key, value in headers.items():
    print(key, value)
print()
print(get_response)
print("====================================")

get_packet = prepare_request("GET", "/test", "HTTP/1.1", {"Connection": "Keep-Alive", "Authorization": "Basic " + (base64.b64encode(b"client1:123")).strip().decode("ascii")}, None)
status_line, headers, body = send_and_receive(get_packet, conn, aes_en, aes_en)
get_response = body.decode()
print("==========GET Response==============")
print(status_line)
for key, value in headers.items():
    print(key, value)
print()
print(get_response)
print("====================================")

conn.close()