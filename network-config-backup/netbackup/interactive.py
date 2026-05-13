"""
Interactive Menu — Guided CLI menu for beginners.

Instead of remembering commands, users can navigate a numbered menu:
  1. Backup devices
  2. List backups
  3. Compliance check
  4. Config diff
  ...etc

Perfect for users who are new to CLI tools or want a quick way
to access features without reading documentation.
"""

import os
import sys

from colorama import Fore, Style, init

init(autoreset=True)


MENU_OPTIONS = [
    ("Backup Devices", "backup"),
    ("Backup Devices (Parallel)", "backup_parallel"),
    ("List Saved Backups", "list_backups"),
    ("Rollback Device Config", "rollback"),
    ("Compliance Check", "comply"),
    ("Config Diff (Compare)", "diff"),
    ("Detect Config Changes", "detect_changes"),
    ("Health Check (Ping)", "health_check"),
    ("Cleanup Old Backups", "cleanup"),
    ("Backup Statistics", "stats"),
    ("Search Configs", "search"),
    ("Network Topology Map", "topology"),
    ("Encrypt Inventory", "encrypt"),
    ("Decrypt Inventory", "decrypt"),
    ("Start Scheduled Backups", "schedule"),
    ("Launch Web Dashboard", "dashboard"),
    ("Setup Email Alerts", "setup_email"),
    ("Run Demo", "demo"),
    ("Exit", "exit"),
]


def show_banner():
    """Print the tool banner."""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   {Fore.WHITE}Network Config Backup & Compliance Checker{Fore.CYAN}            ║
║   {Fore.WHITE}v2.0 — 16+ Features | SSH & Telnet{Fore.CYAN}                   ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def show_menu():
    """Display the main menu."""
    print(f"\n  {Fore.CYAN}MAIN MENU{Style.RESET_ALL}\n")
    for i, (label, _) in enumerate(MENU_OPTIONS, 1):
        if label == "Exit":
            print(f"    {Fore.RED}{i:2}. {label}{Style.RESET_ALL}")
        else:
            print(f"    {Fore.WHITE}{i:2}. {label}{Style.RESET_ALL}")
    print()


def get_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default."""
    if default:
        user_input = input(f"  {prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"  {prompt}: ").strip()


def run_interactive():
    """Run the interactive menu loop."""
    show_banner()

    while True:
        show_menu()
        try:
            choice = input(f"  {Fore.CYAN}Select option (1-{len(MENU_OPTIONS)}): {Style.RESET_ALL}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  Goodbye!")
            break

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(MENU_OPTIONS):
            print(f"\n  {Fore.RED}Invalid option. Try again.{Style.RESET_ALL}")
            continue

        _, action = MENU_OPTIONS[int(choice) - 1]

        if action == "exit":
            print(f"\n  Goodbye!")
            break

        # Build and execute the command
        cmd = _build_command(action)
        if cmd:
            print(f"\n  {Fore.YELLOW}Running: {cmd}{Style.RESET_ALL}\n")
            os.system(cmd)
            input(f"\n  {Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")


def _build_command(action: str) -> str:
    """Build the CLI command based on user inputs."""
    base = sys.executable + " -m netbackup"

    if action == "backup":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        device = get_input("Device hostname (or Enter for all)", "")
        cmd = f'{base} backup -i {inv}'
        if device:
            cmd += f' -d {device}'
        return cmd

    elif action == "backup_parallel":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        workers = get_input("Number of threads", "5")
        return f'{base} backup -i {inv} --parallel --workers {workers}'

    elif action == "list_backups":
        device = get_input("Device hostname (or Enter for all)", "")
        cmd = f'{base} list-backups'
        if device:
            cmd += f' -d {device}'
        return cmd

    elif action == "rollback":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        device = get_input("Device hostname")
        backup_file = get_input("Backup file path")
        return f'{base} rollback -i {inv} -d {device} -f {backup_file}'

    elif action == "comply":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        baseline = get_input("Baseline file path", "baselines/security_baseline.yaml")
        html = get_input("HTML report path (or Enter to skip)", "reports_output/report.html")
        csv_path = get_input("CSV report path (or Enter to skip)", "")
        cmd = f'{base} comply -i {inv} -b {baseline}'
        if html:
            cmd += f' --html-report {html}'
        if csv_path:
            cmd += f' --csv-report {csv_path}'
        return cmd

    elif action == "diff":
        file1 = get_input("First (older) config file")
        file2 = get_input("Second (newer) config file")
        return f'{base} diff -1 {file1} -2 {file2}'

    elif action == "detect_changes":
        return f'{base} detect-changes'

    elif action == "health_check":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        return f'{base} health-check -i {inv}'

    elif action == "cleanup":
        days = get_input("Delete backups older than N days", "30")
        return f'{base} cleanup -r {days}'

    elif action == "stats":
        return f'{base} stats'

    elif action == "search":
        pattern = get_input("Search pattern (text to find in configs)")
        return f'{base} search "{pattern}"'

    elif action == "topology":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        return f'{base} topology -i {inv}'

    elif action == "encrypt":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        return f'{base} encrypt-inventory -i {inv}'

    elif action == "decrypt":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        return f'{base} decrypt-inventory -i {inv}'

    elif action == "schedule":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        interval = get_input("Backup every N hours", "6")
        return f'{base} schedule -i {inv} --interval {interval}'

    elif action == "dashboard":
        inv = get_input("Inventory file path", "inventory/devices.yaml")
        baseline = get_input("Baseline file (or Enter to skip)", "baselines/security_baseline.yaml")
        cmd = f'{base} dashboard -i {inv}'
        if baseline:
            cmd += f' -b {baseline}'
        return cmd

    elif action == "setup_email":
        return f'{base} setup-email'

    elif action == "demo":
        return f'{base} demo'

    return None
