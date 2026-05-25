---
title: Red Team Reviewer
emoji: 🗡
colorFrom: red
colorTo: orange
sdk: streamlit
sdk_version: "1.40.0"
app_file: app.py
pinned: false
---

# 🗡 Red Team Reviewer

> A four-pass AI peer reviewer that finds every weakness in your academic writing before your supervisor does.

![Verdict](https://img.shields.io/badge/verdict-major%20revisions-orange)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/built%20with-streamlit-red)
![LLM](https://img.shields.io/badge/LLM-Groq%20Llama%203.3%2070B-green)
![Cost](https://img.shields.io/badge/cost-%C2%A30%20free-brightgreen)

---

## What it does

Red Team Reviewer reads your essay, dissertation chapter, or research paper and acts as a hostile-but-fair academic peer reviewer. Unlike generic AI writing assistants that offer vague encouragement, this tool produces a structured critique modelled on real journal peer review forms — with severity levels, direct quotes from your text, and concrete suggestions for every issue found.

Tested on a published IJRASET journal paper and returned **4/10 with major revisions** — finding issues the original review process missed.

---

## Four-pass pipeline

Each document goes through four sequential LLM passes, each building on the previous:

```
Pass 1 — Document map
  Extracts thesis, methodology, contribution, and section structure.
  Builds an internal model of what the paper claims to do.

Pass 2 — Claim audit
  Reads every paragraph and flags: unsupported claims, vague assertions,
  weak evidence, overclaiming, and circular reasoning.
  Each issue gets a severity (critical / major / minor) and a concrete fix.

Pass 3 — Consistency check
  Cross-references sections against each other.
  Finds where Section 2 contradicts Section 4, where the conclusion
  claims more than the evidence supports, or where methodology
  doesn't match the stated approach.

Pass 4 — Full synthesis
  Writes a structured peer review:
  Summary → Strengths → Major concerns → Minor concerns → Verdict
  Outputs a score (1–10) and a recommendation.
```

The full document is sent in a single API call per pass — no chunking, no lost context.

---

## Features

- Upload PDF, TXT, or MD files — or paste text directly
- Four-pass structured analysis with cross-section contradiction detection
- Severity-labelled issues with exact quotes from your document
- Genuine strengths listed alongside weaknesses
- Export the full review as a formatted `.docx` peer review document
- Built entirely on free APIs — no credit card required

---

## Tech stack

| Component | Tool | Cost |
|---|---|---|
| LLM | Groq — Llama 3.3 70B | Free |
| PDF parsing | PyMuPDF | Free |
| Orchestration | LangChain | Free |
| UI | Streamlit | Free |
| Export | python-docx | Free |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/Sumanth-Goud/red-team-reviewer.git
cd red-team-reviewer

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up API key
cp .env.example .env
# Edit .env and add your free Groq key from console.groq.com

# 5. Run
streamlit run app.py
```

App opens at `http://localhost:8501`.

---

## Getting a free Groq API key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up with your Google account
3. Click **API Keys** → **Create API key**
4. Copy the key and paste it into your `.env` file

No credit card. No quota limits for normal use.

---

## Project structure

```
red-team-reviewer/
├── app.py          # Streamlit UI — upload, run, display results
├── reviewer.py     # Four-pass pipeline core logic
├── exporter.py     # Formats review output as .docx
├── requirements.txt
├── .env.example    # API key template
└── README.md
```

---

## Example output

Running on a published IJRASET review paper (AI in Cybersecurity, Dec 2024):

```
Verdict:        Major revisions required
Score:          4 / 10
Critical:       1
Major:          5
Minor:          3
Contradictions: 3
```

Issues detected included unsupported quantitative claims ("90% improvement",
"70% reduction") cited to sources that don't report those specific figures,
a two-sentence Discussion section disproportionate to the paper's scope,
and three internal contradictions between the Introduction and Results sections.

---

## Limitations

- Works best on documents over 300 words — very short texts produce shallow reviews
- Quantitative claim verification depends on the LLM's knowledge of cited sources
- Four API calls per review — takes 30–60 seconds depending on document length
- Groq free tier has rate limits; very long documents (10,000+ words) may need retrying

---

## Roadmap

- [ ] Deploy to HuggingFace Spaces (public URL)
- [ ] Add RAGAS-style evaluation of reviewer consistency
- [ ] Citation validity checker (cross-reference claims against cited abstracts)
- [ ] Side-by-side diff view showing original text vs suggested rewrites
- [ ] Batch mode — review multiple drafts and compare scores over time

---

## Author

**Sumanth Goud N G**  
MSc Computing Science, University of Glasgow (2025–26)  
[Portfolio](https://sumanth-goud.github.io) · [LinkedIn](https://linkedin.com/in/sumanth-goud)

---

## Licence

MIT — free to use, modify, and build on.
