# BayMax — Demo Scenarios for Judges

8 test cases covering different cities, insurance plans, symptoms, and features.
Each scenario lists the exact profile to enter, what to say, and what to expect.

---

## How to start each scenario

1. Open `http://localhost:5000`
2. If already logged in → tap **⋮ → Log Out**
3. Fill in the profile from the scenario
4. Tap **📍 Map** → move the pin to the city coordinates shown
5. Hit **Get Started** — then type or speak the first message

---

## Scenario 1 — Emergency detection (English)
**Feature shown:** Emergency short-circuits all LLM calls. Nearest hospitals appear immediately.

### Profile to enter
| Field | Value |
|---|---|
| Name | Rahul Mehta |
| Phone | 9000000003 |
| City | Mumbai |
| Map pin | 19.0493, 72.8245 (Bandra) |
| Insurance | Star Health |

### What to say (first message)
> "I have chest pain and my left arm hurts and I am sweating"

### Expected response
BayMax immediately says (no Claude call, no pain scale, instant):
> *"This sounds serious. Please call 112 immediately."*

### Expected UI
- State changes to **EMERGENCY**
- Full emergency overlay opens automatically
- **Emergency panel** shows: 112, 108, iCall, Vandrevala, NIMHANS
- **Nearest hospitals** (because location is set):
  - Holy Family Hospital — 0.96 km — ☎ 022-26421111
  - Hinduja Hospital — 2.0 km — ☎ 022-24452222
  - Zen Multi Speciality Hospital — 2.72 km

### What this demonstrates
Emergency detection runs in <100ms before any API. Location → instant nearest hospitals. No routing, no cost, no insurance — patient needs to move NOW.

---

## Scenario 2 — Mild headache → General Physician (not Neurologist)
**Feature shown:** Conservative routing. Pain score 4 → ROUTINE → GP. Star Health badge on cards.

### Profile to enter
| Field | Value |
|---|---|
| Name | Priya Sharma |
| Phone | 9152987821 |
| City | Mumbai |
| Map pin | 19.0493, 72.8245 (Bandra) |
| Insurance | Star Health |

### What to say
**Turn 1:** "I have a headache"

### Expected: pain scale auto-fires instantly (no Claude)
> *"On a scale of 1 to 10, how much pain are you in?"*

**Turn 2:** "About a 4, it's been 2 days"

### Expected BayMax response
> *"A pain level of 4 for 2 days is something a General Physician can help you with. Before I find you options nearby, can you tell me if you also have fever, vomiting, or any blurring in your vision? Please see a doctor to confirm."*

**Turn 3:** "No fever, no vomiting, just the headache"

### Expected routing
- **Urgency:** ROUTINE
- **Department:** General Medicine
- **Doctor type:** General Physician (not a neurologist — correct for pain level 4)

### Expected hospital cards
- **Nearby:** 5 real doctors/hospitals near Bandra, sorted by distance
  - Each with: distance, rating, open/closed, 📞 Call button
  - **🛡 Star Health ✓** badge on hospitals in Star Health's network (Hinduja, Nanavati, Kokilaben etc.)
- **GIPSA:** Up to 8 Mumbai GIPSA-empanelled hospitals
- **Cost bar:** ₹300–800 OPD consultation | CGHS rate: ₹350

### What this demonstrates
- Headache defaults to GP (not neurologist) — because most headaches don't need a specialist
- Pain scale fires automatically, not via Claude
- Insurance badge shows which hospitals are cashless
- PMJAY badge: Rahul's phone 9152987821 → active PMJAY beneficiary → **PMJAY** green badge appears

---

## Scenario 3 — Severe knee pain → Urgent, Orthopedic Surgeon (Delhi, HDFC ERGO)
**Feature shown:** Pain score 7 → URGENT routing. Delhi results. HDFC ERGO badge.

### Profile to enter
| Field | Value |
|---|---|
| Name | Anil Gupta |
| Phone | 9876543210 |
| City | New Delhi |
| Map pin | 28.6315, 77.2167 (Connaught Place) |
| Insurance | HDFC ERGO |
| Age | 52 |

### What to say
**Turn 1:** "My right knee has been hurting for 3 weeks"

### Expected: pain scale fires
> *"On a scale of 1 to 10, how much pain are you in?"*

**Turn 2:** "About a 7, it's getting worse, especially when I climb stairs"

### Expected BayMax response
> *"A pain score of 7 that's been going on for 3 weeks and getting worse is something we should take seriously. You likely need an Orthopedic Surgeon for a proper assessment — a General Physician can refer you, but at this severity and duration, I'd recommend going directly. Please confirm with a doctor."*

### Expected routing
- **Urgency:** URGENT
- **Department:** Orthopedics
- **Doctor type:** Orthopedic Surgeon

### Expected hospital cards
- **Nearby:** Delhi hospitals — Fortis Memorial, Apollo Indraprastha, Max Saket, BLK-Max, Sir Ganga Ram
  - **🛡 HDFC ERGO ✓** on hospitals in HDFC ERGO's network (Fortis, Apollo, Medanta)
  - **State Scheme** green badge (phone 9876543210 → State Scheme eligibility → ₹1,55,000 remaining)
- **Cost bar:** ₹700–1800 OPD consultation | CGHS rate: ₹650
- Wait indicator shows estimated busyness (orange/red dot if weekday morning)

### What this demonstrates
- High pain score escalates urgency to URGENT (vs ROUTINE for pain 4)
- Delhi location returns Delhi hospitals
- Multiple insurance/coverage badges stack: HDFC ERGO + State Scheme

---

## Scenario 4 — Hindi speaker + PMJAY emergency
**Feature shown:** Translation layer. Hindi emergency → detected pre-translation. Response in Hindi.

### Profile to enter
| Field | Value |
|---|---|
| Name | Sunita Devi |
| Phone | 9152987821 |
| City | Mumbai |
| Map pin | 19.0760, 72.8777 (Andheri) |

### Language selector
Tap **हिंदी** in the chat header

### What to say (in Hindi)
> "मुझे सीने में दर्द हो रहा है" *(I have chest pain)*

### Expected response (Hindi)
> *"यह गंभीर लग रहा है। कृपया तुरंत 112 पर कॉल करें।"*

Emergency overlay opens. Nearest hospitals appear. PMJAY badge visible on eligible hospitals.

### What this demonstrates
- Hindi emergency keywords trigger instantly — no translation needed for safety
- Response rendered in Hindi
- Works even without Google translation API for this critical path

---

## Scenario 5 — Mental health + CGHS + Bengaluru
**Feature shown:** Psychiatry routing. CGHS coverage. Helpline numbers.

### Profile to enter
| Field | Value |
|---|---|
| Name | Ravi Nair |
| Phone | 9000000003 |
| City | Bengaluru |
| Map pin | 12.9352, 77.6245 (Koramangala) |
| Insurance | CGHS |
| Age | 45 |
| Medical history | Central government employee, no known conditions |

### What to say
**Turn 1:** "I have been feeling very anxious and depressed for months, I can't sleep properly"

### Expected BayMax response (no pain scale — no pain/ache words)
> *"I hear you, Ravi — what you're describing sounds difficult, and it's important to get proper support. Before I find the right specialist for you, can you tell me how long you have been feeling this way, and whether it's been affecting your work or daily life? Please see a doctor to confirm — I am not a doctor."*

**Turn 2:** "About 6 months, it's affecting my work badly"

### Expected routing
- **Urgency:** URGENT
- **Department:** Psychiatry
- **Doctor type:** Psychiatrist

### Expected hospital cards
- **Nearby:** Bengaluru hospitals — Manipal, Fortis Bannerghatta, Apollo, Narayana Health, Columbia Asia
  - **🛡 CGHS ✓** badge on CGHS-empanelled Bengaluru hospitals
- **Cost bar:** ₹800–2,500 OPD consultation | CGHS rate: ₹700
- **GIPSA hospitals** in Bengaluru listed below

### Emergency panel (always visible)
- iCall: 9152987821 — Mental health, IITB
- Vandrevala Foundation: 1860-2662-345 — 24/7

### What this demonstrates
- Mental health symptoms route to Psychiatry correctly (not General Medicine)
- Duration + impact = URGENT
- CGHS badge on government health scheme hospitals
- Mental health helplines always visible at bottom

---

## Scenario 6 — Child with fever + Pune + New India Assurance
**Feature shown:** Pediatrics routing. Pune location. PSU insurer.

### Profile to enter
| Field | Value |
|---|---|
| Name | Meena Kulkarni |
| Phone | 9000000003 |
| City | Pune |
| Map pin | 18.5090, 73.8173 (Kothrud, Pune) |
| Insurance | New India Assurance |
| Medical history | Calling for my 4-year-old child |

### What to say
**Turn 1:** "My 4-year-old has had a fever for 2 days and is not eating"

### Expected response (no pain scale — no pain/ache in text)
> *"A young child with fever and not eating for 2 days does need a doctor's attention today. Can you tell me how high the fever is — is it above 103°F or 39.4°C? Please confirm with a doctor."*

**Turn 2:** "The temperature is 102, she seems a bit lethargic"

### Expected routing
- **Urgency:** URGENT
- **Department:** Pediatrics
- **Doctor type:** Pediatrician

### Expected hospital cards
- **Nearby:** Pune hospitals — Ruby Hall Clinic, Deenanath Mangeshkar, Sahyadri, KEM Pune
  - **🛡 New India Assurance ✓** badge on New India network hospitals
- **Cost bar:** ₹400–1,200 OPD consultation | CGHS rate: ₹400
- **GIPSA hospitals** in Pune

### What this demonstrates
- Child symptoms correctly route to Pediatrics
- 102°F + lethargic = URGENT (not ROUTINE)
- Pune location returns Pune hospitals
- PSU insurer (New India Assurance) has the broadest network — most cards show the badge

---

## Scenario 7 — Treatment validation: Over-treatment (💊 Check Treatment tab)
**Feature shown:** RAG over NLEM 2022 + CGHS detects expensive, non-guideline treatment.

### No profile needed — switch to treatment tab directly

### What to enter in the 💊 Check Treatment tab
| Field | Value |
|---|---|
| Diagnosis | Type 2 Diabetes, newly diagnosed, HbA1c 7.2% |
| Treatment | Weekly GLP-1 agonist injection, SGLT2 inhibitor daily, continuous glucose monitor, monthly specialist visits |
| Cost | ₹45,000 per month |

### Expected output
**Treatment assessment:** ⚠ Some aspects are questionable

**Cost assessment:** ⚠ Cost is highly likely above guidelines

**Baymax says:**
> *"Your treatment plan uses medications that aren't listed in India's essential medicines guidelines for early diabetes, and your blood sugar is already well controlled, which raises questions about whether this level of treatment intensity is necessary right now. I strongly recommend getting a second opinion from another doctor."*

**Potential concerns:**
- May indicate over-treatment: NLEM 2022 lists Glimepiride and Metformin as first-line agents; GLP-1 agonists absent from essential medicines for early-stage T2D
- May indicate excessive specialist involvement: Monthly visits for well-controlled HbA1c 7.2%

**Guideline references:**
- NLEM 2022 Essential Medicines — antidiabetic medicines section: Metformin and Glimepiride listed; Semaglutide not in essential medicines list
- CGHS 2020 Handbook — standard diabetes management protocol

### What this demonstrates
- RAG retrieves relevant NLEM/CGHS sections
- Identifies treatment inconsistency without saying "wrong treatment"
- Cost flag without saying "overcharged"
- Always ends with second opinion recommendation

---

## Scenario 8 — Treatment validation: Under-treatment
**Feature shown:** Guideline-based detection of insufficient treatment.

### What to enter in 💊 Check Treatment tab
| Field | Value |
|---|---|
| Diagnosis | Hypertension, BP consistently 160/100 for 6 months |
| Treatment | Doctor advised lifestyle changes only — diet and exercise, no medication |
| Cost | ₹2,500 total |

### Expected output
**Treatment assessment:** ⚠ Likely inconsistent with guidelines

**Cost assessment:** ✓ Cost appears reasonable

**Baymax says:**
> *"Based on the guidelines, persistent high blood pressure at 160/100 for 6 months may indicate that lifestyle changes alone may not be sufficient, and medication is often recommended at this level according to standard treatment protocols. I strongly recommend getting a second opinion from another doctor."*

**Potential concerns:**
- May indicate under-treatment: Standard Treatment Guidelines recommend antihypertensive medication when BP consistently above 140/90 despite lifestyle modification
- Could suggest missing risk stratification: No mention of cardiovascular risk assessment

**Guideline references:**
- Standard Treatment Guidelines — Hypertension section: Medication indicated for Stage 2 hypertension (≥160/100)

### What this demonstrates
- Detects under-treatment, not just over-treatment — balanced in both directions
- Reasonable cost doesn't guarantee appropriate treatment
- Phrasing: "may not be sufficient" not "you're getting bad treatment"

---

## Summary: what each scenario demonstrates

| # | Scenario | City | Insurance | Key feature |
|---|---|---|---|---|
| 1 | Chest pain + left arm | Mumbai | Star Health | Emergency short-circuit, nearest hospitals |
| 2 | Mild headache, pain 4 | Mumbai | Star Health + PMJAY | GP (not neurologist), pain scale, insurance badge |
| 3 | Severe knee pain, pain 7 | New Delhi | HDFC ERGO | URGENT routing, Delhi hospitals |
| 4 | Hindi chest pain | Mumbai | PMJAY | Hindi emergency, translation layer |
| 5 | Anxiety + insomnia | Bengaluru | CGHS | Psychiatry, mental health helplines |
| 6 | Child fever, 102°F | Pune | New India Assurance | Pediatrics, PSU insurer, Pune hospitals |
| 7 | Diabetes over-treatment | — | — | RAG NLEM/CGHS, cost flag |
| 8 | Hypertension under-treated | — | — | Treatment inconsistency, both directions |

---

## Judge questions answered by these scenarios

**"Who benefits?"**
Scenario 2 + 4: Uninsured/underinsured patients navigating a fragmented system with language barriers

**"What if BayMax routes someone to the wrong doctor?"**
Every response ends with "please confirm with a doctor." BayMax routes, never diagnoses.

**"How does the insurance integration work?"**
Scenario 2 + 3: Pre-parsed insurer network JSONs, three-layer fuzzy name matching, badges on cards

**"What if the API is down?"**
Scenario 1: Emergency detection is purely local — no API, no LLM, just keyword matching. Always works.

**"Can it detect fraud or over-treatment?"**
Scenario 7 + 8: RAG over 5 official Indian medical PDFs with probability-language output
