import os, base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import json

def encrypt_dict(data: dict, key: str, associated_data: bytes = b"") -> str:
    aesgcm = AESGCM(bytes.fromhex(key))
    plaintext = json.dumps(data)
    nonce = os.urandom(12)  # GCM 표준: 12 bytes 권장
    ct = aesgcm.encrypt(nonce, plaintext.encode(), associated_data)  # ct에 태그가 포함됨
    return base64.b64encode(nonce + ct).decode()  # nonce||ciphertext 태그를 합쳐서 반환

def decrypt_dict(token_b64: str, key: str, associated_data: bytes = b"") -> dict:
    aesgcm = AESGCM(bytes.fromhex(key))
    data = base64.b64decode(token_b64)
    nonce, ct = data[:12], data[12:]
    return json.loads(aesgcm.decrypt(nonce, ct, associated_data).decode())