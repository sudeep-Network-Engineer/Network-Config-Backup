"""
Device Health Check — Test reachability of network devices before operations.

Performs two checks per device:
  1. Ping test — Is the device reachable on the network?
  2. Port test — Is SSH (22) or Telnet (23) port open?

Use this before backup or compliance operations to quickly identify
which devices are online and accessible, saving time on connection timeouts.
"""

import socket
import subprocess
import platform
from datetime import datetime
from typing import Optional

from colorama import Fore, Style, init

init(autoreset=True)


def ping_device(host: str, timeout: int = 3) -> bool:
    """
    Ping a device to check basic network reachability.

    Args:
        host:    IP address or hostname
        timeout: Seconds to wait for response

    Returns:
        True if ping succeeds, False otherwise
    """
    # Different ping flags for Windows vs Linux/Mac
    param = "-n" if platform.system().lower() == "windows" else "-c"
    timeout_flag = "-w" if platform.system().lower() == "windows" else "-W"

    try:
        result = subprocess.run(
            ["ping", param, "1", timeout_flag, str(timeout), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_port(host: str, port: int = 22, timeout: int = 3) -> bool:
    """
    Check if a specific port (SSH/Telnet) is open on a device.

    Args:
        host:    IP address or hostname
        port:    Port number (22 for SSH, 23 for Telnet)
        timeout: Seconds to wait for connection

    Returns:
        True if port is open, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (socket.error, OSError):
        return False


def health_check_device(device: dict, timeout: int = 3) -> dict:
    """
    Run a full health check on a single device.

    Checks:
      1. Ping — basic network reachability
      2. Port — SSH or Telnet port open

    Args:
        device:  Device dict from inventory
        timeout: Seconds to wait per check

    Returns:
        Dict with hostname, ping_ok, port_ok, port, status, message
    """
    hostname = device["hostname"]
    host = device["host"]
    port = device.get("port", 22)
    protocol = "Telnet" if "telnet" in device.get("device_type", "") else "SSH"

    result = {
        "hostname": hostname,
        "host": host,
        "port": port,
        "protocol": protocol,
        "ping_ok": False,
        "port_ok": False,
        "status": "unreachable",
        "message": "",
    }

    # Step 1: Ping
    result["ping_ok"] = ping_device(host, timeout)

    # Step 2: Port check
    if result["ping_ok"]:
        result["port_ok"] = check_port(host, port, timeout)

    # Determine status
    if result["ping_ok"] and result["port_ok"]:
        result["status"] = "healthy"
        result["message"] = f"Ping OK, {protocol} port {port} open"
    elif result["ping_ok"] and not result["port_ok"]:
        result["status"] = "port_closed"
        result["message"] = f"Ping OK, but {protocol} port {port} closed"
    else:
        result["status"] = "unreachable"
        result["message"] = f"Device unreachable (ping failed)"

    return result


def health_check_all(
    devices: list[dict],
    timeout: int = 3,
) -> list[dict]:
    """
    Run health checks on ALL devices.

    Args:
        devices: List of device dicts from inventory
        timeout: Seconds to wait per check

    Returns:
        List of health check result dicts
    """
    print(f"\n{'='*60}")
    print(f" DEVICE HEALTH CHECK")
    print(f" Devices: {len(devices)} | Timeout: {timeout}s")
    print(f"{'='*60}\n")

    results = []
    for device in devices:
        result = health_check_device(device, timeout)
        results.append(result)

        # Print status with color
        if result["status"] == "healthy":
            icon = f"{Fore.GREEN}HEALTHY{Style.RESET_ALL}"
        elif result["status"] == "port_closed":
            icon = f"{Fore.YELLOW}PORT CLOSED{Style.RESET_ALL}"
        else:
            icon = f"{Fore.RED}UNREACHABLE{Style.RESET_ALL}"

        print(f"  [{result['hostname']}] {icon} — {result['message']}")

    # Summary
    healthy = sum(1 for r in results if r["status"] == "healthy")
    print(f"\n{'='*60}")
    print(f" HEALTH CHECK COMPLETE: {healthy}/{len(results)} devices healthy")
    print(f"{'='*60}\n")

    return results
