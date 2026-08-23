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

## 2026-08-13
- [chat, 2026-08-13T06:29:45Z] task_2026-08-13_001 is CANCELLED — do not claim/execute. It was created on a misread of the user's request (single-account file-merge). Superseded by a new task for cross-account /topics consolidation. If you see task_2026-08-13_001 pending, ignore/skip it.
- [chat, 2026-08-13T06:30:18Z] [task_2026-08-13_002 — /topics export from account "chat"]

## /topics/coursework.md
- [stated] Elective I subject EX 725 04 — Aeronautical Telecommunication
- [stated] RF and Microwave Engineering Lab reports generated (Lab 1: ADS introduction; Lab 3: impedance matching via Smith Chart, ADS 2021, exercises achieving S11 ≈ −49 to −51 dB at 2 GHz)
- [stated] Aeronautical Telecommunication exam notes compiled covering Primary/Secondary Radar, CNS, ATM, ICAO standards
- [stated] BEI IV/II syllabus converted to Markdown for reference

## /topics/hobbies.md
- [stated] Plays guitar; 7 years, almost entirely self-taught by ear; has prior solo performance experience
- [stated] Can play 20 different instruments
- [stated] Does bodyweight training, no gym
- [stated] Gaming handle "WolframBlade" (COD Mobile origins)
- [stated] Interested in purchasing a 2020–2022 Yamaha FZS FI V2/V3 under Rs. 2 lakhs
- [stated] Has a bespoke 10ml extrait perfume called "Peace in a Bottle" (Spring 0.80ml, Vanilla Sexy 0.72ml, Bergamot 0.59ml; ~21.1% concentration, made at Poshon.np)
- [stated] Interest in Vedic astrology as a framework for self-understanding
- [stated] LEO Club involvement spans 5+ years across two clubs including charter membership

## /topics/home-network.md
- [stated] Prolink PRN3002 router lost config after reboot; required factory reset and full reconfiguration via PowerShell script (Setup-PRN3002.ps1)
- [stated] Script debugged and working; LAN reconfigured to 192.168.1.2

## /topics/recent-work.md
- [stated] CV updated to July 11, 2026 version; pre-existing 4-page overflow noted but not yet resolved
- [stated] ATS-optimized CV produced with table-based header replaced by plain paragraph structure; headshot removed from ATS version; all experience bullets rewritten with [X] metric placeholders

## /topics/tech-stack.md
- [stated] Core stack: Python, HTML/CSS/JS, SQL/SSMS, Arduino/ESP32, ML basics, SciPy, LaTeX
- [stated] Ubuntu dual-boot (manual partitioning + driver config); Windows system hardening (CTT selective + OOShutup10)
- [stated] Portable USB AI engine (Ollama + AnythingLLM + Dolphin 3 Llama 8B with custom batch launcher)
- [stated] Workflow: venv/pip freeze/GitHub sync via VS Code
- [stated] Completed minor project GCSBR (Gesture-Controlled Self-Balancing Robot): PID control (Kp=16.48, Ki=0.8, Kd=45), MPU-6050, MediaPipe, Arduino, DRV8825 stepper drivers — praised by examiners as "major project level"
- [stated] Alpha Android app and SysOptimizer are additional ongoing projects
- [stated] BloodVault (blood donation records web app) built as a functional CRUD testing demo
- [stated] Skills as listed for Makerspace Ambassador bio: Embedded systems (ESP32, Arduino), TinyML/edge AI (TFLite Micro), Android dev (Kotlin, Jetpack Compose), Python/ML, PCB & robotics projects, GitHub Pages web development, 3D printing/design, laser cutting
- [stated] Never pays for AI tools — works entirely within free-tier limits, using the maximum they legally allow

Status: this account's export complete. Waiting on other accounts to push theirs before consolidation step can run.
- [chat, 2026-08-13T06:30:46Z] task_2026-08-13_002 — SCOPE CORRECTION: not /topics/ only. Full memory tree per account: /profile.md, all /areas/*.md, all /people/*.md, all /topics/*.md, /preferences.md — everything. Re-run steps 1–3 of the task spec against memory_list() with no path_prefix (full listing), not just "/topics/". This account's earlier push (topics-only) is incomplete — see the follow-up push below for the full export, which supersedes it.
- [chat, 2026-08-13T06:31:32Z] [task_2026-08-13_002 — FULL memory export from account "chat", supersedes the topics-only push above]

## /profile.md
- [stated] Name: Aaradhya Dev Tamrakar
- [stated] BEI IV/I student at Kathmandu Engineering College (KEC), studying Electronics Communication and Information Engineering (ECIE) under IOE, Tribhuvan University
- [stated] Vice Chair of IEEE KEC KTM Student Branch
- [stated] Fusemachines AI Fellowship Fellow
- [stated] KEC Makerspace Ambassador (web development track)
- [stated] Primary Gmail: aaradhyadevtmr@gmail.com; secondary: devtamrakaraaradhya83@gmail.com

## /areas/6g-rf-presentation.md
- [stated] Topic: "Emerging RF systems: RIS, ISAC, Green RF and AI integration" — 6 speakers, 15 min total presentation
- [stated] Speaker order: Aaradhya, Dolraj, Nayan, Rupesh, Sankalpa, Anustha
- [stated] Aaradhya (the user) opens with introduction and core topics; is male (he/him)
- [stated] Content difficulty taper: peak = Aaradhya, mid = Dolraj/Nayan/Rupesh/Sankalpa (flat, all equal), low = Anustha (wants the easier closing part)
- [stated] Works from Claude_export .md files uploaded at the start of each session to continue prior work

## /areas/fairness-bias-audit.md
- [stated] Capstone swapped from Ward Office Assistant to Fairness & Bias Audit, supervisor Shreejan Kisee (same supervisor as prior registration)
- [stated] Team of 2: user + Tisha (Tisha Manandhar)
- [stated] User studies BEI (Electronics, Communication and Information Engineering) at IOE; Tisha studies BCT (Computer Engineering) at IOE
- [stated] Task split under discussion, not yet finalized/distributed — user asked to hold off distributing tasks
- [stated] Score-comparison approach (W2/W4 Classroom grades) dropped as a basis for the split; user decided to treat Wk5 SHAP scores as similar/not the deciding factor for now

## /areas/fusemachines-fellowship.md
- [stated] Around Week 10/24; onboarded April 2026
- [stated] Repo naming convention: fuseAiF_wk[N]_[topic]
- [stated] Week 9 steel surface defect CNN (NEU-DET dataset, fuseAiF_wk9_neu_defect_cnn) submitted; Week 9 score not yet posted
- [stated] Week 8 (S&P 500 forecasting, 9-model benchmark, 4-model ensemble, Diebold-Mariano p=0.0092) completed and added to CV/master profile
- [stated] Week 7 covered customer segmentation
- [stated] Week 1 covered Python data wrangling and SQL (Classic Models database)
- [stated] Study plan documents designed to be self-executing with either VS Code Copilot agent mode or Claude conversational mode

## /areas/kec-makerspace-website.md
- [stated] KEC Makerspace website (KEC-innovation/makerspace-main) audited across four rounds
- [stated] Issues found: malformed <img> attribute pattern (48 instances, root-caused to optimizer scripts), font faux-bold rendering (Changa One/Gravitas One weight-400 only), WCAG AA contrast failure on --text-faint, navbar animation proposals
- [stated] Jetson Orin Nano sourcing completed May 21, 2026
- [stated] Phase 1 items locally available (Daraz/ONIN/Exort/Quality Computer); USB-TTL to check Giga Nepal/RoboNepal; IMX219 camera + enclosure to order abroad (Ubuy Nepal, REES52 India, AliExpress)
- [stated] Device requires 22-pin FPC cable; requirements doc at v5 with sourcing page appended

## /areas/makerspace-ambassador-bio.md
- [stated] Role/affiliation caps for team.html: MAKERSPACE AMBASSADOR — WEB/IT · KATHMANDU ENGINEERING COLLEGE
- [stated] LinkedIn: https://www.linkedin.com/in/aaradhya-dev-tamrakar/
- [stated] Skills line for the bio: Embedded systems (ESP32, Arduino), TinyML/edge AI (TFLite Micro), Android dev (Kotlin, Jetpack Compose), Python/ML, PCB & robotics projects, GitHub Pages web development, 3D printing/design, laser cutting
- [stated] Bio approved after iteration; final version pushed to orch team-memory (account user_2) for cross-account pickup
- [stated] team.html currently has no Ambassador card markup — only a "Currently Hiring" placeholder under Advisors
- [stated] makerspace-main repo clone blocked in this sandbox — no GitHub auth configured

## /areas/master-profile-system.md
- [stated] Strict versioned master profile document system (AARADHYA_MASTER.md), currently v147 with 59 changelog entries
- [stated] Single source of operational truth across sessions
- [stated] Standing workflow: explicit changelogs, non-destructive historical preservation, cross-document consistency checks
- [stated] Recently completed a complex file reconstruction session to produce AARADHYA_MASTER.md and CHANGELOG.md from a conversation archive

## /areas/nexus.md
- [stated] Nexus personal AI OS project (React/FastAPI/SQLite+FTS5) reached a working state with Notes UI and Project system prompt editor functional
- [stated] Nexus AI workflow hub does multi-model orchestration (Groq + Gemini), FastAPI + React/Vite, SQLite+FTS5
- [stated] Active personal infrastructure project

## /areas/personal-notebook.md
- [stated] NotebookLM notebook id: 95a79d26-2f87-42cd-8cb9-8361a1e56059
- [stated] Title: "Aaradhya — Engineer's Personal Notebook" (⚙️), 9 sources, owned, not shared

## /areas/portfolio-site.md
- [stated] GitHub Pages site at Aaradhya-Dev-Tamrakar.github.io
- [stated] Expanded to multi-page structure (index, projects, experience, about, contact); initially a single index.html at aaradhyadtmr.github.io
- [stated] Filter/search toolbar added on projects.html
- [stated] CSS glow token system (--glow-gold*/--glow-teal*), warm-shifted dark-mode background tokens, AAA contrast compliance confirmed
- [stated] Second repo AaradhyaDTmr exists as an older iteration
- [stated] Contact form uses EmailJS (primary, auto-reply) → Formspree → mailto fallback; live and tested
- [stated] Contact form overhauled from broken Formspree placeholder to full three-tier EmailJS/Formspree/mailto chain
- [stated] Pending fixes: README field name correction, profilePhoto default to "photo.jpg" (never null), profile photo upload, CV download button
- [stated] In index.html, always set profilePhoto: "photo.jpg" (never null); comment should reference "photo.jpg" not "assets/photo.jpg"

## /areas/spark.md
- [stated] SPARK = Signal Pattern Analysis & Real-time Kinetics; full title includes "Explainable Edge AI for Kinetic Pattern Recognition and Distress Signaling"
- [stated] Major project: wearable fall detection system
- [stated] Architecture: ESP32-S3 two-unit wearable, MPU6050 IMU, two-layer TFLite Micro CNN pipeline, laptop-only gateway with SHAP/FastAPI/PostgreSQL/Streamlit/Telegram
- [stated] Hardware locked: ESP32-S3-WROOM-1-N16R8-CAM ×2 replaced the original ESP32 DevKit V1
- [stated] Raspberry Pi 4B gateway dropped entirely in favor of a laptop-only host
- [stated] Confirmed BOM ~NPR 15,004
- [stated] Department funding negotiation ongoing for RPi line-item removal (Action #31)
- [stated] Signed submitted proposal still names the superseded hardware — known defence talking point with supervisor Er. Dipen Manandhar
- [stated] Teammates: Rupesh Kadel (firmware, WP 2.0, highest execution risk), Sankalpa Lamsal, Sonia Thapa
- [stated] Renamed from FallGuard/PrakopNet → SPARK in late June 2026
- [stated] SPARK tracker document at v21
- [stated] Mid-term defence occurred July 13, 2026
- [stated] LaTeX proposal package iterated extensively (v17→v24+): BOM restructuring, system flow diagram rebuilt to print-safe B&W 2×2 grid, Algorithm 5.1 formalization, wearable component figures, grammar/caption corrections
- [stated] LaTeX proposal built from scratch following KEC's six-chapter IEEE-formatted structure, compiled via Overleaf
- [stated] MPU6050 XYZ axis SVG/PNG icon created for presentation deck
- [stated] PowerPoint deck audited and corrected (CNN kernel sizes, GAP vs. Flatten, literature table) ahead of July 9 proposal defence
- [stated] Project direction evolved: Counter-UAV → HimalGuard (LoRa mesh multi-hazard EWS) → PrakopNet → SPARK
- [stated] PrakopNet archived June 29, 2026 due to import-only hardware constraints
- [stated] SPARK NotebookLM notebook id: 2c00f5a4-98dc-4783-96d1-3682fa3cb516, title "SPARK: Two-Layer Edge AI for Wearable Fall Detection", 48 sources

## /people/dipen-manandhar.md
- [stated] Er. Dipen Manandhar — supervisor for the SPARK major project

## /people/rupesh-kadel.md
- [stated] SPARK teammate; owns firmware, WP 2.0; flagged as highest execution risk

## /people/sankalpa-lamsal.md
- [stated] SPARK project teammate

## /people/sonia-thapa.md
- [stated] SPARK project teammate

## /topics/coursework.md
- [stated] Elective I subject EX 725 04 — Aeronautical Telecommunication
- [stated] RF and Microwave Engineering Lab reports generated (Lab 1: ADS introduction; Lab 3: impedance matching via Smith Chart, ADS 2021, exercises achieving S11 ≈ −49 to −51 dB at 2 GHz)
- [stated] Aeronautical Telecommunication exam notes compiled covering Primary/Secondary Radar, CNS, ATM, ICAO standards
- [stated] BEI IV/II syllabus converted to Markdown for reference

## /topics/hobbies.md
- [stated] Plays guitar; 7 years, almost entirely self-taught by ear; has prior solo performance experience
- [stated] Can play 20 different instruments
- [stated] Does bodyweight training, no gym
- [stated] Gaming handle "WolframBlade" (COD Mobile origins)
- [stated] Interested in purchasing a 2020–2022 Yamaha FZS FI V2/V3 under Rs. 2 lakhs
- [stated] Has a bespoke 10ml extrait perfume called "Peace in a Bottle" (Spring 0.80ml, Vanilla Sexy 0.72ml, Bergamot 0.59ml; ~21.1% concentration, made at Poshon.np)
- [stated] Interest in Vedic astrology as a framework for self-understanding
- [stated] LEO Club involvement spans 5+ years across two clubs including charter membership

## /topics/home-network.md
- [stated] Prolink PRN3002 router lost config after reboot; required factory reset and full reconfiguration via PowerShell script (Setup-PRN3002.ps1)
- [stated] Script debugged and working; LAN reconfigured to 192.168.1.2

## /topics/recent-work.md
- [stated] CV updated to July 11, 2026 version; pre-existing 4-page overflow noted but not yet resolved
- [stated] ATS-optimized CV produced with table-based header replaced by plain paragraph structure; headshot removed from ATS version; all experience bullets rewritten with [X] metric placeholders

## /topics/tech-stack.md
- [stated] Core stack: Python, HTML/CSS/JS, SQL/SSMS, Arduino/ESP32, ML basics, SciPy, LaTeX
- [stated] Ubuntu dual-boot (manual partitioning + driver config); Windows system hardening (CTT selective + OOShutup10)
- [stated] Portable USB AI engine (Ollama + AnythingLLM + Dolphin 3 Llama 8B with custom batch launcher)
- [stated] Workflow: venv/pip freeze/GitHub sync via VS Code
- [stated] Completed minor project GCSBR (Gesture-Controlled Self-Balancing Robot): PID control (Kp=16.48, Ki=0.8, Kd=45), MPU-6050, MediaPipe, Arduino, DRV8825 stepper drivers — praised by examiners as "major project level"
- [stated] Alpha Android app and SysOptimizer are additional ongoing projects
- [stated] BloodVault (blood donation records web app) built as a functional CRUD testing demo
- [stated] Skills as listed for Makerspace Ambassador bio: Embedded systems (ESP32, Arduino), TinyML/edge AI (TFLite Micro), Android dev (Kotlin, Jetpack Compose), Python/ML, PCB & robotics projects, GitHub Pages web development, 3D printing/design, laser cutting
- [stated] Never pays for AI tools — works entirely within free-tier limits, using the maximum they legally allow

## /preferences.md
- [stated] Prefers direct, no-preamble interaction
- [stated] Prefers terse, command-style work sessions
- [stated] IEEE student branch is always "IEEE KEC KTM Student Branch" — never omit "KTM"
- [stated] Commit messages: always output as a single fenced code block, git-CLI-ready for direct copy/paste + Enter — no separate prose explanation alongside it

Status: this account's FULL export complete (20 files, all sections above). Waiting on other accounts to push their full exports before consolidation step can run against everyone's data.
- [user_2, 2026-08-13T06:24:39Z] KEC Makerspace Ambassador bio — Aaradhya Dev Tamrakar, finalized draft for team.html:

Aaradhya is a fourth-year BEI student and our Ambassador on the Web/IT track. Between IEEE (he's Vice Chair of the KEC KTM branch) and the Fusemachines AI Fellowship, he builds — his portfolio, embedded projects, the odd broken workflow he decides needs fixing. His own site proves the habit: multi-page, custom-styled, with a contact form he rebuilt three layers deep so it never silently fails. Fun facts: his minor project was a gesture-controlled self-balancing robot. The rest of him runs on the same make-do streak: 7 years of guitar and 20 instruments, all self-taught by ear; workouts with no gym, no equipment; and a refusal to pay for a single AI tool — free tier, pushed as far as it legally goes.

Skills: Embedded systems (ESP32, Arduino), TinyML/edge AI (TFLite Micro), Android dev (Kotlin, Jetpack Compose), Python/ML, PCB & robotics projects, GitHub Pages web development, 3D printing/design, laser cutting.

LinkedIn: https://www.linkedin.com/in/aaradhya-dev-tamrakar/
Role/affiliation caps: MAKERSPACE AMBASSADOR — WEB/IT · KATHMANDU ENGINEERING COLLEGE

Status: bio approved by user, ready for insertion. Still blocked — makerspace-main repo (KEC-innovation/makerspace-main) needs auth to clone in this sandbox (no GitHub token configured), and team.html has no existing Ambassador card markup to match against — only a "Currently Hiring" placeholder under Advisors. Need either repo access or the target team.html Ambassador-section markup pasted in to deliver the actual file edit + commit message.

## 2026-08-13
- [user_3, 2026-08-13T06:37:57Z] [task_2026-08-13_002 — export from account "user_3"]

NOTE ON FORMAT: this account has no memory_list/memory_read tool exposed — I cannot enumerate or read a /profile.md, /areas/*.md, /people/*.md, /topics/*.md, /preferences.md tree the way the task spec assumes. What follows is Claude's own memory-system content available in this session's context (a flatter structure, not the orch per-account file tree). Treat as a different-shaped source, not a literal /topics export.

## Work context
- BEI Year III/Part II student at Kathmandu Engineering College (KEC, IOE), expected graduation January 2027
- Roles: IEEE KEC Vice Chair, Fusemachines AI Fellow (AIF 2026), Event Manager at EPC Club, STEAM Instructor Intern at Robo Tech Nepal, KEC Maker's Space contributor

## Personal context
- DOB Jan 6, 2005, Kathmandu
- Games (Valorant, Warhammer 40K), does 3D printing, interests in RF/microwave engineering and aviation systems
- Family: father (53, NLIC Senior Agency Manager), mother (48, IOM health screening), younger brother (+2 Science/Computer, Damak, Jhapa); family land in Damak, Jhapa (illiquid)

## Top of mind (as of this session)
- Exam prep: EX751 (Wireless Communications) and CT653 (Artificial Intelligence)
- SPARK project (wearable fall detection, ESP32-S3, KEC Makerspace team) — tracker v36, procurement consolidated
- Fusemachines Week 14 assignment: agentic routing/intent classification (encoder vs decoder SLM benchmarking, Bitext dataset)

## SPARK project
- Team: Aaradhya, Rupesh Kadel, Sankalpa Lamsal, Sonia Thapa; supervisor Dipen Manandhar
- Hardware locked: ESP32-S3 MCU, MPU6050 IMU, 1100 mAh LiPo, laptop-only gateway
- Repo: Aaradhya-Dev-Tamrakar/SPARK
- NotebookLM notebook id: 2c00f5a4-98dc-4783-96d1-3682fa3cb516

## Portfolio website
- GitHub Pages at Aaradhya-Dev-Tamrakar.github.io (v38+)
- NotebookLM knowledge base id: 95a79d26-2f87-42cd-8cb9-8361a1e56059
- Canonical count validator: scripts/verify.py (baseline v38: achievements=36, projects=22, journey=34)

## Fusemachines AI Fellowship
- Week 14: encoder vs decoder SLM benchmarking, repo fuseAiF_wk14_agentic_routing
- Capstone: BiasAperture (AI fairness diagnostic tool), teammate Tisha Manandhar, supervisor Shreejan Kisee

## Courses
- EX725 (Aeronautical Telecommunication): ILS presentation, RF lab reports (Labs 3-4)
- EX751, CT653 exam prep (current)

## Tools and environment
- Windows (username: Aaradhya), PowerShell 7, WSL2, OneDrive-redirected Desktop
- GitHub: AaradhyaDT / Aaradhya-Dev-Tamrakar
- Communication style preference: terse, directive, execution-first, minimal re-prompting

## Canteen price list
- College Staff: Veg Khana = Rs. 100; Hostel Students: Rs. 5 less on all Khana items

Status: this account's export complete under the above caveat. This is Claude's persistent-memory content, not a native /topics/ file tree — flag for whoever runs consolidation.

## 2026-08-15
- [claude_chat, 2026-08-15T04:36:10Z] **Skill update — assume-reader-intelligence (writing style)**

Added `references/project-reports.md` variant for SPARK/BiasAperture/thesis/IOE report writing. SKILL.md frontmatter now also triggers on report/thesis writing requests, pointing to the reference file.

Report-mode overrides vs base skill:
1. Cut term definitions harder — examiners (Dipen Manandhar/SPARK, Shreejan Kisee/BiasAperture) are domain experts, don't define CNN/TFLite/IMU/SHAP/fairness metrics/EU AI Act/NIST AI RMF etc. Only define project-specific coined terms.
2. Do NOT cut methodology/design-choice justification for density (base skill's "let reader infer" rule doesn't apply here) — reasoning is the gradable deliverable, not just the conclusion.
3. Epistemic hedges (scope limits, dataset/validity caveats) are required content by default, not defensive padding to trim.
4. Fixed report structure, formal register (no contractions, no "the real problem is" style casual confidence), exact benchmark figures, precise regulatory citations, LaTeX conventions (keywords A–Z, `10 mm` spacing) folded in.

Packaged as .skill, delivered to user for install. Any account drafting SPARK/BiasAperture/thesis prose should consult this variant.

## 2026-08-15
- [claude_chat, 2026-08-15T09:32:08Z] BiasAperture (github.com/Aaradhya-Dev-Tamrakar/BiasAperture) — parallelization plan, WBS/schedule per report/src/chapters/systemArchitectureAndMethodology.tex §Work Breakdown Structure + §Project Plan and Schedule (repo's own source of truth, not invented). 2 people (Aaradhya, Tisha) working the actual WBS Stream A/B split; 4+ orch accounts available as compute lanes on top of that, not additional owners.

WP1 — Classifier Selection & Schema Lock (WBS 1.1/1.2, Together, blocking). Fixes classifier baseline + internal schema: image_id, race/gender/age subgroup fields, predicted/true labels; detection-engine output additionally needs metric name, point estimate, CI bounds, p-value, subgroup sample size. Ends M1. Nothing in WP2/WP3 should start against this schema until locked.

WP2 (1.3, Stream A) / WP3 (1.4, Stream B) — parallel from M1.
- Stream A: dataset acquisition + integrity check, inference run, schema curation, stratified dev subset (FairFace primary; UTKFace only if descope budget allows).
- Stream B: HTML/Jinja2 report template, Model Cards/Datasheets structure, hand-written mock metrics dictionary validating against WP1's field set.
Converge M2.

WP4 (1.5, Together) — Statistical Detection Engine. Consumes Stream A's test matrix, produces the schema-shaped metrics dict Stream B's template expects. AIF360 + Fairlearn backends, 4 disparity metrics (demographic parity diff, equalized odds diff, equal opportunity diff, disparate impact ratio), chi-squared test, bootstrap CI, sample-size guard. Ends M3.

WP5 (1.6, Together) — Integration: mock-to-real swap of Stream B's dict, orchestration module.

WP6/WP7 (1.7/1.8, Together) — V&V (runtime targets, report-completeness rule, case-study run) → M4; then scope-boundary statement, final report, submission package.

Compute-lane assignment for the 4+ accounts: 1 acct executing Stream A, 1 acct executing Stream B, 1 acct running continuous schema-conformance check of both streams' output against WP1's locked field list (catch drift before M2, not at integration), 1 acct floating for WP1/WP4/WP5 Together phases or starting docs (1.8) early since scope-boundary statement doesn't depend on stream convergence.

Descoping order if behind schedule (report's own cutlist, in order): 1) web UI, keep CLI only, 2) UTKFace, keep FairFace only, 3) PDF export, keep HTML only, 4) direct in-process inference, keep predictions-file ingestion only, 5) AIF360, keep Fairlearn only (last resort, only cut that weakens cross-validated claim). Non-negotiable core never cut: data ingestion, one model interface, the fairness engine, one report format, the scope-boundary statement.

Status as of push: repo currently contains ONLY the LaTeX proposal report (report/, docs/, vendor/) — no implementation code yet. No orch tasks created for this yet (user said chat-only for now, not stood up as tasks). No other account has touched BiasAperture — first orch mention of this repo. NLM notebooks dd5fe5c6-bb39-4d35-b23b-332fd2b98de4 and 99bee3c6-07ed-4ff0-8ac8-0027b18ad06a (linked this session, neither matches the known 95a79d26 "Engineer's Personal Notebook") were NOT read — nlm auth was stale/expired this session (refresh_auth confirmed stale, needs `nlm login` on user's end), so their content is unverified and not folded into this plan.

## 2026-08-21
- [claude-spark-orchestrator, 2026-08-21T01:50:12Z] Context for anyone claiming a SPARK deep-research track (task_2026-08-21_002 through _020, parent task_2026-08-21_001):

1. NLM auth was stale as of this planning session (refresh_auth returned "stale", not recoverable without `nlm login` on Aaradhya's machine) — the two notebooks he pointed this session at (95a79d26-2f87-42cd-8cb9-8361a1e56059, personal notebook; 2c00f5a4-98dc-4783-96d1-3682fa3cb516, main SPARK notebook) were NOT queried this session. Check auth before assuming they're unreachable for you too.

2. A third relevant notebook exists per task_2026-08-12_003's own spec: 3b67fc33-d1db-4609-9947-cd4e5bdac235 ("secondary SPARK notebook," 45 sources — 4 original + 41 methodology-research sources via deep search). Literature tracks (1/2/3/16 especially) should check this before starting from zero — it may already have relevant sourcing. task_2026-08-12_003 (pending, unclaimed) wants 19 methodology/citation-verification sources deleted from the main 2c00f5a4 notebook since they're now redundant with this secondary one — that cleanup is orthogonal to the research tracks, don't block on it.

3. team-context.md is still the unedited template (checked via read_team_context this session) — no durable cross-profile context is loaded for any account yet. Aaradhya should fill it in; not something an executor task can fix.

4. Repo state this plan was built against: github.com/AaradhyaDT/SPARK main @ 53f194de7cd0679c866d905275b465f80c0d9bfb, tracker v54 (Aug 20 2026). If your clone is behind this, `git pull` before trusting any "already resolved" boundary stated in a track spec.

## 2026-08-22
- [claude-spark-orchestrator, 2026-08-22T06:18:26Z] Correction to my earlier entry (pushed same session) re: NLM notebooks — auth has since been refreshed by Aaradhya, all 3 notebooks now checked directly:

- 3b67fc33-d1db-4609-9947-cd4e5bdac235 ("SPARK Project Tracker: ESP32-S3 Hardware Upgrade and Design Reference") — the 41 methodology-research sources are GONE (Aaradhya deleted them as irrelevant). Now just 4 sources: fig_cnn_architecture.png, SPARK_Presentation_Proposal_Defense deck, SPARK_Proposal_20260701_v37.pdf, SPARK_TRACKER_v8_20260709.md. NOTE: that tracker copy is v8 (2026-07-09) — far behind live repo's v54. Don't treat this notebook as current for anything tracker-related; it's proposal/presentation reference only now.
- 2c00f5a4-98dc-4783-96d1-3682fa3cb516 ("SPARK: Two-Layer Edge AI for Wearable Fall Detection") — 6 real academic/reference sources already loaded, directly useful for several research tracks: (1) "Comparison of low-complexity fall detection algorithms for body attached accelerometers", (2) "Evaluation of a threshold-based tri-axial accelerometer fall detection algorithm" (PubMed), (3) Nepal National Population and Housing Census 2021 population projections, (4) SisFall dataset paper (Semantic Scholar), (5) "TensorFlow Lite Micro: Embedded ML on TinyML Systems" (MLSys Proceedings), (6) WHO Global report on falls prevention in older age. Tracks 5 (TFLite Micro alternatives), 7 (SisFall taxonomy), 8 (elderly-vs-young validity), 16/17 (related work/motivation) should start here before searching cold.
- Track 8 lead: SisFall's own paper source_describe explicitly states detection algorithms trained on young adults often fail to maintain sensitivity/accuracy on elderly populations — directly on-point for the 18-35-cohort-as-elderly-proxy question. Start there.
- 95a79d26-2f87-42cd-8cb9-8361a1e56059 (personal notebook) — confirmed to also mirror SPARK README/TRACKER/CHANGELOG/WIRE_FORMAT via GitHub-source links, plus cross-project sources (BiasAperture, portfolio site, and a Claude-Desktop repo containing team-context.md/team-memory.md as tracked files — i.e. this orchestrator's own state may itself be git-backed at github.com/Aaradhya-Dev-Tamrakar/Claude-Desktop, unconfirmed, no link given to act on this directly).

## 2026-08-22
- [user14, 2026-08-22T08:16:51Z] NLM auth is stale as of 2026-08-22T08:15Z — refresh_auth returns "reason: stale, disk reload cannot revive expired credentials, run `nlm login` in a terminal." Could not query notebook 2c00f5a4 (main SPARK) or 95a79d26 (personal) for Track 14. Proceeded on external web research only, flagged as a limitation in Track 14's checkpoint. Other tracks planning to "check NLM before external research" (user15+ per their live-status notes) may hit the same wall — needs an interactive `nlm login` from Aaradhya's terminal to clear.
- [user15, 2026-08-22T08:20:40Z] task_2026-08-21_016 (Track 15, aquatic/drowning IMU params) — DONE, checkpoint submitted. Repo used: github.com/AaradhyaDT/SPARK (matches team-context/task_2026-08-21_001 authoritative name, not the stale Aaradhya-Dev-Tamrakar one user4 flagged). Clone HEAD 53f194de7cd0679c866d905275b465f80c0d9bfb matches tracker v54 stamped commit — no drift. NLM 2c00f5a4 auth was stale at session start, refresh_auth fixed it in one call. Summary: stroke-cadence 0.4-1.6Hz well-supported by literature; IDR >2.5Hz struggle-index has no traceable source anywhere (Pia's IDR is qualitative-only) — flagged as unvalidated estimate; >15s submersion timeout brackets between real precedents (Poseidon camera systems=10s, one wearable Sensors paper's ~60s window) but isn't itself derived from either. Full detail in checkpoint result_text.
- [user17, 2026-08-22T08:15:31Z] Track 17 (task_2026-08-21_018): NLM auth stale again this session (refresh_auth confirmed stale) — same issue orchestrator flagged then said was fixed 2026-08-22 06:18; may have re-expired since. Could not query 2c00f5a4 to double-check for commercial-product sources before web searching, but per orchestrator's 06:18 entry the 6 sources there are all academic/dataset (SisFall, WHO falls report, TFLite Micro paper, etc.) — no commercial-product content, so proceeding to cold web search was safe/non-duplicative. Flagging for any other account hitting this: nlm needs a fresh `nlm login` from Aaradhya again.
- [user22, 2026-08-22T08:20:13Z] user22 acting as SPARK deep-research orchestrator check-in (2026-08-22). Board status: 17/19 child tracks (task_2026-08-21_002–_020) done. Remaining: Track 15/task_016 (aquatic distress, user15) and Track 16/task_017 (related-work synthesis, user16), both still 'claimed' (in progress, not blocked). No action needed yet — will re-check before running merge_results. Also flagging for the record: the task-assignment doc handed to this account named the repo as Aaradhya-Dev-Tamrakar/SPARK and a nonexistent user22 track — same stale-repo-name issue user4 already flagged. No repo was cloned under that wrong name.
- [user4, 2026-08-22T08:12:41Z] task_2026-08-21_005 (Track 4, sensitivity-boosting literature) — DONE, checkpoint submitted. Flag for other track-claiming accounts: the task-assignment doc some of us are being handed names the repo as github.com/Aaradhya-Dev-Tamrakar/SPARK — that's stale/wrong. Authoritative per read_team_context + task_2026-08-21_001 is github.com/AaradhyaDT/SPARK @ 53f194de7cd0679c866d905275b465f80c0d9bfb (tracker v54). Cloned the AaradhyaDT one, matched the stamped commit exactly, no issue — just don't clone the Aaradhya-Dev-Tamrakar name if you see it in your own task doc.

## 2026-08-22
- [user5, 2026-08-22T13:24:14Z] Standing workflow instructions (repo gate, sync.ps1 protocol, file delivery, output constraints, nlm notebooks):

**Instructions**
Verify before responding —
1. Recommend a model + effort level + whether extended thinking is needed for this prompt, so it can be switched manually if needed.
2. Before any clone/pull/git tool call: state one line — `repo link/path given this turn: yes` or `repo link/path given this turn: no`. This line is mandatory and not skippable, and must be stated before the tool call, not after. If "no" and no repo has been cloned/pulled yet this session, do not clone or pull — ask which repo rather than assuming. If "no" but a repo was already cloned/pulled earlier in this session, treat a clear pull/sync request ("pull the repo," "check latest," "sync it") as referring to that repo and `git pull` it — state which repo you're assuming. If "yes" and already cloned this session, `git pull` instead of re-cloning.

Diff any new/uploaded content against live repo state (title/search-index diffs, id↔href integrity, syntax, tag balance) before delivering; discover actual repo conventions via inspection, never assume. Be maximally concise — no preamble, no filler. Dive straight to work. Follow the best practices related to the work being done.

When Claude_export md files are present, read them first then continue the work from previous session.

**Abbreviations**
1. nlm — Notebook LM, also relates to the MCP.
2. orch — orchestrator MCP for Claude Desktop.

**Personal details context (nlm):**
- Personal: ⚙️ Aaradhya — Engineer's Personal Notebook | id `95a79d26-2f87-42cd-8cb9-8361a1e56059`
- SPARK: https://notebook.google.com/notebook/2c00f5a4-98dc-4783-96d1-3682fa3cb516
- BiasAperture: https://notebook.google.com/notebook/99bee3c6-07ed-4ff0-8ac8-0027b18ad06a

Clone GitHub links added as prompt rather than fetching, as fetching generally returns error.

**sync.ps1 check — mandatory, self-reporting gate:**
Any time a repo is cloned or pulled this session, explicitly state one line: `sync.ps1: found` or `sync.ps1: not found`. This line is not optional and is not skippable.
- If not found (or no repo touched this turn): skip the sync.ps1 workflow entirely, commit normally with a plain commit message.
- If found: the workflow below is mandatory for every edit in that repo for the rest of the session — no plain `git commit`, no exceptions, no silent reversion.

### Local Git Workflow & Auto-Sync (`sync.ps1`)
To prevent merge conflicts on `assets/js/last-commit.json` (updated automatically by a commit-back bot on every push):
- **Minor / Routine Changes:** `.\sync.ps1`
- **Major Features / Architectural Changes** — update `dev-logs/PortfolioWebsite_TRACKER.md` first, then: `.\sync.ps1 -m "feat(scope): detailed architectural summary"`
- **Safe Pull Only:** `.\sync.ps1 -PullOnly`

For `.ipynb` notebooks, do not execute them — run manually in Google Colab or locally.

**File delivery**
- Individual file edits, however small: save to outputs directory, deliver as a file — never inline.
- Whole repo or multi-file reorg: zip preserving repo-relative paths, deliver as a file.

**Output constraints (strict)**
1. Output only the modified/updated content, edits, or targeted change.
2. No conversational framing, lead-ins, or post-explanations.
3. No commentary on what changed or why, unless asked — except: flag regressions/conflicts found during verification in one line, and one-line reasoning notes when a decision needed disambiguation.
4. Verification (diff, syntax/balance checks, cross-ref greps) shown inline as part of the work, not narrated. If a check fails, halt and flag before delivering.
5. Every edit ends with: commit message, and — only if the sync.ps1 gate above is active — the bare `.\sync.ps1 -m "..."` command in the same block. No `cd`, no other preamble.
6. That block is the last thing in the response — no summary, no sign-off after.

**General principle:** What you explicitly command is what gets done. Anything not explicitly instructed — repo choice, scope, ambiguous formatting calls — gets asked about first.

## 2026-08-22
- [user1, 2026-08-22T17:45:02Z] BiasAperture 20-track research board (task_2026-08-22_002): constraint — no git commit/push to the repo from any of the 20 users until all 20 child tracks (task_2026-08-22_003..022) are done. Each user works in their local clone, saves output to research/results/XX_*.md, and holds it uncommitted. Single consolidated commit/push happens only after the full board is done, to avoid mid-sprint drift on the shared CONTEXT.md ground truth.
- [user1, 2026-08-22T17:45:24Z] BiasAperture 20-track research board (parent task_2026-08-22_002): NO commit/push to the repo from any of the 20 users until all 20 child tracks are submitted/done. Work locally, save results to research/results/ locally, hold. Aaradhya will do a single consolidated commit after merge_results — avoids 20 uncoordinated pushes and mid-sprint drift on research/CONTEXT.md.
- [user1, 2026-08-22T17:46:25Z] BiasAperture 20-track research board (parent task_2026-08-22_002) — correction: no repo write access needed for any of the 20 users, and no git push at all. Handoff is via submit_checkpoint(result_text=<markdown output>) only. Aaradhya does the single consolidated commit himself after merge_results. Supersedes prior note about "save locally and hold."
