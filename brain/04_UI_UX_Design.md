# UI/UX Design Document — v1.2
## Intelligent SQL Assistant

**Supersedes v1.1.** Central change: the main screen is no longer a ChatGPT-style chat log — it's an **analytical investigation surface**, built around the Reliability Score and Evidence Panel.

## 1. Design Principles (revised)
1. **Trust is the product, not a feature.** Every answer visibly carries its own evidence — this is not an optional tab a curious user might click.
2. **Progressive disclosure, corrected framing (fixes v1.1's internal contradiction):** *important evidence is visible by default; implementation detail is progressively disclosed.* Not "nothing is hidden" (too absolute) and not "technical only on demand" (buries evidence) — the Reliability Score and top-line evidence are always visible; SQL/raw validation logs are one click away.
3. **Refusal is a feature, not a failure.** Unsupported/unauthorized/ambiguous states are designed screens (§3.3–3.5), not error toasts.
4. **Security is demonstrated, not just documented** — the Security Attack Lab is a real, visible, re-runnable screen.
5. **Status uses icon + text + color together**, never color alone (WCAG, unchanged from v1.1).

## 2. Information Architecture (revised)

```
App Shell
├── Top Nav: Logo | Dataset Selector | Reliability threshold indicator | User Menu
├── Left Sidebar
│   ├── New Query
│   ├── Query History (rerun-by-default)
│   ├── Saved Reports
│   ├── Schema Browser (Semantic Catalog view — shows sensitivity tags per column)
│   ├── Security Attack Lab (admin)
│   ├── Failure Observatory (admin, P1)
│   └── Evaluation Lab (admin, P1)
└── Main Canvas
    └── Investigation Card (replaces v1.1's "Answer Card" — see §3.1)
```

## 3. Key Screens

### 3.1 Investigation Card (core UI unit — redesigned)

```
┌───────────────────────────────────────────────────────┐
│ QUESTION                                               │
│ Which region had the highest sales growth in 2025?    │
├───────────────────────────────────────────────────────┤
│ ANSWER                                                 │
│ West Region · +23.8%                                   │
│                                                         │
│ Reliability                         92 / 100  ✓ HIGH   │
├──────────────────────┬──────────────────────────────────┤
│ Evidence              │ Result                           │
│ ✓ Schema              │ West     +23.8%                  │
│ ✓ Join                │ South    +17.4%                  │
│ ✓ Filter               │ North    +13.1%                  │
│ ✓ Execution            │ East      +9.8%                  │
├──────────────────────┴──────────────────────────────────┤
│ Chart | Table | SQL | Explanation | Validation | Optimize | Replay │
└───────────────────────────────────────────────────────┘
```
- **Reliability badge** always visible at the top — color + numeric score + text label (HIGH/MEDIUM/LOW), never color alone.
- **Evidence column** is always visible (not behind a tab) — it's the left half of the card by default on desktop; collapses to a top strip on mobile.
- Tabs below are the *implementation detail* layer: Chart/Table/SQL/Explanation/Validation/Optimize/Replay — one click away, consistent with the corrected progressive-disclosure principle.
- If the SQL Critic raised a finding, a warning chip appears next to "SQL" tab: `SQL ⚠`.
- If the Result Validator raised an anomaly, a warning chip appears next to "Result": `Result ⚠ 1.2M rows`.

### 3.2 Ambiguity Clarification Screen (new)
```
"Show me top customers by revenue"

⚠ Ambiguity detected

"Revenue" could mean:
  ○ Gross order value
  ○ Net revenue
  ○ Revenue after refunds

Based on your database schema, net_revenue is available.

[ Use net revenue ]     [ Choose a different metric ]
```
Single targeted question, radio-button style, using real column names from the Semantic Catalog — never a generic "please clarify" text box.

### 3.3 Unsupported-Question Screen (new)
```
🔍 Unsupported Question

I can't answer this from the connected database.

Required evidence:  employee identity ↔ employee-sales relationship
Available tables:   customers · orders · products · sales

Try asking about one of the available tables instead.
```

### 3.4 Policy-Rejection Screen (new, distinct visual treatment from a system error)
```
🔒 Not Authorized

This question requires access to: employees.salary
Your role (Viewer) doesn't include this permission.

[ Request access ]   [ Ask a different question ]
```
Deliberately calmer/lower-alarm styling than a red error banner — this is an expected, correct system behavior, not a fault.

### 3.5 SQL Critic Warning (inline, within the Investigation Card's SQL tab)
```
⚠ Suspicious aggregation detected
`order_id` is an identifier column and is being summed.
Did you mean SUM(order_amount) or COUNT(order_id)?

[ Use suggested fix ]   [ Proceed anyway ]   [ Revise question ]
```

### 3.6 Security Attack Lab (new, admin-only screen)
```
SQL SECURITY LAB                                   [ Run Suite ]

Attack                              Stage Blocked At        Result
──────────────────────────────────────────────────────────────────
DROP TABLE users                     AST                     ✓ BLOCKED
UNION privilege escalation           Column Authorization    ✓ BLOCKED
Unauthorized table access            Schema Authorization    ✓ BLOCKED
Heavy Cartesian join                 Resource Limit          ✓ BLOCKED
Dangerous function (pg_sleep)        Function Allowlist      ✓ BLOCKED
Prompt injection ("ignore rules...")  Policy Engine           ✓ BLOCKED

128 attacks · 128 blocked · Violation rate: 0.00%
Last run: CI build #482, 2 hours ago
```
Table rows use ✓/✗ icon + text ("BLOCKED"/"NOT BLOCKED"), never color alone. A "NOT BLOCKED" row renders in red with a bold warning banner above the table, and this state should fail CI per `08_Rules.md` R6.6.

### 3.7 Failure Observatory (P1, new, admin-only)
```
FAILURE OBSERVATORY                          Last 30 days

Schema hallucination     ████████████████████  31
Join error               ██████████████        22
Ambiguous intent         ███████████           18
Semantic mismatch        █████████             14
Type mismatch            ███████                11
Authorization rejection  █████                   9
Timeout                  ████                    6

Top problematic phrase: "active customer"  (11 occurrences)
Recommended intervention: extend Semantic Catalog definition + add clarification rule
```

### 3.8 Evaluation Lab (P1, new, admin-only)
```
EVALUATION LAB

Run: 2026-XX-XX · 240 questions · 10 categories

                Baseline A   Baseline B   Baseline C   Proposed (D)
Simple             71%          88%          89%           93%
2-3 join           34%          52%          61%           77%
Ambiguous           —            —            —        81% (clarification accuracy)
Adversarial         —            —            —         0% (violation rate)

[ View per-category detail ]   [ Export report ]
```

### 3.9 Query Replay Screen (new)
```
QUERY RUN #1842                                   [ Replay Query ]

Question: "Show sales for July"
SQL (view) | Dialect: postgresql | Schema snapshot: v2026-03-01
Prompt version: v1.4 | Model: gpt-4o-mini | Params: temp=0.1
Validation: ✓ Authorized ✓ Read-only ✓ Critic clean
Execution plan (view) | Latency: 1.8s | Result hash: a91f...
Correction history: none
```
If replaying against a since-changed schema: `⚠ Schema has changed since this run (v2026-03-01 → v2026-05-12) — results may differ.`

### 3.10 Schema Browser → Semantic Catalog view (revised from v1.1's plain tree)
```
employees
  ├─ employee_id        identifier
  ├─ salary             monetary  🔒 HIGH sensitivity
  ├─ department_id      categorical  (Engineering, Sales, HR)
  └─ hire_date          temporal
```
Sensitivity tags are visible to help users understand *why* a question might be refused — this doubles as documentation for R2.4's clarification requirement.

## 4. Visual Design System (unchanged from v1.1, plus:)
- New semantic color for **refusal states** (unsupported/unauthorized): a calm slate/gray-blue, distinct from error-red, since these are correct behaviors, not faults.
- Reliability Score badge uses a 3-tier color+label system: HIGH (green, ≥80), MEDIUM (amber, 50–79), LOW (red, <50) — always paired with the numeric score and the text label.

## 5. Accessibility (unchanged from v1.1, plus:)
- Evidence Panel content has a screen-reader-equivalent linear reading order (Interpretation → Schema Evidence → SQL → Validation → Result → Reliability), matching its visual layout.
- Security Attack Lab and Failure Observatory tables have full text alternatives to any bar-chart visualization.

## 6. Responsive Behavior (unchanged from v1.1)

## 7. Empty & Error States (extended)
- Unsupported/Unauthorized/Ambiguous are now **designed states** (§3.2–3.4), not generic empty states.
- Persistent self-correction failure: apologetic, specific message + "Report this" (feeds Failure Observatory).

## 8. Usability Testing Checklist (extended)
- Do users correctly interpret the Reliability Score as evidence-based rather than "another AI confidence number they should ignore"?
- Do users engage with SQL Critic warnings (proceed/revise) rather than reflexively dismissing them?
- Is the refusal-state styling (§3.3/3.4) read as "the system is being careful" rather than "the system is broken"?
- Can an admin user find and run the Security Attack Lab without guidance?
