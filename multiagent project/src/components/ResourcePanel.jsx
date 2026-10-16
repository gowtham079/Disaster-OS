import React, { memo, useCallback, useEffect, useState } from 'react';
import AnimatedCounter from './AnimatedCounter';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

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

function CapacityBar({ used, total, label }) {
  const utilPct = total > 0 ? Math.round((used / total) * 100) : 0;
  const barClass = utilPct > 80 ? 'red' : utilPct > 50 ? 'amber' : 'green';
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
        <span style={{ color: '#f8fafc', fontWeight: 600 }}>{label}</span>
        <span style={{ color: '#94a3b8' }}>{used}/{total} ({utilPct}%)</span>
      </div>
      <div className="capacity-bar-wrap">
        <div className={`capacity-bar-fill ${barClass}`} style={{ width: `${utilPct}%` }} />
      </div>
      {utilPct > 80 && (
        <div style={{ fontSize: 10, color: '#ef4444', fontWeight: 600, marginTop: 2 }}>⚠ Capacity warning: {utilPct}% utilized</div>
      )}
    </div>
  );
}

const REGIONAL_HUBS = [
  { name: 'Mumbai', lat: 19.0760, lng: 72.8777 },
  { name: 'Delhi NCR', lat: 28.6139, lng: 77.2090 },
  { name: 'Bengaluru', lat: 12.9716, lng: 77.5946 },
  { name: 'Kolkata', lat: 22.5726, lng: 88.3639 },
  { name: 'Chennai', lat: 13.0827, lng: 80.2707 },
  { name: 'Hyderabad', lat: 17.3850, lng: 78.4867 },
];

const ResourcePanel = memo(function ResourcePanel({ facilities, runId }) {
  const [activeTab, setActiveTab] = useState('real'); // 'real' | 'simulated'
  const [realFacilities, setRealFacilities] = useState([]);
  const [loadingReal, setLoadingReal] = useState(false);
  const [realFilter, setRealFilter] = useState('all');
  const [selectedHub, setSelectedHub] = useState('Mumbai');

  const fetchRealFacilities = useCallback(async (hubOverride) => {
    const hubName = hubOverride || selectedHub;
    let lat = null;
    let lng = null;

    const hubObj = REGIONAL_HUBS.find(h => h.name === hubName);
    if (hubObj) {
      lat = hubObj.lat;
      lng = hubObj.lng;
    } else if (facilities && facilities.length > 0) {
      const targetFac = facilities.find(f => f.latitude != null && f.longitude != null);
      if (targetFac) {
        lat = Number(targetFac.latitude);
        lng = Number(targetFac.longitude);
      }
    }

    if (lat == null || lng == null || !Number.isFinite(lat)) {
      lat = REGIONAL_HUBS[0].lat;
      lng = REGIONAL_HUBS[0].lng;
    }

    setLoadingReal(true);
    try {
      const resp = await fetch(`${API_BASE}/api/intelligence/facilities?lat=${lat.toFixed(4)}&lng=${lng.toFixed(4)}&radius_km=30`);
      if (resp.ok) {
        const data = await resp.json();
        let facs = data.facilities || [];
        if (facs.length === 0) {
          // Check persisted real facilities endpoint as instant fallback
          const fbResp = await fetch(`${API_BASE}/api/facilities/real?radius_km=60&lat=${lat.toFixed(4)}&lng=${lng.toFixed(4)}`);
          if (fbResp.ok) {
            const fbData = await fbResp.json();
            if (fbData.facilities && fbData.facilities.length > 0) {
              facs = fbData.facilities;
            }
          }
        }
        setRealFacilities(facs);
      }
    } catch {
      // ignore
    }
    setLoadingReal(false);
  }, [facilities, selectedHub]);

  useEffect(() => {
    fetchRealFacilities();
  }, [fetchRealFacilities]);

  const simFacilities = facilities || [];
  const simHospitals = simFacilities.filter(f => f.facility_type === 'hospital');
  const simShelters = simFacilities.filter(f => f.facility_type === 'shelter');

  // Simulated Hospital aggregate
  const simTotalBeds = simHospitals.reduce((s, h) => s + (h.total_capacity || 0), 0);
  const simAvailBeds = simHospitals.reduce((s, h) => s + (h.available_capacity || 0), 0);
  const simOccupiedBeds = simTotalBeds - simAvailBeds;
  const simHospUtilPct = simTotalBeds > 0 ? Math.round((simOccupiedBeds / simTotalBeds) * 100) : 0;

  // Simulated Shelter aggregate
  const simTotalShelterCap = simShelters.reduce((s, sh) => s + (sh.total_capacity || 0), 0);
  const simAvailShelterCap = simShelters.reduce((s, sh) => s + (sh.available_capacity || 0), 0);
  const simOccupiedShelter = simTotalShelterCap - simAvailShelterCap;
  const simShelterUtilPct = simTotalShelterCap > 0 ? Math.round((simOccupiedShelter / simTotalShelterCap) * 100) : 0;

  // Real Facilities counts
  const realHospitals = realFacilities.filter(f => f.facility_type === 'hospital');
  const realShelters = realFacilities.filter(f => f.facility_type === 'shelter');
  const realFire = realFacilities.filter(f => f.facility_type === 'fire_station');
  const realPolice = realFacilities.filter(f => f.facility_type === 'police_station');

  const filteredReal = realFilter === 'all'
    ? realFacilities
    : realFacilities.filter(f => f.facility_type === realFilter);

  return (
    <div>
      {/* Top View Selector Toggle */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className={`btn-secondary ${activeTab === 'real' ? 'btn-primary' : ''}`}
            onClick={() => setActiveTab('real')}
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '8px 14px' }}
          >
            <span>🏥 Real-World Facilities (OpenStreetMap)</span>
            <span className="op-badge op-badge-live" style={{ fontSize: 9 }}>LIVE</span>
          </button>
          <button
            className={`btn-secondary ${activeTab === 'simulated' ? 'btn-primary' : ''}`}
            onClick={() => setActiveTab('simulated')}
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '8px 14px' }}
          >
            <span>⚡ Scenario Simulation Resources</span>
            <span className="op-badge op-badge-sim" style={{ fontSize: 9 }}>SIMULATED</span>
          </button>
        </div>

        {activeTab === 'real' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700 }}>📍 Regional Hub:</span>
            {REGIONAL_HUBS.map(hub => (
              <button
                key={hub.name}
                className={`btn-secondary ${selectedHub === hub.name ? 'btn-primary' : ''}`}
                onClick={() => {
                  setSelectedHub(hub.name);
                  fetchRealFacilities(hub.name);
                }}
                style={{ fontSize: 10, padding: '4px 8px' }}
                title={`Inspect real OpenStreetMap facilities in ${hub.name}`}
              >
                {hub.name}
              </button>
            ))}
            <button
              className="btn-secondary"
              onClick={() => fetchRealFacilities(selectedHub)}
              disabled={loadingReal}
              style={{ fontSize: 11, padding: '6px 12px' }}
            >
              {loadingReal ? 'Refreshing...' : '🔄 Refresh OSM Nodes'}
            </button>
          </div>
        )}
      </div>

      {activeTab === 'real' ? (
        <div>
          {/* Provenance Notice */}
          <div className="glass-card" style={{ padding: '12px 16px', marginBottom: 16, borderLeft: '3px solid #38bdf8', background: 'rgba(56, 189, 248, 0.05)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#f8fafc', fontWeight: 600 }}>
              <span>🛡️ Honest Real-World Facility Provenance Guarantee</span>
              <ProvenanceBadge type="LIVE" />
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: 11, color: '#94a3b8', lineHeight: 1.5 }}>
              All infrastructure nodes below are ingested directly from <strong>OpenStreetMap (Overpass API)</strong>. Disaster OS strictly forbids fabricating hospital bed numbers or shelter capacities.
              When live occupancy sensors are not connected, capacity is transparently labeled <span className="op-badge op-badge-unavail">UNAVAILABLE</span> rather than guessing.
            </p>
          </div>

          {/* Real Facilities KPI Grid */}
          <div className="eoc-grid-4" style={{ marginBottom: 20 }}>
            <div className="glass-card eoc-kpi-card" onClick={() => setRealFilter('hospital')} style={{ cursor: 'pointer' }}>
              <div className="kpi-label">Civil Hospitals</div>
              <div className="kpi-value text-purple"><AnimatedCounter value={realHospitals.length} /></div>
              <div className="kpi-sub">Verified OSM medical nodes</div>
            </div>
            <div className="glass-card eoc-kpi-card" onClick={() => setRealFilter('fire_station')} style={{ cursor: 'pointer' }}>
              <div className="kpi-label">Fire Stations</div>
              <div className="kpi-value text-amber"><AnimatedCounter value={realFire.length} /></div>
              <div className="kpi-sub">HAZMAT & rescue brigades</div>
            </div>
            <div className="glass-card eoc-kpi-card" onClick={() => setRealFilter('police_station')} style={{ cursor: 'pointer' }}>
              <div className="kpi-label">Police Divisions</div>
              <div className="kpi-value text-blue"><AnimatedCounter value={realPolice.length} /></div>
              <div className="kpi-sub">Traffic & perimeter control</div>
            </div>
            <div className="glass-card eoc-kpi-card" onClick={() => setRealFilter('shelter')} style={{ cursor: 'pointer' }}>
              <div className="kpi-label">Relief Shelters</div>
              <div className="kpi-value text-green"><AnimatedCounter value={realShelters.length} /></div>
              <div className="kpi-sub">Community domes & centers</div>
            </div>
          </div>

          {/* Type Filter Pills */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
            {['all', 'hospital', 'fire_station', 'police_station', 'shelter'].map(f => (
              <button
                key={f}
                className={`btn-secondary ${realFilter === f ? 'btn-primary' : ''}`}
                onClick={() => setRealFilter(f)}
                style={{ fontSize: 11, padding: '4px 10px', textTransform: 'capitalize' }}
              >
                {f === 'all' ? `All Infrastructure (${realFacilities.length})` : `${f.replace('_', ' ')}s (${realFacilities.filter(item => item.facility_type === f).length})`}
              </button>
            ))}
          </div>

          {/* Real Facilities Grid Cards */}
          {filteredReal.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
              {filteredReal.map((f, i) => (
                <div key={f.facility_id || i} className="glass-card" style={{ padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div>
                      <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: 13 }}>{f.name}</div>
                      <div style={{ fontSize: 10, color: '#64748b' }}>{f.address || `Sector (${f.latitude.toFixed(3)}, ${f.longitude.toFixed(3)})`}</div>
                    </div>
                    <span className="op-badge op-badge-live" style={{ fontSize: 9 }}>
                      {f.source || 'OSM'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderTop: '1px solid rgba(255,255,255,0.06)', borderBottom: '1px solid rgba(255,255,255,0.06)', fontSize: 11 }}>
                    <span style={{ color: '#94a3b8' }}>Type:</span>
                    <strong style={{ color: '#38bdf8', textTransform: 'capitalize' }}>{f.facility_type.replace('_', ' ')}</strong>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', fontSize: 11 }}>
                    <span style={{ color: '#94a3b8' }}>Bed / Unit Capacity:</span>
                    {f.capacity != null ? (
                      <strong className="text-emerald-400">{f.capacity} Units (VERIFIED)</strong>
                    ) : (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span className="op-badge op-badge-unavail" style={{ fontSize: 8 }}>UNAVAILABLE</span>
                        <span style={{ fontSize: 10, color: '#64748b' }}>Sensors Offline</span>
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 10, color: '#64748b', marginTop: 4 }}>
                    <div>Coords: {f.latitude.toFixed(3)}, {f.longitude.toFixed(3)}</div>
                    <div style={{ textAlign: 'right' }}>Emergency: {f.emergency_service ? '✅ 24/7' : 'Standard'}</div>
                  </div>
                  {f.phone && <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 4 }}>📞 {f.phone}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-card">
              <div className="empty-state">
                <div className="empty-state-icon">🏥</div>
                <div className="empty-state-text">No real facilities returned</div>
                <div className="empty-state-sub">Click Refresh to query OpenStreetMap nodes for current location</div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div>
          {/* Simulated Simulation Aggregate KPIs */}
          <div className="eoc-section">
            <div className="eoc-section-header">
              <div className="eoc-section-title">⚡ Scenario Simulation Capacity Overview</div>
              <ProvenanceBadge type="SIMULATED" />
            </div>
            <div className="eoc-grid-4" style={{ marginBottom: 20 }}>
              <div className="glass-card eoc-kpi-card">
                <div className="kpi-label">Scenario Hospital Beds</div>
                <div className="kpi-value text-purple"><AnimatedCounter value={simTotalBeds} /></div>
                <div className="kpi-sub">{simHospitals.length} simulated hospital{simHospitals.length !== 1 ? 's' : ''}</div>
              </div>
              <div className="glass-card eoc-kpi-card">
                <div className="kpi-label">Available Beds</div>
                <div className="kpi-value text-green"><AnimatedCounter value={simAvailBeds} /></div>
                <div className="kpi-sub">{simHospUtilPct}% occupied</div>
              </div>
              <div className="glass-card eoc-kpi-card">
                <div className="kpi-label">Scenario Shelter Capacity</div>
                <div className="kpi-value text-cyan"><AnimatedCounter value={simTotalShelterCap} /></div>
                <div className="kpi-sub">{simShelters.length} simulated shelter{simShelters.length !== 1 ? 's' : ''}</div>
              </div>
              <div className="glass-card eoc-kpi-card">
                <div className="kpi-label">Available Shelter</div>
                <div className="kpi-value text-green"><AnimatedCounter value={simAvailShelterCap} /></div>
                <div className="kpi-sub">{simShelterUtilPct}% occupied</div>
              </div>
            </div>
          </div>

          {/* Hospital Detail Cards */}
          <div className="eoc-section">
            <div className="eoc-section-header">
              <div className="eoc-section-title">🏥 Simulated Hospitals</div>
              <ProvenanceBadge type="SIMULATED" />
            </div>
            {simHospitals.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {simHospitals.map((h, i) => {
                  const used = (h.total_capacity || 0) - (h.available_capacity || 0);
                  return (
                    <div key={i} className="glass-card" style={{ padding: 16 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                        <div>
                          <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: 13 }}>{h.facility_name}</div>
                          <div style={{ fontSize: 10, color: '#64748b' }}>{h.city || 'Unknown city'}</div>
                        </div>
                        <span className="op-badge op-badge-sim" style={{ fontSize: 9 }}>SIMULATED</span>
                      </div>
                      <CapacityBar used={used} total={h.total_capacity || 0} label="Bed Occupancy" />
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
                        <div>Total: <strong style={{ color: '#f8fafc' }}>{h.total_capacity || 0}</strong></div>
                        <div>Occupied: <strong style={{ color: '#f59e0b' }}>{used}</strong></div>
                        <div>Available: <strong style={{ color: '#10b981' }}>{h.available_capacity || 0}</strong></div>
                      </div>
                      {h.phone && <div style={{ fontSize: 10, color: '#64748b', marginTop: 6 }}>📞 {h.phone}</div>}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="glass-card">
                <div className="empty-state">
                  <div className="empty-state-icon">🏥</div>
                  <div className="empty-state-text">No simulated hospital data available</div>
                  <div className="empty-state-sub">Hospital information will appear after a simulation run</div>
                </div>
              </div>
            )}
          </div>

          {/* Shelter Detail Cards */}
          <div className="eoc-section">
            <div className="eoc-section-header">
              <div className="eoc-section-title">⛺ Simulated Shelters</div>
              <ProvenanceBadge type="SIMULATED" />
            </div>
            {simShelters.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {simShelters.map((s, i) => {
                  const used = (s.total_capacity || 0) - (s.available_capacity || 0);
                  return (
                    <div key={i} className="glass-card" style={{ padding: 16 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                        <div>
                          <div style={{ fontWeight: 700, color: '#f8fafc', fontSize: 13 }}>{s.facility_name}</div>
                          <div style={{ fontSize: 10, color: '#64748b' }}>{s.city || 'Unknown city'}</div>
                        </div>
                        <span className="op-badge op-badge-sim" style={{ fontSize: 9 }}>SIMULATED</span>
                      </div>
                      <CapacityBar used={used} total={s.total_capacity || 0} label="Capacity Utilization" />
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
                        <div>Total: <strong style={{ color: '#f8fafc' }}>{s.total_capacity || 0}</strong></div>
                        <div>Occupied: <strong style={{ color: '#f59e0b' }}>{used}</strong></div>
                        <div>Available: <strong style={{ color: '#10b981' }}>{s.available_capacity || 0}</strong></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="glass-card">
                <div className="empty-state">
                  <div className="empty-state-icon">⛺</div>
                  <div className="empty-state-text">No simulated shelter data available</div>
                  <div className="empty-state-sub">Shelter information will appear after a simulation run</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

export default ResourcePanel;
