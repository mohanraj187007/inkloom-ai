# Inkloom AI — Brand Governance & Copy Safeguard Platform

Inkloom AI is an enterprise-grade brand-governance web application designed for real-time marketing copy compliance, claim verification, versioned drafts, and reviewer workflows. It provides marketing teams, legal counsel, and brand guardians with an automated safeguard against regulatory fines, deceptive claims, and off-brand copy.

---

## Key Highlights

- **Zero-Setup MVP**: Deploys as a single Python FastAPI process with SQLite and plain HTML/CSS/JS (no separate Node.js or React build step).
- **100% Reliable Review Engine**: Deterministic rule checking runs first. If an optional Google Gemini API key is provided, subtle tone and nuance checks are layered on top; if the key is missing or fails, the app operates uninterrupted using deterministic rules alone.
- **Human-in-the-Loop Safeguard**: AI never publishes copy automatically. Reviewers retain strict editorial and regulatory approval authority.
- **Full Traceability**: Every accepted rewrite creates a new version number (`v1` → `v2`) with complete audit trails of who changed what, when, and why.
- **Guideline Friction Analytics**: Highlights often-ignored brand rules to identify ambiguous or overly restrictive guidelines needing clarification.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Inkloom AI Application                   │
│                                                             │
│   Frontend (Vanilla HTML5 / CSS3 / ES6 Javascript SPA)      │
│   Served directly via FastAPI StaticFiles (Zero Node Build) │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTP / REST API (JSON)
┌─────────────────────────────▼───────────────────────────────┐
│                    FastAPI Backend (Python)                 │
│                                                             │
│  ┌────────────────────────┐    ┌──────────────────────────┐ │
│  │     API Endpoints      │    │    Review & Rule Engine  │ │
│  │  - /api/drafts         │    │  - Banned & Preferred    │ │
│  │  - /api/guidelines     │    │  - Medical / Cure Claims │ │
│  │  - /api/analytics      │    │  - Absolute Guarantees   │ │
│  │  - /api/users          │    │  - Superlative Verifier  │ │
│  └───────────┬────────────┘    │  - Mandatory Disclaimers │ │
│              │                 │  - Editorial Tone Hype   │ │
│              │                 │  - Optional Gemini LLM   │ │
│              │                 └─────────────┬────────────┘ │
│  ┌───────────▼───────────────────────────────▼────────────┐ │
│  │          SQLAlchemy ORM Data Layer (SQLite)            │ │
│  │  - Users (Creator, Reviewer, Admin)                    │ │
│  │  - Brand Rules & Approved Facts Repository             │ │
│  │  - Drafts, DraftVersions & Findings                    │ │
│  │  - ReviewComments & AuditLogs                          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Flows

1. **One-Click Demo Roles**: Switch instantly between **Creator** (Priya Sharma), **Reviewer** (Arjun Mehta), and **Admin** (Vikram Patel) without signups or passwords.
2. **Interactive 6-Step Tour ("Try this")**:
   - Step 1: Open Demo Draft 1 (contains deliberate governance issues).
   - Step 2: Click "Review Copy" to trigger automated evaluation.
   - Step 3: Click "Accept Fix" on any finding (e.g. `cheap` → `affordable` or `cures`); watch a new draft version (`v2`) generate automatically.
   - Step 4: Click "Submit for Review" to push the draft to the human review queue.
   - Step 5: Switch to Reviewer and approve the copy in the Review Queue.
   - Step 6: View the Analytics Dashboard to see recurring issue types and guideline friction alerts.
3. **Interactive Findings Screen**:
   - Flagged text highlighted in draft with color-coded severity badges (High: Red, Medium: Amber, Low: Blue).
   - Side-by-side comparison showing Original vs. Intent-Preserving Suggested Rewrite.
   - Status indicators (`VIOLATION` vs. `NEEDS VERIFICATION`).
   - One-click actions: **Accept Fix**, **Edit Custom**, **Ignore**.
4. **Admin Guideline Library**:
   - Add/edit Brand Rules (banned terms, regex claim patterns, mandatory disclaimers, tone rules).
   - Maintain Approved Facts with 3rd-party source references and versioning.
5. **Analytics & Guideline Intelligence**:
   - Categorized recurring violations (Medical/Cure, Guarantees, Superlatives, Missing Disclaimers, Tone).
   - Most-triggered brand guidelines.
   - **Often-Ignored Rules Watch**: Uncovers guidelines that creators consistently ignore, indicating ambiguous wording or workflow bottlenecks.

---

## Seed Data (Preloaded on First Run)

The application automatically initializes SQLite on launch with:
- **3 Demo Users**: Creator, Reviewer, Admin.
- **8 Brand Rules**:
  1. *Banned Term: Cheap* → `affordable` (Brand Voice Guide v2.4)
  2. *Medical Cure Claims* → `promotes wellness` (Pharma & Health Advertising Act Rule 14)
  3. *Absolute Guarantee Claims* → `satisfaction promise` (Consumer Protection Act Sec 7.3)
  4. *Superlative & Leadership Claims* → Cross-referenced against approved facts; flags `needs verification` if missing evidence (ASCI Code Sec 1.4)
  5. *Mandatory Promotional Disclaimer* → Enforces `*T&C apply. Limited period offer.` on discount claims (Promotional Disclosure Policy 2025)
  6. *Tone: Avoid ALL CAPS Hype* → Prevents aggressive text and multiple exclamation marks (Inkloom Tone Guide Sec 4)
  7. *Competitor Disparagement* → Prohibits direct negative claims against rivals (ASCI Code Sec 4.1)
  8. *Unverified Environmental Claims* → Prevents unsubstantiated `zero carbon` or `100% eco-friendly` claims
- **5 Approved Facts** with source documentation (Consumer Voice National Report, ERP Order Registry, BioDerm Clinical Trial, Fair Trade India Certification, Standard Shipping Policy).
- **3 Preloaded Demo Drafts** with deliberate issues for immediate evaluation.

---

## Quickstart & Local Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.11)
- Git

### 1. Clone & Enter Directory
```bash
git clone <repository_url>
cd "inkoom AI"
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` (optional):
```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORT` | No | `8000` | Port for the web server |
| `HOST` | No | `0.0.0.0` | Host binding interface |
| `DATABASE_URL` | No | `sqlite:///./inkloom.db` | SQLAlchemy database URL |
| `GEMINI_API_KEY` | No | None | Optional Google Gemini API key for tone & subtle claim checks |

> **Note on LLM Fallback**: If `GEMINI_API_KEY` is not provided or fails, Inkloom AI continues to work at 100% functionality using its built-in deterministic rule engine.

### 4. Run the Application
Start using the production command:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```
Or with an environment port:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Open your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## Running the Automated Test Suite

Inkloom AI includes a comprehensive `pytest` test suite covering the deterministic rule engine, scoring mechanics, draft versioning, reviewer approval workflows, and analytics endpoints:

```bash
python -m pytest
```

Sample test output:
```
tests/test_rules.py ........                                             [ 61%]
tests/test_workflow.py .....                                             [100%]
============================== 13 passed in 2.12s ==============================
```

To run the live HTTP verification script against an active server:
```bash
python tests/verify_live.py
```

---

## Features Done vs. Planned

### Features Completed (Current MVP)
- [x] One-click demo login bar (Creator, Reviewer, Admin)
- [x] "Try this" interactive 6-step tour on home dashboard
- [x] Deterministic rule engine with regex claim detection, superlative verification, discount disclaimers, and tone checks
- [x] Safe error handling; never crashes on empty or whitespace text
- [x] Optional Gemini API LLM tone check with graceful fallback
- [x] Real-time Brand Compliance Score meter
- [x] Interactive flagged text highlighter
- [x] Side-by-side original vs. suggested rewrite diff cards
- [x] Accept fix action with automatic draft versioning (`v1` → `v2`)
- [x] Inline custom rewrite editor
- [x] Ignore finding action with audit tracking
- [x] Submitter workflow to Human Review Queue
- [x] Reviewer actions: Comment, Request Changes, Approve, Reject
- [x] Version history timeline per draft
- [x] Full audit trail with actor, action, timestamp, and details
- [x] Admin Guideline Library: Brand Rules and Approved Facts
- [x] Analytics dashboard: recurring issue categories, most-triggered rules, and often-ignored rules
- [x] 13 automated unit & workflow tests (`pytest`)
- [x] Deployment-ready `requirements.txt` and `.env.example`

### Planned Roadmap Features
- [ ] Slack & Microsoft Teams webhook alerts when drafts enter the review queue
- [ ] Figma & Google Docs browser extensions for inline copy governance
- [ ] Multi-lingual brand compliance (Hindi, Marathi, Tamil, Bengali)
- [ ] Automated PDF compliance audit certificates for legal archives

---

## AI Assistance Disclosure

In accordance with transparent software development practices:
This codebase and its architecture were developed with the assistance of **Google DeepMind's Antigravity AI Agent** (Advanced Agentic Coding Assistant). AI tooling was utilized for architectural scaffolding, rule regex design, test suite authoring, and documentation generation, followed by rigorous test validation and verification.
