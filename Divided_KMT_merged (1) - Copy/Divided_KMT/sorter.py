import imaplib
import email
from enum import Enum

class EmailCategory(Enum):
    DOCUMENT_COMPARISON = "Document-Comparison Request"
    NEW_SI = "New SI Request"
    INVOICE_QUERY = "Invoice Query"
    GENERAL_MESSAGE = "General Message / Operational Update"
    SPAM = "Spam"
    ADMIN_ESCALATION = "Admin Email / Unmatched"

class ShippingEmailCategorizer:
    """
    Categorizes shipping operations emails based on keywords and content rules.
    References backend structure from Image 1 and categories from Image 2.
    """
    

    def categorize(self, subject: str, body: str) -> EmailCategory:
        """
        Categorizes an email using subject and body text analysis.
        """
        combined_text = f"{subject} {body}".lower()
        
        # Check against defined categories
        # 🚨 RULE 1: High Priority - Spam Filter
        spam_keywords = ["win", "lottery", "crypto", "free", "discount", "click here", "offer"]
        if any(kw in combined_text for kw in spam_keywords):
            return EmailCategory.SPAM

        # 🚨 RULE 2: Specific Operational Tasks (New SIs)
        si_keywords = ["new si", "prepare si", "shipping instruction template", "submit instruction", "instruction request"]
        # If subject explicitly says "New Shipping Instruction", group it here immediately
        if "new shipping instruction" in combined_text or any(kw in combined_text for kw in si_keywords):
            return EmailCategory.NEW_SI

        # 🚨 RULE 3: Shipping Document Verification (Comparison checks)
        # By matching full phrases like "bill of lading" or specific indicators, we bypass invoice clashes
        comparison_keywords = ["bill of lading", "bl", "compare", "check document", "discrepancy", "bl vs si"]
        if any(kw in combined_text for kw in comparison_keywords):
            return EmailCategory.DOCUMENT_COMPARISON

        # 🚨 RULE 4: Finance and Billing (Only triggers if it didn't match the documents check)
        invoice_keywords = ["invoice", "payment", "charge", "cost", "fee"]
        if any(kw in combined_text for kw in invoice_keywords):
            return EmailCategory.INVOICE_QUERY

        # 🚨 RULE 5: General System Broadcasts
        general_keywords = ["update", "notice", "info", "schedule", "operational"]
        if any(kw in combined_text for kw in general_keywords):
            return EmailCategory.GENERAL_MESSAGE
                
        # Fallback to Admin Email routing (as seen in Image 1)
        return EmailCategory.ADMIN_ESCALATION

# --- Example Usage ---
if __name__ == "__main__":
    categorizer = ShippingEmailCategorizer()

    # Test cases based on Image 2 context
    test_emails = [
        ("Check BL vs SI for Shipment #12345", "Please compare the attached draft Bill of Lading with our Shipping Instruction."),
        ("New Shipping Instruction Request", "We need to prepare a new SI for next week's vessel."),
        ("Question regarding Invoice #9876", "Can you explain the extra port storage fees on this invoice?"),
        ("Operational Update: Terminal hours", "Please note that port operations will close early on Friday."),
        ("CONGRATULATIONS YOU WON", "Click here to claim your free prize now!!!"),
        ("Random inquiry", "Hello, can someone help me?")
    ]

    for subject, body in test_emails:
        result = categorizer.categorize(subject, body)
        print(f"Subject: '{subject}'\n--> Category: {result.value}\n")