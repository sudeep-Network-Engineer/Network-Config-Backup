"""
Config Search — Search across all device backup configs for a specific pattern.

Use cases:
  - "Which devices have SNMP community 'public'?"     → search "snmp-server community public"
  - "Which devices have Telnet enabled?"               → search "transport input telnet"
  - "Which devices use NTP server 10.0.0.50?"          → search "ntp server 10.0.0.50"
  - "Which devices have a specific ACL?"               → search "access-list 101"

Searches the latest.cfg backup for each device, showing matching lines
with context and device hostname.
"""

import re
from pathlib import Path

from colorama import Fore, Style, init

init(autoreset=True)


def search_configs(
    pattern: str,
    backup_dir: str = "backups",
    device_filter: str = None,
    regex: bool = False,
    context_lines: int = 0,
) -> list[dict]:
    """
    Search all device configs for a pattern.

    Args:
        pattern:        Text or regex pattern to search for
        backup_dir:     Backup directory
        device_filter:  Optional device hostname to limit search
        regex:          If True, treat pattern as a regex
        context_lines:  Number of lines to show before/after each match

    Returns:
        List of dicts with hostname, file, matches (list of matching lines)
    """
    backup_path = Path(backup_dir)
    results = []

    if not backup_path.exists():
        return results

    for device_dir in sorted(backup_path.iterdir()):
        if not device_dir.is_dir():
            continue

        hostname = device_dir.name

        if device_filter and hostname != device_filter:
            continue

        # Use latest.cfg for search
        latest = device_dir / "latest.cfg"
        if not latest.exists():
            # Try most recent .cfg file
            cfg_files = sorted(device_dir.glob("*.cfg"), key=lambda f: f.stat().st_mtime)
            if not cfg_files:
                continue
            latest = cfg_files[-1]

        lines = latest.read_text().splitlines()
        device_matches = []

        for i, line in enumerate(lines):
            matched = False
            if regex:
                if re.search(pattern, line, re.IGNORECASE):
                    matched = True
            else:
                if pattern.lower() in line.lower():
                    matched = True

            if matched:
                match_entry = {
                    "line_number": i + 1,
                    "line": line.strip(),
                    "context_before": [],
                    "context_after": [],
                }

                # Add context lines
                if context_lines > 0:
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    match_entry["context_before"] = [
                        lines[j].strip() for j in range(start, i)
                    ]
                    match_entry["context_after"] = [
                        lines[j].strip() for j in range(i + 1, end)
                    ]

                device_matches.append(match_entry)

        if device_matches:
            results.append({
                "hostname": hostname,
                "file": str(latest),
                "match_count": len(device_matches),
                "matches": device_matches,
            })

    return results


def print_search_results(results: list[dict], pattern: str) -> None:
    """
    Print search results with colored output.

    Args:
        results: List from search_configs()
        pattern: The search pattern (for display)
    """
    total_matches = sum(r["match_count"] for r in results)
    total_devices = len(results)

    print(f"\n{'='*60}")
    print(f" CONFIG SEARCH RESULTS")
    print(f" Pattern: \"{pattern}\"")
    print(f" Found: {total_matches} matches across {total_devices} devices")
    print(f"{'='*60}\n")

    if not results:
        print(f"  No matches found for \"{pattern}\"")
        return

    for result in results:
        print(f"  {Fore.CYAN}{result['hostname']}{Style.RESET_ALL} "
              f"({result['match_count']} matches)")

        for match in result["matches"]:
            # Context before
            for ctx in match.get("context_before", []):
                print(f"    {Fore.WHITE}  {ctx}{Style.RESET_ALL}")

            # Matching line (highlighted)
            print(f"    {Fore.GREEN}> Line {match['line_number']}: "
                  f"{match['line']}{Style.RESET_ALL}")

            # Context after
            for ctx in match.get("context_after", []):
                print(f"    {Fore.WHITE}  {ctx}{Style.RESET_ALL}")

            if match.get("context_before") or match.get("context_after"):
                print()

        print()
