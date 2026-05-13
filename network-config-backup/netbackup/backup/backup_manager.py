"""
Backup Manager — Connect to network devices via SSH or Telnet and save their running configs.

This is the core module that:
  1. Connects to each device via SSH or Telnet using Netmiko
  2. Sends the 'show running-config' command (or equivalent)
  3. Saves the output to a file with a timestamp
  4. Organizes backups by device hostname
  5. Supports multi-threaded parallel backups for speed
  6. Detects config changes since last backup
  7. Auto-cleans old backups based on retention policy

Backup folder structure:
  backups/
  ├── core-router-1/
  │   ├── 2024-01-15_143022.cfg    ← timestamped config file
  │   ├── 2024-01-16_090015.cfg
  │   └── latest.cfg               ← always points to the most recent
  ├── core-router-2/
  │   └── ...
"""

import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from netbackup.utils.device_loader import get_netmiko_params


# Map device types to their "show config" commands
# Different vendors use different commands to display the running config
# Works for both SSH and Telnet device types
CONFIG_COMMANDS = {
    "cisco_ios": "show running-config",
    "cisco_ios_telnet": "show running-config",       # Telnet variant
    "cisco_xe": "show running-config",
    "cisco_xe_telnet": "show running-config",        # Telnet variant
    "cisco_xr": "show running-config",
    "cisco_xr_telnet": "show running-config",        # Telnet variant
    "cisco_nxos": "show running-config",
    "cisco_nxos_telnet": "show running-config",      # Telnet variant
    "juniper_junos": "show configuration | display set",
    "juniper_junos_telnet": "show configuration | display set",
    "arista_eos": "show running-config",
    "arista_eos_telnet": "show running-config",
    "hp_procurve": "show running-config",
    "hp_procurve_telnet": "show running-config",
    "dell_force10": "show running-config",
    "huawei": "display current-configuration",
    "huawei_telnet": "display current-configuration",
    "mikrotik_routeros": "/export",
}

# Default backup directory (relative to project root)
DEFAULT_BACKUP_DIR = "backups"


def backup_device(
    device: dict,
    backup_dir: str = DEFAULT_BACKUP_DIR,
) -> dict:
    """
    Backup a single device's running configuration.

    Flow:
      1. Connect to the device via SSH (Netmiko)
      2. Enter enable/privileged mode if enable_secret is set
      3. Run the appropriate 'show config' command
      4. Save the output to: backups/<hostname>/<timestamp>.cfg
      5. Also save a copy as 'latest.cfg' for easy access

    Args:
        device:     Device dict from the inventory (has hostname, host, etc.)
        backup_dir: Directory to store backups (default: 'backups/')

    Returns:
        A result dict with keys:
          - hostname: device name
          - status: 'success' or 'failed'
          - message: details about what happened
          - backup_file: path to saved file (if successful)
    """
    hostname = device["hostname"]
    result = {
        "hostname": hostname,
        "status": "failed",
        "message": "",
        "backup_file": None,
    }

    try:
        # --- Step 1: Connect via SSH or Telnet ---
        protocol = "Telnet" if "telnet" in device["device_type"] else "SSH"
        print(f"  [{hostname}] Connecting via {protocol} to {device['host']}...")
        params = get_netmiko_params(device)
        connection = ConnectHandler(**params)

        # --- Step 2: Enter enable mode if needed ---
        if "enable_secret" in device:
            connection.enable()

        # --- Step 3: Get the config ---
        device_type = device["device_type"]
        command = CONFIG_COMMANDS.get(device_type, "show running-config")
        print(f"  [{hostname}] Running: {command}")
        config = connection.send_command(command)

        # --- Step 4: Save to file ---
        # Create device-specific backup folder
        device_backup_dir = Path(backup_dir) / hostname
        device_backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp filename: 2024-01-15_143022.cfg
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_filename = f"{timestamp}.cfg"
        backup_path = device_backup_dir / backup_filename

        with open(backup_path, "w") as f:
            f.write(config)

        # --- Step 5: Save a 'latest.cfg' copy ---
        latest_path = device_backup_dir / "latest.cfg"
        with open(latest_path, "w") as f:
            f.write(config)

        # --- Disconnect ---
        connection.disconnect()

        result["status"] = "success"
        result["message"] = f"Config saved to {backup_path}"
        result["backup_file"] = str(backup_path)
        print(f"  [{hostname}] ✓ Backup saved: {backup_path}")

    except NetmikoAuthenticationException:
        result["message"] = f"Authentication failed for {hostname} ({device['host']})"
        print(f"  [{hostname}] ✗ Auth failed!")

    except NetmikoTimeoutException:
        result["message"] = f"Connection timed out for {hostname} ({device['host']})"
        print(f"  [{hostname}] ✗ Timeout!")

    except Exception as e:
        result["message"] = f"Error backing up {hostname}: {str(e)}"
        print(f"  [{hostname}] ✗ Error: {e}")

    return result


def backup_all_devices(
    devices: list[dict],
    backup_dir: str = DEFAULT_BACKUP_DIR,
) -> list[dict]:
    """
    Backup ALL devices in the inventory.

    Iterates through each device, calls backup_device(), and collects results.
    Failures on one device don't stop the others — it keeps going.

    Args:
        devices:    List of device dicts from load_devices()
        backup_dir: Directory to store backups

    Returns:
        List of result dicts (one per device)
    """
    print(f"\n{'='*60}")
    print(f" NETWORK CONFIG BACKUP")
    print(f" Devices: {len(devices)} | Backup Dir: {backup_dir}")
    print(f"{'='*60}\n")

    results = []
    for device in devices:
        result = backup_device(device, backup_dir)
        results.append(result)
        print()  # blank line between devices

    # --- Summary ---
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"{'='*60}")
    print(f" BACKUP COMPLETE: {success} succeeded, {failed} failed")
    print(f"{'='*60}\n")

    return results


def backup_all_devices_parallel(
    devices: list[dict],
    backup_dir: str = DEFAULT_BACKUP_DIR,
    max_workers: int = 5,
) -> list[dict]:
    """
    Backup ALL devices in PARALLEL using threads.

    Much faster than sequential backup — instead of backing up one device
    at a time, this runs multiple SSH/Telnet sessions simultaneously.

    Args:
        devices:     List of device dicts from load_devices()
        backup_dir:  Directory to store backups
        max_workers: Maximum number of simultaneous connections (default: 5)

    Returns:
        List of result dicts (one per device)
    """
    print(f"\n{'='*60}")
    print(f" NETWORK CONFIG BACKUP (PARALLEL)")
    print(f" Devices: {len(devices)} | Workers: {max_workers} | Backup Dir: {backup_dir}")
    print(f"{'='*60}\n")

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all backup tasks
        future_to_device = {
            executor.submit(backup_device, device, backup_dir): device
            for device in devices
        }

        # Collect results as they complete
        for future in as_completed(future_to_device):
            device = future_to_device[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    "hostname": device["hostname"],
                    "status": "failed",
                    "message": f"Thread error: {str(e)}",
                    "backup_file": None,
                })

    # --- Summary ---
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n{'='*60}")
    print(f" BACKUP COMPLETE: {success} succeeded, {failed} failed")
    print(f"{'='*60}\n")

    return results


def list_backups(backup_dir: str = DEFAULT_BACKUP_DIR, device_filter: Optional[str] = None) -> dict:
    """
    List all saved backups, organized by device.

    Scans the backup directory for .cfg files and returns them
    sorted by timestamp (newest first).

    Args:
        backup_dir:    Base backup directory
        device_filter: Optional hostname to filter

    Returns:
        Dict mapping hostname -> list of backup file paths (newest first)
    """
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        print(f"[INFO] No backups found. Directory '{backup_dir}' does not exist.")
        return {}

    all_backups = {}

    for device_dir in sorted(backup_path.iterdir()):
        if not device_dir.is_dir():
            continue

        hostname = device_dir.name

        # Apply filter if specified
        if device_filter and hostname != device_filter:
            continue

        # Get all .cfg files except 'latest.cfg'
        cfg_files = sorted(
            [f for f in device_dir.glob("*.cfg") if f.name != "latest.cfg"],
            reverse=True,  # newest first
        )

        if cfg_files:
            all_backups[hostname] = [str(f) for f in cfg_files]

    return all_backups


def detect_config_changes(
    backup_dir: str = DEFAULT_BACKUP_DIR,
    device_filter: Optional[str] = None,
) -> list[dict]:
    """
    Detect if device configs have changed between the two most recent backups.

    Compares the hash (fingerprint) of the latest backup with the previous one.
    If they differ, the config has changed — could indicate unauthorized changes.

    Args:
        backup_dir:    Base backup directory
        device_filter: Optional hostname to filter

    Returns:
        List of dicts with:
          - hostname: device name
          - changed: True/False
          - current_backup: path to latest backup
          - previous_backup: path to previous backup (or None)
          - message: human-readable description
    """
    changes = []
    backup_path = Path(backup_dir)

    if not backup_path.exists():
        return changes

    for device_dir in sorted(backup_path.iterdir()):
        if not device_dir.is_dir():
            continue

        hostname = device_dir.name
        if device_filter and hostname != device_filter:
            continue

        # Get backups sorted newest first (exclude latest.cfg)
        cfg_files = sorted(
            [f for f in device_dir.glob("*.cfg") if f.name != "latest.cfg"],
            reverse=True,
        )

        result = {
            "hostname": hostname,
            "changed": False,
            "current_backup": None,
            "previous_backup": None,
            "message": "",
        }

        if len(cfg_files) < 2:
            result["message"] = "Not enough backups to compare (need at least 2)"
            if cfg_files:
                result["current_backup"] = str(cfg_files[0])
        else:
            current = cfg_files[0]
            previous = cfg_files[1]
            result["current_backup"] = str(current)
            result["previous_backup"] = str(previous)

            # Compare file hashes
            current_hash = hashlib.md5(current.read_bytes()).hexdigest()
            previous_hash = hashlib.md5(previous.read_bytes()).hexdigest()

            if current_hash != previous_hash:
                result["changed"] = True
                result["message"] = (
                    f"CONFIG CHANGED between {previous.name} and {current.name}"
                )
            else:
                result["message"] = "No changes detected"

        changes.append(result)

    return changes


def cleanup_old_backups(
    backup_dir: str = DEFAULT_BACKUP_DIR,
    retention_days: int = 30,
    device_filter: Optional[str] = None,
) -> dict:
    """
    Delete backups older than the retention period.

    Keeps at least the 'latest.cfg' and the most recent timestamped backup
    for each device, even if they're older than the retention period.

    Args:
        backup_dir:     Base backup directory
        retention_days: Delete backups older than this many days (default: 30)
        device_filter:  Optional hostname to filter

    Returns:
        Dict with:
          - total_deleted: number of files deleted
          - total_kept: number of files kept
          - details: per-device breakdown
    """
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    backup_path = Path(backup_dir)

    summary = {
        "total_deleted": 0,
        "total_kept": 0,
        "details": [],
    }

    if not backup_path.exists():
        return summary

    for device_dir in sorted(backup_path.iterdir()):
        if not device_dir.is_dir():
            continue

        hostname = device_dir.name
        if device_filter and hostname != device_filter:
            continue

        cfg_files = sorted(
            [f for f in device_dir.glob("*.cfg") if f.name != "latest.cfg"],
            reverse=True,
        )

        deleted = []
        kept = []

        for i, f in enumerate(cfg_files):
            # Always keep the most recent backup
            if i == 0:
                kept.append(str(f))
                continue

            # Parse timestamp from filename: 2024-01-15_143022.cfg
            try:
                file_date = datetime.strptime(f.stem, "%Y-%m-%d_%H%M%S")
                if file_date < cutoff_date:
                    f.unlink()
                    deleted.append(str(f))
                else:
                    kept.append(str(f))
            except ValueError:
                kept.append(str(f))  # Keep files with non-standard names

        device_detail = {
            "hostname": hostname,
            "deleted": len(deleted),
            "kept": len(kept),
            "deleted_files": deleted,
        }
        summary["details"].append(device_detail)
        summary["total_deleted"] += len(deleted)
        summary["total_kept"] += len(kept)

        if deleted:
            print(f"  [{hostname}] Deleted {len(deleted)} old backups, kept {len(kept)}")
        else:
            print(f"  [{hostname}] No old backups to delete ({len(kept)} kept)")

    return summary
