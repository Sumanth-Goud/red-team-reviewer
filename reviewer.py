"""
reviewer.py — Multi-pass academic review pipeline
Uses Gemini 1.5 Flash (1M token context) — no chunking needed, full document in one shot.

Four passes:
  Pass 1 — Document map:     What is the thesis? What are the sections and key claims?
  Pass 2 — Claim audit:      Which claims are unsupported, vague, or weak per section?
  Pass 3 — Consistency:      Where does the document contradict itself across sections?
  Pass 4 — Full synthesis:   Structured peer review (Summary / Major / Minor / Verdict)
"""

import json
import re
import os
from dataclasses import dataclass, field
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

# ─── Data models ──────────────────────────────────────────────────────────────

@dataclass
class DocumentMap:
    thesis: str
    doc_type: str           # essay / research paper / dissertation chapter / report
    sections: list[dict]    # [{"name": str, "summary": str, "key_claims": [str]}]
    methodology: str
    contribution: str

@dataclass
class ClaimIssue:
    section: str
    quote: str              # exact text from document
    issue_type: str         # unsupported | vague | weak_evidence | overclaiming | circular
    severity: str           # critical | major | minor
    explanation: str
    suggestion: str         # concrete fix, not just "add citation"

@dataclass
class Contradiction:
    section_a: str
    quote_a: str
    section_b: str
    quote_b: str
    explanation: str
    severity: str           # critical | major | minor

@dataclass
class ReviewResult:
    doc_map: DocumentMap
    claim_issues: list[ClaimIssue]
    contradictions: list[Contradiction]
    summary: str
    major_concerns: list[str]
    minor_concerns: list[str]
    strengths: list[str]
    verdict: str            # accept | minor_revisions | major_revisions | reject
    overall_score: int      # 1-10


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.1,
        max_tokens=1500,
    )

def _parse_json(raw: str) -> Optional[dict | list]:
    text = raw.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Second attempt: extract first JSON object/array found
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None


# ─── Pass 1: Document map ─────────────────────────────────────────────────────

_MAP_PROMPT = ChatPromptTemplate.from_template("""
You are a senior academic reviewer. Read this document carefully and extract its structure.

DOCUMENT:
{document}

Return ONLY a valid JSON object with exactly these keys:
{{
  "thesis": "<the central argument or research question in one sentence>",
  "doc_type": "<essay | research_paper | dissertation_chapter | report | other>",
  "methodology": "<how does the author argue or investigate? qualitative/quantitative/theoretical/etc>",
  "contribution": "<what does this claim to add to existing knowledge?>",
  "sections": [
    {{
      "name": "<section title or label like Introduction, Section 2, etc>",
      "summary": "<2 sentence summary of what this section does>",
      "key_claims": ["<claim 1>", "<claim 2>"]
    }}
  ]
}}

Return ONLY the JSON. No preamble.
""")

def _pass1_document_map(llm, document: str) -> DocumentMap:
    chain = _MAP_PROMPT | llm
    result = chain.invoke({"document": document})
    parsed = _parse_json(result.content)
    if not parsed:
        return DocumentMap(
            thesis="Could not extract thesis.",
            doc_type="unknown",
            sections=[],
            methodology="unknown",
            contribution="unknown",
        )
    return DocumentMap(
        thesis=parsed.get("thesis", ""),
        doc_type=parsed.get("doc_type", ""),
        sections=parsed.get("sections", []),
        methodology=parsed.get("methodology", ""),
        contribution=parsed.get("contribution", ""),
    )


# ─── Pass 2: Claim audit ──────────────────────────────────────────────────────

_AUDIT_PROMPT = ChatPromptTemplate.from_template("""
You are a hostile but fair academic peer reviewer. Your job is to find every unsupported,
vague, or unjustified claim in this document. Be thorough and specific.

DOCUMENT:
{document}

DOCUMENT STRUCTURE (for context):
Thesis: {thesis}
Type: {doc_type}

For each problem you find, identify:
- The EXACT quote from the document (keep it under 60 words)
- Which section it appears in
- The issue type: unsupported | vague | weak_evidence | overclaiming | circular | irrelevant
- Severity: critical (undermines the argument) | major (significant gap) | minor (nitpick)
- A specific explanation of WHY it is a problem
- A CONCRETE suggestion for how to fix it (not just "add a citation" — say what evidence is needed)

Return ONLY a valid JSON array of issue objects:
[
  {{
    "section": "<section name>",
    "quote": "<exact text from document, max 60 words>",
    "issue_type": "<type>",
    "severity": "<critical|major|minor>",
    "explanation": "<why this is a problem>",
    "suggestion": "<concrete fix>"
  }}
]

Find at minimum 3 issues, maximum 15. Return ONLY the JSON array.
""")

def _pass2_claim_audit(llm, document: str, doc_map: DocumentMap) -> list[ClaimIssue]:
    chain = _AUDIT_PROMPT | llm
    result = chain.invoke({
        "document": document,
        "thesis": doc_map.thesis,
        "doc_type": doc_map.doc_type,
    })
    parsed = _parse_json(result.content)
    if not parsed or not isinstance(parsed, list):
        return []
    issues = []
    for item in parsed:
        issues.append(ClaimIssue(
            section=item.get("section", "Unknown"),
            quote=item.get("quote", ""),
            issue_type=item.get("issue_type", "vague"),
            severity=item.get("severity", "minor"),
            explanation=item.get("explanation", ""),
            suggestion=item.get("suggestion", ""),
        ))
    return issues


# ─── Pass 3: Consistency check ────────────────────────────────────────────────

_CONSISTENCY_PROMPT = ChatPromptTemplate.from_template("""
You are a meticulous academic reviewer specialising in logical consistency.
Read this document and find every place where it contradicts itself — where a claim in
one section is inconsistent with, undermined by, or directly contradicts a claim elsewhere.

DOCUMENT:
{document}

SECTIONS IDENTIFIED:
{sections_summary}

Look for:
- Direct contradictions (Section 2 says X, Section 4 says not-X)
- Scope inconsistencies (claims X broadly in intro, then only shows it narrowly)
- Methodological contradictions (claims quantitative approach, uses anecdotal evidence)
- Conclusion drift (conclusion claims more than the evidence section supports)

Return ONLY a valid JSON array:
[
  {{
    "section_a": "<where the first claim appears>",
    "quote_a": "<exact quote, max 40 words>",
    "section_b": "<where the contradicting claim appears>",
    "quote_b": "<exact quote, max 40 words>",
    "explanation": "<why these contradict each other>",
    "severity": "<critical|major|minor>"
  }}
]

If you find no contradictions, return an empty array [].
Return ONLY the JSON array.
""")

def _pass3_consistency(llm, document: str, doc_map: DocumentMap) -> list[Contradiction]:
    sections_summary = "\n".join(
        f"- {s['name']}: {s['summary']}" for s in doc_map.sections
    )
    chain = _CONSISTENCY_PROMPT | llm
    result = chain.invoke({
        "document": document,
        "sections_summary": sections_summary,
    })
    parsed = _parse_json(result.content)
    if not parsed or not isinstance(parsed, list):
        return []
    contras = []
    for item in parsed:
        contras.append(Contradiction(
            section_a=item.get("section_a", ""),
            quote_a=item.get("quote_a", ""),
            section_b=item.get("section_b", ""),
            quote_b=item.get("quote_b", ""),
            explanation=item.get("explanation", ""),
            severity=item.get("severity", "minor"),
        ))
    return contras


# ─── Pass 4: Full synthesis ───────────────────────────────────────────────────

_SYNTHESIS_PROMPT = ChatPromptTemplate.from_template("""
You are a senior academic peer reviewer writing your final review.
You have already identified the following issues:

CLAIM ISSUES ({n_issues} found):
{issues_summary}

CONTRADICTIONS ({n_contras} found):
{contras_summary}

DOCUMENT THESIS: {thesis}
DOCUMENT TYPE: {doc_type}
STATED CONTRIBUTION: {contribution}

Now write your final structured review. Return ONLY a valid JSON object:
{{
  "summary": "<2-3 sentence overall assessment of the work>",
  "strengths": ["<genuine strength 1>", "<genuine strength 2>"],
  "major_concerns": [
    "<specific major concern 1 — reference actual content>",
    "<specific major concern 2>"
  ],
  "minor_concerns": [
    "<specific minor concern 1>",
    "<specific minor concern 2>"
  ],
  "verdict": "<accept | minor_revisions | major_revisions | reject>",
  "overall_score": <integer 1-10>,
  "verdict_reasoning": "<one sentence justification for the verdict>"
}}

Be honest, specific, and constructive. Strengths must be genuine, not filler.
Return ONLY the JSON.
""")

def _pass4_synthesis(
    llm,
    doc_map: DocumentMap,
    claim_issues: list[ClaimIssue],
    contradictions: list[Contradiction],
) -> dict:
    issues_summary = "\n".join(
        f"- [{i.severity.upper()}] {i.section}: {i.explanation[:100]}"
        for i in claim_issues
    ) or "None found."
    contras_summary = "\n".join(
        f"- [{c.severity.upper()}] {c.section_a} vs {c.section_b}: {c.explanation[:100]}"
        for c in contradictions
    ) or "None found."

    chain = _SYNTHESIS_PROMPT | llm
    result = chain.invoke({
        "n_issues": len(claim_issues),
        "issues_summary": issues_summary,
        "n_contras": len(contradictions),
        "contras_summary": contras_summary,
        "thesis": doc_map.thesis,
        "doc_type": doc_map.doc_type,
        "contribution": doc_map.contribution,
    })
    parsed = _parse_json(result.content)
    return parsed or {
        "summary": "Could not generate synthesis.",
        "strengths": [],
        "major_concerns": [],
        "minor_concerns": [],
        "verdict": "major_revisions",
        "overall_score": 5,
        "verdict_reasoning": "Parse error — please retry.",
    }


# ─── Main entry point ─────────────────────────────────────────────────────────

def run_review(document: str, on_status=None) -> ReviewResult:
    """
    Run all four passes and return a ReviewResult.
    on_status: optional callback(message: str) for progress updates
    """
    llm = _build_llm()

    if on_status:
        on_status("Pass 1/4 — reading document structure...")
    doc_map = _pass1_document_map(llm, document)

    if on_status:
        on_status("Pass 2/4 — auditing claims and evidence...")
    claim_issues = _pass2_claim_audit(llm, document, doc_map)

    if on_status:
        on_status("Pass 3/4 — checking internal consistency...")
    contradictions = _pass3_consistency(llm, document, doc_map)

    if on_status:
        on_status("Pass 4/4 — writing full peer review...")
    synthesis = _pass4_synthesis(llm, doc_map, claim_issues, contradictions)

    return ReviewResult(
        doc_map=doc_map,
        claim_issues=claim_issues,
        contradictions=contradictions,
        summary=synthesis.get("summary", ""),
        major_concerns=synthesis.get("major_concerns", []),
        minor_concerns=synthesis.get("minor_concerns", []),
        strengths=synthesis.get("strengths", []),
        verdict=synthesis.get("verdict", "major_revisions"),
        overall_score=synthesis.get("overall_score", 5),
    )
