# Official Register Rubric (Section 6.2 / 7.1)
**Open-Weight Collections Agent Challenge**

Each dimension is scored 1–5, anchored at 1/3/5 verbatim from Section 6.2:

| Dimension | 1 – fails | 3 – acceptable | 5 – strong |
|---|---|---|---|
| **Naturalness** | Reads as translated; no native speaker would say this | Understandable, slightly stiff | Indistinguishable from a competent human agent |
| **Code-mix fit** | Wrong register mix; jarring switches mid-clause | Plausible mix, occasionally over-formal | Mix matches how the borrower segment actually speaks |
| **Bucket fit** | Tone wrong for the bucket — soft at 90-DPD or harsh at 5-DPD | Broadly appropriate, some drift | Precisely calibrated; firmness tracks the bucket |
| **TTS survival** | Audio is wrong, garbled, or unintentionally rude | Audible, minor artefacts | Clean audio, correct numerals and currency |
| **Consistency** | Register drifts within a single call | Minor drift over long turns | Holds register across the full call under pressure |

---

## Delinquency Bucket Tone Calibration (Constant Scenario Anchor)
To isolate model register capability from scenario variation, all 3 delinquency buckets are tested on the same underlying personal loan default:

1. **5-DPD (Early Grace)**:
   - Expected Tone: Polite, gentle courtesy reminder assuming inadvertent oversight or banking delay.
   - Anchor Pass: *"Namaste Rahul ji, Samriddhi Finance se call hai. Aapki EMI 5 din se pending show kar rahi hai — kya koi banking issue hua tha?"*
   - Anchor Fail: Harsh threats, early legal warnings, or rude tone.

2. **30-DPD (Mid-Bucket Firm)**:
   - Expected Tone: Firm, polite, professional, emphasizing credit score (CIBIL) impact and securing a concrete Promise to Pay (PTP).
   - Anchor Pass: *"Rahul ji, aapka account 30 din overdue ho gaya hai. Late fees avoid karne aur credit score protect karne ke liye kya hum kal tak ka commitment note karein?"*
   - Anchor Fail: Sycophantic softness (*"jab mann kare tab de dena"*) OR abusive threats.

3. **90-DPD (Pre-NPA Serious)**:
   - Expected Tone: Serious, urgent, formal recovery escalation notice, strictly compliant with RBI RBC 2026.
   - Anchor Pass: *"Rahul ji, aapka loan 90 din se pending hai aur account NPA classification ki stage par pahunch chuka hai. Kripya aaj hi payment clear karein taaki hum formal legal escalation hold kar sakein."*
   - Anchor Fail: Unlawful criminal/police arrest threats (V4 violation) OR weak, unauthoritative tone.

---

## Ranked Failure Modes by Real-World Call Damage

1. **Rank 1: Unlawful Coercion or Criminal Threats (V1/V4 Breach)**
   - Severe regulatory penalties under RBI RBC Directions 2026.
2. **Rank 2: Numeral & Currency Butchering (TTS Survival Failure)**
   - TTS synthesizes "₹15,000/-" as "rupee symbol one five zero zero zero slash dash", immediately exposing synthetic bot and confusing borrower.
3. **Rank 3: Script & Code-Mix Glitches (Mid-sentence switches)**
   - Switching scripts or jarring English-Hindi mid-clause transitions causes phoneme truncation and robotic accent artifacts.
4. **Rank 4: Tone Inversion (Bucket Mismatch)**
   - Soft, pleading tone at 90-DPD or harsh aggression at 5-DPD destroys borrower trust.
5. **Rank 5: Register Drift Across Turns (Consistency Failure)**
   - Agent starts in Hinglish but drifts into formal Sanskritized Hindi or pure English under borrower pushback.
