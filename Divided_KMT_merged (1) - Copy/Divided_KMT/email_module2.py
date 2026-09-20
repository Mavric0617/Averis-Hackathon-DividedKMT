"""
email_module.py
================
My (Email part) responsibilities:
    1. Fetch emails -- either from the local fake_inbox/ folder (demo)
       or from a real mailbox via IMAP (production)
    2. Parse emails, extracting subject / body / attachments into one
       unified dict format, regardless of where the email came from
    3. Call the teammate's categorizer.categorize(subject, body) in Averis.py
    4. If the category is "Document-Comparison Request" -> extract the 7
       fields from the SI / BL attachments and hand them to the Compare part
    5. If the category is "Admin Email / Unmatched" (or extraction fails)
       -> auto-generate an escalation email to notify staff
"""

import os
import json
import imaplib
import email
import email.message
from email.header import decode_header
from email.utils import parseaddr

# Import the categorizer from Averis
from sorter import ShippingEmailCategorizer, EmailCategory


# ====================================================================
# PART 1: Fetch emails (this replaces the old hardcoded fake inbox)
# 【Execution order: Step 1 -- called exactly once for the whole program,
#  to pull in every email as a list of raw email.message.Message objects.】
# ====================================================================

FAKE_INBOX_DIR = "fake_inbox"


def fetch_from_local_folder(folder: str = FAKE_INBOX_DIR) -> list[email.message.Message]:
    """
    Read every .eml file in `folder` and parse it into a real
    email.message.Message object -- this is how we simulate "receiving"
    emails during the demo. Run generate_fake_emails.py first to create
    this folder.
    """
    if not os.path.isdir(folder):
        raise FileNotFoundError(
            f"Can't find the {folder}/ folder. Please run generate_fake_emails.py first to generate fake emails."
        )

    messages = []
    filenames = sorted(f for f in os.listdir(folder) if f.endswith(".eml"))
    for filename in filenames:
        filepath = os.path.join(folder, filename)
        with open(filepath, "rb") as f:
            msg = email.message_from_binary_file(f)
        messages.append(msg)
    return messages


def fetch_from_imap(
    host: str,
    user: str,
    password: str,
    mailbox: str = "INBOX",
    port: int = 993,
    limit: int | None = None,
) -> list[email.message.Message]:
    """
    Connect to a REAL mailbox over IMAP and fetch emails.

    Example:
        messages = fetch_from_imap(
            host="imap.gmail.com",
            user="youraccount@gmail.com",
            password="your-app-password",  # Gmail needs an "app password",
                                            # not your normal login password
        )

    This returns the exact same type of object (email.message.Message)
    as fetch_from_local_folder(), so parse_email() below doesn't need
    any special-casing for "real" vs "fake" emails.
    """
    imap = imaplib.IMAP4_SSL(host, port)
    try:
        imap.login(user, password)
        imap.select(mailbox)

        status, data = imap.search(None, "ALL")
        if status != "OK":
            raise RuntimeError(f"IMAP search failed: {status}")

        email_ids = data[0].split()
        if limit:
            email_ids = email_ids[-limit:]

        messages = []
        for eid in email_ids:
            status, msg_data = imap.fetch(eid, "(RFC822)")
            if status != "OK":
                continue
            raw_bytes = msg_data[0][1]
            msg = email.message_from_bytes(raw_bytes)
            messages.append(msg)
        return messages
    finally:
        imap.logout()


# ====================================================================
# PART 2: Parse emails -> unify the format, ready for the classifier
# 【Execution order: Step 2 -- takes one raw email.message.Message at a
#  time (from either PART 1 function above) and converts it into the
#  same clean dict shape the rest of the pipeline already expects.】
# ====================================================================

def _decode_header_value(value: str) -> str:
    """Decode a possibly MIME-encoded header (e.g. non-ASCII subjects)."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = ""
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded += text.decode(encoding or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


def parse_email(msg: email.message.Message, email_id: int) -> dict:
    """
    Convert a raw email.message.Message (from a real mailbox OR from a
    local .eml file -- doesn't matter which) into a clean, unified dict.
    Every function after this one in the pipeline only ever sees this
    dict shape, so nothing downstream needs to change when the email
    source changes.

    Output shape (unchanged from before):
        {
            "id": int,
            "sender": str,
            "subject": str,
            "body": str,
            "date": str,
            "has_attachment": bool,
            "attachments": {filename: text_content},
        }
    """
    _, sender_addr = parseaddr(msg.get("From", ""))
    subject = _decode_header_value(msg.get("Subject", ""))
    date_str = msg.get("Date", "")

    body = ""
    attachments: dict[str, str] = {}

    if msg.is_multipart():
        for part in msg.walk():
            filename = part.get_filename()
            content_type = part.get_content_type()
            content_disp = str(part.get("Content-Disposition", ""))

            if filename:
                # This part is an attachment -> decode it as text.
                # (Our attachments are always plain-text SI/BL files;
                # a real system would also need to handle PDFs etc.)
                try:
                    payload = part.get_payload(decode=True)
                    attachments[filename] = payload.decode("utf-8", errors="replace")
                except Exception:
                    attachments[filename] = "(could not decode attachment)"
            elif content_type == "text/plain" and "attachment" not in content_disp:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")

    return {
        "id": email_id,
        "sender": sender_addr,
        "subject": subject,
        "body": body.strip(),
        "date": date_str,
        "has_attachment": len(attachments) > 0,
        "attachments": attachments,
    }


# ====================================================================
# PART 3: Extract SI / BL fields
# used when the category is Document-Comparison)
# ====================================================================

REQUIRED_FIELDS = [
    "Shipper",
    "Consignee",
    "Notify Party",
    "Port of Loading",
    "Port of Discharge",
    "Container Count",
    "Gross Weight (kg)",
]


FIELD_ALIASES = {
    "Shipper": [
        "shipper", "shiper", "shippr", "shpr", "exporter",
    ],
    "Consignee": [
        "consignee", "consigne", "consingee", "consginee", "cnee",
    ],
    "Notify Party": [
        "notify party", "notify", "notifyparty", "notify pty", "np", "n/p",
    ],
    "Port of Loading": [
        "port of loading", "loading port", "port loading", "load port",
        "pol", "p.o.l", "p l",
    ],
    "Port of Discharge": [
        "port of discharge", "discharge port", "port discharge", "destination port",
        "pod", "p.o.d", "p d",
    ],
    "Container Count": [
        "container count", "containers", "container qty", "container quantity",
        "container no", "number of containers", "no of containers", "cntr count",
        "ctr count", "cnt count", "cc",
    ],
    "Gross Weight (kg)": [
        "gross weight (kg)", "gross weight kg", "gross weight", "gross wt",
        "gross wgt", "grossweight", "total weight", "cargo weight", "weight",
        "gw", "g.w.",
    ],
}


def _normalize_field_label(label: str) -> str:
    """Normalize spacing and punctuation so aliases can match reliably."""
    return " ".join(label.lower().replace("&", "and").split())


def extract_fields_from_text(text: str) -> dict:
    """
    Grab fields out of a plain-text attachment, following the
    "field name: value" format. Any field that isn't found is marked
    as None in the result, which makes it easy to detect "extraction
    failed" later on.
    """
    result = {field: None for field in REQUIRED_FIELDS}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = _normalize_field_label(key.strip())
        value = value.strip()
        for field in REQUIRED_FIELDS:
            aliases = FIELD_ALIASES.get(field, [field])
            if any(key == _normalize_field_label(alias) for alias in aliases):
                result[field] = value
    return result


def extract_si_bl_fields(attachments: dict) -> dict | None:
    """
    Find the SI and BL files among the email's attachments and
    extract 7 fields from each. If either the SI or BL attachment
    can't be found, or too many fields are missing after extraction,
    return None (meaning extraction failed, which will later trigger
    an escalation email).
    """
    si_text, bl_text = None, None

    for filename, content in attachments.items():
        lower_name = filename.lower()
        if "si" in lower_name:
            si_text = content
        elif "bl" in lower_name:
            bl_text = content

    if si_text is None or bl_text is None:
        return None

    si_fields = extract_fields_from_text(si_text)
    bl_fields = extract_fields_from_text(bl_text)

    si_missing = sum(1 for v in si_fields.values() if v is None)
    bl_missing = sum(1 for v in bl_fields.values() if v is None)
    if si_missing > len(REQUIRED_FIELDS) // 2 or bl_missing > len(REQUIRED_FIELDS) // 2:
        return None

    return {"SI": si_fields, "BL": bl_fields}


# PART 4: Generate escalation email

def generate_escalation_email(parsed_email: dict, reason: str) -> str:
    """
    Generate a plain-text email body to send to staff. During the
    demo we just print it / save it to a file; to actually send it,
    pass this text as the email body via smtplib.
    """
    return f"""To: staff@company.com
Subject: [Needs manual review] Email from {parsed_email['sender']} (ID: {parsed_email['id']})

The system could not process this email automatically. Reason: {reason}

------ Email information ------
Sender      : {parsed_email['sender']}
Date        : {parsed_email['date']}
Subject     : {parsed_email['subject']}
Body        : {parsed_email['body']}
Attachments : {list(parsed_email['attachments'].keys()) if parsed_email['attachments'] else '(no attachment)'}
-------------------------------

Please review and handle this manually.
"""


# ====================================================================
# PART 5: Main flow -- ties everything above together
#
# Full execution order overview:
#   Step 1: fetch_from_local_folder() OR fetch_from_imap()
#           -> runs once, returns a list of raw email.message.Message
#   ------ Steps 2~4 below repeat for every email fetched ------
#   Step 2: parse_email()                  -> normalize into unified format
#   Step 3: categorizer.categorize()       -> call the teammate's classifier
#   Step 4: pick one of three branches based on the category:
#          A. extract_si_bl_fields()      -> category = comparison request
#          B. generate_escalation_email() -> category = unmatched, OR
#                                             extraction failed
#          C. do nothing, skip            -> any other category
# ====================================================================

def process_inbox(use_real_mailbox: bool = False, imap_config: dict | None = None):
    """
    use_real_mailbox=False (default): reads from ./fake_inbox/*.eml
    use_real_mailbox=True: connects to a real mailbox instead. Pass the
        connection details via imap_config, e.g.:
        process_inbox(
            use_real_mailbox=True,
            imap_config={"host": "imap.gmail.com", "user": "...", "password": "..."},
        )
    """
    categorizer = ShippingEmailCategorizer()

    # --- Step 1: fetch raw emails (real or fake -- same output type either way) ---
    if use_real_mailbox:
        if not imap_config:
            raise ValueError("When use_real_mailbox=True, you must also provide imap_config")
        raw_messages = fetch_from_imap(**imap_config)
    else:
        raw_messages = fetch_from_local_folder()

    comparison_tasks = []
    escalation_emails = []

    # --- Steps 2~4: repeat for every email ---
    for i, raw_msg in enumerate(raw_messages, start=1):
        # Step 2
        parsed = parse_email(raw_msg, email_id=i)

        # Step 3: call the teammate's classifier
        category = categorizer.categorize(parsed["subject"], parsed["body"])

        print(f"[email {parsed['id']}] Subject: {parsed['subject']}")
        print(f"   -> Category: {category.value}")

        # Step 4 - Branch A: category is "comparison request"
        if category == EmailCategory.DOCUMENT_COMPARISON:
            extracted = extract_si_bl_fields(parsed["attachments"])

            if extracted is None:
                reason = (
                    "The email was classified as a comparison request, but the "
                    "valid SI/BL fields couldn't be extracted from the attachment "
                    "(either the attachment is missing or the format can't be recognized)"
                )
                email_text = generate_escalation_email(parsed, reason)
                escalation_emails.append(email_text)
                print("   -> Extraction failed, an escalation email has been generated\n")
            else:
                comparison_tasks.append({
                    "email_id": parsed["id"],
                    "sender": parsed["sender"],
                    "subject": parsed["subject"],
                    "fields": extracted,
                })
                print("   -> Extraction successful, handed over to the Compare module\n")

        # Step 4 - Branch B: the teammate's classifier couldn't figure it out either
        elif category == EmailCategory.ADMIN_ESCALATION:
            reason = "The system can't categorize this email into any known category."
            email_text = generate_escalation_email(parsed, reason)
            escalation_emails.append(email_text)
            print("   -> Cannot be categorized, an escalation email has been generated\n")

        # Step 4 - Branch C: any other category -> only needs classifying
        else:
            print("   -> No further action needed\n")

    return comparison_tasks, escalation_emails


if __name__ == "__main__":
    # Demo mode: reads ./fake_inbox/*.eml (run generate_fake_emails.py first)
    comparison_tasks, escalation_emails = process_inbox()

    # To switch to a real mailbox instead, comment out the line above and
    # uncomment this:
    # comparison_tasks, escalation_emails = process_inbox(
    #     use_real_mailbox=True,
    #     imap_config={"host": "imap.gmail.com", "user": "you@gmail.com", "password": "app-password"},
    # )

    print("=" * 60)
    print(f"Total: {len(comparison_tasks)} comparison task(s), handed over to the Compare module")
    print(json.dumps(comparison_tasks, indent=2, ensure_ascii=False))

    print("=" * 60)
    print(f"Total: {len(escalation_emails)} escalation email(s) generated for staff:")
    for i, mail in enumerate(escalation_emails, 1):
        print(f"\n--- Escalation email {i} ---")
        print(mail)
