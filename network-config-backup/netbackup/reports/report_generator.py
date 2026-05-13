"""
Report Generator — Creates CLI, HTML, and CSV compliance reports.

Three output formats:
  1. CLI Report:  Pretty table printed to the terminal using PrettyTable
  2. HTML Report: Professional web page generated using Jinja2 templates
  3. CSV Report:  Export to CSV for Excel/Google Sheets analysis

All formats show the same data:
  - Overall summary (devices scanned, average score, fully compliant count)
  - Per-device breakdown with every rule's pass/fail status
"""

import csv
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from prettytable import PrettyTable
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)


def generate_cli_report(compliance_results: list[dict]) -> None:
    """
    Print a colored compliance report to the terminal.

    Output includes:
      1. A summary table (one row per device with score)
      2. Detailed tables per device (one row per rule)

    Colors:
      - Green = PASS / good score
      - Red   = FAIL / bad score
      - Yellow = medium score

    Args:
        compliance_results: List of compliance result dicts from checker.py
    """
    print(f"\n{'='*70}")
    print(f"  COMPLIANCE REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    # ---- Summary Table ----
    summary_table = PrettyTable()
    summary_table.field_names = ["Device", "Score", "Passed", "Failed", "Total Rules"]
    summary_table.align = "l"

    for result in compliance_results:
        score = result["score"]
        # Color the score based on value
        if score >= 80:
            score_str = f"{Fore.GREEN}{score}%{Style.RESET_ALL}"
        elif score >= 50:
            score_str = f"{Fore.YELLOW}{score}%{Style.RESET_ALL}"
        else:
            score_str = f"{Fore.RED}{score}%{Style.RESET_ALL}"

        summary_table.add_row([
            result["hostname"],
            score_str,
            result["passed"],
            result["failed"],
            result["total_rules"],
        ])

    print("  SUMMARY")
    print(summary_table)

    # ---- Overall Stats ----
    total_devices = len(compliance_results)
    avg_score = sum(r["score"] for r in compliance_results) / total_devices if total_devices else 0
    fully_compliant = sum(1 for r in compliance_results if r["score"] == 100)

    print(f"\n  Average Score: {avg_score:.1f}%")
    print(f"  Fully Compliant: {fully_compliant}/{total_devices} devices")

    # ---- Detailed Per-Device Tables ----
    print(f"\n{'='*70}")
    print("  DETAILED RESULTS")
    print(f"{'='*70}")

    for result in compliance_results:
        print(f"\n  --- {result['hostname']} (Score: {result['score']}%) ---\n")

        detail_table = PrettyTable()
        detail_table.field_names = ["ID", "Rule", "Severity", "Status", "Detail"]
        detail_table.align = "l"
        detail_table.max_width["Detail"] = 40  # Truncate long details

        for rule in result["results"]:
            status = (
                f"{Fore.GREEN}PASS{Style.RESET_ALL}" if rule["passed"]
                else f"{Fore.RED}FAIL{Style.RESET_ALL}"
            )
            severity_colors = {
                "critical": Fore.RED,
                "high": Fore.YELLOW,
                "medium": Fore.CYAN,
                "low": Fore.GREEN,
            }
            sev_color = severity_colors.get(rule["severity"], "")
            severity = f"{sev_color}{rule['severity'].upper()}{Style.RESET_ALL}"

            detail_table.add_row([
                rule["rule_id"],
                rule["rule_name"],
                severity,
                status,
                rule["detail"][:40],  # Truncate long details
            ])

        print(detail_table)

    print()


def generate_html_report(
    compliance_results: list[dict],
    output_path: str,
    baseline_name: str = "security_baseline.yaml",
) -> str:
    """
    Generate a professional HTML compliance report using Jinja2.

    The report includes:
      - Summary cards (devices, rules, avg score, fully compliant)
      - Per-device sections with expandable rule tables
      - Color-coded pass/fail and severity badges

    Args:
        compliance_results: List of compliance result dicts
        output_path:        Where to save the HTML file
        baseline_name:      Name of the baseline file (shown in report header)

    Returns:
        Path to the generated HTML file
    """
    # ---- Calculate summary stats ----
    total_devices = len(compliance_results)
    total_rules = compliance_results[0]["total_rules"] if compliance_results else 0
    avg_score = round(
        sum(r["score"] for r in compliance_results) / total_devices, 1
    ) if total_devices else 0
    fully_compliant = sum(1 for r in compliance_results if r["score"] == 100)

    # ---- Load Jinja2 template ----
    # Templates are in netbackup/templates/
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("report.html.j2")

    # ---- Render HTML ----
    html = template.render(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        baseline_name=baseline_name,
        total_devices=total_devices,
        total_rules=total_rules,
        avg_score=avg_score,
        fully_compliant=fully_compliant,
        devices=compliance_results,
    )

    # ---- Save to file ----
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w") as f:
        f.write(html)

    print(f"\n  HTML report saved to: {output}")
    return str(output)


def generate_csv_report(
    compliance_results: list[dict],
    output_path: str,
) -> str:
    """
    Export compliance results to a CSV file for Excel/Google Sheets.

    Creates a CSV with one row per rule per device:
      Device, Score, Rule_ID, Rule_Name, Severity, Status, Detail

    Args:
        compliance_results: List of compliance result dicts
        output_path:        Where to save the CSV file

    Returns:
        Path to the generated CSV file
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="") as f:
        writer = csv.writer(f)

        # Header row
        writer.writerow([
            "Device", "Device_Score", "Rule_ID", "Rule_Name",
            "Severity", "Status", "Check_Type", "Pattern", "Detail",
        ])

        # Data rows
        for result in compliance_results:
            for rule in result["results"]:
                writer.writerow([
                    result["hostname"],
                    f"{result['score']}%",
                    rule["rule_id"],
                    rule["rule_name"],
                    rule["severity"],
                    "PASS" if rule["passed"] else "FAIL",
                    rule["check_type"],
                    rule["pattern"],
                    rule["detail"],
                ])

        # Summary row
        writer.writerow([])
        writer.writerow(["SUMMARY"])
        writer.writerow(["Total Devices", len(compliance_results)])
        total_rules = compliance_results[0]["total_rules"] if compliance_results else 0
        writer.writerow(["Rules per Device", total_rules])
        avg_score = sum(r["score"] for r in compliance_results) / len(compliance_results) if compliance_results else 0
        writer.writerow(["Average Score", f"{avg_score:.1f}%"])
        fully_compliant = sum(1 for r in compliance_results if r["score"] == 100)
        writer.writerow(["Fully Compliant", fully_compliant])

    print(f"\n  CSV report saved to: {output}")
    return str(output)
