import React, { memo, useState, useEffect, useCallback } from 'react';

import { API_BASE } from '../config';

function ProvenanceBadge({ type }) {
  const map = {
    DATABASE: 'op-badge op-badge-db',
    CALCULATED: 'op-badge op-badge-calc',
    SIMULATED: 'op-badge op-badge-sim',
    LIVE: 'op-badge op-badge-live',
    UNAVAILABLE: 'op-badge op-badge-unavail',
  };
  return <span className={map[type] || 'op-badge op-badge-live'}>{type}</span>;
}

/* ── Haversine distance (km) ─────────────────── */
function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const IntelligencePanel = memo(function IntelligencePanel({ earthquakes, disasters, sourceHealth, incidents, onRefresh }) {
  const eqs = earthquakes || [];
  const gds = disasters || [];
  const sources = sourceHealth || [];

  const [compoundEvents, setCompoundEvents] = useState([]);
  const [compoundLoading, setCompoundLoading] = useState(false);
  const [probing, setProbing] = useState(false);

  const handleProbeAll = async () => {
    setProbing(true);
    try {
      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      await fetch(`${API_BASE}/api/intelligence/status/refresh`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include',
      });
      if (onRefresh) await onRefresh();
    } catch { /* ignore */ }
    setProbing(false);
  };

  const fetchCompoundEvents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/intelligence/compound-events`);
      if (res.ok) {
        const data = await res.json();
        setCompoundEvents(data.compound_events || []);
      }
    } catch { /* ignore */ }
  }, []);

  const triggerCorrelation = useCallback(async () => {
    setCompoundLoading(true);
    try {
      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      const res = await fetch(`${API_BASE}/api/intelligence/correlate`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setCompoundEvents(data.compound_events || []);
      }
    } catch { /* ignore */ }
    finally { setCompoundLoading(false); }
  }, []);

  useEffect(() => {
    fetchCompoundEvents();
  }, [fetchCompoundEvents]);

  // Build spatial correlations
  const correlations = [];
  (incidents || []).forEach(inc => {
    if (!inc.latitude || !inc.longitude) return;
    eqs.forEach(eq => {
      if (!eq.latitude || !eq.longitude) return;
      const dist = haversineKm(inc.latitude, inc.longitude, eq.latitude, eq.longitude);
      if (dist < 100) {
        correlations.push({
          incident: inc,
          event: eq,
          eventType: 'EARTHQUAKE',
          distance: dist,
          label: `M${eq.magnitude?.toFixed(1)} — ${eq.place}`,
        });
      }
    });
  });
  correlations.sort((a, b) => a.distance - b.distance);

  return (
    <div>
      {/* Source Health Matrix */}
      <div className="eoc-section">
        <div className="eoc-section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="eoc-section-title">📡 External Data Source Health Matrix</div>
          <button
            className="btn-secondary"
            onClick={handleProbeAll}
            disabled={probing}
            style={{ fontSize: 11, padding: '4px 12px', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <span>{probing ? '⚡ Probing All Providers...' : '🔄 Verify & Probe All Feeds'}</span>
          </button>
        </div>
        <div className="glass-card" style={{ padding: 14 }}>
          {sources.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e293b' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Provider</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Status</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Latency</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Freshness</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Records</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s, i) => {
                  const st = String(s.status || '').toLowerCase();
                  const isOp = st.includes('operational');
                  const isDeg = st.includes('degraded');
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(30,41,59,0.5)' }}>
                      <td style={{ padding: '8px', color: '#f8fafc', fontWeight: 600 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className={`sh-dot ${isOp ? 'operational' : isDeg ? 'degraded' : 'unavailable'}`} style={{ width: 8, height: 8, borderRadius: '50%', display: 'inline-block' }} />
                          {s.name}
                        </div>
                      </td>
                      <td style={{ padding: '8px' }}>
                        <span className={`status-badge ${isOp ? 'healthy' : isDeg ? 'warning' : 'error'}`} style={{ fontSize: 9 }}>
                          {isOp ? 'OPERATIONAL' : isDeg ? 'DEGRADED' : 'UNAVAILABLE'}
                        </span>
                      </td>
                      <td style={{ padding: '8px', textAlign: 'right', color: '#94a3b8', fontFamily: 'monospace' }}>
                        {s.response_time_ms ? `${s.response_time_ms.toFixed(0)}ms` : '—'}
                      </td>
                      <td style={{ padding: '8px', textAlign: 'right', color: '#94a3b8', fontFamily: 'monospace' }}>
                        {s.freshness_seconds != null ? `${s.freshness_seconds.toFixed(0)}s` : '—'}
                      </td>
                      <td style={{ padding: '8px', textAlign: 'right', color: '#94a3b8' }}>{s.record_count || 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="empty-state">
              <div className="empty-state-text">Source health data loading...</div>
            </div>
          )}
        </div>
      </div>

      {/* USGS Earthquakes */}
      <div className="eoc-section">
        <div className="eoc-section-header">
          <div className="eoc-section-title">🌍 USGS Earthquake Feed</div>
          <ProvenanceBadge type={eqs.length > 0 ? 'LIVE' : 'UNAVAILABLE'} />
        </div>
        <div className="glass-card" style={{ padding: 14 }}>
          {eqs.length > 0 ? (
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1e293b' }}>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>MAG</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>PLACE</th>
                    <th style={{ textAlign: 'right', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>DEPTH</th>
                    <th style={{ textAlign: 'right', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>COORDS</th>
                  </tr>
                </thead>
                <tbody>
                  {eqs.map((eq, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(30,41,59,0.5)' }}>
                      <td style={{ padding: '6px 8px' }}>
                        <span style={{
                          fontWeight: 800,
                          color: eq.magnitude >= 6 ? '#ef4444' : eq.magnitude >= 5 ? '#f59e0b' : '#10b981',
                          fontSize: 13,
                        }}>
                          M{eq.magnitude?.toFixed(1)}
                        </span>
                      </td>
                      <td style={{ padding: '6px 8px', color: '#f8fafc', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{eq.place}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', color: '#94a3b8', fontFamily: 'monospace' }}>{eq.depth_km?.toFixed(0)}km</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', color: '#64748b', fontFamily: 'monospace', fontSize: 10 }}>{eq.latitude?.toFixed(2)}, {eq.longitude?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state"><div className="empty-state-text">No earthquake data available</div><div className="empty-state-sub">USGS feed may be temporarily unavailable</div></div>
          )}
        </div>
      </div>

      {/* GDACS Alerts */}
      <div className="eoc-section">
        <div className="eoc-section-header">
          <div className="eoc-section-title">⚠️ GDACS Global Disaster Alerts</div>
          <ProvenanceBadge type={gds.length > 0 ? 'LIVE' : 'UNAVAILABLE'} />
        </div>
        <div className="glass-card" style={{ padding: 14 }}>
          {gds.length > 0 ? (
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1e293b' }}>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>TYPE</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>LOCATION</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>ALERT</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10 }}>SEVERITY</th>
                  </tr>
                </thead>
                <tbody>
                  {gds.map((d, i) => {
                    const level = String(d.alert_level || d.alertlevel || '').toLowerCase();
                    return (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(30,41,59,0.5)' }}>
                        <td style={{ padding: '6px 8px', color: '#f8fafc', fontWeight: 600 }}>{d.event_type?.toUpperCase() || '—'}</td>
                        <td style={{ padding: '6px 8px', color: '#94a3b8', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.place || d.title || '—'}</td>
                        <td style={{ padding: '6px 8px' }}>
                          <span className={`status-badge ${level === 'red' ? 'error' : level === 'orange' ? 'warning' : 'healthy'}`} style={{ fontSize: 9 }}>
                            {level.toUpperCase() || '—'}
                          </span>
                        </td>
                        <td style={{ padding: '6px 8px', color: '#94a3b8' }}>{d.severity || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state"><div className="empty-state-text">No GDACS alerts available</div><div className="empty-state-sub">GDACS feed may be temporarily unavailable</div></div>
          )}
        </div>
      </div>

      {/* Compound Events & Cascading Hazard Modeling (Phase P3.3) */}
      <div className="eoc-section">
        <div className="eoc-section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="eoc-section-title">
            💥 Compound Disaster Events & Cascading Lifelines ({compoundEvents.length})
          </div>
          <button
            onClick={triggerCorrelation}
            disabled={compoundLoading}
            style={{
              background: '#ea580c',
              border: 'none',
              color: '#fff',
              padding: '6px 12px',
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 700,
              cursor: compoundLoading ? 'not-allowed' : 'pointer',
            }}
          >
            {compoundLoading ? 'Evaluating Cascade Graphs...' : '⚡ Run Compound Correlation Engine'}
          </button>
        </div>

        <div className="glass-card" style={{ padding: 14 }}>
          {compoundEvents.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {compoundEvents.map(ce => (
                <div
                  key={ce.compound_id}
                  style={{
                    background: 'rgba(15, 23, 42, 0.7)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderLeft: `4px solid ${ce.cascade_risk_level === 'CRITICAL' ? '#ef4444' : '#f59e0b'}`,
                    borderRadius: 8,
                    padding: 12,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <strong style={{ color: '#f8fafc', fontSize: 12 }}>{ce.correlation_type?.replace(/_/g, ' ')}</strong>
                      <span className={`status-badge ${ce.cascade_risk_level === 'CRITICAL' ? 'error' : 'warning'}`} style={{ fontSize: 9 }}>
                        {ce.cascade_risk_level}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 10, color: '#38bdf8' }}>Confidence: {(ce.confidence_score * 100).toFixed(0)}%</span>
                      <ProvenanceBadge type="CALCULATED" />
                    </div>
                  </div>

                  {/* Cascade Chain Steps */}
                  <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: '8px 10px', borderRadius: 6, margin: '8px 0' }}>
                    <div style={{ fontSize: 10, color: '#64748b', fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>
                      Causal Failure Progression Chain:
                    </div>
                    {(ce.cascade_chain || []).map((step, idx) => (
                      <div key={idx} style={{ fontSize: 11, color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: 6, margin: '3px 0' }}>
                        <span style={{ color: '#ea580c', fontWeight: 700 }}>{idx + 1}.</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>

                  {/* Tactical Precautions */}
                  {ce.recommendations && ce.recommendations.length > 0 && (
                    <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 6 }}>
                      <strong style={{ color: '#38bdf8' }}>Recommended Precautions: </strong>
                      {ce.recommendations.join(' ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-text">No Compound Cascades Detected</div>
              <div className="empty-state-sub">Click "Run Compound Correlation Engine" to evaluate multi-hazard graphs across active intelligence feeds.</div>
            </div>
          )}
        </div>
      </div>

      {/* Incident ↔ Intelligence Correlation */}
      {correlations.length > 0 && (
        <div className="eoc-section">
          <div className="eoc-section-header">
            <div className="eoc-section-title">⚡ Incident ↔ Intelligence Spatial Correlations</div>
          </div>
          <div className="glass-card" style={{ padding: 14 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 250, overflowY: 'auto' }}>
              {correlations.slice(0, 10).map((c, i) => (
                <div key={i} className="correlation-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontWeight: 700, color: '#f8fafc' }}>{c.eventType}: {c.label}</span>
                    </div>
                    <ProvenanceBadge type="LIVE" />
                  </div>
                  <div className="correlation-arrow">↕ {c.distance.toFixed(0)} km from INC-{c.incident.incident_id} ({c.incident.location})</div>
                  <div className="correlation-warning">⚠ Possible spatial proximity. Requires operator confirmation. Does not imply causation.</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

export default IntelligencePanel;
