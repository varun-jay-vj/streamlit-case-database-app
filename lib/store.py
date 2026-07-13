"""Loading, validating and indexing cases. Cases live as one JSON file each in data/cases/."""
import json, pathlib, streamlit as st

CASES_DIR = pathlib.Path(__file__).parent.parent / "data" / "cases"

# Fields that get concatenated into the full-text index (PRD F2: nothing excluded).
TEXT_FIELDS = [
    "question", "recommendation", "company_name", "industry", "business_model",
    "geography", "background", "complication", "outcome", "risks", "next_steps",
    "lessons_narrative",
]
LIST_FIELDS = ["lessons", "tags", "outcome_user", "outcome_business"]


def _blob(case: dict) -> str:
    """Every scrap of text in the case, flattened. This is what search runs against."""
    parts = [str(case.get(f, "")) for f in TEXT_FIELDS]
    for f in LIST_FIELDS:
        parts += [str(x) for x in case.get(f, [])]
    for r in case.get("reasons", []):
        parts += [str(r.get(k, "")) for k in
                  ("claim", "hypothesis", "test_method", "data_source", "verdict", "exhibit_caption")]
    parts += [s.get("label", "") for s in case.get("sources", [])]
    return "\n".join(p for p in parts if p)


REQUIRED = ["slug", "question", "company_name", "industry", "business_model",
            "recommendation", "background", "reasons", "risks", "next_steps", "lessons"]


def validate(case: dict) -> list[str]:
    """PRD: the structure is the product. A case that breaks it does not publish."""
    errs = [f"missing: {f}" for f in REQUIRED if not case.get(f)]
    if len(case.get("reasons", [])) < 3:
        errs.append("needs at least 3 reasons")
    if len(case.get("recommendation", "").split()) > 40:
        errs.append("recommendation over 40 words")
    return errs


@st.cache_data(show_spinner=False)
def load_cases(include_drafts: bool = False) -> list[dict]:
    cases = []
    for p in sorted(CASES_DIR.glob("*.json")):
        c = json.loads(p.read_text())
        if c.get("status") != "published" and not include_drafts:
            continue
        c["_blob"] = _blob(c)
        c["_blob_lower"] = c["_blob"].lower()
        c["read_time"] = max(2, len(c["_blob"].split()) // 220)
        cases.append(c)
    return sorted(cases, key=lambda c: c.get("published_date", ""), reverse=True)


def save_case(case: dict) -> pathlib.Path:
    path = CASES_DIR / f"{case['slug']}.json"
    path.write_text(json.dumps(case, indent=2))
    load_cases.clear()
    return path


def facets(cases: list[dict]) -> dict:
    def uniq(key, is_list=False):
        vals = set()
        for c in cases:
            vals.update(c.get(key, []) if is_list else [c.get(key)])
        return sorted(v for v in vals if v)
    return {
        "company_name": uniq("company_name"),
        "industry": uniq("industry"),
        "business_model": uniq("business_model"),
        "question_type": uniq("question_type"),
        "geography": uniq("geography"),
        "lessons": uniq("lessons", True),
    }
