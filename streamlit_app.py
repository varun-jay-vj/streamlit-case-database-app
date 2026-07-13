import json
import streamlit as st
from lib.store import load_cases, facets, save_case, validate
from lib.search import search, highlight

st.set_page_config(page_title="Case Library", page_icon="◆", layout="wide")

VERDICT_COLOUR = {"supported": "🟢", "rejected": "🔴", "inconclusive": "🟡"}


# ─────────────────────────────  LIBRARY (index)  ─────────────────────────────
def page_library():
    cases = load_cases()
    st.title("Case Library")
    st.caption("Transformation is a balancing act — solving the right business problem while helping people win.")

    q = st.text_input("Search", placeholder="Search anything — a company, a hypothesis, a lesson…",
                      value=st.query_params.get("q", ""), label_visibility="collapsed")

    f = facets(cases)
    c1, c2, c3, c4 = st.columns(4)
    filters = {
        "industry":       c1.multiselect("Industry", f["industry"]),
        "business_model": c2.multiselect("Model", f["business_model"]),
        "lessons":        c3.multiselect("Lesson", f["lessons"]),
        "question_type":  c4.multiselect("Type", f["question_type"]),
    }

    # shareable URL state (PRD F4)
    st.query_params.update({k: v for k, v in {"q": q, **{k: v for k, v in filters.items() if v}}.items() if v})

    results = search(cases, q, filters)
    st.write(f"**{len(results)}** case{'s' if len(results) != 1 else ''}")

    if not results and q:
        st.info("No match. Closest cases:")
        results = search(cases, "", {})[:3]

    for case, score, snippet in results:
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.markdown(f"#### {highlight(case['question'], q)}")
            left.markdown(f"*{case['recommendation']}*")
            left.caption(f"**{case['company_name']}** · {case['industry']} — {case['business_model']} · "
                         f"{case['question_type'].title()} · {case['read_time']} min")
            if q and snippet:
                left.markdown(f"<small>{highlight(snippet, q)}</small>", unsafe_allow_html=True)
            left.write(" ".join(f"`{l}`" for l in case.get("lessons", [])))
            if right.button("Read →", key=case["slug"]):
                st.query_params.clear()
                st.query_params["slug"] = case["slug"]
                st.rerun()


# ─────────────────────────────  CASE DETAIL  ─────────────────────────────
def page_case():
    slug = st.query_params.get("slug")
    case = next((c for c in load_cases() if c["slug"] == slug), None)
    if not case:
        st.warning("Case not found."); return

    if st.button("← All cases"):
        st.query_params.clear(); st.rerun()

    st.title(case["question"])
    st.caption(f"**{case['company_name']}** · {case['industry']} — {case['business_model']} · "
               f"{case['geography']} · {case['question_type'].title()}")

    # Above the fold: the answer and the reason headlines. Everything below is proof.
    st.success(f"**Recommendation.** {case['recommendation']}")
    for i, r in enumerate(case["reasons"], 1):
        st.markdown(f"**{i}. {r['claim']}**")
    st.write(" ".join(f"`{l}`" for l in case.get("lessons", [])))
    st.divider()

    st.header("Background & Context")
    st.write(case["background"])
    st.write(case["complication"])

    st.header("Outcome Sought")
    st.write(case.get("outcome", ""))
    st.caption("User: " + ", ".join(case.get("outcome_user", [])) +
               "  |  Business: " + ", ".join(case.get("outcome_business", [])))

    if case.get("decomposition_exhibit"):
        st.header("How the question breaks down")
        st.image(case["decomposition_exhibit"])

    st.header("Answer")
    for i, r in enumerate(case["reasons"], 1):
        with st.expander(f"**Reason {i} — {r['claim']}**  {VERDICT_COLOUR.get(r.get('verdict',''), '')} {r.get('verdict','').title()}"):
            st.markdown(f"**Hypothesis.** {r.get('hypothesis','')}")
            st.markdown(f"**How it was tested.** {r.get('test_method','')}")
            st.markdown(f"**Data.** {r.get('data_source','')}")
            if r.get("exhibit_url"):
                st.image(r["exhibit_url"], caption=r.get("exhibit_caption", ""))

    st.header("Risks & Next Steps")
    st.write(case["risks"])
    st.write(case["next_steps"])

    st.header("Lessons")
    st.write(case.get("lessons_narrative", ""))

    with st.expander("Sources & disclaimer"):
        for s in case.get("sources", []):
            st.markdown(f"- [{s['label']}]({s['url']})")
        st.caption(case.get("disclaimer",
                   "Based on publicly available information. Illustrative analysis, not investment advice."))


# ─────────────────────────────  ADMIN  ─────────────────────────────
def page_admin():
    st.title("Publish a case")
    if st.text_input("Password", type="password") != st.secrets.get("admin_password", ""):
        st.stop()

    st.caption("Paste or edit the case JSON. It won't publish unless the structure is complete.")
    template = {
        "slug": "", "status": "draft", "published_date": "2026-07-13",
        "question": "", "question_type": "strategic",
        "company_name": "", "industry": "", "business_model": "", "geography": "",
        "lessons": [], "lessons_narrative": "", "tags": [],
        "outcome": "", "outcome_user": [], "outcome_business": [],
        "background": "", "complication": "",
        "recommendation": "",
        "reasons": [{"claim": "", "hypothesis": "", "test_method": "",
                     "data_source": "", "verdict": "supported", "exhibit_url": "", "exhibit_caption": ""}] * 3,
        "risks": "", "next_steps": "", "sources": [{"label": "", "url": ""}],
    }
    raw = st.text_area("Case JSON", json.dumps(template, indent=2), height=500)
    if st.button("Validate & save"):
        try:
            case = json.loads(raw)
        except json.JSONDecodeError as e:
            st.error(f"Bad JSON: {e}"); return
        errs = validate(case)
        if errs:
            st.error("Not publishable:\n" + "\n".join(f"- {e}" for e in errs)); return
        path = save_case(case)
        st.success(f"Saved → {path.name}. Commit and push to make it live.")


# ─────────────────────────────  STATIC  ─────────────────────────────
def page_method():
    st.title("Method")
    st.markdown("""
Every case here answers one question, the same way.

1. **Background & Context** — the situation, and the complication that forced a decision.
2. **Outcome Sought** — what good looks like, in numbers.
3. **Case Question** — one sentence. Strategic (many entities) or operational (one).
4. **Answer** — a recommendation, then three or more reasons. Each reason carries its own
   hypothesis and the data used to test it. You can see what I checked, and what I got wrong.
5. **Risks & Next Steps** — what would make this wrong, and what to do first.

The structure is the point. If the reasoning doesn't survive being shown, it wasn't reasoning.
""")


def page_about():
    st.title("About")
    st.markdown("Varunraj (Jay) Jayaraman — technology and transformation, Canada & India.")


# ─────────────────────────────  ROUTER  ─────────────────────────────
if "slug" in st.query_params:
    page_case()
else:
    pg = st.navigation([
        st.Page(page_library, title="Library", default=True),
        st.Page(page_method, title="Method"),
        st.Page(page_about, title="About"),
        st.Page(page_admin, title="Admin"),
    ])
    pg.run()
