# Tactical Multi-Agent Disaster Management OS (v2.0)

A research-grade, industry-level Multi-Agent Disaster Management and Tactical Decision Support System. Developed with a high-fidelity visual framework inspired by n8n, React, FastAPI, SQLite, and Python.

---

## 🌟 Key Platform Features

1. **AI-Driven Severity Classification**: Uses a trained Random Forest model (`severity_model.joblib`) that dynamically categorizes incident risk levels using spatial metrics and victim density forecasts rather than raw hardcoded templates.
2. **Centralized Message Bus & Health Monitoring**: Implements a thread-safe, priority-queued message bus for inter-agent communication supporting target/broadcast messaging, health telemetry, and automatic retry delays.
3. **Optimized Route Planning (A* Solver)**: Plans tactical highway paths between Indian cities utilizing coordinate distances (Haversine formula), handles simulated road blockages, and generates detailed distance-based ETAs.
4. **AI Decision Support (Google Gemini API)**: Generates detailed justifications explaining disaster severity, dispatch choices, and evacuation protocols (includes fail-safe heuristic templates for offline execution).
5. **Real-time WebSocket Streams**: Streams system state updates, logs, and inter-agent message logs to the frontend via active WebSocket broadcasts.
6. **Leaflet & OSM Live Map Visualizer**: Displays interactive disaster sectors, shelters, fire brigades, route polylines, and animated rescue movement tags.
7. **CSV & PDF Report Exporters**: Compiles styled, print-ready reports containing run logs and AI decision support using ReportLab.
8. **Role-Based Access Directories**: Restricts parameter modifications and user management through SQLite-backed operator registries.

---

## 🏗️ System Architecture & Workflow

The platform leverages **14 Operational Response Agents + 1 Post-Mission Evaluation Service** (15 total registered entities) communicating over a thread-safe, priority-queued **Message Bus**:

### 14 Operational Response Agents:
1. **IncidentAgent**: Detects disaster type, ML severity, and secondary hazards.
2. **WeatherAgent**: Live OpenWeather/NOAA integration with spatial rainfall/wind propagation.
3. **VictimAgent**: Triage tagging, casualty escalation, and survivor tracking.
4. **ResourceAgent**: Response fleet dispatch (Ambulances, Fire Engines, Police, Rescue Boats).
5. **HospitalAgent**: Trauma bed occupancy & emergency room triage.
6. **ShelterAgent**: Evacuee capacity allocation & high-ground shelter management.
7. **TrafficAgent**: Highway congestion monitoring, blocked road alerts & detour triggers.
8. **PoliceAgent**: Perimeter security, traffic diversion, and evacuation corridor control.
9. **FireAgent**: Fire containment, HAZMAT chemical leak suppression & urban search.
10. **DroneAgent**: Aerial thermal scanning, casualty tracking & airborne recon.
11. **RouteAgent**: OSRM real-road pathfinding & dynamic detour routing.
12. **RescueAgent**: Coordinate-based rescue execution & triage progression.
13. **CommunicationAgent**: Inter-agent message router, cell broadcast warnings & emergency alerts.
14. **AIAgent**: Gemini LLM predictive threat analysis & tactical recommendations.

### 1 Post-Mission Evaluation Service:
15. **EvaluationAgent**: Mission success scoring, response time audit & post-disaster evaluation.

---

## 🛠️ Quick Installation & Setup

### 1. Requirements
Ensure you have **Python 3.10+** and **Node.js 18+** installed.

### 2. Backend Setup
```bash
# Navigate to the backend directory
cd Multi-Agent-System

# Create python virtual environment
python -m venv venv
source venv/bin/activate  # Or venv\Scripts\activate on Windows

# Install Python dependencies
pip install -r requirements.txt
pip install reportlab

# Optional: Add your Google Gemini Key to a local .env file
# GEMINI_API_KEY=your_key_here

# Start the FastAPI server
python app.py
```
The backend API is now running at `http://localhost:8000`. Swagger documentation is available at `http://localhost:8000/docs`.

### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd "multiagent project"

# Install frontend modules
npm install

# Start the React client
npm start
```
Open `http://localhost:3000` in your web browser to access the dashboard.

---

## 🧪 Running Integration Verification

To run the automated integration test suite confirming Database, ML models, Message Bus routing, A* Pathfinder routing, and ReportLab PDF document exports:
```bash
cd Multi-Agent-System
python scratch/run_all_tests.py
```
All tests should return `SUCCESS` outputs.
