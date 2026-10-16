import React, { memo } from 'react';
import AnimatedCounter from './AnimatedCounter';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

function ProvenanceBadge({ type }) {
  const map = {
    DATABASE: 'op-badge op-badge-db',
    CALCULATED: 'op-badge op-badge-calc',
    SIMULATED: 'op-badge op-badge-sim',
    LIVE: 'op-badge op-badge-live',
  };
  return <span className={map[type] || 'op-badge op-badge-sim'}>{type}</span>;
}

const FLEET_TYPES = [
  { key: 'ambulance', icon: '🚑', label: 'Ambulance', color: '#ef4444' },
  { key: 'fire_truck', icon: '🚒', label: 'Fire Engine', color: '#f97316' },
  { key: 'police_car', icon: '🚔', label: 'Police Patrol', color: '#3b82f6' },
  { key: 'rescue_boat', icon: '⛵', label: 'Rescue Boat', color: '#06b6d4' },
  { key: 'helicopter', icon: '🚁', label: 'Helicopter', color: '#8b5cf6' },
  { key: 'drone', icon: '🛸', label: 'Recon Drone', color: '#10b981' },
  { key: 'supply_truck', icon: '🚛', label: 'Supply Truck', color: '#f59e0b' },
];

const FleetPanel = memo(function FleetPanel({ resources, fleet, runId, onRefresh, onNavigateToMap }) {
  const [localFleet, setLocalFleet] = React.useState([]);

  React.useEffect(() => {
    let isMounted = true;
    const initial = resources || fleet;
    if ((!initial || initial.length === 0) && runId) {
      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      fetch(`${API_BASE}/api/run/${runId}/resources`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((res) => res.json())
        .then((data) => {
          if (isMounted && data.resources) {
            setLocalFleet(data.resources);
          }
        })
        .catch(() => {});
    }
    return () => {
      isMounted = false;
    };
  }, [resources, fleet, runId]);

  const allResources = (resources && resources.length > 0)
    ? resources
    : (fleet && fleet.length > 0)
    ? fleet
    : localFleet;

  // Overall stats
  const total = allResources.length;
  const available = allResources.filter(r => r.status === 'available').length;
  const dispatched = allResources.filter(r => ['dispatched', 'en_route', 'active'].includes(r.status)).length;
  const busy = allResources.filter(r => r.status === 'busy').length;
  const utilPct = total > 0 ? Math.round(((total - available) / total) * 100) : 0;

  return (
    <div>
      {/* Overall Stats */}
      <div className="eoc-section">
        <div className="eoc-section-header">
          <div className="eoc-section-title">🚑 Response Fleet Overview</div>
          <ProvenanceBadge type="SIMULATED" />
        </div>

        <div className="eoc-grid-4" style={{ marginBottom: 20 }}>
          <div className="glass-card eoc-kpi-card">
            <div className="kpi-label">Total Units</div>
            <div className="kpi-value text-blue"><AnimatedCounter value={total} /></div>
            <div className="kpi-sub">All fleet vehicles</div>
          </div>
          <div className="glass-card eoc-kpi-card">
            <div className="kpi-label">Available</div>
            <div className="kpi-value text-green"><AnimatedCounter value={available} /></div>
            <div className="kpi-sub">Ready for dispatch</div>
          </div>
          <div className="glass-card eoc-kpi-card">
            <div className="kpi-label">Dispatched</div>
            <div className="kpi-value text-amber"><AnimatedCounter value={dispatched} /></div>
            <div className="kpi-sub">En route / active</div>
          </div>
          <div className="glass-card eoc-kpi-card">
            <div className="kpi-label">Utilization</div>
            <div className="kpi-value text-purple">{utilPct}%</div>
            <div className="capacity-bar-wrap" style={{ marginTop: 6 }}>
              <div className={`capacity-bar-fill ${utilPct > 80 ? 'red' : utilPct > 50 ? 'amber' : 'green'}`} style={{ width: `${utilPct}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Fleet Type Breakdown */}
      <div className="eoc-section">
        <div className="eoc-section-header">
          <div className="eoc-section-title">Fleet Breakdown by Category</div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
          {FLEET_TYPES.map(ft => {
            const units = allResources.filter(r => r.resource_type === ft.key);
            if (units.length === 0 && total > 0) return null;
            const avail = units.filter(r => r.status === 'available').length;
            const disp = units.filter(r => ['dispatched', 'en_route', 'active'].includes(r.status)).length;
            return (
              <div key={ft.key} className="glass-card" style={{ padding: 16, cursor: 'pointer' }} onClick={onNavigateToMap}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <div className="fleet-icon" style={{ background: `${ft.color}18` }}>{ft.icon}</div>
                  <div>
                    <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: 14 }}>{ft.label}</div>
                    <div style={{ fontSize: 10, color: '#94a3b8' }}>{units.length} unit{units.length !== 1 ? 's' : ''}</div>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 11 }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontWeight: 800, color: '#10b981', fontSize: 16 }}>{avail}</div>
                    <div style={{ color: '#64748b', fontSize: 9 }}>READY</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontWeight: 800, color: '#f59e0b', fontSize: 16 }}>{disp}</div>
                    <div style={{ color: '#64748b', fontSize: 9 }}>ACTIVE</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontWeight: 800, color: '#64748b', fontSize: 16 }}>{units.length - avail - disp}</div>
                    <div style={{ color: '#64748b', fontSize: 9 }}>OTHER</div>
                  </div>
                </div>
              </div>
            );
          }).filter(Boolean)}
        </div>
        {total === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">🚑</div>
            <div className="empty-state-text">No fleet data available</div>
            <div className="empty-state-sub">Run a simulation to deploy response units</div>
          </div>
        )}
      </div>

      {/* Unit Table */}
      {total > 0 && (
        <div className="eoc-section">
          <div className="eoc-section-header">
            <div className="eoc-section-title">Unit Registry</div>
            <div className="eoc-section-meta">{total} units total</div>
          </div>
          <div className="glass-card" style={{ padding: 14 }}>
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1e293b' }}>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Unit</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Type</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Status</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Location</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', color: '#64748b', fontWeight: 700, fontSize: 10, textTransform: 'uppercase' }}>Assignment</th>
                  </tr>
                </thead>
                <tbody>
                  {allResources.slice(0, 50).map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(30,41,59,0.5)' }}>
                      <td style={{ padding: '6px 8px', color: '#f8fafc', fontWeight: 600 }}>{r.resource_name}</td>
                      <td style={{ padding: '6px 8px', color: '#94a3b8' }}>{r.resource_type}</td>
                      <td style={{ padding: '6px 8px' }}>
                        <span className={`status-badge ${r.status === 'available' ? 'healthy' : r.status === 'dispatched' ? 'running' : 'warning'}`}>
                          {r.status}
                        </span>
                      </td>
                      <td style={{ padding: '6px 8px', color: '#64748b', fontFamily: 'monospace', fontSize: 10 }}>{r.latitude?.toFixed(3)}, {r.longitude?.toFixed(3)}</td>
                      <td style={{ padding: '6px 8px', color: '#94a3b8', fontSize: 10 }}>{r.assigned_incident || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

export default FleetPanel;
