"""
Email notification module for apartment availability alerts.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(smtp_host, smtp_port, email_from, email_password, email_to, subject, body_html):
    """Send an email notification via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    # Plain text fallback
    plain_text = body_html.replace("<br>", "\n").replace("</li>", "\n")
    import re
    plain_text = re.sub(r"<[^>]+>", "", plain_text)

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
        server.starttls()
        server.login(email_from, email_password)
        server.sendmail(email_from, email_to.split(","), msg.as_string())


def build_availability_email(newly_free_apartments):
    """
    Build email subject and HTML body for newly available apartments.
    Returns (subject, body_html).
    """
    count = len(newly_free_apartments)
    subject = f"🏠 {count} apartment(s) now available at Campus Living Darmstadt!"

    td = "padding: 8px; border: 1px solid #ccc; text-align: left;"
    rows = ""
    for apt_id, info in sorted(newly_free_apartments.items()):
        size = info.get('size', '')
        kaltmiete = info.get('kaltmiete', '')
        nebenkosten = info.get('nebenkosten', '')
        total = info.get('total', 'N/A')
        rows += (
            f"<tr>"
            f"<td style=\"{td}\">{apt_id}</td>"
            f"<td style=\"{td}\">{info['type']}</td>"
            f"<td style=\"{td}\">{size}</td>"
            f"<td style=\"{td}\">{kaltmiete}</td>"
            f"<td style=\"{td}\">{nebenkosten}</td>"
            f"<td style=\"{td}\"><strong>{total}</strong></td>"
            f"</tr>\n"
        )

    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px;">
        <h2 style="color: #2e7d32;">Room Available at Campus Living Darmstadt!</h2>
        <p>{count} apartment(s) just became available:</p>
        <table style="border-collapse: collapse; width: 100%;">
            <tr style="background: #e8f5e9;">
                <th style="padding: 8px; border: 1px solid #ccc; text-align: left;">Apartment</th>
                <th style="padding: 8px; border: 1px solid #ccc; text-align: left;">Type</th>
                <th style="padding: 8px; border: 1px solid #ccc; text-align: left;">Size</th>
                <th style="padding: 8px; border: 1px solid #ccc; text-align: left;">Kaltmiete</th>
                <th style="padding: 8px; border: 1px solid #ccc; text-align: left;">Nebenkosten</th>
                <th style="padding: 8px; border: 1px solid #ccc; text-align: left;">Total</th>
            </tr>
            {rows}
        </table>
        <p style="margin-top: 16px;">
            <a href="https://www.campus-living-darmstadt.de/mieten"
               style="background: #2e7d32; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                View on Website
            </a>
        </p>
        <p style="color: #666; font-size: 12px; margin-top: 24px;">
            This alert was sent by Ilive Tracker.
        </p>
    </body>
    </html>
    """

    return subject, body_html


def notify_available(config, newly_free_apartments):
    """Send notification about newly available apartments."""
    if not newly_free_apartments:
        return

    subject, body_html = build_availability_email(newly_free_apartments)

    send_email(
        smtp_host=config["SMTP_HOST"],
        smtp_port=config["SMTP_PORT"],
        email_from=config["EMAIL_FROM"],
        email_password=config["EMAIL_PASSWORD"],
        email_to=config["EMAIL_TO"],
        subject=subject,
        body_html=body_html,
    )

    print(f"  Email sent to {config['EMAIL_TO']}")
