import re

def find_match(patterns, txt, default_val):
    for pattern in patterns:
        match = re.search(pattern, txt, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if val:
                return val
    return default_val

text = (
    "INCOMETAX DEPARTMENT = 8S GOV'T. OF INDIA\n\n"
    "f . Permanent Account Number Card Pes ote eS 4\n\n"
    "ie sks ws anes * oes is\n"
    "PAXPS0432J : ae hae “s\n\n"
    "~ we ' eng\n\n"
    "ATHY / Name s Wore oF ae\n"
    "LEELANJAN S Sa\n\n"
    "of Fag Bare\n"
    "Pra ary | Father's Name\n\n"
    "SATHISH SHIVAPPA\n"
)

name = "pan_number"
label_guess = name.replace('_', ' ')
label_guess_no_space = name.replace('_', '')

# Test standard matcher
val = find_match([
    r"(?:pan number|pan no|pan|card no)\s*[:=-]?\s*([A-Z]{5}\d{4}[A-Z])",
    r"\b([A-Z]{5}\d{4}[A-Z])\b"
], text, None)
print("Standard Matcher Val:", val)

# Test generic fallback
val_fallback = find_match([
    rf"\b(?:{label_guess}|{label_guess_no_space})\s*[:=-]\s*([^\n]+)",
    rf"\b(?:{label_guess}|{label_guess_no_space})\s+([^\n]+)"
], text, None)
print("Generic Fallback Val:", val_fallback)

# Wait! Let's check if there is another match in llm.py that matched "Card"
# Let's search if "pan" in name matched:
# Wait, "pan_number" contains "number".
# Does it match numbers/IDs matcher?
# "passport_number" in name or "license_number" in name or "invoice_number" in name or "po_number" in name or "roll_number" in name or "number" in name or "num" in name or "id_number" in name
# Yes! "pan_number" contains "number"!
# So it went into the Numbers/IDs matcher first!
# Let's test that!
val_id = find_match([
    r"(?:passport|license|invoice|po|roll|document|id|employee id|emp id|seat|usn|register|reg)\s*(?:number|no|#)?\s*[:=-]?\s*([A-Za-z0-9-]+)",
    r"(?:passport|license|invoice|po|roll|document|id|employee id|emp id|seat|usn|register|reg)\s*[:=-]?\s*([A-Za-z0-9-]+)",
    r"(?:number|no|#)\s*[:=-]?\s*([A-Za-z0-9-]+)"
], text, None)
print("Numbers/IDs Matcher Val:", val_id)
