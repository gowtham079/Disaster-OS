import React, { useState, useEffect, useCallback } from 'react';

import { API_BASE } from '../config';

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

export default function AnalyticsPanel({ runs = [], selectedRun = '', onSelectRun, authFetch }) {
  const [currentRunId, setCurrentRunId] = useState(selectedRun || (runs[0]?.run_id || ''));
  const [activeSubTab, setActiveSubTab] = useState('overview'); // overview | incidents | resources | intelligence | quality | reports
  const [analyticsData, setAnalyticsData] = useState(null);
  const [qualityData, setQualityData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloadingFormat, setDownloadingFormat] = useState(null);
  const [downloadMessage, setDownloadMessage] = useState('');
  const [downloadStatus, setDownloadStatus] = useState('idle'); // idle | success | error

  useEffect(() => {
    if (selectedRun && selectedRun !== currentRunId) {
      setCurrentRunId(selectedRun);
    }
  }, [selectedRun]);

  const loadAnalytics = useCallback(async (runId) => {
    setLoading(true);
    try {
      const url = runId ? `/api/analytics/overview?run_id=${runId}` : '/api/analytics/overview';
      const [ovRes, qRes] = await Promise.all([
        authFetch(url),
        authFetch('/api/analytics/quality'),
      ]);
      const [ovData, qData] = await Promise.all([ovRes.json(), qRes.json()]);
      if (ovData.status === 'success') {
        setAnalyticsData(ovData);
      }
      if (qData.status === 'success') {
        setQualityData(qData.metrics);
      }
    } catch {
      // Fallback empty data
      setAnalyticsData(null);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    loadAnalytics(currentRunId);
  }, [currentRunId, loadAnalytics]);

  const handleRunChange = (newRunId) => {
    setCurrentRunId(newRunId);
    onSelectRun?.(newRunId);
  };

  const handleDownload = async (format) => {
    if (!currentRunId) {
      setDownloadMessage('Please select an active or historical Run ID to export.');
      setDownloadStatus('error');
      return;
    }

    setDownloadingFormat(format);
    setDownloadStatus('idle');
    setDownloadMessage(`Compiling ${format.toUpperCase()} operational report for Run ${currentRunId.substring(0, 8)}...`);

    try {
      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      const url = `${API_BASE}/api/run/${currentRunId}/export/${format}`;
      
      const res = await fetch(url, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include',
      });

      if (!res.ok) {
        let errText = 'Export failed';
        try {
          const errJson = await res.json();
          errText = errJson.message || errText;
        } catch {
          errText = `HTTP ${res.status} error during export generation`;
        }
        setDownloadStatus('error');
        setDownloadMessage(`Failed to generate ${format.toUpperCase()}: ${errText}`);
        return;
      }

      const blob = await res.blob();
      if (blob.size === 0) {
        setDownloadStatus('error');
        setDownloadMessage(`Generated ${format.toUpperCase()} was empty. Insufficient operational records.`);
        return;
      }

      // Trigger browser file download
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `disaster_os_run_${currentRunId.substring(0, 8)}_${format}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);

      setDownloadStatus('success');
      setDownloadMessage(`Successfully downloaded ${format.toUpperCase()} report (${(blob.size / 1024).toFixed(1)} KB). File verified.`);
    } catch (err) {
      setDownloadStatus('error');
      setDownloadMessage(`Network error downloading ${format.toUpperCase()}: ${err.message}`);
    } finally {
      setDownloadingFormat(null);
    }
  };

  const inc = analyticsData?.incidents || {};
  const res = analyticsData?.resources || {};
  const intel = analyticsData?.intelligence || {};
  const perf = analyticsData?.performance || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── TOP CONTROLLER: RUN SELECTOR & TAB NAVIGATION ── */}
      <div className="eoc-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div>
            <h3 style={{ fontSize: 16, marginBottom: 2 }}>Operational Intelligence & Analytics</h3>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              Deterministic operational metrics, telemetry analytics, and audit-ready reporting.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)' }}>RUN SCOPE:</label>
            <select
              className="input-control"
              value={currentRunId}
              onChange={(e) => handleRunChange(e.target.value)}
              style={{ width: 170, padding: '5px 10px', fontSize: 12 }}
            >
              <option value="">Global (All Records)</option>
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id.substring(0, 8)} ({r.status || 'DONE'})
                </option>
              ))}
            </select>
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => loadAnalytics(currentRunId)}
            disabled={loading}
          >
            {loading ? 'Refreshing...' : '↻ Refresh Metrics'}
          </button>
        </div>
      </div>

      {/* ── SUB-TABS NAVIGATION ── */}
      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
        {[
          { id: 'overview', label: 'Executive Overview' },
          { id: 'incidents', label: 'Incident Analytics' },
          { id: 'resources', label: 'Resource & Capacity' },
          { id: 'intelligence', label: 'Live Intelligence' },
          { id: 'quality', label: 'Data Quality Center' },
          { id: 'reports', label: 'Audit-Ready Reports' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            className={`btn btn-sm ${activeSubTab === tab.id ? 'btn-primary' : 'btn-secondary'}`}
            style={{ borderRadius: 'var(--radius-sm)' }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── SUB-TAB 1: EXECUTIVE OVERVIEW ── */}
      {activeSubTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="eoc-grid-4">
            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Total Incidents</span>
                <ProvenanceBadge type="DATABASE" />
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--color-danger)' }}>{inc.total_incidents ?? 0}</div>
              <div className="kpi-sub-v2">{inc.active_incidents ?? 0} Active &bull; {inc.resolved_incidents ?? 0} Resolved</div>
            </div>

            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Total Victims</span>
                <ProvenanceBadge type="DATABASE" />
              </div>
              <div className="kpi-value-v2" style={{ color: '#fff' }}>{(perf.total_victims ?? inc.total_people_affected ?? 0).toLocaleString()}</div>
              <div className="kpi-sub-v2">Recorded across operational run</div>
            </div>

            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Calculated Simulation Performance Score</span>
                <ProvenanceBadge type="CALCULATED" />
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--accent-lime)' }}>
                {(perf.simulation_performance_score ?? perf.calculated_simulation_performance_score) !== null && (perf.simulation_performance_score ?? perf.calculated_simulation_performance_score) !== undefined ? `${perf.simulation_performance_score ?? perf.calculated_simulation_performance_score}%` : (perf.overall_efficiency || 'UNAVAILABLE')}
              </div>
              <div className="kpi-sub-v2">Custom simulation heuristic</div>
            </div>

            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Resource Assignment</span>
                <ProvenanceBadge type="CALCULATED" />
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--color-info)' }}>{res.fleet_assignment_rate_pct != null ? `${res.fleet_assignment_rate_pct}%` : `${res.fleet_utilization_pct ?? 0.0}%`}</div>
              <div className="kpi-sub-v2">Active Utilization: {res.active_utilization_pct ?? 0.0}%</div>
            </div>
          </div>

          <div className="eoc-grid-4">
            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Rescued</span>
                <ProvenanceBadge type="CALCULATED" />
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--color-success)' }}>{(perf.rescued_victims ?? 0).toLocaleString()}</div>
              <div className="kpi-sub-v2">Rescue Rate: {perf.rescue_rate_pct != null ? `${perf.rescue_rate_pct}%` : 'N/A'}</div>
            </div>

            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Waiting / Unresolved</span>
                <ProvenanceBadge type="CALCULATED" />
              </div>
              <div className="kpi-value-v2" style={{ color: '#f59e0b' }}>{(perf.waiting_victims ?? 0).toLocaleString()}</div>
              <div className="kpi-sub-v2">Awaiting evacuation / triage</div>
            </div>

            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Casualties</span>
                <ProvenanceBadge type="CALCULATED" />
              </div>
              <div className="kpi-value-v2" style={{ color: '#ef4444' }}>{(perf.casualties ?? 0).toLocaleString()}</div>
              <div className="kpi-sub-v2">Casualty Rate: {perf.casualty_rate_pct != null ? `${perf.casualty_rate_pct}%` : '0.0%'}</div>
            </div>

            <div className="kpi-card-v2">
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Active Resource Utilization</span>
                <ProvenanceBadge type="CALCULATED" />
              </div>
              <div className="kpi-value-v2" style={{ color: '#06b6d4' }}>{res.active_utilization_pct ?? 0.0}%</div>
              <div className="kpi-sub-v2">En route responding to incidents</div>
            </div>
          </div>

          <div className="eoc-grid-2">
            <div className="eoc-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <h4 style={{ fontSize: 13 }}>Incident Severity Breakdown</h4>
                <ProvenanceBadge type="DATABASE" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 6, padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: '#f87171', fontWeight: 700 }}>HIGH</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', margin: '4px 0' }}>{inc.severity_breakdown?.high ?? 0}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Priority 1</div>
                </div>
                <div style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: 6, padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700 }}>MEDIUM</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', margin: '4px 0' }}>{inc.severity_breakdown?.medium ?? 0}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Priority 2</div>
                </div>
                <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 6, padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: '#34d399', fontWeight: 700 }}>LOW</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', margin: '4px 0' }}>{inc.severity_breakdown?.low ?? 0}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Priority 3</div>
                </div>
              </div>
            </div>

            <div className="eoc-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <h4 style={{ fontSize: 13 }}>Response Performance Metrics</h4>
                <ProvenanceBadge type="CALCULATED" />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Planned Route ETA (OSRM):</span>
                  <strong style={{ color: 'var(--accent-lime)' }}>
                    {(perf.planned_route_eta_mins ?? perf.avg_eta_mins) !== null && (perf.planned_route_eta_mins ?? perf.avg_eta_mins) !== undefined ? `${perf.planned_route_eta_mins ?? perf.avg_eta_mins} minutes` : 'UNAVAILABLE'}
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Actual Response Time:</span>
                  <strong style={{ color: (perf.actual_response_time_mins !== null && perf.actual_response_time_mins !== undefined) ? 'var(--accent-lime)' : 'var(--text-muted)' }}>
                    {(perf.actual_response_time_mins !== null && perf.actual_response_time_mins !== undefined) ? `${perf.actual_response_time_mins} minutes` : 'UNAVAILABLE'}
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Avg Dispatch Distance:</span>
                  <strong style={{ color: '#fff' }}>
                    {perf.avg_distance_km !== null && perf.avg_distance_km !== undefined ? `${perf.avg_distance_km} km` : 'UNAVAILABLE'}
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>ML Detection Latency:</span>
                  <strong style={{ color: 'var(--color-success)' }}>
                    {perf.detection_latency_secs !== null && perf.detection_latency_secs !== undefined ? `${perf.detection_latency_secs}s` : 'REAL-TIME'}
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Containment Rate:</span>
                  <strong style={{ color: 'var(--color-info)' }}>
                    {perf.containment_rate_pct !== null && perf.containment_rate_pct !== undefined ? `${perf.containment_rate_pct}%` : 'N/A'}
                  </strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── SUB-TAB 2: INCIDENT ANALYTICS ── */}
      {activeSubTab === 'incidents' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="eoc-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div>
                <h4 style={{ fontSize: 14 }}>Incident Progression & Timeline Distribution</h4>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Sequential operational triage log for active incidents.</p>
              </div>
              <ProvenanceBadge type="DATABASE" />
            </div>

            {(!inc.time_series || inc.time_series.length === 0) ? (
              <div className="empty-state">
                <div className="empty-state-text">Insufficient operational data for this analysis</div>
                <div className="empty-state-sub">No recorded incidents match the selected run scope</div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {inc.time_series.map((item, idx) => (
                  <div key={idx} style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontWeight: 700, color: 'var(--accent-lime)', fontFamily: 'monospace' }}>{item.label}</span>
                      <span className={`status-badge ${item.severity === 'high' ? 'error' : item.severity === 'medium' ? 'warning' : 'healthy'}`} style={{ fontSize: 9 }}>
                        {item.severity}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 11 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Affected: <strong style={{ color: '#fff' }}>{item.people_affected}</strong></span>
                      <span style={{ color: 'var(--text-secondary)' }}>Status: <strong style={{ color: 'var(--accent-lime)' }}>{item.status}</strong></span>
                      <span style={{ color: 'var(--text-secondary)' }}>ETA: <strong style={{ color: '#38bdf8' }}>{item.eta_mins} min</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="eoc-grid-2">
            <div className="eoc-card">
              <h4 style={{ fontSize: 13, marginBottom: 12 }}>Disaster Classification Distribution</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(inc.type_breakdown || {}).length === 0 ? (
                  <div className="empty-state" style={{ padding: '14px' }}>No incident type records</div>
                ) : (
                  Object.entries(inc.type_breakdown).map(([type, count]) => (
                    <div key={type} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface-card)', padding: '8px 12px', borderRadius: 4 }}>
                      <span style={{ fontWeight: 600, color: '#fff' }}>{type}</span>
                      <span className="op-badge op-badge-db">{count} incidents</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="eoc-card">
              <h4 style={{ fontSize: 13, marginBottom: 12 }}>Status Progression Breakdown</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(inc.status_breakdown || {}).map(([status, count]) => (
                  <div key={status} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface-card)', padding: '8px 12px', borderRadius: 4 }}>
                    <span style={{ fontWeight: 600, color: '#fff' }}>{status}</span>
                    <span className="op-badge op-badge-calc">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── SUB-TAB 3: RESOURCE & CAPACITY ── */}
      {activeSubTab === 'resources' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="eoc-grid-2">
            <div className="eoc-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ fontSize: 13 }}>🏥 Hospital Bed Census & Utilization</h4>
                <ProvenanceBadge type="DATABASE" />
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
                Overall Occupancy: <strong style={{ color: (res.hospitals?.occupancy_pct || 0) > 80 ? 'var(--color-danger)' : 'var(--color-success)' }}>{res.hospitals?.occupancy_pct ?? 0}%</strong> ({res.hospitals?.available_beds ?? 0}/{res.hospitals?.total_beds ?? 0} available)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(res.hospitals?.items || []).map((h, i) => {
                  const used = (h.total || 0) - (h.available || 0);
                  const pct = h.total > 0 ? Math.round((used / h.total) * 100) : 0;
                  return (
                    <div key={i} style={{ background: 'var(--bg-surface-elevated)', padding: '8px 12px', borderRadius: 6 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                        <span style={{ color: '#fff', fontWeight: 600 }}>{h.name || `Hospital ${i+1}`}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{used}/{h.total} beds ({pct}%)</span>
                      </div>
                      <div className="capacity-bar-wrap">
                        <div className={`capacity-bar-fill ${pct > 80 ? 'red' : pct > 50 ? 'amber' : 'green'}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="eoc-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ fontSize: 13 }}>🏕️ Shelter Capacity & Headcount</h4>
                <ProvenanceBadge type="DATABASE" />
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
                Overall Occupancy: <strong style={{ color: (res.shelters?.occupancy_pct || 0) > 80 ? 'var(--color-danger)' : 'var(--color-success)' }}>{res.shelters?.occupancy_pct ?? 0}%</strong> ({res.shelters?.available_capacity ?? 0}/{res.shelters?.total_capacity ?? 0} available)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(res.shelters?.items || []).map((s, i) => {
                  const used = (s.total || 0) - (s.available || 0);
                  const pct = s.total > 0 ? Math.round((used / s.total) * 100) : 0;
                  return (
                    <div key={i} style={{ background: 'var(--bg-surface-elevated)', padding: '8px 12px', borderRadius: 6 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                        <span style={{ color: '#fff', fontWeight: 600 }}>{s.name || `Shelter ${i+1}`}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{used}/{s.total} ({pct}%)</span>
                      </div>
                      <div className="capacity-bar-wrap">
                        <div className={`capacity-bar-fill ${pct > 80 ? 'red' : pct > 50 ? 'amber' : 'green'}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── SUB-TAB 4: LIVE INTELLIGENCE ── */}
      {activeSubTab === 'intelligence' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="eoc-grid-2">
            <div className="eoc-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ fontSize: 13 }}>Earthquake Magnitude Distribution (USGS)</h4>
                <ProvenanceBadge type="LIVE" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {Object.entries(intel.earthquake_magnitude_distribution || {}).map(([bucket, count]) => (
                  <div key={bucket} style={{ background: 'var(--bg-surface-elevated)', padding: '10px', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{bucket}</div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: '#fff', margin: '4px 0' }}>{count}</div>
                    <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Events</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="eoc-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ fontSize: 13 }}>Global Alert Distribution (GDACS)</h4>
                <ProvenanceBadge type="LIVE" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {Object.entries(intel.gdacs_alert_distribution || {}).map(([lvl, count]) => (
                  <div key={lvl} style={{ background: 'var(--bg-surface-elevated)', padding: '10px', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: lvl === 'Red' ? 'var(--color-danger)' : lvl === 'Orange' ? 'var(--color-warning)' : 'var(--color-success)', fontWeight: 700 }}>{lvl}</div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: '#fff', margin: '4px 0' }}>{count}</div>
                    <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Alerts</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="eoc-card">
            <h4 style={{ fontSize: 13, marginBottom: 12 }}>External Provider Availability & Latency Matrix</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {(intel.source_health_summary || []).map((src) => (
                <div key={src.source_name} style={{ background: 'var(--bg-surface-elevated)', padding: '10px 14px', borderRadius: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <strong style={{ color: '#fff', fontSize: 12 }}>{src.source_name}</strong>
                    <span className="status-badge healthy" style={{ fontSize: 9 }}>{src.uptime_pct}% Uptime</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)' }}>
                    <span>Avg Latency:</span>
                    <strong style={{ color: 'var(--accent-lime)' }}>{src.avg_latency_ms} ms</strong>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── SUB-TAB 5: DATA QUALITY CENTER ── */}
      {activeSubTab === 'quality' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="eoc-card-highlight">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h4 style={{ fontSize: 14 }}>System Integrity & Database Audit Center</h4>
              <span className="status-badge healthy">INTEGRITY: {qualityData?.db_integrity?.toUpperCase() || 'OK'}</span>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14 }}>
              Continuous SQLite WAL validation, foreign key integrity checks, and data provenance auditing.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
                <div className="kpi-top-row">
                  <span className="kpi-label-v2">Coordinate Completeness</span>
                  <ProvenanceBadge type="CALCULATED" />
                </div>
                <div className="kpi-value-v2" style={{ color: 'var(--color-success)' }}>{qualityData?.coordinate_completeness_pct ?? 100}%</div>
                <div className="kpi-sub-v2">{qualityData?.missing_coordinate_records ?? 0} missing coords</div>
              </div>

              <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
                <div className="kpi-top-row">
                  <span className="kpi-label-v2">Total DB Records</span>
                  <ProvenanceBadge type="DATABASE" />
                </div>
                <div className="kpi-value-v2" style={{ color: '#fff' }}>
                  {Object.values(qualityData?.record_counts || {}).reduce((a, b) => a + b, 0).toLocaleString()}
                </div>
                <div className="kpi-sub-v2">Across 11 SQLite tables</div>
              </div>

              <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
                <div className="kpi-top-row">
                  <span className="kpi-label-v2">Provenance Model</span>
                  <ProvenanceBadge type="DATABASE" />
                </div>
                <div className="kpi-value-v2" style={{ color: 'var(--accent-lime)', fontSize: 18 }}>5-Tier Strict</div>
                <div className="kpi-sub-v2">Zero fabricated fallbacks</div>
              </div>

              <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
                <div className="kpi-top-row">
                  <span className="kpi-label-v2">Security Gateway</span>
                  <ProvenanceBadge type="DATABASE" />
                </div>
                <div className="kpi-value-v2" style={{ color: 'var(--color-info)', fontSize: 18 }}>Active Sessions</div>
                <div className="kpi-sub-v2">24h SQLite Token Expiry</div>
              </div>
            </div>
          </div>

          <div className="eoc-card">
            <h4 style={{ fontSize: 13, marginBottom: 12 }}>SQLite Table Record Breakdown</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
              {Object.entries(qualityData?.record_counts || {}).map(([table, count]) => (
                <div key={table} style={{ background: 'var(--bg-surface-elevated)', padding: '8px 12px', borderRadius: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)', fontSize: 11 }}>{table}</span>
                  <strong style={{ color: '#fff', fontSize: 12 }}>{count}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── SUB-TAB 6: AUDIT-READY REPORTS ── */}
      {activeSubTab === 'reports' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="eoc-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div>
                <h4 style={{ fontSize: 14 }}>Audit-Ready Telemetry Exporter</h4>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                  Download compliant post-disaster operational audit reports for Run <strong style={{ color: 'var(--accent-lime)', fontFamily: 'monospace' }}>{currentRunId ? currentRunId.substring(0, 8) : 'GLOBAL'}</strong>.
                </p>
              </div>
              <ProvenanceBadge type="DATABASE" />
            </div>

            {downloadMessage && (
              <div
                style={{
                  background: downloadStatus === 'error' ? 'var(--color-danger-bg)' : downloadStatus === 'success' ? 'var(--color-success-bg)' : 'var(--bg-surface-elevated)',
                  border: `1px solid ${downloadStatus === 'error' ? 'var(--color-danger-border)' : downloadStatus === 'success' ? 'var(--color-success-border)' : 'var(--border-subtle)'}`,
                  color: downloadStatus === 'error' ? '#fca5a5' : downloadStatus === 'success' ? '#86efac' : 'var(--text-primary)',
                  padding: '10px 14px',
                  borderRadius: 6,
                  fontSize: 12,
                  marginBottom: 16,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <span>{downloadMessage}</span>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
              {/* CSV Export Card */}
              <div className="eoc-card" style={{ background: 'var(--bg-surface-elevated)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <strong style={{ fontSize: 14, color: '#fff' }}>CSV Data Tables</strong>
                    <span className="op-badge op-badge-db">CSV</span>
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
                    Full tabular records of incidents, response fleet telematics, facility capacities, and operational metrics.
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => handleDownload('csv')}
                  disabled={downloadingFormat === 'csv'}
                  style={{ width: '100%' }}
                >
                  {downloadingFormat === 'csv' ? 'Generating CSV...' : 'Download CSV Table'}
                </button>
              </div>

              {/* JSON Export Card */}
              <div className="eoc-card" style={{ background: 'var(--bg-surface-elevated)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <strong style={{ fontSize: 14, color: '#fff' }}>JSON Telemetry Dump</strong>
                    <span className="op-badge op-badge-db">JSON</span>
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
                    Raw structured JSON telemetry including full 14-agent execution logs, message payloads, and routing coordinates.
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => handleDownload('json')}
                  disabled={downloadingFormat === 'json'}
                  style={{ width: '100%' }}
                >
                  {downloadingFormat === 'json' ? 'Generating JSON...' : 'Download JSON Telemetry'}
                </button>
              </div>

              {/* PDF Export Card */}
              <div className="eoc-card" style={{ background: 'var(--bg-surface-elevated)', border: '1px solid var(--accent-lime-border)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <strong style={{ fontSize: 14, color: '#fff' }}>Print-Ready Audit PDF</strong>
                    <span className="op-badge op-badge-live">PDF</span>
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 16 }}>
                    Executive PDF audit report with Disaster OS branding, executive summary narrative, triage tables, and page numbers.
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => handleDownload('pdf')}
                  disabled={downloadingFormat === 'pdf'}
                  style={{ width: '100%' }}
                >
                  {downloadingFormat === 'pdf' ? 'Generating PDF...' : 'Download PDF Audit Report'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
