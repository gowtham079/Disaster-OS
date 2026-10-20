import React, { memo, useState, useEffect, useCallback } from 'react';

import { API_BASE } from '../config';
const VALID_STATUSES = ['NEW', 'ASSESSED', 'RESPONDING', 'CONTAINED', 'RESOLVED'];
const SEV_ICONS = { high: '🔴', medium: '🟡', low: '🟢' };
const SEV_ORDER = { high: 0, medium: 1, low: 2 };

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

/* ── Haversine distance (km) ─────────────────── */
function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/* ── Incident Detail Drawer ──────────────────── */
function IncidentDetailDrawer({ incident, onClose, facilities, earthquakes, disasters, onUpdateStatus, onViewOnMap }) {
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [timeline, setTimeline] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [statusReason, setStatusReason] = useState('');
  const [impactAssessment, setImpactAssessment] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const inc = incident;

  const fetchTimeline = useCallback(async (incId) => {
    if (!incId) return;
    setTimelineLoading(true);
    try {
      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      const res = await fetch(`${API_BASE}/api/incidents/${incId}/timeline`, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include',
      });
      const data = await res.json();
      if (data.status === 'success' && data.timeline) {
        setTimeline(data.timeline);
      }
    } catch {
      setTimeline([]);
    } finally {
      setTimelineLoading(false);
    }
  }, []);

  const fetchImpact = useCallback(async (targetInc) => {
    if (!targetInc?.latitude || !targetInc?.longitude) return;
    setImpactLoading(true);
    try {
      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      const res = await fetch(`${API_BASE}/api/impact/assess`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({
          latitude: targetInc.latitude,
          longitude: targetInc.longitude,
          disaster_type: targetInc.disaster_type || 'incident',
          event_id: `INC-${targetInc.incident_id}`,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success') {
          setImpactAssessment(data.assessment);
        }
      }
    } catch {
      /* ignore */
    } finally {
      setImpactLoading(false);
    }
  }, []);

  useEffect(() => {
    if (inc?.incident_id) {
      fetchTimeline(inc.incident_id);
      setImpactAssessment(null);
    }
  }, [inc?.incident_id, fetchTimeline]);

  if (!inc) return null;

  const sev = String(inc.severity || 'low').toLowerCase();
  const st = String(inc.status || 'NEW').toUpperCase();

  // Nearby facilities
  const nearbyHospitals = (facilities || [])
    .filter(f => f.facility_type === 'hospital' && f.latitude && f.longitude && inc.latitude && inc.longitude)
    .map(f => ({ ...f, dist: haversineKm(inc.latitude, inc.longitude, f.latitude, f.longitude) }))
    .filter(f => f.dist < 50)
    .sort((a, b) => a.dist - b.dist)
    .slice(0, 3);

  const nearbyShelters = (facilities || [])
    .filter(f => f.facility_type === 'shelter' && f.latitude && f.longitude && inc.latitude && inc.longitude)
    .map(f => ({ ...f, dist: haversineKm(inc.latitude, inc.longitude, f.latitude, f.longitude) }))
    .filter(f => f.dist < 50)
    .sort((a, b) => a.dist - b.dist)
    .slice(0, 3);

  // Nearby intelligence events (spatial correlation)
  const nearbyEqs = (earthquakes || [])
    .filter(eq => eq.latitude && eq.longitude && inc.latitude && inc.longitude)
    .map(eq => ({ ...eq, dist: haversineKm(inc.latitude, inc.longitude, eq.latitude, eq.longitude) }))
    .filter(eq => eq.dist < 100)
    .sort((a, b) => a.dist - b.dist)
    .slice(0, 3);

  async function handleStatusChange(newStatus) {
    setUpdatingStatus(true);
    try {
      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      const res = await fetch(`${API_BASE}/api/incidents/${inc.incident_id}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({ status: newStatus, reason: statusReason || `Operator marked ${newStatus}` }),
      });
      if (res.ok) {
        const data = await res.json();
        onUpdateStatus?.(inc.incident_id, newStatus);
        if (data.timeline) setTimeline(data.timeline);
        setStatusReason('');
      }
    } catch { /* ignore */ }
    setUpdatingStatus(false);
  }

  return (
    <aside className={`incident-detail-drawer open`}>
      <div className="detail-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>{SEV_ICONS[sev]}</span>
          <div>
            <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: 14 }}>INC-{inc.incident_id}</div>
            <div style={{ fontSize: 10, color: '#94a3b8' }}>{inc.disaster_type?.toUpperCase()}</div>
          </div>
        </div>
        <button onClick={onClose} style={{ background: '#1e293b', border: '1px solid #334155', color: '#94a3b8', borderRadius: 6, padding: '4px 10px', cursor: 'pointer' }}>✕</button>
      </div>

      <div className="detail-body">
        {/* Core Info */}
        <div className="detail-section">
          <div className="detail-section-title">Incident Details</div>
          <div className="detail-field"><span className="detail-field-label">Location</span><span className="detail-field-value">{inc.location || 'Unknown'}</span></div>
          <div className="detail-field"><span className="detail-field-label">Coordinates</span><span className="detail-field-value">{inc.latitude?.toFixed(4)}, {inc.longitude?.toFixed(4)}</span></div>
          <div className="detail-field"><span className="detail-field-label">Severity</span><span className={`severity-badge severity-${sev}`}>{sev.toUpperCase()}</span></div>
          <div className="detail-field"><span className="detail-field-label">People Affected</span><span className="detail-field-value">{inc.people_affected || 0}</span></div>
          <div className="detail-field"><span className="detail-field-label">Status</span><span className={`incident-status incident-status-${st.toLowerCase()}`}>{st}</span></div>
          {inc.ml_predicted_severity && <div className="detail-field"><span className="detail-field-label">ML Prediction</span><span className="detail-field-value">{inc.ml_predicted_severity} ({(inc.ml_confidence * 100)?.toFixed(0)}%)</span></div>}
          {inc.assigned_team_id && <div className="detail-field"><span className="detail-field-label">Assigned Team</span><span className="detail-field-value">{inc.assigned_team_id}</span></div>}
        </div>

        {/* Route Info */}
        {inc.route_distance_km != null && (
          <div className="detail-section">
            <div className="detail-section-title">Route Information</div>
            <div className="detail-field"><span className="detail-field-label">Distance</span><span className="detail-field-value">{inc.route_distance_km?.toFixed(1)} km</span></div>
            <div className="detail-field"><span className="detail-field-label">PLANNED ROUTE ETA</span><span className="detail-field-value">{inc.route_eta_hours != null ? `${(inc.route_eta_hours * 60).toFixed(0)} min` : '—'}</span></div>
            <div className="detail-field">
              <span className="detail-field-label">Route Provider</span>
              <span className="detail-field-value" style={{ fontWeight: 600 }}>
                {inc.route_provider || 'UNAVAILABLE'}
              </span>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">Route Type</span>
              <span className="detail-field-value" style={{ fontSize: 11, color: '#94a3b8' }}>
                {inc.route_provider === 'OSRM'
                  ? 'ROAD_ROUTE (OSRM road network)'
                  : inc.route_provider === 'LOCAL_ASTAR'
                  ? 'GRAPH_ESTIMATE (Calculated graph estimate, not a verified road route)'
                  : inc.route_provider === 'DIRECT_GEOMETRIC'
                  ? 'STRAIGHT_LINE_ESTIMATE (Straight-line estimate, not a verified road route)'
                  : 'UNAVAILABLE'}
              </span>
            </div>
            <div className="detail-field">
              <span className="detail-field-label">Provenance</span>
              <ProvenanceBadge type={inc.route_provider === 'OSRM' ? 'LIVE' : (inc.route_provider === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'CALCULATED')} />
            </div>
          </div>
        )}

        {/* Status Update Actions */}
        <div className="detail-section">
          <div className="detail-section-title">Operator Actions & Lifecycle</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {VALID_STATUSES.map(s => (
              <button
                key={s}
                onClick={() => handleStatusChange(s)}
                disabled={updatingStatus || s === st}
                className={`incident-status incident-status-${s.toLowerCase()}`}
                style={{
                  cursor: s === st ? 'default' : 'pointer',
                  opacity: s === st ? 0.5 : 1,
                  padding: '5px 10px',
                  border: 'none',
                  background: s === st ? 'rgba(255,255,255,0.05)' : undefined,
                }}
              >
                {s}
              </button>
            ))}
          </div>

          <input
            type="text"
            className="input-control"
            placeholder="Optional transition reason / operational note..."
            value={statusReason}
            onChange={(e) => setStatusReason(e.target.value)}
            style={{ fontSize: 11, padding: '6px 10px', marginBottom: 8 }}
          />

          <button
            onClick={() => onViewOnMap?.(inc)}
            style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#cbd5e1', padding: '8px', borderRadius: 6, fontSize: 11, cursor: 'pointer' }}
          >
            🗺️ View on Operations Map
          </button>
        </div>

        {/* Incident Audit Timeline */}
        <div className="detail-section" style={{ background: 'rgba(15, 23, 42, 0.6)' }}>
          <div className="detail-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Incident Audit Timeline</span>
            <ProvenanceBadge type="DATABASE" />
          </div>
          {timelineLoading ? (
            <div style={{ fontSize: 11, color: '#94a3b8', padding: '8px 0' }}>Loading audit timeline...</div>
          ) : timeline.length === 0 ? (
            <div style={{ fontSize: 11, color: '#64748b', padding: '8px 0' }}>Initial status: {st} (No transitions logged yet)</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
              {timeline.map((entry, idx) => (
                <div key={idx} style={{ background: 'var(--bg-surface-elevated)', padding: '8px 10px', borderRadius: 4, fontSize: 11, borderLeft: '3px solid var(--accent-lime)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                    <strong style={{ color: '#fff' }}>{entry.previous_status || 'INITIAL'} &rarr; {entry.new_status}</strong>
                    <span style={{ fontSize: 9, color: 'var(--accent-lime)' }}>
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '—'}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                    By: <strong>{entry.operator_name || 'System'}</strong> &bull; {entry.reason || 'Status updated'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Empirical Impact Assessment (Phase P3.2) */}
        <div className="detail-section" style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
          <div className="detail-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>💥 Joyner-Boore Impact Modeling</span>
            <ProvenanceBadge type="CALCULATED" />
          </div>

          {!impactAssessment ? (
            <div>
              <p style={{ fontSize: 11, color: '#94a3b8', margin: '4px 0 8px 0' }}>
                Compute empirical physical attenuation isoseismals and identify exposed critical infrastructure.
              </p>
              <button
                onClick={() => fetchImpact(inc)}
                disabled={impactLoading || !inc.latitude || !inc.longitude}
                style={{
                  width: '100%',
                  background: '#ea580c',
                  border: 'none',
                  color: '#fff',
                  padding: '7px 12px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: (impactLoading || !inc.latitude) ? 'not-allowed' : 'pointer',
                  opacity: (impactLoading || !inc.latitude) ? 0.6 : 1,
                }}
              >
                {impactLoading ? 'Calculating Ground Motion Radii...' : '⚡ Calculate Impact Isoseismals'}
              </button>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 6 }}>
                <span style={{ color: '#94a3b8' }}>Method: <strong>{impactAssessment.methodology}</strong></span>
                <span className="op-badge op-badge-calc">{impactAssessment.confidence}</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 8 }}>
                {(impactAssessment.impact_zones || []).map(z => (
                  <div key={z.zone_id} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 6px', background: 'rgba(0,0,0,0.3)', borderLeft: `3px solid ${z.color}`, borderRadius: 4, fontSize: 10 }}>
                    <span style={{ color: z.color, fontWeight: 600 }}>{z.name}</span>
                    <strong style={{ color: '#f8fafc' }}>{z.radius_km} km</strong>
                  </div>
                ))}
              </div>

              <div className="detail-field">
                <span className="detail-field-label">Exposed Infrastructure</span>
                <span className="detail-field-value">{impactAssessment.summary?.total_facilities_exposed || impactAssessment.facilities_in_impact_zone?.length || 0} Facilities</span>
              </div>
              <div className="detail-field">
                <span className="detail-field-label">Road Network Status</span>
                <span className="detail-field-value" style={{ color: impactAssessment.route_accessibility_status === 'CLEAR' ? '#10b981' : '#f59e0b', fontWeight: 700 }}>
                  {impactAssessment.route_accessibility_status}
                </span>
              </div>

              <button
                onClick={() => onViewOnMap?.(inc)}
                style={{ width: '100%', marginTop: 8, background: '#0284c7', border: 'none', color: '#fff', padding: '6px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
              >
                🗺️ View Calculated Zones on Map
              </button>
            </div>
          )}
        </div>

        {/* Nearby Hospitals */}
        {nearbyHospitals.length > 0 && (
          <div className="detail-section">
            <div className="detail-section-title">Nearby Hospitals</div>
            {nearbyHospitals.map((h, i) => (
              <div key={i} className="detail-field">
                <span className="detail-field-label">🏥 {h.facility_name}</span>
                <span className="detail-field-value">{h.dist.toFixed(1)} km · {h.available_capacity}/{h.total_capacity} beds</span>
              </div>
            ))}
          </div>
        )}

        {/* Nearby Shelters */}
        {nearbyShelters.length > 0 && (
          <div className="detail-section">
            <div className="detail-section-title">Nearby Shelters</div>
            {nearbyShelters.map((s, i) => (
              <div key={i} className="detail-field">
                <span className="detail-field-label">🏕️ {s.facility_name}</span>
                <span className="detail-field-value">{s.dist.toFixed(1)} km · {s.available_capacity}/{s.total_capacity}</span>
              </div>
            ))}
          </div>
        )}

        {/* Intelligence Correlation */}
        {nearbyEqs.length > 0 && (
          <div className="detail-section" style={{ background: 'rgba(99, 102, 241, 0.06)', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
            <div className="detail-section-title">⚡ Spatial Intelligence Correlation</div>
            {nearbyEqs.map((eq, i) => (
              <div key={i} className="correlation-card" style={{ marginBottom: 6 }}>
                <div style={{ fontWeight: 600, color: '#f8fafc' }}>M{eq.magnitude?.toFixed(1)} — {eq.place}</div>
                <div className="correlation-arrow">↕ {eq.dist.toFixed(0)} km from incident</div>
                <div className="correlation-warning">SPATIAL CORRELATION ({eq.dist.toFixed(0)} km). Requires operator confirmation. Does not imply causation.</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

/* ══════════════════════════════════════════════════════════
   MAIN: INCIDENT FEED (FULL PAGE)
   ══════════════════════════════════════════════════════════ */
const IncidentFeed = memo(function IncidentFeed({
  incidents, facilities, earthquakes, disasters, onUpdateStatus, onViewOnMap,
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [filters, setFilters] = useState({ severity: 'all', type: 'all', status: 'all' });

  const filteredIncidents = (incidents || []).filter(inc => {
    if (filters.severity !== 'all' && String(inc.severity).toLowerCase() !== filters.severity) return false;
    if (filters.type !== 'all' && inc.disaster_type !== filters.type) return false;
    if (filters.status !== 'all' && String(inc.status || 'NEW').toUpperCase() !== filters.status) return false;
    return true;
  }).sort((a, b) => {
    const sa = SEV_ORDER[String(a.severity).toLowerCase()] ?? 2;
    const sb = SEV_ORDER[String(b.severity).toLowerCase()] ?? 2;
    if (sa !== sb) return sa - sb;
    return (b.incident_id || 0) - (a.incident_id || 0);
  });

  const selectedIncident = selectedId ? (incidents || []).find(i => i.incident_id === selectedId) : null;
  const disasterTypes = [...new Set((incidents || []).map(i => i.disaster_type).filter(Boolean))];

  return (
    <div style={{ position: 'relative' }}>
      {/* Filter Bar */}
      <div className="filter-bar" style={{ marginBottom: 16 }}>
        <label>Severity</label>
        <select value={filters.severity} onChange={e => setFilters(f => ({ ...f, severity: e.target.value }))}>
          <option value="all">All</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <label>Type</label>
        <select value={filters.type} onChange={e => setFilters(f => ({ ...f, type: e.target.value }))}>
          <option value="all">All Types</option>
          {disasterTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <label>Status</label>
        <select value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}>
          <option value="all">All</option>
          {VALID_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <div style={{ marginLeft: 'auto', fontSize: 11, color: '#94a3b8' }}>
          {filteredIncidents.length} of {(incidents || []).length} incidents
        </div>
      </div>

      {/* Incident Table */}
      <div className="glass-card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 'calc(100vh - 240px)', overflowY: 'auto' }}>
          {filteredIncidents.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <div className="empty-state-text">
                {(incidents || []).length === 0 ? 'No incidents available' : 'No incidents match the selected filters'}
              </div>
              <div className="empty-state-sub">
                {(incidents || []).length === 0 ? 'Run a simulation to generate incidents' : 'Try adjusting your filters'}
              </div>
            </div>
          ) : (
            filteredIncidents.map(inc => {
              const sev = String(inc.severity || 'low').toLowerCase();
              const st = String(inc.status || 'NEW').toUpperCase();
              return (
                <div
                  key={inc.incident_id}
                  className={`incident-row ${selectedId === inc.incident_id ? 'selected' : ''}`}
                  onClick={() => setSelectedId(inc.incident_id)}
                >
                  <div className={`incident-sev-dot ${sev}`}>{SEV_ICONS[sev]}</div>
                  <div>
                    <div style={{ color: '#f8fafc', fontWeight: 600, fontSize: 12 }}>{inc.disaster_type?.toUpperCase() || 'INCIDENT'}</div>
                    <div style={{ color: '#94a3b8', fontSize: 10 }}>{inc.location || 'Unknown'} · {inc.people_affected || 0} affected</div>
                  </div>
                  <span className={`incident-status incident-status-${st.toLowerCase()}`}>{st}</span>
                  <span className={`severity-badge severity-${sev}`}>{sev.toUpperCase()}</span>
                  <div style={{ color: '#64748b', fontSize: 10, fontFamily: 'monospace' }}>INC-{inc.incident_id}</div>
                  <ProvenanceBadge type="DATABASE" />
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Detail Drawer */}
      {selectedIncident && (
        <IncidentDetailDrawer
          incident={selectedIncident}
          onClose={() => setSelectedId(null)}
          facilities={facilities}
          earthquakes={earthquakes}
          disasters={disasters}
          onUpdateStatus={(id, status) => {
            onUpdateStatus?.(id, status);
            // Update local selection
          }}
          onViewOnMap={onViewOnMap}
        />
      )}
    </div>
  );
});

export default IncidentFeed;
