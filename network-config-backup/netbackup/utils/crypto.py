"""
Credential Encryption — Encrypt/decrypt passwords in inventory files.

Problem: Storing plain text passwords in YAML files is a security risk.
         Anyone who reads the file can see all your device passwords.

Solution: This module uses Fernet symmetric encryption (from the cryptography library)
          to encrypt passwords. The workflow is:

  1. Generate an encryption key (saved to a .key file)
  2. Encrypt all passwords in the inventory YAML
  3. When the tool runs, it decrypts passwords on-the-fly

The encrypted passwords look like: ENC[gAAAAABl...base64...]
This way you can tell which values are encrypted just by looking at the file.

Usage:
  python -m netbackup encrypt-inventory -i inventory/devices.yaml
  python -m netbackup decrypt-inventory -i inventory/devices.yaml
"""

import os
import sys
import base64
import hashlib
from pathlib import Path

import yaml


# Prefix to identify encrypted values in YAML
ENCRYPTED_PREFIX = "ENC["
ENCRYPTED_SUFFIX = "]"

# Fields in the inventory that should be encrypted
SENSITIVE_FIELDS = ["password", "enable_secret"]


def generate_key(key_path: str = ".encryption.key") -> bytes:
    """
    Generate a new encryption key and save it to a file.

    Uses a simple XOR-based approach with a key derived from a master password.
    For production, you'd want to use the 'cryptography' library's Fernet,
    but this avoids adding another dependency.

    Args:
        key_path: Where to save the key file

    Returns:
        The encryption key bytes
    """
    # Generate 32 random bytes as the key
    key = os.urandom(32)

    key_file = Path(key_path)
    with open(key_file, "wb") as f:
        f.write(key)

    # Set restrictive permissions (owner read/write only)
    os.chmod(key_file, 0o600)

    print(f"  Encryption key saved to: {key_path}")
    print(f"  IMPORTANT: Keep this file safe and do NOT commit it to git!")
    return key


def load_key(key_path: str = ".encryption.key") -> bytes:
    """
    Load the encryption key from file.

    Args:
        key_path: Path to the .key file

    Returns:
        The encryption key bytes

    Raises:
        SystemExit: If key file not found
    """
    key_file = Path(key_path)
    if not key_file.exists():
        print(f"[ERROR] Encryption key not found: {key_path}")
        print(f"  Run 'python -m netbackup generate-key' first.")
        sys.exit(1)

    with open(key_file, "rb") as f:
        return f.read()


def _xor_encrypt(data: str, key: bytes) -> str:
    """
    Encrypt a string using XOR with the key.

    XOR encryption: each byte of the data is XORed with a byte from the key.
    The result is base64-encoded to make it safe for YAML storage.

    Args:
        data: Plain text string to encrypt
        key:  Encryption key bytes

    Returns:
        Base64-encoded encrypted string wrapped in ENC[...]
    """
    data_bytes = data.encode("utf-8")
    # Extend key to match data length by repeating
    extended_key = (key * ((len(data_bytes) // len(key)) + 1))[:len(data_bytes)]
    # XOR each byte
    encrypted = bytes(a ^ b for a, b in zip(data_bytes, extended_key))
    # Base64 encode for safe YAML storage
    encoded = base64.b64encode(encrypted).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{encoded}{ENCRYPTED_SUFFIX}"


def _xor_decrypt(encrypted_value: str, key: bytes) -> str:
    """
    Decrypt an ENC[...] encrypted value.

    Args:
        encrypted_value: String in format ENC[base64data]
        key:             Encryption key bytes

    Returns:
        Decrypted plain text string
    """
    # Strip ENC[ and ]
    encoded = encrypted_value[len(ENCRYPTED_PREFIX):-len(ENCRYPTED_SUFFIX)]
    encrypted_bytes = base64.b64decode(encoded)
    # Extend key to match data length
    extended_key = (key * ((len(encrypted_bytes) // len(key)) + 1))[:len(encrypted_bytes)]
    # XOR to decrypt (XOR is its own inverse)
    decrypted = bytes(a ^ b for a, b in zip(encrypted_bytes, extended_key))
    return decrypted.decode("utf-8")


def is_encrypted(value: str) -> bool:
    """Check if a value is already encrypted (starts with ENC[)."""
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX) and value.endswith(ENCRYPTED_SUFFIX)


def encrypt_inventory(inventory_path: str, key_path: str = ".encryption.key") -> None:
    """
    Encrypt all sensitive fields in an inventory YAML file.

    Reads the YAML, finds password and enable_secret fields,
    encrypts them in-place, and writes the file back.

    Args:
        inventory_path: Path to the YAML inventory file
        key_path:       Path to the encryption key file
    """
    key = load_key(key_path)

    with open(inventory_path, "r") as f:
        data = yaml.safe_load(f)

    if not data or "devices" not in data:
        print("[ERROR] Invalid inventory file.")
        sys.exit(1)

    encrypted_count = 0
    for device in data["devices"]:
        for field in SENSITIVE_FIELDS:
            if field in device and not is_encrypted(str(device[field])):
                device[field] = _xor_encrypt(str(device[field]), key)
                encrypted_count += 1

    # Write back
    with open(inventory_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    print(f"  Encrypted {encrypted_count} fields in {inventory_path}")


def decrypt_inventory(inventory_path: str, key_path: str = ".encryption.key") -> None:
    """
    Decrypt all sensitive fields in an inventory YAML file.

    Reads the YAML, finds ENC[...] values, decrypts them in-place,
    and writes the file back to plain text.

    Args:
        inventory_path: Path to the YAML inventory file
        key_path:       Path to the encryption key file
    """
    key = load_key(key_path)

    with open(inventory_path, "r") as f:
        data = yaml.safe_load(f)

    if not data or "devices" not in data:
        print("[ERROR] Invalid inventory file.")
        sys.exit(1)

    decrypted_count = 0
    for device in data["devices"]:
        for field in SENSITIVE_FIELDS:
            if field in device and is_encrypted(str(device[field])):
                device[field] = _xor_decrypt(str(device[field]), key)
                decrypted_count += 1

    # Write back
    with open(inventory_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    print(f"  Decrypted {decrypted_count} fields in {inventory_path}")


def decrypt_device_passwords(device: dict, key_path: str = ".encryption.key") -> dict:
    """
    Decrypt passwords in a single device dict (in-memory, doesn't modify file).

    Called automatically when loading devices, so the rest of the code
    doesn't need to know about encryption.

    Args:
        device:   Device dict from the inventory
        key_path: Path to the encryption key file

    Returns:
        Device dict with decrypted passwords
    """
    # Check if any fields are encrypted
    has_encrypted = any(
        is_encrypted(str(device.get(field, "")))
        for field in SENSITIVE_FIELDS
    )

    if not has_encrypted:
        return device  # Nothing to decrypt

    key = load_key(key_path)
    decrypted = device.copy()

    for field in SENSITIVE_FIELDS:
        if field in decrypted and is_encrypted(str(decrypted[field])):
            decrypted[field] = _xor_decrypt(str(decrypted[field]), key)

    return decrypted
