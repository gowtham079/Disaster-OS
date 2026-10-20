import React, { memo } from 'react';
import AnimatedCounter from './AnimatedCounter';

/* ── Provenance Badge ────────────────────────── */
function ProvenanceBadge({ type }) {
  const map = {
    DATABASE: 'op-badge op-badge-db',
    CALCULATED: 'op-badge op-badge-calc',
    SIMULATED: 'op-badge op-badge-sim',
    LIVE: 'op-badge op-badge-live',
    UNAVAILABLE: 'op-badge op-badge-unavail',
  };
  return <span className={map[type] || 'op-badge op-badge-db'}>{type}</span>;
}

/* ── Severity Icons ──────────────────────────── */
const SEV_ICONS = { high: '🔴', medium: '🟡', low: '🟢' };
const STATUS_LABELS = { NEW: '●', ASSESSED: '◐', RESPONDING: '◑', CONTAINED: '◒', RESOLVED: '✓' };

/* ── KPI Card ────────────────────────────────── */
function KpiCard({ label, value, icon, color, provenance, sub }) {
  return (
    <div className="glass-card eoc-kpi-card">
      <div className="kpi-provenance"><ProvenanceBadge type={provenance} /></div>
      <div className="kpi-icon" style={{ background: `${color}18` }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
      </div>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ color, fontSize: value === null || value === undefined ? 16 : 24 }}>
        {value === null || value === undefined ? <span style={{ color: '#64748b', fontSize: 13 }}>Unavailable</span> : <AnimatedCounter value={value} />}
      </div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

/* ── Capacity Bar ────────────────────────────── */
function CapacityBar({ used, total, label }) {
  const pct = total > 0 ? Math.round(((total - (total - used)) / total) * 100) : 0;
  const utilPct = total > 0 ? Math.round((used / total) * 100) : 0;
  const barClass = utilPct > 80 ? 'red' : utilPct > 50 ? 'amber' : 'green';
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
        <span style={{ color: '#f8fafc', fontWeight: 600 }}>{label}</span>
        <span style={{ color: '#94a3b8' }}>{used}/{total} ({utilPct}%)</span>
      </div>
      <div className="capacity-bar-wrap">
        <div className={`capacity-bar-fill ${barClass}`} style={{ width: `${utilPct}%` }} />
      </div>
    </div>
  );
}

/* ── Source Health Status ─────────────────────── */
function SourceHealthRow({ sources }) {
  if (!sources || sources.length === 0) return <div className="empty-state"><div className="empty-state-text">Source health loading...</div></div>;
  return (
    <div className="source-health-grid">
      {sources.map(s => {
        const st = String(s.status || '').toLowerCase().replace('sourcehealthstatus.', '');
        return (
          <div key={s.name} className="source-health-pill" title={`Latency: ${s.response_time_ms?.toFixed(0) || 0}ms`}>
            <span className={`sh-dot ${st.includes('operational') ? 'operational' : st.includes('degraded') ? 'degraded' : 'unavailable'}`} />
            <span className="sh-name">{s.name}</span>
            <span className="sh-latency">{s.response_time_ms ? `${s.response_time_ms.toFixed(0)}ms` : '—'}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ── Critical Alert Panel ────────────────────── */
function CriticalAlerts({ incidents, earthquakes, disasters, sourceHealth }) {
  const alerts = [];
  // Critical incidents
  (incidents || []).forEach(inc => {
    if (String(inc.severity).toLowerCase() === 'high' && String(inc.status || 'NEW').toUpperCase() !== 'RESOLVED') {
      alerts.push({
        type: 'CRITICAL INCIDENT',
        icon: '🚨',
        severity: 'critical',
        title: `${inc.disaster_type?.toUpperCase() || 'INCIDENT'} — ${inc.location || 'Unknown'}`,
        meta: [`${inc.people_affected || 0} affected`, `Status: ${inc.status || 'NEW'}`],
        cssClass: '',
      });
    }
  });
  // Major earthquakes
  (earthquakes || []).forEach(eq => {
    if (eq.magnitude >= 5.0) {
      alerts.push({
        type: 'MAJOR EARTHQUAKE',
        icon: '🌍',
        severity: 'warning',
        title: `M${eq.magnitude?.toFixed(1)} — ${eq.place || 'Unknown'}`,
        meta: [`Depth: ${eq.depth_km?.toFixed(0) || '?'}km`, 'Source: USGS'],
        cssClass: 'alert-warning',
      });
    }
  });
  // GDACS red alerts
  (disasters || []).forEach(d => {
    if (String(d.alert_level || d.alertlevel).toLowerCase() === 'red') {
      alerts.push({
        type: 'GDACS RED ALERT',
        icon: '⚠️',
        severity: 'critical',
        title: `${d.event_type?.toUpperCase() || 'DISASTER'} — ${d.place || d.title || 'Global'}`,
        meta: ['Alert Level: RED', 'Source: GDACS'],
        cssClass: '',
      });
    }
  });
  // Source failures
  (sourceHealth || []).forEach(s => {
    const st = String(s.status || '').toLowerCase();
    if (st.includes('unavailable') && s.name !== 'Open-Meteo') {
      alerts.push({
        type: 'SOURCE FAILURE',
        icon: '📡',
        severity: 'info',
        title: `${s.name} — Service Unavailable`,
        meta: [s.error_message || 'Connection failed'],
        cssClass: 'alert-info',
      });
    }
  });

  if (alerts.length === 0) {
    return (
      <div className="empty-state" style={{ padding: '20px 16px' }}>
        <div className="empty-state-icon">✅</div>
        <div className="empty-state-text">No active critical alerts</div>
        <div className="empty-state-sub">System operating normally</div>
      </div>
    );
  }

  return (
    <div className="alert-panel">
      {alerts.slice(0, 10).map((a, i) => (
        <div key={i} className={`alert-item ${a.cssClass}`}>
          <div className="alert-icon">{a.icon}</div>
          <div className="alert-content">
            <div className="alert-title">{a.title}</div>
            <div className="alert-meta">
              <span style={{ fontWeight: 700, color: a.severity === 'critical' ? '#ef4444' : '#f59e0b' }}>{a.type}</span>
              {a.meta.map((m, j) => <span key={j}>{m}</span>)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Incident Feed (compact, max 8 rows) ─────── */
function IncidentFeedCompact({ incidents, onSelect, onViewAll }) {
  const sorted = [...(incidents || [])].sort((a, b) => {
    const sevOrder = { high: 0, medium: 1, low: 2 };
    const sa = sevOrder[String(a.severity).toLowerCase()] ?? 2;
    const sb = sevOrder[String(b.severity).toLowerCase()] ?? 2;
    if (sa !== sb) return sa - sb;
    return (b.incident_id || 0) - (a.incident_id || 0);
  });

  if (sorted.length === 0) {
    return (
      <div className="empty-state" style={{ padding: '20px 16px' }}>
        <div className="empty-state-icon">📋</div>
        <div className="empty-state-text">No active incidents</div>
        <div className="empty-state-sub">Incidents will appear when a simulation runs</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 340, overflowY: 'auto' }}>
      {sorted.slice(0, 8).map(inc => {
        const sev = String(inc.severity || 'low').toLowerCase();
        const st = String(inc.status || 'NEW').toUpperCase();
        return (
          <div key={inc.incident_id} className="incident-row" onClick={() => onSelect?.(inc)}>
            <div className={`incident-sev-dot ${sev}`}>{SEV_ICONS[sev] || '⚪'}</div>
            <div>
              <div style={{ color: '#f8fafc', fontWeight: 600, fontSize: 12 }}>{inc.disaster_type?.toUpperCase() || 'INCIDENT'}</div>
              <div style={{ color: '#94a3b8', fontSize: 10 }}>{inc.location || 'Unknown location'}</div>
            </div>
            <div style={{ color: '#cbd5e1', fontSize: 11 }}>{inc.people_affected || 0} affected</div>
            <span className={`incident-status incident-status-${st.toLowerCase()}`}>{st}</span>
            <div style={{ color: '#64748b', fontSize: 10, fontFamily: 'monospace' }}>INC-{inc.incident_id}</div>
            <span className={`severity-badge severity-${sev}`}>{sev.toUpperCase()}</span>
          </div>
        );
      })}
      {sorted.length > 8 && (
        <button onClick={onViewAll} style={{ background: '#1e293b', border: '1px solid #334155', color: '#94a3b8', padding: '8px', borderRadius: 6, fontSize: 11, cursor: 'pointer', textAlign: 'center' }}>
          View all {sorted.length} incidents →
        </button>
      )}
    </div>
  );
}

/* ── Fleet Summary (compact) ─────────────────── */
function FleetSummaryCompact({ resources, onViewAll }) {
  const FLEET_TYPES = [
    { key: 'ambulance', icon: '🚑', label: 'Ambulance', color: '#ef4444' },
    { key: 'fire_truck', icon: '🚒', label: 'Fire', color: '#f97316' },
    { key: 'police_car', icon: '🚔', label: 'Police', color: '#3b82f6' },
    { key: 'rescue_boat', icon: '⛵', label: 'Rescue', color: '#06b6d4' },
    { key: 'helicopter', icon: '🚁', label: 'Heli', color: '#8b5cf6' },
    { key: 'drone', icon: '🛸', label: 'Drone', color: '#10b981' },
    { key: 'supply_truck', icon: '🚛', label: 'Supply', color: '#f59e0b' },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 }}>
      {FLEET_TYPES.map(ft => {
        const units = (resources || []).filter(r => r.resource_type === ft.key);
        const avail = units.filter(r => r.status === 'available').length;
        if (units.length === 0 && (resources || []).length > 0) return null;
        return (
          <div key={ft.key} className="glass-card fleet-card" onClick={onViewAll}>
            <div className="fleet-icon" style={{ background: `${ft.color}18` }}>{ft.icon}</div>
            <div className="fleet-count" style={{ color: ft.color }}>{units.length}</div>
            <div className="fleet-label">{ft.label}</div>
            <div className="fleet-status">{avail} ready</div>
          </div>
        );
      }).filter(Boolean)}
      {(!resources || resources.length === 0) && (
        <div className="empty-state" style={{ gridColumn: '1 / -1', padding: '16px' }}>
          <div className="empty-state-text">No fleet data available</div>
          <div className="empty-state-sub">Run a simulation to deploy response units</div>
        </div>
      )}
    </div>
  );
}

/* ── Intelligence Summary (compact) ──────────── */
function IntelligenceSummary({ earthquakes, disasters, onViewAll }) {
  const eqs = earthquakes || [];
  const gds = disasters || [];
  const maxMag = eqs.length > 0 ? Math.max(...eqs.map(e => e.magnitude || 0)) : null;
  const latestEq = eqs.length > 0 ? eqs[0] : null;
  const redAlerts = gds.filter(d => String(d.alert_level || d.alertlevel).toLowerCase() === 'red').length;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      <div className="glass-card" style={{ padding: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>USGS Earthquakes</div>
          <ProvenanceBadge type={eqs.length > 0 ? 'LIVE' : 'UNAVAILABLE'} />
        </div>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#f8fafc', fontFamily: 'Outfit' }}>{eqs.length}</div>
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>
          {maxMag !== null ? `Highest: M${maxMag.toFixed(1)}` : 'No recent events'}
        </div>
        {latestEq && <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>Latest: {latestEq.place}</div>}
      </div>
      <div className="glass-card" style={{ padding: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>GDACS Alerts</div>
          <ProvenanceBadge type={gds.length > 0 ? 'LIVE' : 'UNAVAILABLE'} />
        </div>
        <div style={{ fontSize: 20, fontWeight: 800, color: '#f8fafc', fontFamily: 'Outfit' }}>{gds.length}</div>
        <div style={{ fontSize: 10, color: redAlerts > 0 ? '#ef4444' : '#64748b', fontWeight: redAlerts > 0 ? 700 : 400, marginTop: 4 }}>
          {redAlerts > 0 ? `${redAlerts} RED alert${redAlerts > 1 ? 's' : ''}` : 'No red alerts'}
        </div>
      </div>
    </div>
  );
}

/* ── Resource Capacity Summary (compact) ─────── */
function ResourceCapacitySummary({ metrics }) {
  const hospitals = metrics?.hospitals || [];
  const shelters = metrics?.shelters || [];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      <div className="glass-card" style={{ padding: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>🏥 Hospitals</div>
          <ProvenanceBadge type="DATABASE" />
        </div>
        {hospitals.length > 0 ? hospitals.map((h, i) => {
          const used = (h.total || 0) - (h.available || 0);
          return <CapacityBar key={i} used={used} total={h.total || 0} label={h.name || `Hospital ${i+1}`} />;
        }) : (
          <div style={{ fontSize: 11, color: '#64748b', textAlign: 'center', padding: 12 }}>No hospital data</div>
        )}
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>
          Occupancy: {metrics?.hospital_capacity_pct != null ? `${metrics.hospital_capacity_pct}%` : 'Unavailable'}
        </div>
      </div>
      <div className="glass-card" style={{ padding: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>🏕️ Shelters</div>
          <ProvenanceBadge type="DATABASE" />
        </div>
        {shelters.length > 0 ? shelters.map((s, i) => {
          const used = (s.total || 0) - (s.available || 0);
          return <CapacityBar key={i} used={used} total={s.total || 0} label={s.name || `Shelter ${i+1}`} />;
        }) : (
          <div style={{ fontSize: 11, color: '#64748b', textAlign: 'center', padding: 12 }}>No shelter data</div>
        )}
        <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>
          Occupancy: {metrics?.shelter_capacity_pct != null ? `${metrics.shelter_capacity_pct}%` : 'Unavailable'}
        </div>
      </div>
    </div>
  );
}

/* ── AI Tactical Panel (real data only) ──────── */
function AiTacticalPanel({ aiRecs }) {
  const hasData = aiRecs && (
    (aiRecs.recommended_actions && aiRecs.recommended_actions.length > 0 && aiRecs.recommended_actions[0] !== '') ||
    (aiRecs.predicted_threat && aiRecs.predicted_threat !== '')
  );

  return (
    <div className="glass-card" style={{ padding: 18, background: 'linear-gradient(135deg, rgba(30,27,75,0.7) 0%, rgba(15,23,42,0.85) 100%)', border: '1px solid #4338ca', marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'Outfit' }}>
          🛡️ AI Tactical Decision Support
        </div>
        <ProvenanceBadge type={hasData ? 'CALCULATED' : 'UNAVAILABLE'} />
      </div>
      {hasData ? (
        <>
          {aiRecs.predicted_threat && (
            <div style={{ background: 'rgba(49,46,129,0.6)', color: '#e0e7ff', padding: '10px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, marginBottom: 12 }}>
              ⚠️ THREAT ASSESSMENT: {aiRecs.predicted_threat}
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: '#93c5fd', textTransform: 'uppercase', marginBottom: 6 }}>Recommendations</div>
              <ul style={{ margin: 0, paddingLeft: 16, color: '#f8fafc', fontSize: 11, lineHeight: 1.6 }}>
                {(aiRecs.recommended_actions || []).map((act, i) => <li key={i}>{act}</li>)}
              </ul>
            </div>
            <div>
              {aiRecs.evacuation_instructions && (
                <>
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#fca5a5', textTransform: 'uppercase', marginBottom: 6 }}>Evacuation Protocol</div>
                  <div style={{ fontSize: 11, color: '#cbd5e1' }}>{aiRecs.evacuation_instructions}</div>
                </>
              )}
              {aiRecs.resource_adjustments && (
                <div style={{ fontSize: 11, color: '#cbd5e1', marginTop: 6 }}><strong>Fleet Reallocation:</strong> {aiRecs.resource_adjustments}</div>
              )}
            </div>
          </div>
          {aiRecs.summary && (
            <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 10, fontStyle: 'italic' }}>Context: {aiRecs.summary}</div>
          )}
        </>
      ) : (
        <div className="empty-state" style={{ padding: '16px 12px' }}>
          <div className="empty-state-icon">🤖</div>
          <div className="empty-state-text">Awaiting simulation/intelligence data...</div>
          <div className="empty-state-sub">AI recommendations will appear after a simulation pipeline completes or intelligence events arrive</div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   MAIN: EOC COMMAND DASHBOARD
   ══════════════════════════════════════════════════════════ */
const EOCDashboard = memo(function EOCDashboard({
  metrics, incidents, resources, sourceHealth, earthquakes, disasters,
  aiRecs, selectedRun, onSelectIncident, onNavigate,
}) {
  const m = metrics || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>

      {/* ── 8 Operational KPI Cards ── */}
      <div className="eoc-section">
        <div className="eoc-section-header">
          <div className="eoc-section-title">📊 Active Situation</div>
          <div className="eoc-section-meta">Run: {selectedRun ? selectedRun.substring(0, 8) : '—'}</div>
        </div>
        <div className="eoc-grid-8" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          <KpiCard label="Active Incidents" value={m.total_incidents} icon="🚨" color="#ef4444" provenance="DATABASE" sub="Total reported" />
          <KpiCard label="Total Victims" value={m.total_victims} icon="👥" color="#f59e0b" provenance="DATABASE" sub="People affected" />
          <KpiCard label="Rescued" value={m.rescued_victims ?? m.victims_rescued} icon="🛟" color="#10b981" provenance="CALCULATED" sub={m.rescue_rate_pct != null ? `${m.rescue_rate_pct}% rescue rate` : 'People secured'} />
          <KpiCard label="Waiting / Unresolved" value={m.waiting_victims ?? m.victims_waiting} icon="⏳" color="#f59e0b" provenance="CALCULATED" sub="Awaiting evacuation" />
          <KpiCard label="Casualties" value={m.casualties ?? 0} icon="⚠️" color="#ef4444" provenance="CALCULATED" sub={m.casualty_rate_pct != null ? `${m.casualty_rate_pct}% casualty rate` : 'Fatal state transitions'} />
          <KpiCard label="Rescue Rate" value={m.rescue_rate_pct != null ? `${m.rescue_rate_pct}%` : 'N/A'} icon="📊" color="#10b981" provenance="CALCULATED" sub="Rescued / Total" />
          <KpiCard label="Casualty Rate" value={m.casualty_rate_pct != null ? `${m.casualty_rate_pct}%` : 'N/A'} icon="📉" color="#ef4444" provenance="CALCULATED" sub="Casualties / Total" />
          <KpiCard label="Resource Assignment" value={m.resource_assignment_rate_pct != null ? `${m.resource_assignment_rate_pct}%` : (m.resource_utilization != null ? `${m.resource_utilization}%` : 'N/A')} icon="🚑" color="#3b82f6" provenance="CALCULATED" sub="Fleet assigned" />
          <KpiCard label="Active Resource Utilization" value={m.active_resource_utilization_pct != null ? `${m.active_resource_utilization_pct}%` : '0.0%'} icon="⚡" color="#06b6d4" provenance="CALCULATED" sub="Actively en route" />
          <KpiCard label="Planned Route ETA" value={m.planned_route_eta_mins != null ? `${m.planned_route_eta_mins} min` : (m.avg_eta_mins != null ? `${m.avg_eta_mins} min` : 'UNAVAILABLE')} icon="⏱️" color="#818cf8" provenance="CALCULATED" sub="OSRM route estimate" />
          <KpiCard label="Actual Response Time" value={m.actual_response_time_mins != null ? `${m.actual_response_time_mins} min` : "UNAVAILABLE"} icon="⌛" color="#94a3b8" provenance="UNAVAILABLE" sub="Arrival timestamps N/A" />
          <KpiCard label="Calculated Simulation Performance Score" value={(m.simulation_performance_score ?? m.calculated_simulation_performance_score) != null ? `${m.simulation_performance_score ?? m.calculated_simulation_performance_score}%` : (m.overall_efficiency || 'N/A')} icon="📈" color="#a855f7" provenance="CALCULATED" sub="Custom simulation heuristic; not an authoritative real-world disaster-response metric." />
        </div>
      </div>

      {/* ── AI Tactical Panel ── */}
      <AiTacticalPanel aiRecs={aiRecs} />

      {/* ── Critical Alerts + Incident Feed (2-column) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        <div className="glass-card" style={{ padding: 16 }}>
          <div className="eoc-section-header" style={{ marginBottom: 10 }}>
            <div className="eoc-section-title">🚨 Critical Alerts</div>
          </div>
          <CriticalAlerts incidents={incidents} earthquakes={earthquakes} disasters={disasters} sourceHealth={sourceHealth} />
        </div>
        <div className="glass-card" style={{ padding: 16 }}>
          <div className="eoc-section-header" style={{ marginBottom: 10 }}>
            <div className="eoc-section-title">📋 Live Incident Feed</div>
            <div className="eoc-section-meta">{(incidents || []).length} incidents</div>
          </div>
          <IncidentFeedCompact incidents={incidents} onSelect={onSelectIncident} onViewAll={() => onNavigate?.('incidents')} />
        </div>
      </div>

      {/* ── Source Health + Intelligence (2-column) ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        <div className="glass-card" style={{ padding: 16 }}>
          <div className="eoc-section-header" style={{ marginBottom: 10 }}>
            <div className="eoc-section-title">📡 Source Health</div>
          </div>
          <SourceHealthRow sources={sourceHealth} />
        </div>
        <div>
          <div className="eoc-section-header" style={{ marginBottom: 10 }}>
            <div className="eoc-section-title">🌍 Live Intelligence</div>
            <button onClick={() => onNavigate?.('intelligence')} style={{ background: '#1e293b', border: '1px solid #334155', color: '#94a3b8', padding: '4px 10px', borderRadius: 6, fontSize: 10, cursor: 'pointer' }}>View All →</button>
          </div>
          <IntelligenceSummary earthquakes={earthquakes} disasters={disasters} onViewAll={() => onNavigate?.('intelligence')} />
        </div>
      </div>

      {/* ── Fleet Summary ── */}
      <div className="eoc-section">
        <div className="eoc-section-header">
          <div className="eoc-section-title">🚑 Response Fleet Status</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <ProvenanceBadge type="SIMULATED" />
            <button onClick={() => onNavigate?.('fleet')} style={{ background: '#1e293b', border: '1px solid #334155', color: '#94a3b8', padding: '4px 10px', borderRadius: 6, fontSize: 10, cursor: 'pointer' }}>Details →</button>
          </div>
        </div>
        <FleetSummaryCompact resources={resources} onViewAll={() => onNavigate?.('fleet')} />
      </div>

      {/* ── Resource Capacity ── */}
      <div className="eoc-section">
        <div className="eoc-section-header">
          <div className="eoc-section-title">📦 Resource Capacity</div>
          <button onClick={() => onNavigate?.('resources')} style={{ background: '#1e293b', border: '1px solid #334155', color: '#94a3b8', padding: '4px 10px', borderRadius: 6, fontSize: 10, cursor: 'pointer' }}>Details →</button>
        </div>
        <ResourceCapacitySummary metrics={m} />
      </div>
    </div>
  );
});

export default EOCDashboard;
