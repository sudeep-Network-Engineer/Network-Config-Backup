"""
Compliance Checker — Scans device configs against YAML-defined security baselines.

This module:
  1. Loads compliance rules from a YAML baseline file
  2. Checks each device's running config against every rule
  3. Returns pass/fail results with a compliance score per device

Check types explained:
  - must_contain:     Config must have at least one line containing the pattern
  - must_not_contain: Config must NOT have any line containing the pattern
  - regex_match:      Config must have at least one line matching the regex
  - regex_no_match:   Config must NOT have any line matching the regex
"""

import re
import sys
from pathlib import Path
from typing import Optional

import yaml

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

from netbackup.utils.device_loader import get_netmiko_params
from netbackup.backup.backup_manager import CONFIG_COMMANDS


def load_baseline(baseline_path: str) -> list[dict]:
    """
    Load compliance rules from a YAML baseline file.

    Args:
        baseline_path: Path to the YAML file (e.g., 'baselines/security_baseline.yaml')

    Returns:
        List of rule dicts, each containing id, name, check_type, pattern, etc.
    """
    path = Path(baseline_path)
    if not path.exists():
        print(f"[ERROR] Baseline file not found: {baseline_path}")
        sys.exit(1)

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not data or "rules" not in data:
        print(f"[ERROR] Baseline file must have a 'rules' key.")
        sys.exit(1)

    return data["rules"]


def check_rule(config: str, rule: dict) -> dict:
    """
    Check a SINGLE rule against a device's config.

    This is the core matching logic:
      - 'must_contain':     Searches for the pattern as a substring in any line
      - 'must_not_contain': Fails if any line contains the pattern
      - 'regex_match':      Searches for a regex match in any line
      - 'regex_no_match':   Fails if any line matches the regex

    Args:
        config: The full running config as a string
        rule:   A rule dict from the baseline

    Returns:
        Dict with rule info + 'passed' (True/False) and 'detail' (explanation)
    """
    check_type = rule["check_type"]
    pattern = rule["pattern"]

    result = {
        "rule_id": rule["id"],
        "rule_name": rule["name"],
        "description": rule["description"],
        "severity": rule["severity"],
        "check_type": check_type,
        "pattern": pattern,
        "passed": False,
        "detail": "",
    }

    config_lines = config.splitlines()

    if check_type == "must_contain":
        # At least one line must contain this exact substring
        found = any(pattern in line for line in config_lines)
        result["passed"] = found
        result["detail"] = (
            f"Found '{pattern}' in config" if found
            else f"'{pattern}' NOT found in config"
        )

    elif check_type == "must_not_contain":
        # NO line should contain this substring
        found_lines = [line.strip() for line in config_lines if pattern in line]
        result["passed"] = len(found_lines) == 0
        if found_lines:
            result["detail"] = f"Found prohibited pattern in: {found_lines[0]}"
        else:
            result["detail"] = f"'{pattern}' correctly absent from config"

    elif check_type == "regex_match":
        # At least one line must match this regex
        found = any(re.search(pattern, line) for line in config_lines)
        result["passed"] = found
        result["detail"] = (
            f"Regex '{pattern}' matched" if found
            else f"Regex '{pattern}' did NOT match any line"
        )

    elif check_type == "regex_no_match":
        # NO line should match this regex
        found_lines = [line.strip() for line in config_lines if re.search(pattern, line)]
        result["passed"] = len(found_lines) == 0
        if found_lines:
            result["detail"] = f"Prohibited regex matched: {found_lines[0]}"
        else:
            result["detail"] = f"Regex '{pattern}' correctly absent"

    else:
        result["detail"] = f"Unknown check_type: {check_type}"

    return result


def check_device_compliance(
    device: dict,
    rules: list[dict],
    config: Optional[str] = None,
    backup_dir: str = "backups",
) -> dict:
    """
    Check a single device against ALL compliance rules.

    The config can come from:
      1. Passed directly (if you already have it)
      2. Read from the latest backup file
      3. Fetched live from the device via SSH

    Args:
        device:     Device dict from inventory
        rules:      List of rule dicts from the baseline
        config:     Optional pre-loaded config string
        backup_dir: Where to look for saved backups

    Returns:
        Dict with:
          - hostname: device name
          - total_rules: how many rules were checked
          - passed: how many passed
          - failed: how many failed
          - score: percentage (0-100)
          - results: list of individual rule results
          - status: 'success' or 'error'
    """
    hostname = device["hostname"]
    compliance_result = {
        "hostname": hostname,
        "total_rules": len(rules),
        "passed": 0,
        "failed": 0,
        "score": 0.0,
        "results": [],
        "status": "success",
        "error": None,
    }

    # --- Get config if not provided ---
    if config is None:
        # Try reading from latest backup first
        latest_backup = Path(backup_dir) / hostname / "latest.cfg"
        if latest_backup.exists():
            print(f"  [{hostname}] Reading from backup: {latest_backup}")
            with open(latest_backup, "r") as f:
                config = f.read()
        else:
            # Fetch live from device
            print(f"  [{hostname}] No backup found, fetching live config...")
            try:
                params = get_netmiko_params(device)
                connection = ConnectHandler(**params)
                if "enable_secret" in device:
                    connection.enable()
                command = CONFIG_COMMANDS.get(device["device_type"], "show running-config")
                config = connection.send_command(command)
                connection.disconnect()
            except (NetmikoAuthenticationException, NetmikoTimeoutException, Exception) as e:
                compliance_result["status"] = "error"
                compliance_result["error"] = str(e)
                print(f"  [{hostname}] ✗ Could not get config: {e}")
                return compliance_result

    # --- Check each rule ---
    for rule in rules:
        rule_result = check_rule(config, rule)
        compliance_result["results"].append(rule_result)

        if rule_result["passed"]:
            compliance_result["passed"] += 1
        else:
            compliance_result["failed"] += 1

    # --- Calculate score ---
    if compliance_result["total_rules"] > 0:
        compliance_result["score"] = round(
            (compliance_result["passed"] / compliance_result["total_rules"]) * 100, 1
        )

    return compliance_result


def check_all_devices(
    devices: list[dict],
    rules: list[dict],
    backup_dir: str = "backups",
) -> list[dict]:
    """
    Run compliance checks on ALL devices.

    Args:
        devices:    List of device dicts
        rules:      List of compliance rules
        backup_dir: Where to look for backups

    Returns:
        List of compliance result dicts (one per device)
    """
    print(f"\n{'='*60}")
    print(f" COMPLIANCE CHECK")
    print(f" Devices: {len(devices)} | Rules: {len(rules)}")
    print(f"{'='*60}\n")

    all_results = []
    for device in devices:
        print(f"  Checking: {device['hostname']}")
        result = check_device_compliance(device, rules, backup_dir=backup_dir)
        all_results.append(result)

        # Quick summary per device
        status_icon = "✓" if result["score"] == 100 else "✗"
        print(f"  [{device['hostname']}] {status_icon} Score: {result['score']}% "
              f"({result['passed']}/{result['total_rules']} passed)\n")

    return all_results
