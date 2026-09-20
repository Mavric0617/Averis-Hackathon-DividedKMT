import os
from flask import Flask, render_template, jsonify, send_from_directory, request, send_file
from dotenv import load_dotenv

# Load provider settings before importing modules that read them.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "api.env"))

# Import processing functions and Category list from your new module
from email_module2 import process_inbox, fetch_from_local_folder, parse_email, EmailCategory
from sorter import ShippingEmailCategorizer

# --- AI summary feature (added) ---
from llm_client import DEFAULT_MODEL, LLMError
from categorizer import categorize_email
from summarizer import format_emails_for_prompt, summarize_emails
from pdf_export import build_pdf

system_prompt = """
You are a strict deadline extraction tool.
Your sole task is to extract assignment "due dates" from the provided text.
You are strictly forbidden from extracting, analyzing, reading, or outputting any other context, personal information, or irrelevant data.
If no due date is found, simply return "Not found" and do not make any assumptions or guesses.
"""
app = Flask(__name__)

# 🔥 AUTOMATED IMAGE ROUTE BYPASS 🔥
# This catches any request for an asset starting with "img/" 
# and serves it directly out of your existing templates/img folder automatically!
@app.route('/img/<path:filename>')
def serve_images_from_templates(filename):
    img_dir = os.path.join(app.template_folder, 'img')
    return send_from_directory(img_dir, filename)

# 1. Base route: defaults to home.html when you open 127.0.0.1:5000/
@app.route('/')
def index():
    return render_template('home.html')

# 2. Catch-all route for multi-page linkage navigation
@app.route('/<path:page>')
def serve_any_html_page(page):
    if not page.endswith('.html') and os.path.exists(os.path.join(app.template_folder, f"{page}.html")):
        page = f"{page}.html"
        
    try:
        return render_template(page)
    except Exception:
        return f"File '{page}' not found inside your templates folder. Check your files!", 404


# 3. Dynamic API endpoint for the email classification hub data streams
# Replace ONLY the get_classified_emails() function block inside app.py with this:

def _get_classified_dataset():
    """
    Same pipeline as before (fetch -> parse -> categorize -> extract SI/BL
    fields -> track escalations), just pulled into its own function so both
    /api/classified-emails AND the new AI summary routes below can reuse it
    without duplicating the logic or making an HTTP round trip to itself.
    """
    categorizer = ShippingEmailCategorizer()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_inbox_path = os.path.join(base_dir, "fake_inbox")

    import email_module2
    email_module2.FAKE_INBOX_DIR = target_inbox_path

    raw_messages = fetch_from_local_folder(target_inbox_path)

    classified_dataset = []

    for i, raw_msg in enumerate(raw_messages, start=1):
        parsed = parse_email(raw_msg, email_id=i)
        category_enum = categorizer.categorize(parsed["subject"], parsed["body"])

        attachment_names = list(parsed["attachments"].keys()) if parsed["attachments"] else []

        # 🔑 REAL PIPELINE DATA EXTRACTION AND ESCALATION TRACKING LOGIC
        extracted_fields = None
        escalation_reason = None
        generated_email_body = None

        from email_module2 import extract_si_bl_fields, generate_escalation_email

        if category_enum == EmailCategory.DOCUMENT_COMPARISON:
            extracted_fields = extract_si_bl_fields(parsed["attachments"])
            # If extraction failed, capture the exact structural failure reason
            if extracted_fields is None:
                escalation_reason = "Extraction Failed"
                generated_email_body = generate_escalation_email(
                    parsed,
                    "The email was classified as a comparison request, but valid SI/BL fields couldn't be extracted."
                )
        elif category_enum == EmailCategory.ADMIN_ESCALATION:
            escalation_reason = "Unmatched Category"
            generated_email_body = generate_escalation_email(
                parsed,
                "The system can't categorize this email into any known operational workflow."
            )

        tab_mapping = {
            EmailCategory.DOCUMENT_COMPARISON.value: "comparison",
            EmailCategory.NEW_SI.value: "new-si",
            EmailCategory.INVOICE_QUERY.value: "invoice",
            EmailCategory.GENERAL_MESSAGE.value: "general",
            EmailCategory.SPAM.value: "spam",
            EmailCategory.ADMIN_ESCALATION.value: "escalation"
        }

        # Override tab assignment if an extraction failure forced it into the manual queue
        assigned_tab = tab_mapping.get(category_enum.value, "general")
        if category_enum == EmailCategory.DOCUMENT_COMPARISON and extracted_fields is None:
            assigned_tab = "escalation"

        classified_dataset.append({
            "id": parsed["id"],
            "category": assigned_tab,
            "sender": parsed["sender"],
            "subject": parsed["subject"],
            "date": parsed.get("date", "Received"),
            "body": parsed["body"],
            "attachments": attachment_names,
            "fields": extracted_fields,
            "reason": escalation_reason,         # Feeds the warning text badge directly
            "generated_email": generated_email_body # Feeds the matrix-green log display terminal
        })

    return classified_dataset


@app.route('/api/classified-emails', methods=['GET'])
def get_classified_emails():
    try:
        return jsonify(_get_classified_dataset())
    except Exception as e:
        return jsonify({"error": f"Backend pipeline error: {str(e)}"}), 500


# --- AI summary feature (added) -------------------------------------------
# Maps the "comparison"/"new-si"/... tab slugs above back to the same
# human-readable category labels EmailCategory already defines, so the AI
# summary and the PDF report use the exact same category names as the
# dashboard tabs. "escalation" covers BOTH an unmatched category AND a
# comparison request whose SI/BL extraction failed (see assigned_tab above),
# so its label stays generic on purpose.
REVERSE_TAB_MAPPING = {
    "comparison": EmailCategory.DOCUMENT_COMPARISON.value,
    "new-si": EmailCategory.NEW_SI.value,
    "invoice": EmailCategory.INVOICE_QUERY.value,
    "general": EmailCategory.GENERAL_MESSAGE.value,
    "spam": EmailCategory.SPAM.value,
    "escalation": EmailCategory.ADMIN_ESCALATION.value,
}


def _format_extracted_fields(fields):
    if not fields:
        return ""
    lines = ["--- Extracted SI/BL fields ---"]
    for doc_label, doc_fields in fields.items():
        lines.append(f"{doc_label}:")
        for k, v in (doc_fields or {}).items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _dataset_to_email_records(dataset):
    """Adapts _get_classified_dataset()'s output into the
    {subject, from, date, content, source_category} shape summarizer.py /
    categorizer.py / pdf_export.py expect. Escalation reason (and the
    auto-generated staff email, if any) get folded into the content so the
    AI summary can call out *why* something needs manual review."""
    emails = []
    for r in dataset:
        content = (r.get("body") or "").strip()

        extra = _format_extracted_fields(r.get("fields"))
        if extra:
            content = f"{content}\n\n{extra}" if content else extra

        if r.get("reason"):
            content += f"\n\n[ESCALATED — reason: {r['reason']}]"

        attachments = r.get("attachments") or []
        if attachments:
            content += f"\n\n(Attachments: {', '.join(attachments)})"

        emails.append({
            "subject": r.get("subject", ""),
            "from": r.get("sender", ""),
            "date": r.get("date", ""),
            "content": content.strip(),
            "source_category": REVERSE_TAB_MAPPING.get(r.get("category")),
        })
    return emails


def _resolve_api_key(payload=None):
    payload = payload or {}
    return (
        (payload.get("api_key") or "").strip()
        or os.getenv("AI_API_KEY", "").strip()
        or os.getenv("API_KEY", "").strip()
        or os.getenv("NVIDIA_API_KEY", "").strip()
    )


def _resolve_model(payload=None):
    payload = payload or {}
    return (
        (payload.get("model") or "").strip()
        or os.getenv("AI_MODEL", "").strip()
        or os.getenv("NVIDIA_MODEL", "").strip()
        or DEFAULT_MODEL
    )


@app.route('/api/summary', methods=['GET', 'POST'])
def api_summary():
    """
    Powers the "summary"/"sum"/"review" trigger in the AI chat box: pulls
    the current inbox (same pipeline as /api/classified-emails), runs it
    through the AI summarizer, and returns the summary text.
    """
    payload = {}
    if request.method == "POST":
        payload = request.get_json(force=True, silent=True) or {}
    api_key = _resolve_api_key(payload)
    model = _resolve_model(payload)

    if not api_key:
        return jsonify({"error": "Missing AI_API_KEY. Set it in api.env, or pass api_key in the request."}), 400

    try:
        dataset = _get_classified_dataset()
    except Exception as e:
        return jsonify({"error": f"Could not load the inbox: {e}"}), 500

    emails = _dataset_to_email_records(dataset)
    if not emails:
        return jsonify({"error": "Inbox is empty — nothing to summarize."}), 400

    try:
        summary, _ = summarize_emails(emails, api_key, model)
    except LLMError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"summary": summary, "email_count": len(emails)})


@app.route('/api/summary/pdf', methods=['GET', 'POST'])
def api_summary_pdf():
    """Same as /api/summary, but returns a downloadable PDF report instead
    of JSON — this is the "print as PDF" action in the chat."""
    payload = {}
    if request.method == "POST":
        payload = request.get_json(force=True, silent=True) or {}
    api_key = _resolve_api_key(payload)
    model = _resolve_model(payload)

    if not api_key:
        return jsonify({"error": "Missing AI_API_KEY. Set it in api.env, or pass api_key in the request."}), 400

    try:
        dataset = _get_classified_dataset()
        emails = _dataset_to_email_records(dataset)
        if not emails:
            return jsonify({"error": "Inbox is empty — nothing to summarize."}), 400
        summary, _ = summarize_emails(emails, api_key, model)
        pdf_buffer = build_pdf(summary, emails)
    except LLMError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        return jsonify({"error": f"Could not generate the report: {e}"}), 500

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="email-summary-report.pdf",
    )
# --- end AI summary feature -------------------------------------------------


if __name__ == '__main__':
    app.run(debug=True, port=5000)
