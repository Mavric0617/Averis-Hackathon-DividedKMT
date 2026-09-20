# DKMT: Email Classification and AI Summary

DKMT is a Flask application for classifying operational emails, extracting
shipping-document fields, and routing items that need human attention. The
included `fake_inbox/` provides a repeatable local demo. The processing module
also contains an IMAP path for connecting the same parsing pipeline to a real
mailbox.

## Features

- Classifies messages into comparison, new SI, invoice, general, spam, and
  escalation workflows.
- Parses sender, subject, date, body, and attachments from `.eml` messages.
- Extracts seven SI/BL fields from plain-text attachments for comparison
  requests: shipper, consignee, notify party, ports, container count, and
  gross weight.
- Escalates unmatched categories and failed document extraction, including a
  generated staff-review email body.
- Provides an AI assistant on the Email Classification Hub, Data Extraction,
  and Manual Review pages. Enter `summary`, `sum`, or `review` to generate a
  category-organized inbox summary.
- Supports printing the summary and downloading an `email-summary-report.pdf`.

## Project Flow

```text
fake_inbox/*.eml or IMAP
        |
        v
parse_email -> ShippingEmailCategorizer -> SI/BL extraction or escalation
        |
        +-> /api/classified-emails
        |
        +-> AI categorizer -> summarizer -> JSON or PDF report
```

## Setup

Run these commands from the `Divided_KMT` directory:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy api.env.example api.env
```

The application loads `api.env` explicitly; it does not automatically read a
file named `.env`. Add an API key and, optionally, an OpenAI-compatible model
and endpoint:

```env
API_KEY=your-api-key
AI_BASE_URL=base-url
AI_MODEL=ai-model
```

`app.py` accepts `AI_API_KEY`, `API_KEY`, or `NVIDIA_API_KEY`. `AI_MODEL` and
`NVIDIA_MODEL` are supported model names. The default endpoint and model are
defined in `llm_client.py`; replace them when using another
OpenAI-compatible provider.

## Run the Demo

Generate the sample messages once, then start Flask:

```bash
python generate_fake_emails.py
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The home page links to
the operational views. The classification and summary APIs use the messages
currently present in `fake_inbox/`.

## API Endpoints

### `GET /api/classified-emails`

Runs the local inbox through parsing, classification, extraction, and
escalation tracking. The response is a JSON array containing the message ID,
category, sender, subject, date, body, attachments, extracted fields, and any
escalation reason or generated email.

### `GET|POST /api/summary`

Runs the same classification pipeline, sends the normalized records to the
configured AI provider, and returns JSON in this shape:

```json
{
  "summary": "...",
  "email_count": 7
}
```

For a `POST`, an optional JSON body can provide `api_key` and `model`. The
server first checks those values, then the environment configuration.

### `GET|POST /api/summary/pdf`

Creates the same AI summary and returns it as a downloadable PDF. The PDF
includes the summary and the source email records. A Unicode font in
`fonts/` is used so supported non-English text renders correctly.

## Email Sources

The Flask dashboard currently reads from `fake_inbox/`. For standalone or
future mailbox integrations, `email_module2.py` exposes
`fetch_from_imap(host, user, password, mailbox="INBOX", port=993, limit=None)`
and `process_inbox(use_real_mailbox=True, imap_config=...)`. Gmail requires an
app password rather than the normal account password.

## Key Files

- `app.py`: Flask routes and the shared classified dataset pipeline.
- `email_module2.py`: local/IMAP fetching, MIME parsing, SI/BL extraction, and
  escalation-email generation.
- `sorter.py`: operational shipping-email categories.
- `categorizer.py`: keyword categories used to structure AI prompts.
- `summarizer.py`: AI prompt construction and summary generation.
- `llm_client.py`: OpenAI-compatible HTTP client and provider defaults.
- `pdf_export.py`: PDF report generation.
- `generate_fake_emails.py`: creates the demo inbox.
- `templates/`: Flask pages and their client-side dashboard behavior.

## Troubleshooting

- **Missing API key:** check that the file is named `api.env` and contains
  `API_KEY`, `AI_API_KEY`, or `NVIDIA_API_KEY`.
- **Missing inbox:** run `python generate_fake_emails.py` and confirm that
  `fake_inbox/` contains `.eml` files.
- **AI request failures:** verify `AI_BASE_URL`, `AI_MODEL`, network access,
  and that the selected provider supports the configured model.
- **PDF font issues:** keep `fonts/wqy-zenhei.ttf` available beside the
  application so non-English characters do not render as empty boxes.
