"""Turn a batch of emails (subject / from / date / content) into a plain-language summary."""

from llm_client import call_llm
from categorizer import categorize_email


def format_emails_for_prompt(emails_with_categories):
    blocks = []
    for i, (email, categories) in enumerate(emails_with_categories, start=1):
        blocks.append(
            f"[Email {i}]\n"
            f"Subject: {email.get('subject', '')}\n"
            f"From: {email.get('from', '')}\n"
            f"Date: {email.get('date', '')}\n"
            f"Category (keyword-matched): {', '.join(categories)}\n"
            f"Content: {email.get('content', '')}"
        )
    return "\n\n".join(blocks)


def summarize_emails(emails, api_key, model):
    emails_with_categories = [(e, categorize_email(e)) for e in emails]
    email_text = format_emails_for_prompt(emails_with_categories)

    system = (
        "You are an email assistant. You will be given a batch of emails "
        "(subject, sender, date, content), each already tagged with a category "
        "based on keyword matching. Write a concise, natural-language summary "
        "organized BY CATEGORY. For each category that has at least one email:\n"
        "- Name the category as a short heading\n"
        "- Summarize what those emails are about, grouping similar ones\n"
        "- Call out anything that needs urgent attention or a response\n"
        "Skip categories with no emails. End with one line on what needs the "
        "most attention overall, if anything. Output only the summary text, "
        "no extra preamble."
    )

    summary = call_llm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": email_text},
        ],
        api_key=api_key,
        model=model,
        temperature=0.4,
        max_tokens=900,
    )

    return summary, emails_with_categories
