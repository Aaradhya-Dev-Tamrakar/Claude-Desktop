---
name: cross-linking-hub
description: Aaradhya's map of which GitHub repos and Google NotebookLM notebooks belong together, and which notebook is the central hub. Use whenever work touches a repo or notebook in this project, when logging/summarizing progress, when asked "which notebook does X belong to" or similar, or before treating any repo/notebook as standalone. Always consult this before cross-referencing project status across repos/notebooks.
---

# Cross-Linking Hub

Fixed map of Aaradhya's personally maintained repos and notebooks, and how they relate. Apply without asking. If a new repo or notebook is mentioned that isn't in this map, ask where it fits rather than guessing.

## Hub

**Engineer's Personal Notebook** (NLM `95a79d26-2f87-42cd-8cb9-8361a1e56059`) is the central hub. It is the notebook progress/status from leaf repos and notebooks eventually gets logged or summarized into. Treat it as the parent node in any cross-linking task.

## Leaf nodes

| Repo | Linked NLM | Notes |
|---|---|---|
| `AaradhyaDT/BiasAperture` | BiasAperture — Fairness and Bias Audit Engineering and Implementation Strategy (`99bee3c6-07ed-4ff0-8ac8-0027b18ad06a`) | Direct 1:1 link. |
| `AaradhyaDT/SPARK` | SPARK: Two-Layer Edge AI for Wearable Fall Detection (`2c00f5a4-98dc-4783-96d1-3682fa3cb516`) | Authoritative research notebook; `3b67fc33` serves as proposal/deck reference. Tracker: `dev_logs/SPARK_TRACKER.md`. |
| `Aaradhya-Dev-Tamrakar/Aaradhya-Dev-Tamrakar.github.io` | Engineer's Personal Notebook (hub itself) | Portfolio/CV/study-hub repo — feeds directly into the hub notebook, not a separate leaf notebook. |
| `Aaradhya-Dev-Tamrakar/Claude-Desktop` | none | Standalone. No NLM cross-link exists. |
| `Aaradhya-Dev-Tamrakar/FuseAIF2026` | none *(unconfirmed)* | Fellowship-related repo; distinct from SPARK. Do not assume link without confirmation. |

## Unlinked notebooks

*(None currently active — all primary project notebooks are mapped to leaf repos or the central hub.)*

## Coursework notebooks (IV/I, exam sequence order)

No linked repos — standalone exam-prep notebooks, feed into the hub notebook for status only.

| Order | Subject | Exam Date | NLM |
|---|---|---|---|
| 1 | EX751 — Wireless Communications | Sep 4, 2026 (2083 Bhadra 19) | `c627a211-552e-496b-9ebb-42d22ac05a95` |
| 2 | CT704 — Digital Signal Analysis and Processing | Sep 8, 2026 (2083 Bhadra 23) | `bc8653c3-a1d3-42b7-bca1-cd8e4effc038` |
| 3 | CT653 — Artificial Intelligence | Sep 12, 2026 (2083 Bhadra 27) | `96a12a04-073e-43ca-9f6d-ca0048d63486` |
| 4 | EX752 — RF and Microwave Engineering | Sep 16, 2026 (2083 Bhadra 31) | `c3c8ecd4-2884-42a1-aa49-c4de168c1ec7` |
| 5 | ME708 — Organization and Management | Sep 20, 2026 (2083 Ashoj 4) | `94cd4e14-802d-4231-b27d-6a4f4a2e6182` |
| 6 | EX725 04 — Aeronautical Telecommunication | Sep 24, 2026 (2083 Ashoj 8) | `56cdad30-13d3-4621-a0b7-8f841858476b` |

## Query Protocol (Token Savings)

Before performing ANY web search for a topic covered by a linked notebook:
1. Check this hub for matching NLM notebook ID
2. Use `notebooklm-mcp` → `notebook_query` with the notebook ID
3. Only fall back to web search if NLM returns insufficient results

Cost comparison:
- Web search round-trip: ~3,000–5,000 tokens (query + results + re-read)
- NLM notebook_query: ~500–1,000 tokens (pre-curated, citation-linked)

## Pending

- If a 4th repo, or a notebook/repo outside the sets above, surfaces, treat it as unmapped — ask where it fits before using it in any cross-linking or status-summary task.

## Application rules

1. **Status/progress summaries**: when asked to summarize or log project status, route leaf-repo/leaf-notebook content toward the hub notebook framing, not sideways to unrelated leaves.
2. **No silent linking**: never infer a repo↔notebook relationship not listed above, even if names or topics seem to match (e.g. don't auto-link SPARK to FuseAIF2026).
3. **This map is fixed but not final**: update it (via explicit instruction, not inference) as new repos/notebooks are added or confirmed.
