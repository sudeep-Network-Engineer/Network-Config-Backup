"""
Rollback Module — Push a previously saved config back to a network device.

Use case: You backed up a router's config, someone made bad changes,
and now you want to restore the old config.

How it works:
  1. Read the saved backup file (.cfg)
  2. Connect to the device via SSH
  3. Push the config line-by-line using Netmiko's send_config_set()
  4. Optionally save to startup-config so it persists across reboots

WARNING: Rollback replaces the running config. Use with caution!
"""

from pathlib import Path

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from netbackup.utils.device_loader import get_netmiko_params


# Commands to save config to startup (so it survives a reboot)
SAVE_COMMANDS = {
    "cisco_ios": "write memory",
    "cisco_xe": "write memory",
    "cisco_xr": "commit",
    "cisco_nxos": "copy running-config startup-config",
    "juniper_junos": "commit",
    "arista_eos": "write memory",
}


def rollback_device(
    device: dict,
    backup_file: str,
    save_config: bool = True,
) -> dict:
    """
    Rollback a device to a previously saved configuration.

    Flow:
      1. Read the backup .cfg file
      2. Parse it into individual config lines
      3. SSH into the device
      4. Push all config lines via Netmiko's send_config_set()
      5. Optionally save to startup-config

    Args:
        device:      Device dict from inventory
        backup_file: Path to the .cfg backup file to restore
        save_config: If True, save config to startup after rollback

    Returns:
        Result dict with status and message
    """
    hostname = device["hostname"]
    result = {
        "hostname": hostname,
        "status": "failed",
        "message": "",
    }

    # --- Step 1: Read the backup file ---
    backup_path = Path(backup_file)
    if not backup_path.exists():
        result["message"] = f"Backup file not found: {backup_file}"
        print(f"  [{hostname}] ✗ File not found: {backup_file}")
        return result

    with open(backup_path, "r") as f:
        config_text = f.read()

    # --- Step 2: Parse config lines ---
    # Filter out comments, empty lines, and non-config lines
    config_lines = []
    for line in config_text.splitlines():
        stripped = line.strip()
        # Skip common non-config lines
        if not stripped:
            continue
        if stripped.startswith("!"):  # Cisco comment lines
            continue
        if stripped.startswith("Building configuration"):
            continue
        if stripped.startswith("Current configuration"):
            continue
        if stripped == "end":
            continue
        config_lines.append(line)  # Keep original indentation

    if not config_lines:
        result["message"] = "Backup file is empty or has no valid config lines."
        print(f"  [{hostname}] ✗ No config lines found in backup file")
        return result

    print(f"  [{hostname}] Loaded {len(config_lines)} config lines from {backup_file}")

    try:
        # --- Step 3: Connect via SSH ---
        print(f"  [{hostname}] Connecting to {device['host']}...")
        params = get_netmiko_params(device)
        connection = ConnectHandler(**params)

        # Enter enable mode if needed
        if "enable_secret" in device:
            connection.enable()

        # --- Step 4: Push config ---
        print(f"  [{hostname}] Pushing config ({len(config_lines)} lines)...")
        output = connection.send_config_set(
            config_lines,
            exit_config_mode=True,  # exit config mode after pushing
        )
        print(f"  [{hostname}] Config pushed successfully")

        # --- Step 5: Save config ---
        if save_config:
            device_type = device["device_type"]
            save_cmd = SAVE_COMMANDS.get(device_type, "write memory")
            print(f"  [{hostname}] Saving config: {save_cmd}")
            connection.send_command(save_cmd)

        connection.disconnect()

        result["status"] = "success"
        result["message"] = (
            f"Rollback complete. {len(config_lines)} lines pushed to {hostname}."
        )
        print(f"  [{hostname}] ✓ Rollback successful!")

    except NetmikoAuthenticationException:
        result["message"] = f"Authentication failed for {hostname}"
        print(f"  [{hostname}] ✗ Auth failed!")

    except NetmikoTimeoutException:
        result["message"] = f"Connection timed out for {hostname}"
        print(f"  [{hostname}] ✗ Timeout!")

    except Exception as e:
        result["message"] = f"Rollback error for {hostname}: {str(e)}"
        print(f"  [{hostname}] ✗ Error: {e}")

    return result
