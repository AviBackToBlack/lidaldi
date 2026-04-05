#!/usr/bin/env python3
"""
Generate VAPID key pair for Web Push notifications.

Usage:
    python generate_vapid_keys.py [output_directory]

Generates:
    - vapid_private.pem  (private key, chmod 600)
    - Prints the public key in base64url format for config.py
"""

import base64
import os
import sys

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

    # Save private key as PEM
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pem_path = os.path.join(out_dir, "vapid_private.pem")
    with open(pem_path, "wb") as f:
        f.write(pem)
    try:
        os.chmod(pem_path, 0o600)
    except OSError:
        pass  # Windows doesn't support Unix permissions

    # Public key in uncompressed point format, base64url-encoded (no padding)
    pub_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

    print(f"Private key saved to: {pem_path}")
    print(f"\nPublic key (put this in config.py as VAPID_PUBLIC_KEY):\n{pub_b64}")


if __name__ == "__main__":
    main()
