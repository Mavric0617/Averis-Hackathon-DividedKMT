# Access our system via link below:

https://averis-hackathon-divided-kmt.vercel.app/
\nIf you decided to review the codes and run it locally, follow the following steps ↓

# DKMT — AI Summary in the chat box

The AI Assistant chat box (bottom-right 🤖 button — now on all three pages:
Email Classification Hub, Data Extraction, and Manual Review) does something
real now: type **"summary"**, **"sum"**, or **"review"** and it generates an
AI summary of the current inbox — organized by category, including *why*
anything got escalated (extraction failure, unmatched category, etc.) — with
a **🖨 Print** and **⬇ Download PDF** button underneath. Anything else you
type just gets a hint to use one of those words.

## Setup (one-time)

```bash
pip install -r requirements.txt
cp api.env.example api.env
```

Open `api.env` and put your NVIDIA API key in:

```
NVIDIA_API_KEY=nvapi-your-key-here
```

**Note the filename is `api.env`, not `.env`** — `app.py` is set up to read
specifically from `api.env` (`load_dotenv(dotenv_path="api.env")`).

Get a key free at https://build.nvidia.com. Default model is
`moonshotai/kimi-k3` — change `NVIDIA_MODEL` in the same file for a
different one.

## Run it

Same as before:

```bash
python generate_fake_emails.py   # only needed once, to create fake_inbox/
python app.py
```

Open http://127.0.0.1:5000, log in, go to any of the three inbox pages,
click 🤖, type "summary".

## What changed

- **`app.py`** — `get_classified_emails()`'s existing logic (including the
  escalation-reason / auto-generated-email tracking) is unchanged, just
  pulled into a `_get_classified_dataset()` helper so it can be reused.
  Added: that helper, an adapter that turns its output into what the
  summarizer expects (escalation reasons get folded into the email content
  so the AI can explain *why* something needs review), and two new routes:
  `GET /api/summary` (JSON) and `GET /api/summary/pdf` (PDF download).
- **`email_class.html`, `dataExtract.html`, `manualReview.html`** — only
  `sendAIMessage()` changed (was a fake `setTimeout` reply on all three).
  Checks for the trigger words client-side; if matched, calls
  `/api/summary` and renders the result with Print/PDF buttons.
- **New files**: `llm_client.py`, `categorizer.py`, `summarizer.py`,
  `pdf_export.py`, `fonts/wqy-zenhei.ttf` (font for the PDF; without it,
  non-English text renders as black boxes).
- **`sorter.py`, `email_module2.py`, `generate_fake_emails.py`** — untouched.
