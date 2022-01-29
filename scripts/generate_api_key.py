import hashlib
import sys
import uuid


def main():
    salt = uuid.uuid4().hex
    raw_key = uuid.uuid4().hex
    encrypted_key = hashlib.sha256(salt.encode() + raw_key.encode()).hexdigest()
    print(f"ENCRYPTION_SALT: {salt}")
    print(f"PANGEO_FORGE_API_KEY: {raw_key}")
    print(f"ADMIN_API_KEY_SHA256: {encrypted_key}")


if __name__ == "__main__":
    sys.exit(main())
