"""A single model-response envelope; JSON contents and strict decoders stay intact."""

def unwrap_model_json(raw):
    """Remove one complete model-only wrapper, never rewrite JSON contents."""
    import re
    text = raw.strip()
    fenced = re.fullmatch(r"(?P<fence>`{3}|'{3})(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n(?P=fence)", text, re.IGNORECASE)
    if fenced:
        candidate = fenced['body'].strip()
        if any(re.fullmatch(r"(?:`{3}|'{3})(?:json)?", line.strip(), re.IGNORECASE) for line in candidate.splitlines()):
            return raw
    elif text.startswith(('```', "'''")):
        return raw
    elif len(text) >= 2 and text[0] in "'`" and text[-1] == text[0]:
        candidate = text[1:-1].strip()
    else:
        return raw
    if not (candidate.startswith('{') and candidate.endswith('}')):
        return raw
    return candidate

