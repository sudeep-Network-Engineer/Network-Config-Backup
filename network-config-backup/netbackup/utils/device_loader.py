"""
Device Loader — Reads device inventory from a YAML file.

This module is responsible for:
  1. Loading the YAML inventory file
  2. Validating that each device has the required fields
  3. Returning a list of device dictionaries ready for Netmiko

Each device dict can be passed directly to Netmiko's ConnectHandler().
"""

import yaml
import sys
from pathlib import Path
from typing import Optional

from netbackup.utils.crypto import decrypt_device_passwords, is_encrypted


# These fields MUST be present for every device
REQUIRED_FIELDS = ["hostname", "host", "device_type", "username", "password"]


def load_devices(inventory_path: str, device_filter: Optional[str] = None) -> list[dict]:
    """
    Load devices from a YAML inventory file.

    Args:
        inventory_path: Path to the YAML file (e.g., 'inventory/devices.yaml')
        device_filter:  Optional hostname to filter — if provided, only that
                        device is returned. Useful for single-device operations.

    Returns:
        List of device dictionaries, each containing connection details.

    Raises:
        SystemExit: If file not found, invalid YAML, or missing required fields.
    """
    path = Path(inventory_path)

    # --- Check file exists ---
    if not path.exists():
        print(f"[ERROR] Inventory file not found: {inventory_path}")
        sys.exit(1)

    # --- Parse YAML ---
    with open(path, "r") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"[ERROR] Invalid YAML in {inventory_path}: {e}")
            sys.exit(1)

    # --- Validate structure ---
    if not data or "devices" not in data:
        print(f"[ERROR] Inventory file must have a 'devices' key at the top level.")
        sys.exit(1)

    devices = data["devices"]
    if not isinstance(devices, list):
        print(f"[ERROR] 'devices' must be a list of device entries.")
        sys.exit(1)

    # --- Validate each device ---
    validated = []
    for i, device in enumerate(devices):
        missing = [f for f in REQUIRED_FIELDS if f not in device]
        if missing:
            print(f"[ERROR] Device #{i+1} is missing fields: {', '.join(missing)}")
            sys.exit(1)

        # Set defaults
        device.setdefault("port", 22)

        # Auto-decrypt encrypted passwords if encryption key exists
        has_encrypted = any(
            is_encrypted(str(device.get(f, "")))
            for f in ["password", "enable_secret"]
        )
        if has_encrypted:
            device = decrypt_device_passwords(device)

        validated.append(device)

    # --- Apply filter if provided ---
    if device_filter:
        filtered = [d for d in validated if d["hostname"] == device_filter]
        if not filtered:
            print(f"[ERROR] Device '{device_filter}' not found in inventory.")
            sys.exit(1)
        return filtered

    return validated


def get_netmiko_params(device: dict) -> dict:
    """
    Convert our device dict into Netmiko-compatible connection parameters.

    Netmiko expects specific keys like 'device_type', 'host', 'username', etc.
    Our inventory uses the same keys, but we strip out 'hostname' since
    Netmiko doesn't need it (it's our friendly name for backups/reports).

    Args:
        device: A device dictionary from load_devices()

    Returns:
        Dictionary of Netmiko connection parameters.
    """
    params = {
        "device_type": device["device_type"],
        "host": device["host"],
        "username": device["username"],
        "password": device["password"],
        "port": device.get("port", 22),
    }

    # Only add enable_secret if provided (not all devices need it)
    if "enable_secret" in device:
        params["secret"] = device["enable_secret"]

    return params
