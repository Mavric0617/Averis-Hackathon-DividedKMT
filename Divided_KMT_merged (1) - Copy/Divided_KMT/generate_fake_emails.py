"""
generate_fake_emails.py
========================
Creates a folder of REAL .eml email files that simulate a shipping-ops
inbox (7 demo emails covering every scenario the checker needs).

Each file is a genuine RFC 822 email message -- exactly the same format
you'd get back from a real mail server over IMAP. That means
email_module.py (the "receiving" module) can read these fake emails
using the *exact same code path* it would use for a real mailbox --
there is no hardcoded email content living inside the receiving module
anymore.

Run this file once (or whenever you want to regenerate the demo data):
    python generate_fake_emails.py

It creates a ./fake_inbox/ folder containing 001.eml ... 007.eml
"""

import os
from email.message import EmailMessage
from email.utils import formatdate

OUTPUT_DIR = "fake_inbox"


def _build_email(sender: str, subject: str, body: str, attachments: dict | None = None) -> EmailMessage:
    """
    Build one real email.message.EmailMessage object.
    attachments: dict of {filename: text_content}, or None for no attachment.
    """
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "ops-inbox@company.com"
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body)

    if attachments:
        for filename, content in attachments.items():
            msg.add_attachment(
                content.encode("utf-8"),
                maintype="text",
                subtype="plain",
                filename=filename,
            )
    return msg


def generate_fake_inbox() -> None:
    """
    Build all 7 demo emails and save each one as a real .eml file inside
    fake_inbox/. This is the ONLY place fake email content is written --
    the receiving module (email_module.py) never hardcodes email text.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- Attachment templates (same test scenarios as before) ----
    si_match = (
        "Shipper: ABC Trading Co\n"
        "Consignee: XYZ Import Ltd\n"
        "Notify Party: XYZ Import Ltd\n"
        "Port of Loading: Port Klang\n"
        "Port of Discharge: Rotterdam\n"
        "Container Count: 3\n"
        "Gross Weight (kg): 22000\n"
    )
    bl_match = si_match  # identical -> "no mismatch" case

    si_mismatch = si_match
    bl_mismatch = (
        "Shipper: ABC Trading Co\n"
        "Consignee: XYZ Import Ltd\n"
        "Notify Party: XYZ Import Ltd\n"
        "Port of Loading: Port Klang\n"
        "Port of Discharge: Rotterdam\n"
        "Container Count: 4\n"          # <-- mismatch on purpose
        "Gross Weight (kg): 22000\n"
    )

    # Unreadable / broken attachment content, to trigger the escalation path
    si_broken = "This document is all over the place, there's no standard key: value format. Just write something randomly."
    bl_broken = "BL attachment missing required fields"

    emails = [
        _build_email(
            "buyer1@company.com", "Check BL vs SI for Shipment #12345",
            "Hi team, please compare the attached SI and BL documents.",
            {"SI.txt": si_match, "BL.txt": bl_match},
        ),
        _build_email(
            "buyer2@company.com", "Discrepancy check needed - Shipment #67890",
            "Please verify the shipping instruction against the bill of lading.",
            {"SI.txt": si_mismatch, "BL.txt": bl_mismatch},
        ),
        _build_email(
            "ops@company.com", "New Shipping Instruction Request",
            "We need to prepare a new SI for next week's vessel departure.",
        ),
        _build_email(
            "finance@partner.com", "Question regarding Invoice #9876",
            "Can you explain the extra port storage fees on this invoice?",
        ),
        _build_email(
            "port-authority@terminal.com", "Operational Update: Terminal hours",
            "Please note that port operations will close early on Friday.",
        ),
        _build_email(
            "spam123@random.com", "CONGRATULATIONS YOU WON",
            "Click here to claim your free prize now!!!",
        ),
        _build_email(
            "confused_client@company.com", "Please compare documents for shipment",
            "Attached are the documents, please check bill of lading and si.",
            {"weird_file.txt": si_broken, "another_file.txt": bl_broken},
        ),
    ]

    for i, msg in enumerate(emails, start=1):
        filepath = os.path.join(OUTPUT_DIR, f"{i:03d}.eml")
        with open(filepath, "wb") as f:
            f.write(msg.as_bytes())

    print(f"Generated {len(emails)} fake emails in ./{OUTPUT_DIR}/ (real .eml format)")


if __name__ == "__main__":
    generate_fake_inbox()
