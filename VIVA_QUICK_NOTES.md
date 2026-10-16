# Viva Quick Notes - Multi-Agent Disaster Management Simulator (Updated)

## 1) What is this project? (Say this to your guide)

**In simple words:** It is a **web-based simulation** of disaster emergency response. The computer treats emergencies like fires or cyclones as **data**. Specialized pieces of software (**agents**) pretend to be roles—finding incidents, assigning ambulances and rescue teams, running rescue, and scoring results—moving step-by-step through a **state machine** so nothing skips phases accidentally. The **dashboard** (React) talks to the **backend** (FastAPI). Results are **saved in SQLite** plus **printed JSON logs** for proof.

**Technical name:** Multi-Agent Disaster Management Simulator with orchestration, analytics, and smart suggestions.

---

## 2) Why did we build it?

To show **coordinated emergency-style decision-making** that you can **audit** (every step logged), **repeat** (seed), and **measure** (lives saved, efficiency, utilization)—and to compare **Smart vs Baseline** strategies.

---

## 3) What are the main parts of the workspace?

| Part | Folder / files | What it does |
|------|----------------|--------------|
| **Backend API + orchestrator** | `Multi-Agent-System/` | Runs the pipeline, saves DB, exposes REST API |
| **React dashboard** | `multiagent project/` | Browser UI on port **3000** |
| **Core CLI simulator** (optional demo) | `main.py`, `state_manager.py`, etc. | Separate grid simulator; **not** what the dashboard uses |
| **Synopsis diagrams** | `docs/diagrams/` | ER diagram, architecture, use cases, sequence, DFD |

---

## 4) Which agents run in the web/backend pipeline?

1. **IncidentDetectionAgent** – reads each disaster record → priority, risk.  
2. **ResourceAllocationAgent** – decides teams + resources (ambulance, fire_force, etc.).  
3. **RescueCoordinationAgent** – mock rescue result (how many rescued vs affected).  
4. **EvaluationAgent** – efficiency, lives saved, resource_usage label.

**Orchestrator state flow:**  
`INIT` → `INCIDENT_REPORTED` → `RESOURCE_ALLOCATED` → `RESCUE_IN_PROGRESS` → `COMPLETED` (or `ERROR`).

---

## 5) New / advanced features (important for viva)

- **Strategy:** `smart` (improved rules) vs `baseline` (simpler rules)—chosen in UI, sent in `POST /api/run`.  
- **Enhanced database:** not only `run_logs`—also `users`, `simulation_runs`, `incidents`, `agent_logs`, `run_metrics`.  
- **Analytics API:** `GET /api/analytics/summary` (totals across all runs).  
- **Smart Suggestions:** `GET /api/suggestions` looks at past runs and suggests seed/strategy and text tips.  
- **Diagram pack:** PNG files under `docs/diagrams/images/` for slides/synopsis.

---

## 6) API endpoints you should know

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Backend alive check |
| POST | `/api/run` | Body: `{ "seed": number, "strategy": "smart" \| "baseline", "user_id": 1 }` |
| GET | `/api/runs` | List run IDs |
| GET | `/api/run/{run_id}/history` | State + JSON payloads |
| GET | `/api/run/{run_id}/status` | RUNNING / COMPLETED / ERROR |
| GET | `/api/run/{run_id}/incidents` | Rows saved per run |
| GET | `/api/analytics/summary` | Aggregate stats |
| GET | `/api/suggestions?seed=...` | Recommendations |

**Swagger docs:** `http://localhost:8000/docs` (only works when backend is running).

---

## 7) What each dashboard section means (match your screenshot)

### Run Controls (top left)

- **API Health ONLINE/OFFLINE** – Can the browser reach the backend? If OFFLINE, fix backend first.  
- **Seed** – Number that fixes randomness so runs are **repeatable**; change it = different random behaviour inside agents.  
- **Strategy** – Smart (Advanced) vs Baseline – changes how aggressively teams/resources are assigned.  
- **Start Run** – Starts one full pipeline over `data/input_data.json` (~150 incidents).  
- **Reset View** – Clears **only** what you see on screen; **does not** delete database runs.  
- **Refresh Runs** – Reloads run list from backend.  
- **Selected Run** – UUID of one execution; pick another to see old history.  
- **Message / Latest State / Run Status** – Human-readable progress; status goes RUNNING → COMPLETED.

### Final Metrics (top right)

Shown when history has a `COMPLETED` step:

- **Total incidents** – How many disaster records processed in that run.  
- **Total affected** – Sum of `people_affected`.  
- **Total lives saved** – Sum from evaluation.  
- **Overall efficiency** – `(lives_saved / affected) × 100%` style aggregate.  
- **Resource utilization** – Label **optimal** vs **suboptimal** from efficiency threshold.  
- **Strategy** – Which strategy was used for that run.

### Analytics Summary (middle left)

Roll-up **across all runs** in the database: total runs, incidents, lives saved, **strategy_breakdown** JSON.

### Smart Suggestions (middle right)

Plain-English tips from querying metrics (e.g. “cyclone had highest average affected”, “prefer smart”, “try seed X”). Buttons **Apply Seed** / **Apply Strategy** copy recommendation into controls.

### State Transition History (bottom)

Each row = one **state** + **timestamp** + **payload** (JSON). This proves the **state machine** ran in order.

---

## 8) Diagram images (`docs/diagrams/images/`)

| File | What it shows |
|------|----------------|
| `01_er_diagram.png` | Database tables and relationships |
| `02_system_architecture.png` | User → React → FastAPI → agents → SQLite |
| `03_use_case_operator.png` | What an operator can do |
| `04_use_case_admin.png` | What an admin could do (reports, compare strategies) |
| `05_sequence_diagram.png` | Order of messages: UI → API → DB → Smart module |
| `06_data_flow_diagram.png` | High-level data movement |

**Editable source:** open `docs/diagrams/PROJECT_DIAGRAMS.html` in a browser.

---

## 9) Ports and URLs

- **Dashboard (what you show):** `http://localhost:3000`  
- **Backend API:** `http://localhost:8000`  
- **API docs:** `http://localhost:8000/docs`

---

## 10) Port 8000 “not opening” — checklist

1. **Start backend from the right folder:**  
   `cd d:\multi_agent_bug_detector\Multi-Agent-System`  
   `python -m pip install -r requirements.txt`  
   `python app.py`  

2. **Read the terminal** – If Python crashes (ImportError), fix install; if “address already in use”, another program uses 8000.

3. **Try in browser:** `http://127.0.0.1:8000/docs` (sometimes works when `localhost` fails).

4. **Firewall** – Allow Python through Windows Firewall if prompted.

5. **Wrong expectation** – The **pretty UI is port 3000**, not 8000. Port 8000 is mostly JSON + Swagger.

---

## 11) Limitations (honest viva answers)

- Simulation uses **synthetic/JSON** data, not live government feeds.  
- No real GIS map in UI (could be future work).  
- Two code paths exist: **CLI `main.py`** vs **orchestrator pipeline**; the **dashboard** uses the **orchestrator** only.

---

## 12) One-line conclusion

> We built a full-stack, multi-agent disaster-response **simulation** with a **traceable state machine**, **SQLite persistence**, **Smart vs Baseline comparison**, **analytics**, and **data-driven suggestions**—demoable through a React dashboard.

---

## Simple demo flow for guide

1. Show **API Health: ONLINE**.  
2. Pick **Smart**, set seed, **Start Run**.  
3. Point to **Run Status** → COMPLETED.  
4. Explain **Final Metrics** and **State History** JSON.  
5. Open **Analytics** + **Smart Suggestions**.  
6. **Phase P3 Live Demonstrations**:
   - **Real Facilities**: Toggle Real OSM layer on LiveMap. Point out `UNAVAILABLE` capacity badges (Zero Fake Data Guarantee).
   - **Joyner-Boore Impact**: In Incident Feed, click "Evaluate Impact Assessment". Show concentric MMI attenuation rings (red MMI VII+, amber MMI V+, blue MMI III+) and OSM hospital intersections.
   - **Compound Disasters**: In Intelligence Panel, run Compound Correlation. Show cascading lifelines (e.g. Seismic -> Substation Failure -> Hospital Power Failure) with conditional probabilities.
   - **Evacuation Corridors**: On LiveMap, view planned multi-profile corridors with safety tiers (Green Tier 1, Amber Tier 2, Red Tier 3) and LWR clearance hours.
7. Show **Export Reports** (CSV, JSON, PDF) with 5-Tier Data Provenance.
8. Optionally show **`http://localhost:8000/docs`**.

---

## 13) Phase P3 Architecture & Technical Talking Points

| Phase | Subsystem | Scientific / Mathematical Basis | Data Provenance Guarantee |
|---|---|---|---|
| **P3.1** | Real Facility Intelligence | Overpass QL multi-mirror failover across 4 OSM servers | Zero fake capacities. Missing beds = `None` (`UNAVAILABLE`) |
| **P3.2** | Disaster Impact Engine | Joyner-Boore empirical attenuation ($\ln Y = c_1 + c_2 M - \ln r - k r$) | Marked `CALCULATED`, exposes exact equations & assumptions |
| **P3.3** | Compound Correlation Engine | Spatio-temporal event clustering & directed cascade trees | Quantified conditional probabilities $P(\text{fail} \mid \text{event})$ |
| **P3.4** | Evacuation Corridor Routing | Lighthill-Whitham-Richards flow dynamics & OSRM avoidance | Clearance time $T = \frac{N}{q_{\max}} + \frac{D}{v}$ exposed with safety tiers |
| **P3.5** | Provenance & Audit Reports | SQLite persistence with ReportLab PDF/CSV/JSON exports | 5-Tier Provenance: `LIVE`, `DATABASE`, `CALCULATED`, `SIMULATED`, `UNAVAILABLE` |


