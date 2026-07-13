"""Full-text search across every field of a case (PRD F2 / F2a).

Weighting: question + recommendation > lessons + company > body.
Fuzzy so typos don't dead-end. Returns a snippet showing WHERE the match landed.
"""
import re
from rapidfuzz import fuzz

WEIGHTS = {
    "question": 5.0,
    "recommendation": 4.0,
    "lessons": 3.0,
    "company_name": 3.0,
    "industry": 2.0,
    "business_model": 2.0,
    "tags": 2.0,
    "body": 1.0,   # everything else, incl. hypotheses, tests, risks, next steps
}

# Which body section a match came from — shown in the result snippet.
SECTIONS = {
    "background": "Background", "complication": "Complication", "outcome": "Outcome",
    "risks": "Risks", "next_steps": "Next Steps", "lessons_narrative": "Lessons",
}


def _field_text(case, field):
    v = case.get(field, "")
    return " ".join(v) if isinstance(v, list) else str(v)


def _hit(query, text):
    """Score one field. Exact substring beats fuzzy; fuzzy catches typos/stems."""
    if not text:
        return 0.0
    t = text.lower()
    if query in t:
        return 1.0
    score = fuzz.partial_ratio(query, t) / 100
    return score if score >= 0.85 else 0.0


def _snippet(case, query, width=90):
    """Find the query in the raw blob and return surrounding text + its section."""
    # Try the structured sections first so we can label the hit.
    for field, label in SECTIONS.items():
        text = case.get(field, "")
        if text and query in text.lower():
            i = text.lower().index(query)
            frag = text[max(0, i - width // 2): i + width].strip()
            return f"{label} — …{frag}…"
    for r in case.get("reasons", []):
        for key, label in (("claim", "Reason"), ("hypothesis", "Hypothesis"),
                           ("test_method", "Test"), ("data_source", "Data")):
            text = r.get(key, "")
            if text and query in text.lower():
                return f"{label} — {text[:120]}"
    return case.get("recommendation", "")[:140]


def search(cases, query, filters=None):
    filters = filters or {}
    out = []
    for c in cases:
        # --- facet filters: AND across facets, OR within a facet ---
        keep = True
        for key, selected in filters.items():
            if not selected:
                continue
            val = c.get(key)
            vals = val if isinstance(val, list) else [val]
            if not set(selected) & set(vals):
                keep = False
                break
        if not keep:
            continue

        if not query:
            out.append((c, 0.0, c.get("recommendation", "")[:140]))
            continue

        q = query.lower().strip()
        score = 0.0
        for field, w in WEIGHTS.items():
            if field == "body":
                continue
            score += w * _hit(q, _field_text(c, field))
        # body = the whole blob, so hypotheses/tests/risks are all searchable
        score += WEIGHTS["body"] * _hit(q, c["_blob_lower"])

        if score > 0:
            out.append((c, score, _snippet(c, q)))

    out.sort(key=lambda x: (-x[1], x[0].get("published_date", "")), reverse=False)
    return out


def highlight(text, query):
    if not query:
        return text
    return re.sub(f"({re.escape(query)})", r"**\1**", text, flags=re.I)
