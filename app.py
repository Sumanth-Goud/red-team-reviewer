"""
app.py — Red Team Reviewer: hostile-but-fair academic peer review
Run:  streamlit run app.py
"""

import os
import tempfile
import streamlit as st
from dotenv import load_dotenv
from reviewer import run_review, ReviewResult
from exporter import export_review_docx

load_dotenv()

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Red Team Reviewer",
    page_icon="🗡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Header ───────────────────────────────────────────────────────────────────
st.title("🗡 Red Team Reviewer")
st.caption("Four-pass AI peer reviewer — finds every weakness before your supervisor does")
st.divider()

# ─── Input section ────────────────────────────────────────────────────────────
col_upload, col_paste = st.columns([1, 1])

with col_upload:
    st.subheader("📄 Upload document")
    uploaded = st.file_uploader(
        "PDF or text file",
        type=["pdf", "txt", "md"],
        label_visibility="collapsed",
    )

with col_paste:
    st.subheader("✏️ Or paste text")
    pasted = st.text_area(
        "Paste your writing here",
        height=200,
        placeholder="Paste essay, dissertation chapter, or research paper...",
        label_visibility="collapsed",
    )

# Document name for export
doc_name = st.text_input("Document name (for the review report)", placeholder="e.g. Chapter 2 Draft — May 2025")

# ─── Review button ────────────────────────────────────────────────────────────
_, btn_col, _ = st.columns([2, 1, 2])
with btn_col:
    run_btn = st.button("⚔️ Red Team It", type="primary", use_container_width=True)

# ─── Review logic ─────────────────────────────────────────────────────────────
if run_btn:
    # Resolve document text
    document_text = ""
    if uploaded:
        if uploaded.name.endswith(".pdf"):
            import pymupdf
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            doc = pymupdf.open(tmp_path)
            document_text = "\n".join(p.get_text() for p in doc)
            doc.close()
            os.unlink(tmp_path)
        else:
            document_text = uploaded.read().decode("utf-8", errors="ignore")
    elif pasted.strip():
        document_text = pasted.strip()

    if not document_text:
        st.error("Please upload a file or paste some text first.")
        st.stop()

    if len(document_text) < 200:
        st.error("Document is too short for a meaningful review (minimum ~200 characters).")
        st.stop()

    # Run the four-pass pipeline
    st.divider()
    status_box = st.empty()
    progress = st.progress(0)

    pass_steps = {
        "Pass 1/4 — reading document structure...": 0.25,
        "Pass 2/4 — auditing claims and evidence...": 0.50,
        "Pass 3/4 — checking internal consistency...": 0.75,
        "Pass 4/4 — writing full peer review...": 0.95,
    }

    def on_status(msg: str):
        status_box.caption(f"🔍 {msg}")
        progress.progress(pass_steps.get(msg, 0))

    with st.spinner("Running four-pass review (takes ~30–60 seconds)..."):
        result: ReviewResult = run_review(document_text, on_status=on_status)

    progress.progress(1.0)
    status_box.empty()

    # ── Display results ────────────────────────────────────────────────────────
    st.divider()

    # Verdict banner
    verdict_colors = {
        "accept":           ("🟢", "success"),
        "minor_revisions":  ("🟡", "warning"),
        "major_revisions":  ("🟠", "warning"),
        "reject":           ("🔴", "error"),
    }
    verdict_labels = {
        "accept":           "Accept",
        "minor_revisions":  "Accept with minor revisions",
        "major_revisions":  "Major revisions required",
        "reject":           "Reject",
    }
    icon, color_fn = verdict_colors.get(result.verdict, ("⚪", "info"))
    label = verdict_labels.get(result.verdict, result.verdict)
    getattr(st, color_fn)(f"{icon} **Verdict: {label}**   |   Score: {result.overall_score}/10")

    # Metrics row
    m1, m2, m3, m4 = st.columns(4)
    critical_n = sum(1 for i in result.claim_issues if i.severity == "critical")
    major_n    = sum(1 for i in result.claim_issues if i.severity == "major")
    minor_n    = sum(1 for i in result.claim_issues if i.severity == "minor")
    m1.metric("Critical issues", critical_n)
    m2.metric("Major issues", major_n)
    m3.metric("Minor issues", minor_n)
    m4.metric("Contradictions", len(result.contradictions))

    st.divider()

    tab_overview, tab_claims, tab_contras, tab_synthesis = st.tabs([
        "📋 Overview", "🎯 Claim issues", "⚡ Contradictions", "📝 Full review"
    ])

    # ── Tab 1: Overview ────────────────────────────────────────────────────────
    with tab_overview:
        st.subheader("Document map")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Thesis:** {result.doc_map.thesis}")
            st.markdown(f"**Type:** {result.doc_map.doc_type}")
            st.markdown(f"**Methodology:** {result.doc_map.methodology}")
        with c2:
            st.markdown(f"**Contribution:** {result.doc_map.contribution}")

        if result.doc_map.sections:
            st.divider()
            st.subheader("Sections detected")
            for sec in result.doc_map.sections:
                with st.expander(sec.get("name", "Section")):
                    st.caption(sec.get("summary", ""))
                    if sec.get("key_claims"):
                        st.write("Key claims:")
                        for claim in sec["key_claims"]:
                            st.markdown(f"- {claim}")

        st.divider()
        st.subheader("✅ Genuine strengths")
        for s in result.strengths:
            st.success(s)

    # ── Tab 2: Claim issues ────────────────────────────────────────────────────
    with tab_claims:
        severity_order = {"critical": 0, "major": 1, "minor": 2}
        sorted_issues = sorted(result.claim_issues, key=lambda i: severity_order.get(i.severity, 3))

        severity_icons = {"critical": "🔴", "major": "🟠", "minor": "🟡"}
        severity_fns   = {"critical": st.error, "major": st.warning, "minor": st.info}

        if not sorted_issues:
            st.success("No major claim issues found — well supported writing.")
        else:
            for issue in sorted_issues:
                icon = severity_icons.get(issue.severity, "⚪")
                sev_fn = severity_fns.get(issue.severity, st.info)
                with st.expander(
                    f"{icon} [{issue.severity.upper()}] {issue.section} — {issue.issue_type.replace('_', ' ').title()}"
                ):
                    if issue.quote:
                        st.markdown(f"> *\"{issue.quote}\"*")
                    st.markdown(f"**Problem:** {issue.explanation}")
                    sev_fn(f"**Suggestion:** {issue.suggestion}")

    # ── Tab 3: Contradictions ─────────────────────────────────────────────────
    with tab_contras:
        if not result.contradictions:
            st.success("No internal contradictions detected — document is consistent.")
        else:
            for c in result.contradictions:
                sev_fn = severity_fns.get(c.severity, st.info)
                with st.expander(
                    f"{severity_icons.get(c.severity, '⚪')} [{c.severity.upper()}]  {c.section_a}  ↔  {c.section_b}"
                ):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.caption(c.section_a)
                        st.markdown(f"> *\"{c.quote_a}\"*")
                    with col_b:
                        st.caption(c.section_b)
                        st.markdown(f"> *\"{c.quote_b}\"*")
                    sev_fn(c.explanation)

    # ── Tab 4: Full synthesis ─────────────────────────────────────────────────
    with tab_synthesis:
        st.subheader("Reviewer summary")
        st.write(result.summary)

        st.divider()
        col_maj, col_min = st.columns(2)
        with col_maj:
            st.subheader(f"Major concerns ({len(result.major_concerns)})")
            for c in result.major_concerns:
                st.error(c)
        with col_min:
            st.subheader(f"Minor concerns ({len(result.minor_concerns)})")
            for c in result.minor_concerns:
                st.warning(c)

        st.divider()
        getattr(st, color_fn)(
            f"**Final verdict:** {label}  |  Score: {result.overall_score}/10"
        )

    # ── Export ────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Export review")
    docx_bytes = export_review_docx(result, doc_name=doc_name or "document")
    st.download_button(
        "Download full review as .docx",
        data=docx_bytes,
        file_name=f"review_{(doc_name or 'document').replace(' ', '_')}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=False,
    )
