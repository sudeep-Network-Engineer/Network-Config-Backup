"""
Config Diff — Compare two configuration backups side-by-side.

This module lets you:
  1. Compare any two backup files for the same device
  2. See exactly which lines were added, removed, or changed
  3. Generate a colored CLI diff or an HTML diff report

Use cases:
  - "What changed on this router between yesterday and today?"
  - "Before I rollback, let me see what's different"
  - "Someone made changes — show me what they did"
"""

import difflib
from pathlib import Path
from datetime import datetime

from colorama import Fore, Style, init

init(autoreset=True)


def diff_configs(
    file1: str,
    file2: str,
    context_lines: int = 3,
) -> dict:
    """
    Compare two config files and return the differences.

    Uses Python's difflib to produce a unified diff — the same format
    you see in 'git diff'. Lines prefixed with:
      + (green)  = added in file2
      - (red)    = removed from file1
      (no prefix) = unchanged (context)

    Args:
        file1:         Path to the older/first config file
        file2:         Path to the newer/second config file
        context_lines: How many unchanged lines to show around changes

    Returns:
        Dict with:
          - file1, file2: paths
          - has_changes: True if configs differ
          - added_lines: count of added lines
          - removed_lines: count of removed lines
          - diff_lines: list of diff strings (for CLI display)
          - html_diff: HTML table diff (for HTML display)
    """
    path1 = Path(file1)
    path2 = Path(file2)

    result = {
        "file1": file1,
        "file2": file2,
        "has_changes": False,
        "added_lines": 0,
        "removed_lines": 0,
        "diff_lines": [],
        "html_diff": "",
    }

    # Read both files
    if not path1.exists():
        result["diff_lines"] = [f"ERROR: File not found: {file1}"]
        return result
    if not path2.exists():
        result["diff_lines"] = [f"ERROR: File not found: {file2}"]
        return result

    lines1 = path1.read_text().splitlines()
    lines2 = path2.read_text().splitlines()

    # Generate unified diff
    diff = list(difflib.unified_diff(
        lines1, lines2,
        fromfile=path1.name,
        tofile=path2.name,
        lineterm="",
        n=context_lines,
    ))

    result["diff_lines"] = diff
    result["has_changes"] = len(diff) > 0
    result["added_lines"] = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    result["removed_lines"] = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    # Generate HTML side-by-side diff
    html_differ = difflib.HtmlDiff(wrapcolumn=80)
    result["html_diff"] = html_differ.make_file(
        lines1, lines2,
        fromdesc=path1.name,
        todesc=path2.name,
    )

    return result


def print_diff(diff_result: dict) -> None:
    """
    Print a colored diff to the terminal.

    Colors:
      - Red:   lines removed (prefixed with -)
      - Green: lines added (prefixed with +)
      - Cyan:  section headers (prefixed with @@)
      - White: context lines (unchanged)

    Args:
        diff_result: Dict from diff_configs()
    """
    if not diff_result["has_changes"]:
        print(f"\n  No differences found between the files.")
        return

    print(f"\n{'='*70}")
    print(f"  CONFIG DIFF")
    print(f"  Old: {diff_result['file1']}")
    print(f"  New: {diff_result['file2']}")
    print(f"  Changes: +{diff_result['added_lines']} added, "
          f"-{diff_result['removed_lines']} removed")
    print(f"{'='*70}\n")

    for line in diff_result["diff_lines"]:
        if line.startswith("+++") or line.startswith("---"):
            print(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
        elif line.startswith("+"):
            print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
        elif line.startswith("-"):
            print(f"{Fore.RED}{line}{Style.RESET_ALL}")
        elif line.startswith("@@"):
            print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
        else:
            print(f"  {line}")

    print()


def save_html_diff(diff_result: dict, output_path: str) -> str:
    """
    Save the HTML diff to a file.

    Args:
        diff_result: Dict from diff_configs()
        output_path: Where to save the HTML file

    Returns:
        Path to the saved HTML file
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w") as f:
        f.write(diff_result["html_diff"])

    print(f"  HTML diff saved to: {output}")
    return str(output)
