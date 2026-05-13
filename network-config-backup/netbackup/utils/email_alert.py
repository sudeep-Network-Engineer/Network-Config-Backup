"""
Email Alerts — Send compliance reports and backup notifications via email.

Supports:
  - SMTP (Gmail, Outlook, custom mail servers)
  - HTML email with the compliance report embedded
  - Plain text summary emails
  - Configurable via YAML settings file

Setup for Gmail:
  1. Enable 2-Step Verification on your Google account
  2. Generate an App Password: https://myaccount.google.com/apppasswords
  3. Use the App Password (not your regular password) in email_settings.yaml
"""

import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from datetime import datetime

import yaml


def load_email_settings(settings_path: str = "email_settings.yaml") -> dict:
    """
    Load email configuration from a YAML file.

    Args:
        settings_path: Path to the email settings YAML file

    Returns:
        Dict with smtp_server, smtp_port, username, password, from_addr, to_addrs
    """
    path = Path(settings_path)
    if not path.exists():
        print(f"[ERROR] Email settings file not found: {settings_path}")
        print(f"  Create it with: python -m netbackup setup-email")
        sys.exit(1)

    with open(path, "r") as f:
        return yaml.safe_load(f)


def send_compliance_email(
    compliance_results: list[dict],
    settings_path: str = "email_settings.yaml",
    html_report_path: str = None,
) -> bool:
    """
    Send a compliance report summary via email.

    Args:
        compliance_results: List of compliance result dicts
        settings_path:      Path to email settings YAML
        html_report_path:   Optional path to HTML report to attach

    Returns:
        True if email sent successfully, False otherwise
    """
    settings = load_email_settings(settings_path)

    # Build email content
    total_devices = len(compliance_results)
    avg_score = sum(r["score"] for r in compliance_results) / total_devices if total_devices else 0
    fully_compliant = sum(1 for r in compliance_results if r["score"] == 100)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Subject line
    if avg_score >= 80:
        status_emoji = "OK"
    elif avg_score >= 50:
        status_emoji = "WARN"
    else:
        status_emoji = "ALERT"

    subject = f"[{status_emoji}] Network Compliance Report — {avg_score:.1f}% avg score ({timestamp})"

    # HTML body
    rows = ""
    for r in compliance_results:
        color = "#2e7d32" if r["score"] >= 80 else "#f57f17" if r["score"] >= 50 else "#c62828"
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee">{r['hostname']}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;color:{color};font-weight:bold">{r['score']}%</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{r['passed']}/{r['total_rules']}</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{r['failed']}</td>
        </tr>
        """

    html_body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;padding:20px">
        <h2 style="color:#1a237e">Network Compliance Report</h2>
        <p style="color:#666">Generated: {timestamp}</p>

        <div style="background:#f5f5f5;padding:15px;border-radius:8px;margin:15px 0">
            <strong>Summary:</strong>
            {total_devices} devices scanned |
            Average score: <strong>{avg_score:.1f}%</strong> |
            Fully compliant: {fully_compliant}/{total_devices}
        </div>

        <table style="width:100%;border-collapse:collapse">
            <tr style="background:#1a237e;color:white">
                <th style="padding:10px;text-align:left">Device</th>
                <th style="padding:10px;text-align:left">Score</th>
                <th style="padding:10px;text-align:left">Passed</th>
                <th style="padding:10px;text-align:left">Failed</th>
            </tr>
            {rows}
        </table>

        <p style="color:#999;margin-top:20px;font-size:12px">
            — Network Config Backup & Compliance Checker (Automated Report)
        </p>
    </body>
    </html>
    """

    # Plain text fallback
    text_body = f"Network Compliance Report ({timestamp})\n"
    text_body += f"Average Score: {avg_score:.1f}%\n"
    text_body += f"Devices: {total_devices} | Fully Compliant: {fully_compliant}\n\n"
    for r in compliance_results:
        text_body += f"  {r['hostname']}: {r['score']}% ({r['passed']}/{r['total_rules']} passed)\n"

    # Build email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings["from_addr"]
    msg["To"] = ", ".join(settings["to_addrs"])

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Attach HTML report file if provided
    if html_report_path and Path(html_report_path).exists():
        with open(html_report_path, "rb") as f:
            attachment = MIMEBase("application", "octet-stream")
            attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition",
                f"attachment; filename=compliance_report_{timestamp.replace(' ','_').replace(':','')}.html",
            )
            msg.attach(attachment)

    # Send email
    try:
        server = smtplib.SMTP(settings["smtp_server"], settings["smtp_port"])
        server.starttls()
        server.login(settings["username"], settings["password"])
        server.sendmail(settings["from_addr"], settings["to_addrs"], msg.as_string())
        server.quit()
        print(f"  Email sent to: {', '.join(settings['to_addrs'])}")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to send email: {e}")
        return False


def create_email_settings_template(output_path: str = "email_settings.yaml") -> None:
    """
    Create a template email_settings.yaml file.

    Args:
        output_path: Where to save the template
    """
    template = {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "your_email@gmail.com",
        "password": "your_app_password_here",
        "from_addr": "your_email@gmail.com",
        "to_addrs": [
            "recipient1@example.com",
            "recipient2@example.com",
        ],
    }

    with open(output_path, "w") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)

    print(f"  Email settings template created: {output_path}")
    print(f"  Edit it with your SMTP credentials.")
    print(f"\n  For Gmail:")
    print(f"    1. Enable 2-Step Verification")
    print(f"    2. Go to: https://myaccount.google.com/apppasswords")
    print(f"    3. Generate an App Password")
    print(f"    4. Use that password in {output_path}")
