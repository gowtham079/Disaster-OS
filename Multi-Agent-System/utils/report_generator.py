"""Simulation Report Generator Utility for CSV, JSON, and PDF Exports.

Generates audit-ready, client-grade reports from SQLite operational data.
"""

import io
import csv
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

logger = logging.getLogger(__name__)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print 'Page X of Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 0.5 * inch, 0.4 * inch, page_text)
        self.drawString(
            0.5 * inch,
            0.4 * inch,
            "DISASTER OS — Emergency Operations Center Audit Report | CONFIDENTIAL",
        )
        self.restoreState()


def get_run_details(run_id: str) -> Dict[str, Any]:
    """Fetch run metadata, logs, incidents, resources, facilities, and metrics from SQLite."""
    from database import get_connection

    conn = get_connection()

    run_row = conn.execute(
        "SELECT * FROM simulation_runs WHERE run_id = ?", (run_id,)
    ).fetchone()

    history_rows = conn.execute(
        "SELECT state, payload, timestamp FROM run_logs WHERE run_id = ? ORDER BY timestamp ASC",
        (run_id,),
    ).fetchall()

    incidents_rows = conn.execute(
        """
        SELECT incident_id, location, latitude, longitude, severity, people_affected, disaster_type,
               priority, status, estimated_risk, ml_predicted_severity, assigned_team_id,
               route_distance_km, route_eta_hours, route_source
        FROM incidents WHERE run_id = ?
        ORDER BY incident_id ASC
        """,
        (run_id,),
    ).fetchall()

    res_rows = conn.execute(
        "SELECT resource_name, resource_type, latitude, longitude, status, capacity FROM simulation_resources WHERE run_id = ?",
        (run_id,),
    ).fetchall()

    fac_rows = conn.execute(
        "SELECT facility_name, facility_type, latitude, longitude, total_capacity, available_capacity, status FROM facilities WHERE run_id = ?",
        (run_id,),
    ).fetchall()

    rm_row = conn.execute(
        "SELECT * FROM run_metrics WHERE run_id = ?",
        (run_id,),
    ).fetchone()

    # Phase P3: Real-World Operational Foundation Data
    real_fac_count = 0
    try:
        rfc = conn.execute("SELECT COUNT(*) as cnt FROM external_facilities").fetchone()
        real_fac_count = rfc["cnt"] if rfc else 0
    except Exception:
        pass

    recent_assessments = []
    try:
        ia_rows = conn.execute(
            "SELECT assessment_id, source_event_type, max_radius_km, route_accessibility_status FROM impact_assessments ORDER BY rowid DESC LIMIT 5"
        ).fetchall()
        recent_assessments = [dict(r) for r in ia_rows]
    except Exception:
        pass

    recent_compounds = []
    try:
        ce_rows = conn.execute(
            "SELECT compound_id, correlation_type, cascade_risk_level, confidence_score FROM compound_events ORDER BY rowid DESC LIMIT 5"
        ).fetchall()
        recent_compounds = [dict(r) for r in ce_rows]
    except Exception:
        pass

    recent_corridors = []
    try:
        co_rows = conn.execute(
            "SELECT corridor_id, name, profile, status, safety_tier, estimated_clearance_hours FROM evacuation_corridors ORDER BY rowid DESC LIMIT 5"
        ).fetchall()
        recent_corridors = [dict(r) for r in co_rows]
    except Exception:
        pass

    conn.close()

    if not run_row and not incidents_rows:
        return {}

    history = []
    for row in history_rows:
        try:
            history.append({
                "state": row["state"],
                "payload": json.loads(row["payload"]) if row["payload"] else {},
                "timestamp": row["timestamp"],
            })
        except Exception:
            pass

    rm_dict = dict(rm_row) if rm_row else {}
    if rm_dict:
        tot = rm_dict.get("total_victims") if rm_dict.get("total_victims") is not None else rm_dict.get("total_affected", sum(i.get("people_affected", 0) for i in incidents_rows))
        resc = rm_dict.get("rescued_victims") if rm_dict.get("rescued_victims") is not None else rm_dict.get("total_lives_saved", 0)
        cas = rm_dict.get("casualties") if rm_dict.get("casualties") is not None else 0
        wait = rm_dict.get("waiting_victims") if rm_dict.get("waiting_victims") is not None else max(0, tot - resc - cas)

        rm_dict["total_victims"] = tot
        rm_dict["total_affected"] = tot
        rm_dict["rescued_victims"] = resc
        rm_dict["total_lives_saved"] = resc
        rm_dict["waiting_victims"] = wait
        rm_dict["casualties"] = cas

        rescue_rate = rm_dict.get("rescue_rate_pct")
        if rescue_rate is None and tot > 0:
            rescue_rate = round((resc / tot) * 100, 1)
        casualty_rate = rm_dict.get("casualty_rate_pct")
        if casualty_rate is None and tot > 0:
            casualty_rate = round((cas / tot) * 100, 1)

        rm_dict["rescue_rate_pct"] = rescue_rate
        rm_dict["casualty_rate_pct"] = casualty_rate

        raw_util = rm_dict.get("resource_utilization")
        if raw_util is not None and "resource_assignment_rate_pct" not in rm_dict:
            try:
                util_val = float(str(raw_util).replace("%", "").strip())
                rm_dict["resource_assignment_rate_pct"] = util_val
            except Exception:
                rm_dict["resource_assignment_rate_pct"] = None
        if "active_resource_utilization_pct" not in rm_dict or rm_dict.get("active_resource_utilization_pct") is None:
            rm_dict["active_resource_utilization_pct"] = 0.0

        from utils.metrics import calculate_simulation_performance_score
        score_res = calculate_simulation_performance_score(
            rescue_rate_pct=rm_dict.get("rescue_rate_pct"),
            casualty_rate_pct=rm_dict.get("casualty_rate_pct"),
            resource_assignment_rate_pct=rm_dict.get("resource_assignment_rate_pct"),
            planned_route_eta_mins=rm_dict.get("planned_route_eta_mins"),
        )
        sim_score = score_res.get("score")
        rm_dict["simulation_performance_score"] = sim_score
        rm_dict["overall_score"] = sim_score
        rm_dict["overall_efficiency"] = f"{sim_score}%" if sim_score is not None else "N/A"
        rm_dict["score_details"] = score_res

    return {
        "run_id": run_row["run_id"] if run_row else run_id,
        "strategy": run_row["strategy"] if run_row else "smart",
        "seed": run_row["seed"] if run_row else 42,
        "started_at": run_row["started_at"] if run_row else datetime.now(timezone.utc).isoformat(),
        "completed_at": run_row["completed_at"] if run_row else None,
        "status": run_row["status"] if run_row else "COMPLETED",
        "history": history,
        "incidents": [dict(r) for r in incidents_rows],
        "resources": [dict(r) for r in res_rows],
        "facilities": [dict(r) for r in fac_rows],
        "metrics": rm_dict,
        "real_facilities_count": real_fac_count,
        "impact_assessments": recent_assessments,
        "compound_events": recent_compounds,
        "evacuation_corridors": recent_corridors,
    }


def generate_json_report(run_id: str) -> str:
    """Compile run metadata, logs, and telemetry into a formatted JSON string."""
    data = get_run_details(run_id)
    if not data:
        return json.dumps({"status": "error", "message": f"Run ID '{run_id}' not found or contains no data."})
    return json.dumps({"status": "success", "run": data}, indent=2)


def generate_csv_report(run_id: str) -> str:
    """Compile incident, resource, facility, and metrics data into a structured CSV string."""
    data = get_run_details(run_id)
    if not data:
        return f"error,Run ID '{run_id}' not found or contains no operational records."

    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header Metadata
    writer.writerow(["DISASTER OS — EMERGENCY OPERATIONS CENTER AUDIT REPORT"])
    writer.writerow(["Run ID", data.get("run_id"), "Status", data.get("status"), "Strategy", data.get("strategy"), "Seed", data.get("seed")])
    writer.writerow(["Generated At", datetime.now(timezone.utc).isoformat(), "Classification", "EOC Operational Audit"])
    writer.writerow([])

    # 2. Metrics Summary
    metrics = data.get("metrics", {})
    has_metrics = bool(metrics)
    tot_victims = metrics.get("total_victims", metrics.get("total_affected", 0 if has_metrics else "N/A"))
    rescued = metrics.get("rescued_victims", metrics.get("total_lives_saved", 0 if has_metrics else "N/A"))
    waiting = metrics.get("waiting_victims", max(0, tot_victims - rescued) if isinstance(tot_victims, (int, float)) and isinstance(rescued, (int, float)) else ("0" if has_metrics else "N/A"))
    casualties = metrics.get("casualties", 0 if has_metrics else "N/A")
    rescue_rate = metrics.get("rescue_rate_pct")
    rescue_rate_str = f"{rescue_rate}%" if rescue_rate is not None else "N/A"
    casualty_rate = metrics.get("casualty_rate_pct")
    casualty_rate_str = f"{casualty_rate}%" if casualty_rate is not None else "N/A"
    sim_score = metrics.get("simulation_performance_score")
    sim_score_str = f"{sim_score}%" if sim_score is not None else "N/A"

    planned_eta = metrics.get("planned_route_eta_mins")
    actual_resp = metrics.get("actual_response_time_mins")
    assign_rate = metrics.get("resource_assignment_rate_pct", metrics.get("resource_utilization", "N/A"))
    assign_str = f"{assign_rate}%" if isinstance(assign_rate, (int, float)) else str(assign_rate)
    active_rate = metrics.get("active_resource_utilization_pct", 0.0 if has_metrics else "N/A")
    active_str = f"{active_rate}%" if isinstance(active_rate, (int, float)) else str(active_rate)
    writer.writerow(["--- OPERATIONAL METRICS SUMMARY ---"])
    writer.writerow([
        "Total Incidents", metrics.get("total_incidents", len(data.get("incidents", []))),
        "Total People Affected", tot_victims,
        "Total Victims", tot_victims,
        "Total Lives Saved", rescued,
        "Rescued Victims", rescued,
        "Waiting / Unresolved Victims", waiting,
        "Casualties", casualties,
        "Rescue Rate", rescue_rate_str,
        "Casualty Rate", casualty_rate_str,
        "Overall Efficiency", sim_score_str,
        "Calculated Simulation Performance Score", sim_score_str,
        "Resource Assignment Rate", assign_str,
        "Active Resource Utilization", active_str,
        "Planned Route ETA (mins)", f"{planned_eta} mins" if planned_eta is not None else "N/A",
        "Actual Response Time (mins)", f"{actual_resp} mins" if actual_resp is not None else "N/A",
    ])
    writer.writerow([])

    # 3. Incidents Table
    writer.writerow(["--- INCIDENTS DETAIL ---"])
    writer.writerow([
        "Incident ID", "Location", "Latitude", "Longitude", "Disaster Type",
        "Severity", "Status", "People Affected", "Priority", "Assigned Team",
        "Route Distance (km)", "Route ETA (mins)", "Route Source",
    ])
    for inc in data.get("incidents", []):
        eta_mins = round(float(inc.get("route_eta_hours", 0)) * 60, 1) if inc.get("route_eta_hours") is not None else ""
        writer.writerow([
            f"INC-{inc.get('incident_id')}",
            inc.get("location"),
            inc.get("latitude"),
            inc.get("longitude"),
            inc.get("disaster_type"),
            inc.get("severity"),
            inc.get("status", "NEW"),
            inc.get("people_affected"),
            inc.get("priority"),
            inc.get("assigned_team_id"),
            inc.get("route_distance_km"),
            eta_mins,
            inc.get("route_source", "SIMULATED"),
        ])
    writer.writerow([])

    # 4. Response Fleet Table
    writer.writerow(["--- RESPONSE FLEET TELEMETRY ---"])
    writer.writerow(["Resource Name", "Resource Type", "Latitude", "Longitude", "Status", "Capacity"])
    for r in data.get("resources", []):
        writer.writerow([
            r.get("resource_name"),
            r.get("resource_type"),
            r.get("latitude"),
            r.get("longitude"),
            r.get("status"),
            r.get("capacity"),
        ])
    writer.writerow([])

    # 5. Facilities Table
    writer.writerow(["--- HOSPITAL & SHELTER CAPACITY ---"])
    writer.writerow(["Facility Name", "Facility Type", "Latitude", "Longitude", "Available Capacity", "Total Capacity", "Status"])
    for f in data.get("facilities", []):
        writer.writerow([
            f.get("facility_name"),
            f.get("facility_type"),
            f.get("latitude"),
            f.get("longitude"),
            f.get("available_capacity"),
            f.get("total_capacity"),
            f.get("status"),
        ])
    writer.writerow([])

    # 6. Phase P3 Disaster Impact Assessments
    impacts = data.get("impact_assessments", [])
    if impacts:
        writer.writerow(["--- OPERATIONAL IMPACT ASSESSMENTS (JOYNER-BOORE) ---"])
        writer.writerow(["Assessment ID", "Disaster Type", "Max Radius (km)", "Route Status"])
        for imp in impacts:
            writer.writerow([
                imp.get("assessment_id"),
                imp.get("source_event_type"),
                imp.get("max_radius_km"),
                imp.get("route_accessibility_status"),
            ])
        writer.writerow([])

    # 7. Phase P3 Compound Events
    compounds = data.get("compound_events", [])
    if compounds:
        writer.writerow(["--- COMPOUND DISASTER EVENTS & CASCADES ---"])
        writer.writerow(["Compound ID", "Correlation Type", "Cascade Risk", "Confidence Score"])
        for comp in compounds:
            writer.writerow([
                comp.get("compound_id"),
                comp.get("correlation_type"),
                comp.get("cascade_risk_level"),
                comp.get("confidence_score"),
            ])
        writer.writerow([])

    # 8. Phase P3 Evacuation Corridors
    corridors = data.get("evacuation_corridors", [])
    if corridors:
        writer.writerow(["--- EVACUATION CORRIDORS & CLEARANCE DYNAMICS ---"])
        writer.writerow(["Corridor ID", "Name", "Profile", "Status", "Safety Tier", "Clearance Hours"])
        for corr in corridors:
            writer.writerow([
                corr.get("corridor_id"),
                corr.get("name"),
                corr.get("profile"),
                corr.get("status"),
                corr.get("safety_tier"),
                corr.get("estimated_clearance_hours"),
            ])
        writer.writerow([])

    return output.getvalue()


def generate_pdf_report(run_id: str, buffer: io.BytesIO) -> None:
    """Generate a high-fidelity, styled ReportLab PDF audit report with page numbers."""
    data = get_run_details(run_id)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=45,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )

    h2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=14,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )

    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )

    cell_body = ParagraphStyle(
        "CellBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("DISASTER OS — EMERGENCY OPERATIONS CENTER", title_style))
    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"Mission Audit & Telemetry Report &bull; Generated: {gen_time}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1"), spaceAfter=12))

    if not data:
        # Empty run message
        story.append(Paragraph("<b>Report Notice:</b> Insufficient operational data available for this Run ID.", body_style))
        story.append(Spacer(1, 12))
        doc.build(story, canvasmaker=NumberedCanvas)
        return

    # 2. Metadata Grid
    incidents = data.get("incidents", [])
    resources = data.get("resources", [])
    facilities = data.get("facilities", [])
    metrics = data.get("metrics", {})

    meta_table_data = [
        [
            Paragraph("<b>Run ID:</b>", cell_bold), Paragraph(str(data.get("run_id")), cell_body),
            Paragraph("<b>Execution Status:</b>", cell_bold), Paragraph(str(data.get("status")), cell_body),
        ],
        [
            Paragraph("<b>AI Strategy:</b>", cell_bold), Paragraph(str(data.get("strategy")), cell_body),
            Paragraph("<b>Random Seed:</b>", cell_bold), Paragraph(str(data.get("seed")), cell_body),
        ],
        [
            Paragraph("<b>Started At:</b>", cell_bold), Paragraph(str(data.get("started_at", "—")), cell_body),
            Paragraph("<b>Data Classification:</b>", cell_bold), Paragraph("5-Tier Provenance Verified", cell_body),
        ],
    ]
    meta_table = Table(meta_table_data, colWidths=[90, 180, 110, 160])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Executive Summary
    story.append(Paragraph("1. Executive Summary", h2_style))
    tot_inc = len(incidents)
    tot_victims = metrics.get("total_victims", sum(i.get("people_affected", 0) for i in incidents))
    rescued = metrics.get("rescued_victims", metrics.get("total_lives_saved", 0))
    casualties = metrics.get("casualties", 0)
    waiting = metrics.get("waiting_victims", max(0, tot_victims - rescued - (casualties or 0)))
    rescue_rate = metrics.get("rescue_rate_pct")
    rescue_rate_str = f"{rescue_rate}%" if rescue_rate is not None else "N/A"
    casualty_rate = metrics.get("casualty_rate_pct")
    casualty_rate_str = f"{casualty_rate}%" if casualty_rate is not None else "N/A"
    sim_score = metrics.get("simulation_performance_score")
    score_str = f"{sim_score}%" if sim_score is not None else (metrics.get("overall_efficiency", "N/A"))
    planned_eta = metrics.get("planned_route_eta_mins")
    eta_str = f"{planned_eta} min" if planned_eta is not None else "UNAVAILABLE"
    actual_resp = metrics.get("actual_response_time_mins")
    actual_str = f"{actual_resp} min" if actual_resp is not None else "UNAVAILABLE"
    assign_rate = metrics.get("resource_assignment_rate_pct", metrics.get("resource_utilization", "N/A"))
    assign_str = f"{assign_rate}%" if isinstance(assign_rate, (int, float)) else str(assign_rate)
    active_rate = metrics.get("active_resource_utilization_pct", 0.0)
    active_str = f"{active_rate}%" if isinstance(active_rate, (int, float)) else str(active_rate)

    summary_text = (
        f"During operational run <b>{data.get('run_id')}</b>, the multi-agent emergency response simulation managed "
        f"<b>{tot_inc} active incidents</b> impacting an estimated <b>{tot_victims:,} citizens</b>. "
        f"Victim simulation status: <b>{rescued:,} rescued</b>, <b>{waiting:,} waiting/unresolved</b>, and <b>{casualties:,} casualties</b>. "
        f"Overall evaluation resulted in a Calculated Simulation Performance Score of <b>{score_str}</b> "
        f"(planned average route ETA: <b>{eta_str}</b>, resource assignment: <b>{assign_str}</b>)."
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 4))
    if casualties == 0:
        story.append(Paragraph("<i>Notice: Zero casualties recorded in this simulation run; unresolved victims remain classified as WAITING/UNRESOLVED rather than casualties.</i>", body_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 6))

    # KPI summary boxes: 3 rows x 4 columns
    kpi_data = [
        [
            Paragraph(f"<b>{rescued:,}</b><br/><font size='7' color='#64748b'>RESCUED</font>", cell_bold),
            Paragraph(f"<b>{waiting:,}</b><br/><font size='7' color='#64748b'>WAITING / UNRESOLVED</font>", cell_bold),
            Paragraph(f"<b>{casualties:,}</b><br/><font size='7' color='#64748b'>CASUALTIES</font>", cell_bold),
            Paragraph(f"<b>{tot_victims:,}</b><br/><font size='7' color='#64748b'>TOTAL VICTIMS</font>", cell_bold),
        ],
        [
            Paragraph(f"<b>{rescue_rate_str}</b><br/><font size='7' color='#64748b'>RESCUE RATE</font>", cell_bold),
            Paragraph(f"<b>{casualty_rate_str}</b><br/><font size='7' color='#64748b'>CASUALTY RATE</font>", cell_bold),
            Paragraph(f"<b>{assign_str}</b><br/><font size='7' color='#64748b'>RESOURCE ASSIGNMENT</font>", cell_bold),
            Paragraph(f"<b>{active_str}</b><br/><font size='7' color='#64748b'>ACTIVE UTILIZATION</font>", cell_bold),
        ],
        [
            Paragraph(f"<b>{eta_str}</b><br/><font size='7' color='#64748b'>PLANNED ROUTE ETA</font>", cell_bold),
            Paragraph(f"<b>{actual_str}</b><br/><font size='7' color='#64748b'>ACTUAL RESPONSE TIME</font>", cell_bold),
            Paragraph(f"<b>{score_str}</b><br/><font size='7' color='#64748b'>CALCULATED SIMULATION PERFORMANCE SCORE</font>", cell_bold),
            Paragraph(f"<b>Custom Heuristic</b><br/><font size='7' color='#64748b'>METHODOLOGY</font>", cell_bold),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[135, 135, 135, 135])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 12))

    # 4. Incident Roster & Triage Table
    story.append(Paragraph("2. Operational Incident Triage & Allocation", h2_style))
    if incidents:
        inc_headers = ["ID", "Location", "Disaster Type", "Severity", "Status", "Affected", "Assigned Team", "ETA"]
        inc_table_rows = [[Paragraph(f"<b>{h}</b>", cell_bold) for h in inc_headers]]
        for inc in incidents[:12]:
            eta_str = f"{round(float(inc.get('route_eta_hours', 0)) * 60)} min" if inc.get("route_eta_hours") else "—"
            sev = str(inc.get("severity", "low")).upper()
            inc_table_rows.append([
                Paragraph(f"INC-{inc.get('incident_id')}", cell_body),
                Paragraph(str(inc.get("location", "Unknown")), cell_body),
                Paragraph(str(inc.get("disaster_type", "")).upper(), cell_body),
                Paragraph(sev, cell_body),
                Paragraph(str(inc.get("status", "NEW")), cell_body),
                Paragraph(str(inc.get("people_affected", 0)), cell_body),
                Paragraph(str(inc.get("assigned_team_id") or "Unassigned"), cell_body),
                Paragraph(eta_str, cell_body),
            ])
        inc_table = Table(inc_table_rows, colWidths=[45, 95, 75, 55, 65, 50, 95, 60])
        inc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(inc_table)
    else:
        story.append(Paragraph("No active incidents recorded for this run.", body_style))
    story.append(Spacer(1, 12))

    # 5. Response Fleet & Facility Capacity Tables
    story.append(Paragraph("3. Response Fleet & Capacity Audit", h2_style))
    if resources or facilities:
        res_summary = {}
        for r in resources:
            rt = r.get("resource_type", "Unit")
            res_summary[rt] = res_summary.get(rt, 0) + 1

        fleet_text = ", ".join([f"<b>{k.replace('_', ' ').title()}:</b> {v}" for k, v in res_summary.items()])
        story.append(Paragraph(f"<b>Response Fleet Deployment ({len(resources)} Units Total):</b> {fleet_text or 'Standard Fleet'}", body_style))
        story.append(Spacer(1, 6))

        if facilities:
            fac_headers = ["Facility Name", "Type", "Total Beds/Cap", "Available", "Occupancy %", "Status"]
            fac_rows_data = [[Paragraph(f"<b>{h}</b>", cell_bold) for h in fac_headers]]
            for f in facilities[:8]:
                tot = f.get("total_capacity", 0) or 1
                avail = f.get("available_capacity", 0) or 0
                used = max(0, tot - avail)
                occ_pct = round((used / tot) * 100, 1)
                fac_rows_data.append([
                    Paragraph(str(f.get("facility_name")), cell_body),
                    Paragraph(str(f.get("facility_type", "")).capitalize(), cell_body),
                    Paragraph(str(tot), cell_body),
                    Paragraph(str(avail), cell_body),
                    Paragraph(f"{occ_pct}%", cell_body),
                    Paragraph(str(f.get("status", "operational")), cell_body),
                ])
            fac_table = Table(fac_rows_data, colWidths=[150, 75, 75, 75, 75, 90])
            fac_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(fac_table)
    story.append(Spacer(1, 12))

    # 6. Data Provenance & Methodology
    story.append(Paragraph("4. Data Provenance & Methodology Verification", h2_style))
    prov_text = (
        "Every operational metric in this report is audited under the Disaster OS 5-Tier Data Provenance Model: "
        "<b>LIVE</b> (external feeds), <b>DATABASE</b> (audited SQLite operational records), "
        "<b>CALCULATED</b> (deterministic mathematical triage and routing models), "
        "<b>SIMULATED</b> (14-agent drill telemetry), and <b>UNAVAILABLE</b> (explicit offline state). "
        "Route ETA values reflect planned OSRM routes; actual response times require real dispatch-to-arrival simulation timestamps. "
        "The Simulation Performance Score is a heuristic simulation evaluation metric and not an authoritative real-world operational benchmark."
    )
    story.append(Paragraph(prov_text, body_style))

    doc.build(story, canvasmaker=NumberedCanvas)
