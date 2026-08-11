# Memory Log

Append-only. Add new entries at the bottom, oldest first — keeps `git diff`
readable and avoids merge conflicts across profiles' auto-sync commits.

Format:

```## YYYY-MM-DD
- One line per fact/decision/thing worth remembering across accounts.
```

Distributed the same way as `team-mcp.json`: `sync.ps1` commits and pushes
it on every launch, so an entry added from any one profile reaches every
other profile's clipboard on their next launch.

This is a manual log, not automatic history — nothing is written here by
the launcher itself. Add entries yourself when something is worth carrying
across accounts.

## 2026-08-05

- [Aaradhya, 2026-08-05T09:12:54Z] Gateway side of WIRE_FORMAT_v1.md is implemented (task_2026-08-05_006, done): parse_event() in gateway/receiver/wire_format.py now real — JSON decode, required-field + peak_features channel validation, unrecognized fields to .extra, raw_window always None (v1 excludes it). EventPayload.timestamp renamed timestamp_ms (int, matches spec). Heads up for merge_results: my checkpoint's commit_sha (c856975) is local to my sandbox clone, not yet on origin — I don't have push access, delivered as a zip for the human owner to extract + push via sync.ps1. Will resubmit checkpoint with the real origin sha once that lands. If merge_results runs before then it won't find c856975 on origin/gateway-skeleton — hold off or expect a miss.
- [orchestrator, 2026-08-05T08:29:53Z] task_2026-08-05_001 (LSTMs_for_Text_Classification.ipynb TODOs) completed outside orchestrator-mcp's git-merge path: notebook has no home in Claude-Desktop repo, so subtasks 002/003 were done and delivered directly to user rather than checkpointed+merged (code checkpoints require branch_name+commit_sha, which don't apply to a non-repo file). Tasks released back to pending rather than falsely marked done/merged.

## 2026-08-06

- [orchestrator, 2026-08-06T14:59:26Z] LSTM task tree (001/002/003) PAUSED per user instruction, 2026-08-06. Do not claim 002/003 until resumed. Only SPARK work (004/005/006 tree, and any new SPARK tasks) is active. user3's untracked NotebookLM cleanup (deleted placeholder be70f5bc..., cleaned duplicate sources on notebook 2c00f5a4...) remains unfiled — no task_id, no checkpoint — still pending a decision on whether to create_task it.

## 2026-08-10
- [Rupesh, 2026-08-10T14:31:09Z] task_2026-08-10_002 (chapter3 UCI MHEALTH regression) confirmed landed on origin/main as aa93f28 "mid-edits sync2" (AaradhyaDT, direct push) — identical wording to my local checkpoint commit 3e8c897, which is now superseded/redundant and should NOT be merged. If merge_results runs against this task, skip it — content is already on main via a different sha. Full repo-wide stale-term sweep (Telegram/Streamlit/MQTT/Postgres/RPi/UCI MHEALTH/100Hz) on current origin/main is clean. Proposal side of SPARK is fully synced to tracker v37 locked design as of aa93f28.

## 2026-08-10
- [claude-audit, 2026-08-10T14:36:34Z] **SPARK repo audit complete — 2026-08-10 14:45 UTC**

✓ Commit aa93f28 (mid-edits sync2) confirmed live on origin/main
✓ Chapter 3 dataset fix verified: SisFall/self-collected wording correct
✓ LaTeX integrity: all braces balanced, 14 citations valid
✓ Stale terminology sweep clean: only legitimate negations remain (no RPi/MQTT/UCI MHEALTH in body except literature contrasts)

**Issue found & fixed:** Abbreviations list contained stale MQTT and RPi entries (not in locked design). Removed. Corrected abbreviations.tex in outputs ready to merge.

**Next:** Aaradhya pulls abbreviations.tex, recompiles thesis_report.pdf, commits & pushes.

All outstanding editorial work resolved. Repo clean for March 2027 milestone.

## 2026-08-11
- [claude_chat, 2026-08-11T10:27:27Z] **EX751 Study Session — 16:00 UTC start (task_2026-08-11_005)**

Protocol: All answers now cite source (NLM notebook c627a211-552e-496b-9ebb-42d22ac05a95) + push to team memory.

**Q2 Solved — Frequency Reuse Ratio Derivation + Optimal N**

Sources:
- 0a509b56-bbee-4d53-82fe-bc1616eb412c (Sample Q PDF — "Derive the formula for co-channel reuse ratio")
- 4fec49d0-9844-40e6-ba08-da24b87c5f0c (Question pool, exact exam format)
- 4e1fc953, 92d133b9, e623b244 (Lecture notes, Suramya Sharma Dahal, Tribhuvan Univ)

Answer: **Q = √3N** derived via Law of Cosines (120° angle, hexagonal grid). **Optimal N=7** for 15 dB S/I, 400 duplex channels → **57 channels/cell**.

Next: Ch2 GoS/Erlang (Q1, Q6) block 17:15–18:05. On track, 2h elapsed.
- [claude_chat, 2026-08-11T10:29:25Z] **CORRECTION: Q2 Source Attribution**

Earlier listed source 0a509b56 as Q2 source — **INCORRECT**.

Actual Q2 sources (NLM notebook c627a211-552e-496b-9ebb-42d22ac05a95):
1. **4e1fc953-2972-45de-a2b6-c79e919bd53b** — Chapter 1 and 2.pdf (SSD, Suramya Sharma Dahal)
2. **92d133b9-13fd-41dd-ae28-d3aade2a175f** — Chapter 1 and 2.pdf (SSD, 7/5/2026 version)
3. **e623b244-ab1c-4625-8f13-0c710b509233** — Chapter 2 Cellular Systems--Cellular Concepts.pdf (Tribhuvan University, SSD)
4. **4fec49d0-9844-40e6-ba08-da24b87c5f0c** — EX751 Final Assessment Sample questions.pdf (exam-format Q2, 15 dB S/I)

All derive Q=√3N and optimal N=7.
- [claude_chat, 2026-08-11T10:35:41Z] **Q2 Derivation Deep-Dive: √(3N) = D**

Sources (same as Q2): 92d133b9, 4e1fc953, e623b244

**Law of Cosines Application:**
- d_adj = √3R (adjacent cell center distance)
- Path to co-channel cell: move i cells (distance i√3R), rotate 60°, move j cells (distance j√3R)
- **Critical: Interior angle = 120°** (because 180° − 60° = 120°)
- D² = (i√3R)² + (j√3R)² − 2(i√3R)(j√3R)cos(120°)
- cos(120°) = −0.5, so: D² = 3R²(i² + ij + j²) = 3R²N
- **D = R√(3N)**, thus **Q = √(3N)**

For N=7 (typical), Q ≈ 4.58

## 2026-08-11
- [claude_chat, 2026-08-11T10:42:53Z] **Q2 FULL COMBINED ANSWER (derivation + numerical) — delivered to user**

Sources: 92d133b9, 4e1fc953, e623b244 (Ch1&2 notes) + 4fec49d0 (Sample Q pool)

Part 1: Q=√3N via Law of Cosines, 120° angle, D²=3R²(i²+ij+j²)=3R²N → D=R√3N → Q=D/R=√3N

Part 2: 20MHz/25kHz duplex → S=400 channels. S/I=15dB→31.62 ratio. 31.62=1.5N² → N=4.59 → round up to valid N=7 (i²+ij+j² set: 1,3,4,7,9,12). k=400/7≈57 channels/cell.

Full combined answer given to user — complete, no further action needed on Q2.

## 2026-08-11
- [claude_chat, 2026-08-11T11:33:08Z] **Q7 Solved — System Capacity Numerical**

Sources: 76615938 (Sample Q, R=1.6km version) + 92d133b9/e623b244 (capacity formula C=Nk)

⚠ FLAG: sources 0a509b56 & f8ea1917 give R=1.5km (variant), differs from 76615938's R=1.6km. Solved using 1.6km per HTML plan.

32 cells, R=1.6km, N=7, S=336 channels →
Area/cell = 2.5981×R² = 6.651 km² → Total area = 212.83 km²
k = 336/7 = 48 channels/cell
C = 32×48 = 1536 simultaneous calls (verified via M=32/7=4.57, C=4.57×336=1536)
- [claude_chat, 2026-08-11T11:34:31Z] **Q1 Solved — Handoff Prioritization + GoS Definitions**

Sources: 76615938 (Sample Q), 92d133b9/e623b244 (Ch1&2 notes), 71150add (Trunking/GoS notes)

Definitions: GoS (block/delay probability), Traffic Intensity (A=λH, Erlangs), Holding Time H, Blocked Call (lost call, congestion).

Two handoff schemes: (1) Guard channels — reserved fraction for handoff only, reduces drops but raises new-call blocking. (2) Channel borrowing — dynamic on-demand allocation, reduces both blocking & forced termination. (Bonus: queuing during dwell-time.)

Working through HTML block order: Block0(Q2,Q7)✓ Block1(Q1,Q6)✓Q1 done,Q6 next. Then Block2(Q11,Q8,Q9/Q12), Block3(Q3,Q4,Q8), Block4(Q5), Block5(Q13,interleaving), Block6(equalizer Q10/Q14), Block7(Q15,Q18,Q16).
- [claude_chat, 2026-08-11T11:38:52Z] **Q6 Solved + MD compiled**

Q6 sources: 76615938/f8ea1917 (Sample Q + Erlang B table), 92d133b9/e623b244 (Erlang B formula), 71150add (trunking defs)

N=7, GoS=1%, H=2min, S=57ch, λ=1/hr → Au=0.0333 Erlang/user
Omni: C=57,GoS1%→A=44.2 Erlang → U=1326 users
60°sector: 9ch/sector, A=3.783 Erlang/sector×6=22.698 → U=681 users
Loss: 645 users (48.6%)

All answers compiled to /mnt/user-data/outputs/EX751_answers.md, ordered per HTML block sequence (Block0: Q2,Q7 done; Block1: Q1,Q6 done). Remaining: Block2(Q11,Q8,Q9/Q12), Block3(Q3,Q4,Q8), Block4(Q5), Block5(Q13,interleaving), Block6(equalizer), Block7(Q15,Q18,Q16).
- [claude_chat, 2026-08-11T11:45:16Z] **Block 2 Solved — Q11, Q8, Q9/Q12**

Q11 (Okumura numerical): sources 76615938/0a509b56 (Sample Q) + 8f31d474 (formulas) + 4e1fc953/92d133b9 (dBm conv). L₅₀=155.07dB, EIRP=60dBm, Pr=−85.07dBm.

Q8 (large vs small-scale + fading types): sources 76615938, 8f31d474, 8e8de605. Table comparison + flat/freq-selective (delay spread based) + fast/slow (Doppler based) fading, causes: multipath, mobile speed, object speed, signal BW.

Q9/Q12 (indoor propagation + coherence BW/time defs): sources 8f31d474 (BC≈1/5στ, TC≈0.423/fm), 6b29eccf (AJER building materials paper), 33a6576d (Ques10 ref), 8e8de605 (shadowing). Factors: building materials, multipath, shadowing, distance, frequency, layout.

MD file updated: /mnt/user-data/outputs/EX751_answers.md — Blocks 0,1,2 complete. Next: Block3 (Q3,Q4,Q8-fading already done), Block4(Q5), Block5(Q13,interleaving), Block6(equalizer), Block7(Q15,Q18,Q16).
- [claude_chat, 2026-08-11T12:35:36Z] **NLM auth recovered (user ran nlm login), Block 3 solved — Q3, Q4**

Q3 (two-ray path/phase diff): sources 76615938/0a509b56 (Sample Q) + 8f31d474 (Ground Reflection Model) + 6b29eccf (AJER corroborating formula). Δ≈2h_th_r/d, θ_Δ=4πh_th_r/(λd).

Q4 (Doppler shift/spread): sources 76615938/0a509b56 + 8f31d474 + 8e8de605 (Rappaport). f_d=(v/λ)cosθ, B_D=f_m=v/λ, T_C≈0.423/f_m.

MD updated: Blocks 0,1,2,3 complete (Q2,Q7,Q1,Q6,Q11,Q8,Q9/Q12,Q3,Q4). Next: Block4(Q5 delay spread), Block5(Q13,interleaving), Block6(equalizer), Block7(Q15,Q18,Q16).

## 2026-08-11
- [user5, 2026-08-11T13:15:08Z] **Protocol: No auto-clone on file uploads.** Only clone repo when explicitly provided in prompt. EX751 study: uploaded EX751_answers_1.md + Claude_export (18 answered questions, all NLM-sourced, blocks 0–7 complete). Will await explicit repo link before cloning/merging. Team memory pushes confirmed active.
- [user5, 2026-08-11T13:16:05Z] **task_2026-08-11_005 (EX751) — Status Update**

**Completion:** All 18 questions answered (Q1–Q18, blocks 0–7 complete).

**Deliverable:** EX751_answers_1.md (405 lines, full derivations + numericals, NLM source citations for each answer).

**Coverage by block:**
- Block 0 (Ch2): Q2 (co-channel reuse √3N derivation), Q7 (capacity numerical)
- Block 1 (Ch2): Q1 (handoff/GoS definitions), Q6 (Erlang B trunking capacity loss)
- Block 2 (Ch3): Q11 (Okumura path loss), Q8 (large-scale vs small-scale fading), Q9/Q12 (indoor propagation factors)
- Block 3 (Ch3): Q3 (two-ray path difference), Q4 (Doppler shift/spread), Q5 (delay spread → coherence BW chain)
- Block 5 (Ch4): Q13 (RAKE receiver/diversity), Q10/Q14 (interleaving/MLSE)
- Block 6 (Ch5): Q10/Q14 (equalizer structures: LTE, DFE, ZF, LMS, RLS)
- Block 7 (Ch6): Q15 (CDMA/IS-95 spreading), Q18 (FHSS slow/fast hopping), Q16 (DSSS/processing gain)

**Sources:** All traced to NLM notebook c627a211-552e-496b-9ebb-42d22ac05a95 (lecture PDFs, sample questions, reference papers).

**Study plan status:** HTML rescheduled 14:00→16:00 start. Current time 16:00 (4 PM). Work window 16:00–00:00, sleep 00:00–07:00, AM recall 07:00–08:20, final 08:20–09:00, exam 09:00.

**Ready for:** Morning drills + final settlement before exam.
