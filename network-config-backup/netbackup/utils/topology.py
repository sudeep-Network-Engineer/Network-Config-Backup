"""
Network Topology Map — Generate a visual text-based network diagram.

Creates an ASCII art topology map from your device inventory,
grouping devices by type and showing their connections.

This is purely a visual representation of your inventory —
it doesn't discover real physical connections.

Impressive for demos and interviews — shows you think about
network visualization, not just automation.
"""

from pathlib import Path
from typing import Optional
from collections import defaultdict

from colorama import Fore, Style, init

init(autoreset=True)


# Device type categories for grouping
DEVICE_CATEGORIES = {
    "Router": ["cisco_ios", "cisco_xe", "cisco_xr", "cisco_ios_telnet",
               "cisco_xe_telnet", "cisco_xr_telnet", "juniper_junos",
               "juniper_junos_telnet", "mikrotik_routeros"],
    "Switch": ["cisco_nxos", "cisco_nxos_telnet", "arista_eos",
               "arista_eos_telnet", "hp_procurve", "hp_procurve_telnet",
               "dell_force10"],
    "Firewall": ["paloalto_panos", "fortinet"],
    "Other": ["huawei", "huawei_telnet"],
}


def _categorize_device(device_type: str) -> str:
    """Get the category for a device type."""
    for category, types in DEVICE_CATEGORIES.items():
        if device_type in types:
            return category
    # Infer from naming
    dt = device_type.lower()
    if "switch" in dt or "nxos" in dt or "eos" in dt:
        return "Switch"
    if "fw" in dt or "firewall" in dt or "panos" in dt:
        return "Firewall"
    return "Router"


def _get_protocol(device: dict) -> str:
    """Get connection protocol."""
    return "Telnet" if "telnet" in device.get("device_type", "") else "SSH"


def generate_topology(
    devices: list[dict],
    backup_dir: str = "backups",
) -> str:
    """
    Generate an ASCII topology map from device inventory.

    Groups devices by category (Router, Switch, Firewall, Other)
    and shows them in a visual network diagram.

    Args:
        devices:    List of device dicts from inventory
        backup_dir: Backup directory (to check backup status)

    Returns:
        String containing the ASCII topology map
    """
    # Group devices by category
    groups = defaultdict(list)
    for device in devices:
        category = _categorize_device(device["device_type"])
        groups[category].append(device)

    # Check backup status
    backup_path = Path(backup_dir)

    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append(" NETWORK TOPOLOGY MAP")
    lines.append(f" Devices: {len(devices)} | Generated from inventory")
    lines.append("=" * 70)
    lines.append("")

    # Management station at the top
    lines.append("                    ┌──────────────────────┐")
    lines.append("                    │   Management PC      │")
    lines.append("                    │   (This Tool)        │")
    lines.append("                    └──────────┬───────────┘")
    lines.append("                               │")
    lines.append("                    SSH / Telnet Connections")
    lines.append("                               │")

    # Draw each category
    category_order = ["Router", "Switch", "Firewall", "Other"]

    for category in category_order:
        if category not in groups:
            continue

        cat_devices = groups[category]
        lines.append("          ┌─────────────────────────────────────────┐")
        lines.append(f"          │  {category.upper() + 'S':<39} │")
        lines.append("          ├─────────────────────────────────────────┤")

        for device in cat_devices:
            hostname = device["hostname"]
            host = device["host"]
            protocol = _get_protocol(device)
            port = device.get("port", 22)

            # Check if has backup
            has_backup = (backup_path / hostname / "latest.cfg").exists()
            backup_status = "backed-up" if has_backup else "no-backup"

            line = f"  {hostname:<20} {host:<16} {protocol}:{port}"
            padded = f"          │  {line:<39} │"
            lines.append(padded)

        lines.append("          └─────────────────────────────────────────┘")
        lines.append("                               │")

    # Footer
    lines.append("")
    lines.append("  Legend:")
    lines.append("    SSH  = Secure Shell (port 22)")
    lines.append("    Telnet = Telnet (port 23)")
    lines.append("")

    return "\n".join(lines)


def print_topology(devices: list[dict], backup_dir: str = "backups") -> None:
    """
    Print the topology map with colors.

    Args:
        devices:    List of device dicts
        backup_dir: Backup directory
    """
    topo = generate_topology(devices, backup_dir)

    # Add colors
    for line in topo.split("\n"):
        if "TOPOLOGY MAP" in line or "=" * 10 in line:
            print(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
        elif "Management PC" in line or "This Tool" in line:
            print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
        elif "ROUTERS" in line or "SWITCHES" in line or "FIREWALLS" in line or "OTHERS" in line:
            print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
        elif "SSH" in line and ":" in line and "Legend" not in line:
            print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
        elif "Telnet" in line and ":" in line and "Legend" not in line:
            print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
        elif "┌" in line or "└" in line or "├" in line or "│" in line:
            print(f"{Fore.BLUE}{line}{Style.RESET_ALL}")
        else:
            print(line)
