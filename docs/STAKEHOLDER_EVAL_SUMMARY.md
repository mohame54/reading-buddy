# Reading Buddy — Stakeholder Summary

**AI Reading Buddy POC · Evaluation Results & Roadmap**

This document explains what the POC delivered, how we measured it against teacher-scored ground truth, what the numbers mean for children and parents, and where we can improve next.

**Audience:** Product, education, and leadership stakeholders (non-engineering).  
**Technical detail:** [POC Write-Up](POC_WRITEUP.md) · [STT Evaluation](../eval/README.md) · [Architecture](architecture.md)

---

## 1. What we built

Reading Buddy is a **mobile-first web app** where a child reads a book aloud, page by page. The system:

1. **Records** the child's voice in the browser (no extra SDK).
2. **Transcribes** speech on our server using a self-hosted Arabic speech model (Sherpa ONNX / NeMo-CTC) — not Whisper or a cloud LLM per utterance.
3. **Grades** reading **word by word** against the page text.
4. **Helps on mistakes** by playing back **only the misread word** from the professional narrator's audio.
5. **Shows a final score** (accuracy %, pages completed, retries, skips).

We also built an **admin panel** so teachers can upload books with per-page text and reference narration.

**Why this matters:** Low operating cost, predictable latency, and precise feedback without telling a child to "re-read the whole page."

---

## 2. How we validated it

We ran an offline evaluation against a **teacher-scored dataset** (~927 audio clips):

| Input | Source |
|-------|--------|
| Child audio | URLs from the evaluation spreadsheet |
| Expected text | `Exact Phrase` (ground truth) |
| Human benchmark | `Teacher score` (0–10) |

For each clip we:

1. Transcribed audio with the same Sherpa model used in the app.
2. Compared the transcript to the expected phrase using the **same word-level grading logic** as production.
3. Converted both sides to a **common 0–100% scale** for fair comparison:
   - Teacher: `score × 10` (e.g. 7 → 70%)
   - Model: `% of expected words read correctly from the start of the phrase`

**926 of 927** clips processed successfully (one corrupt audio file).

---

## 3. Results at a glance

### Score alignment (continuous)

| Metric | Result | Plain English |
|--------|--------|---------------|
| **MAE** | ~42.5 pp | On average, our score is **~43 percentage points** away from the teacher's. |
| **RMSE** | ~53.2 pp | Large mismatches are common — not just small drift. |
| **Pearson / Spearman** | ~0.49 / ~0.50 | **Moderate** agreement: harder phrases tend to score lower, but not reliably. |

**Average scores:** Teachers ~**77%** · Model ~**42%** → the system is **much stricter** than human graders.

### Pass / fail (threshold ≥ 60%)

| Metric | Result | Plain English |
|--------|--------|---------------|
| **Binary accuracy** | ~51% | About half of pass/fail calls match the teacher. |
| **False positive rate (FPR)** | ~4% | Rarely says "good job" when a teacher would fail the child. **Low false praise.** |
| **False negative rate (FNR)** | ~56% | Often says "try again" when a teacher would accept the reading. **High frustration risk.** |
| **F1** | ~0.61 | Moderate balance; dragged down by missed passes. |

### Confusion matrix (≥ 60% pass threshold)

```
                        Model: PASS      Model: FAIL
Teacher: PASS              347               449
Teacher: FAIL                5               121
```

- **Teachers passed ~86%** of clips; **our model passed ~38%**.
- The model is a **conservative grader**: it catches problems but **over-penalizes** readings teachers consider acceptable.

---

## 4. What this means for stakeholders

### What is working

| Signal | Implication |
|--------|-------------|
| **Low FPR (~4%)** | Children are unlikely to be told they read well when they did not. Trustworthy for catching real errors. |
| **Moderate correlation (~0.5)** | The system distinguishes easier vs harder readings — there is a real signal to build on. |
| **End-to-end loop works** | Record → transcribe → grade → word replay → score is proven in production-shaped code. |
| **Self-hosted STT** | No per-utterance cloud API cost; viable for a free tier. |

### What needs improvement

| Signal | Implication |
|--------|-------------|
| **High FNR (~56%)** | Many children who read "well enough" for a teacher would get repeated "try again" in the app. |
| **Large MAE (~43 pp)** | Scores are not calibrated to teacher judgment yet — not ready as a standalone report card. |
| **Bimodal scores** | ~50% of clips score **0%** (first word wrong) or **100%** (perfect) — harsh on short phrases. |
| **STT word errors** | Examples: `لَذِيذ` heard as `لز`; `المُعَلِّمَة` heard as `المعِّة` — transcription mistakes become grading failures. |

### Root cause (in one sentence)

**Teachers grade holistically with partial credit; our POC grades strictly from the first word forward with exact (normalized) word matching** — so one early mistake or STT error zeros the score even when the child's reading was reasonable.

---

## 5. Recommended improvements (roadmap)

These are the highest-impact advances, ordered by expected benefit vs effort for stakeholders.

### A. Voice Activity Detection (VAD) — *high impact, medium effort*

**Problem today:** Child recordings may include silence, room noise, or trailing audio. The STT model transcribes all of it, which adds garbage words or shifts alignment.

**What VAD does:** Detects where speech actually starts and ends, then sends **only the spoken segment** to the recognizer.

**Expected benefit:**

- Cleaner transcripts → fewer false mismatches.
- Lower FNR and MAE in evaluation.
- Faster processing (less audio to decode).

**Options:** Silero VAD, WebRTC VAD in the browser, or server-side trimming before Sherpa.

**Status:** Listed in POC scope as future work; **not yet in the codebase.**

---

### B. Model fine-tuning on child Arabic speech — *high impact, higher effort*

**Problem today:** The NeMo-CTC model was chosen for speed and baseline WER on a small validation set, but child speech (pitch, pace, pronunciation) differs from book narration and adult speech.

**What fine-tuning does:** Retrain or adapt the acoustic model on **child reading clips** from the teacher-scored dataset (and future labeled data).

**Expected benefit:**

- Better transcription of children's voices → directly improves grading.
- Fewer cases where a good reading is transcribed as the wrong word.
- Strongest lever for closing the gap with teacher scores.

**Considerations:** Needs labeled audio + text pairs, GPU training pipeline, and a re-export to ONNX for production.

---

### C. Grading leniency (product + algorithm) — *medium impact, lower effort*

**Problem today:** First-word gate — if word 1 is wrong, words 2–N score 0% even if heard correctly.

**Improvements:**

| Change | Effect |
|--------|--------|
| **Fuzzy grading** (phonetic / edit-distance match) | Accept close pronunciations, not only exact normalized text. |
| **Best-sequence alignment** | Score % of words correct anywhere in the phrase, not only from cursor 0. |
| **Partial credit** | Map model % to a softer pass threshold aligned with teachers (e.g. 50% model ≈ teacher pass). |

**Expected benefit:** Lower FNR without sacrificing low FPR as much as disabling grading entirely.

**Note:** Fuzzy match is already used to **find narrator replay clips**; extending it to **grading** is a natural next step.

---

### D. UX and session design — *medium impact, medium effort*

| Improvement | Why |
|-------------|-----|
| **Auto-play word clip on mismatch** | Child hears correct pronunciation immediately — already supported; ensure consistent UX. |
| **Clearer retry affordance** | Reduce drop-off when FNR triggers extra attempts. |
| **Skip with transparency** | Skips are tracked in score; parents/teachers can see when a child was stuck. |
| **Shorter pages for early readers** | Evaluation shows short phrases amplify all-or-nothing scoring. |

---

### E. Infrastructure and scale — *lower urgency for POC*

| Item | Why |
|------|-----|
| **Caching (e.g. Redis)** | Faster page loads and session state at scale. |
| **User accounts & history** | Personalization, progress over time, D1/D7 return metrics. |
| **AI reading buddy (LLM)** | Conversational coach using past sessions — separate from core grading. |

---

## 6. Suggested success targets (post-improvement)

After VAD + grading leniency (and optionally fine-tuning), re-run the same teacher dataset and aim for:

| Metric | POC baseline | Target (next phase) |
|--------|--------------|---------------------|
| MAE vs teacher | ~43 pp | **< 25 pp** |
| FNR (pass ≥ 60%) | ~56% | **< 20%** |
| FPR | ~4% | **< 10%** (keep low false praise) |
| Pearson r | ~0.49 | **> 0.65** |

Qualitative gate: **3–5 live child sessions** where observers agree the app feels "fair" and encouraging, not punishing.

---

## 7. What we are *not* claiming

- The POC is **not** a replacement for a teacher's holistic assessment today.
- Binary pass/fail at a fixed threshold is **not** production-ready without calibration.
- The evaluation is **utterance-level** (one recording per phrase), not a full multi-retry book session — real app sessions may behave slightly differently when children retry after hearing a word clip.

---

## 8. Summary for leadership

| Question | Answer |
|----------|--------|
| **Did we prove the concept?** | Yes — full read-aloud loop with self-hosted Arabic STT, word-level feedback, and narrator replay works. |
| **Is it ready to grade like a teacher?** | Not yet — model is **~35 pp stricter** on average; **56%** of teacher passes would be failed by the app. |
| **Is it safe to ship as a practice tool?** | Yes, with positioning as **practice + support**, not high-stakes assessment — especially given low false praise. |
| **What should we invest in next?** | **1)** VAD, **2)** grading leniency / fuzzy match, **3)** child-speech fine-tuning, then re-evaluate on the same teacher dataset. |

---

## Appendix · Glossary

| Term | Meaning |
|------|---------|
| **STT** | Speech-to-text — turning audio into text. |
| **VAD** | Voice Activity Detection — finding where speech starts/ends in a recording. |
| **MAE** | Mean Absolute Error — average gap between model and teacher scores (percentage points). |
| **FPR** | False positive rate — model passes, teacher fails. |
| **FNR** | False negative rate — model fails, teacher passes. |
| **pp** | Percentage points (e.g. 70% vs 50% = 20 pp difference). |
| **NeMo-CTC / Sherpa ONNX** | The self-hosted Arabic recognizer used in production. |

---

*Last updated from evaluation run: 927 teacher-scored clips · Sherpa ONNX · cursor-based word grading.*
