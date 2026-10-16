import React, { useCallback, useEffect, useRef, useState } from 'react';
import LiveMap from './components/LiveMap';
import AnimatedCounter from './components/AnimatedCounter';
import CommandPalette from './components/CommandPalette';
import NotificationCenter from './components/NotificationCenter';
import CitizenReportModal from './components/CitizenReportModal';
import LandingPage from './components/LandingPage';
import LoginPage from './components/LoginPage';
import EOCDashboard from './components/EOCDashboard';
import IncidentFeed from './components/IncidentFeed';
import FleetPanel from './components/FleetPanel';
import IntelligencePanel from './components/IntelligencePanel';
import ResourcePanel from './components/ResourcePanel';
import AnalyticsPanel from './components/AnalyticsPanel';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

/* SVG ICONS */
const Icons = {
  Shield: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
  Dashboard: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg>,
  Simulation: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  LiveMap: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>,
  Analytics: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  AgentHealth: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>,
  Search: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
  Bell: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
  Exit: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>,
  SOS: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" {...props}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  Incident: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>,
  Fleet: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>,
  Intel: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  Resource: (props) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>,
};

/* 14-AGENT PIPELINE STAGES */
const FOURTEEN_STAGES = [
  { id: '1', label: 'Incident Detection', state: 'INCIDENT_REPORTED', desc: 'ML Severity' },
  { id: '2', label: 'Weather Analysis', state: 'WEATHER_ANALYZED', desc: 'OpenWeather API' },
  { id: '3', label: 'Victim Triage', state: 'VICTIMS_TRIAGED', desc: 'Medical Triage' },
  { id: '4', label: 'Resource Allocation', state: 'RESOURCE_ALLOCATED', desc: 'Fleet Dispatch' },
  { id: '5', label: 'Hospital Mgmt', state: 'HOSPITAL_ASSIGNED', desc: 'Trauma Beds' },
  { id: '6', label: 'Shelter Mgmt', state: 'SHELTER_ASSIGNED', desc: 'Evacuee Allocation' },
  { id: '7', label: 'Traffic Control', state: 'TRAFFIC_MANAGED', desc: 'Road Blockages' },
  { id: '8', label: 'Police Patrol', state: 'POLICE_DEPLOYED', desc: 'Perimeter Security' },
  { id: '9', label: 'Fire & HAZMAT', state: 'FIRE_HAZMAT_MANAGED', desc: 'Chemical Safety' },
  { id: '10', label: 'Drone Recon', state: 'DRONE_RECON_ACTIVE', desc: 'Thermal Airborne' },
  { id: '11', label: 'Route Planning', state: 'ROUTE_PLANNED', desc: 'OSRM Real Roads' },
  { id: '12', label: 'Rescue Coord', state: 'RESCUE_IN_PROGRESS', desc: 'Active Rescues' },
  { id: '13', label: 'Communication', state: 'COMMUNICATION_BROADCAST', desc: 'Cell Broadcast' },
  { id: '14', label: 'AI & Evaluation', state: 'COMPLETED', desc: 'Gemini & Audit' },
];

function shortId(id) {
  return id ? id.substring(0, 8) : '-';
}

function fmtTime(ts) {
  if (!ts) return '-';
  try { return new Date(ts).toLocaleTimeString('en-GB', { hour12: false }); } catch { return ts; }
}

export default function App() {
  const [view, setView] = useState('loading'); // 'loading' | 'landing' | 'login' | 'eoc'
  const [currentUser, setCurrentUser] = useState(null);
  const [authToken, setAuthToken] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Modals & Drawers
  const [cmdOpen, setCmdOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [sosOpen, setSosOpen] = useState(false);

  // Simulation controls
  const [seed, setSeed] = useState(42);
  const [strategy, setStrategy] = useState('smart');
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState('');
  const [history, setHistory] = useState([]);
  const [runStatus, setRunStatus] = useState('IDLE');
  const [latestState, setLatestState] = useState('-');
  const [loading, setLoading] = useState(false);

  // EOC Dashboard Metrics
  const [eocMetrics, setEocMetrics] = useState({});

  // Entities & Intelligence
  const [mapIncidents, setMapIncidents] = useState([]);
  const [allIncidents, setAllIncidents] = useState([]);
  const [citizenReports, setCitizenReports] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [agentHealth, setAgentHealth] = useState([]);
  const [fleetData, setFleetData] = useState([]);
  const [facilityData, setFacilityData] = useState([]);
  const [sourceHealth, setSourceHealth] = useState([]);
  const [earthquakes, setEarthquakes] = useState([]);
  const [disasters, setDisasters] = useState([]);
  const [aiTacticalGuidance, setAiTacticalGuidance] = useState(null);

  // WebSocket state
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // ── AUTHENTICATED FETCH HELPER ──────────────────────────────────────────
  const authFetch = useCallback(async (endpoint, options = {}) => {
    const token = authToken || localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
    const headers = {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    };

    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      credentials: 'include',
    });

    if (res.status === 401) {
      // Session expired or invalid -> logout
      handleLogout();
      throw new Error('Unauthorized');
    }

    return res;
  }, [authToken]);

  // ── INITIAL SESSION CHECK ────────────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
    fetch(`${API_BASE}/api/auth/me`, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      credentials: 'include',
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success' && data.user) {
          setCurrentUser(data.user);
          setAuthToken(token || '');
          setView('eoc');
        } else {
          setView('landing');
        }
      })
      .catch(() => {
        setView('landing');
      });
  }, []);

  const handleLoginSuccess = (user, token) => {
    setCurrentUser(user);
    setAuthToken(token);
    setView('eoc');
  };

  const handleLogout = async () => {
    try {
      const token = authToken || localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include',
      });
    } catch {
      // Ignore network failures on logout
    }
    localStorage.removeItem('disaster_os_token');
    localStorage.removeItem('disaster_os_user');
    sessionStorage.removeItem('disaster_os_token');
    sessionStorage.removeItem('disaster_os_user');
    setCurrentUser(null);
    setAuthToken('');
    setView('landing');
  };

  // ── LOAD OPERATIONAL DATA ────────────────────────────────────────────────
  const loadRuns = useCallback(async () => {
    if (view !== 'eoc') return;
    try {
      const res = await authFetch('/api/runs');
      const data = await res.json();
      if (data.runs && data.runs.length > 0) {
        setRuns(data.runs);
        if (!selectedRun) {
          setSelectedRun(data.runs[0].run_id);
        }
      }
    } catch {}
  }, [authFetch, view, selectedRun]);

  const loadRunData = useCallback(async (runId) => {
    if (!runId || view !== 'eoc') return;
    try {
      const [histRes, statRes, dashRes, geoRes, sumRes] = await Promise.all([
        authFetch(`/api/run/${runId}/history`),
        authFetch(`/api/run/${runId}/status`),
        authFetch(`/api/run/${runId}/dashboard`),
        authFetch(`/api/incidents/geo/${runId}`),
        authFetch(`/api/run/${runId}/summary`),
      ]);

      const [histData, statData, dashData, geoData, sumData] = await Promise.all([
        histRes.json(), statRes.json(), dashRes.json(), geoRes.json(), sumRes.json()
      ]);

      if (histData.history) setHistory(histData.history);
      if (statData.status) setRunStatus(statData.status);
      if (statData.latest_state) setLatestState(statData.latest_state);
      if (dashData.metrics) setEocMetrics(dashData.metrics);
      if (geoData.incidents) setMapIncidents(geoData.incidents);

      if (sumData.status === 'success') {
        if (sumData.incidents) setAllIncidents(sumData.incidents);
        if (sumData.resources) setFleetData(sumData.resources);
        if (sumData.facilities) setFacilityData(sumData.facilities);
      }
    } catch {}
  }, [authFetch, view]);

  const loadLiveIntelligence = useCallback(async () => {
    try {
      const [srcRes, eqRes, gdRes] = await Promise.all([
        fetch(`${API_BASE}/api/intelligence/status`),
        fetch(`${API_BASE}/api/intelligence/earthquakes`),
        fetch(`${API_BASE}/api/intelligence/disasters`),
      ]);
      const [srcData, eqData, gdData] = await Promise.all([srcRes.json(), eqRes.json(), gdRes.json()]);
      if (srcData.sources) setSourceHealth(srcData.sources);
      if (eqData.events) setEarthquakes(eqData.events);
      if (gdData.events) setDisasters(gdData.events);
    } catch {}
  }, []);

  const loadAgentHealth = useCallback(async () => {
    if (view !== 'eoc') return;
    try {
      const res = await authFetch('/api/agents/health');
      const data = await res.json();
      if (data.agents) setAgentHealth(data.agents);
    } catch {}
  }, [authFetch, view]);

  // Periodic polling & initial load
  useEffect(() => {
    if (view === 'eoc') {
      loadRuns();
      loadLiveIntelligence();
      loadAgentHealth();
      const interval = setInterval(() => {
        loadLiveIntelligence();
        loadAgentHealth();
      }, 10000);
      return () => clearInterval(interval);
    }
  }, [view, loadRuns, loadLiveIntelligence, loadAgentHealth]);

  useEffect(() => {
    if (view === 'eoc' && selectedRun) {
      loadRunData(selectedRun);
    }
  }, [view, selectedRun, loadRunData]);

  // ── WEBSOCKET CONNECTION WITH RECONNECT ──────────────────────────────────
  const connectWebSocket = useCallback(() => {
    if (view !== 'eoc') return;
    if (wsRef.current) {
      try { wsRef.current.close(); } catch {}
    }

    const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws/simulation';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setWsConnected(true);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      reconnectTimeoutRef.current = setTimeout(() => {
        connectWebSocket();
      }, 3000);
    };

    ws.onerror = () => {
      setWsConnected(false);
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'RUN_COMPLETED' || msg.status === 'COMPLETED') {
          setRunStatus('COMPLETED');
          loadRuns();
          const targetRun = msg.run_id || selectedRun;
          if (targetRun) loadRunData(targetRun);
        } else if (msg.type === 'INCIDENT_STATUS_CHANGED') {
          setAllIncidents((prev) =>
            prev.map((inc) =>
              inc.incident_id === msg.incident_id ? { ...inc, status: msg.new_status } : inc
            )
          );
        } else if (msg.type === 'STATE_TRANSITION') {
          if (msg.state === 'AI_RECOMMENDATION' && msg.payload) {
            setAiTacticalGuidance(msg.payload);
          }
          if (msg.run_id) {
            loadRunData(msg.run_id);
          } else if (selectedRun) {
            loadRunData(selectedRun);
          }
        } else if (msg.type === 'SOURCE_STATUS_CHANGED') {
          loadLiveIntelligence();
        }
      } catch {}
    };

    wsRef.current = ws;
  }, [view, selectedRun, loadRunData, loadLiveIntelligence, loadRuns]);

  // Active run polling while status is RUNNING
  useEffect(() => {
    if (view === 'eoc' && selectedRun && runStatus === 'RUNNING') {
      const interval = setInterval(async () => {
        try {
          const res = await authFetch(`/api/run/${selectedRun}/status`);
          const data = await res.json();
          if (data.status) {
            setRunStatus(data.status);
            if (data.status === 'COMPLETED' || data.status === 'ERROR') {
              loadRuns();
              loadRunData(selectedRun);
            }
          }
        } catch {}
      }, 1500);
      return () => clearInterval(interval);
    }
  }, [view, selectedRun, runStatus, authFetch, loadRuns, loadRunData]);

  useEffect(() => {
    if (view === 'eoc') {
      connectWebSocket();
      return () => {
        if (wsRef.current) wsRef.current.close();
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      };
    }
  }, [view, connectWebSocket]);

  // ── SIMULATION TRIGGER ───────────────────────────────────────────────────
  const handleTriggerRun = async () => {
    setLoading(true);
    try {
      const res = await authFetch('/api/run', {
        method: 'POST',
        body: JSON.stringify({ seed: parseInt(seed, 10), strategy }),
      });
      const data = await res.json();
      if (data.run_id) {
        setSelectedRun(data.run_id);
        setRunStatus('RUNNING');
        loadRuns();
        loadRunData(data.run_id);
      }
    } catch {}
    setLoading(false);
  };

  const handleIncidentStatusChange = async (incidentId, newStatus) => {
    try {
      const res = await authFetch(`/api/incidents/${incidentId}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status: newStatus }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        setAllIncidents((prev) =>
          prev.map((inc) => (inc.incident_id === incidentId ? { ...inc, status: newStatus } : inc))
        );
      }
    } catch {}
  };

  // ── ROUTING RENDERS ──────────────────────────────────────────────────────
  if (view === 'loading') {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)', color: 'var(--text-secondary)' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="brand-logo-icon" style={{ width: 44, height: 44, fontSize: 20, margin: '0 auto 16px auto' }}>D</div>
          <div style={{ fontFamily: 'Outfit', fontSize: 16, fontWeight: 700, color: '#fff', marginBottom: 6 }}>DISASTER OS</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Initializing EOC Security Gateway...</div>
        </div>
      </div>
    );
  }

  if (view === 'landing') {
    return <LandingPage onNavigateLogin={() => setView('login')} />;
  }

  if (view === 'login') {
    return <LoginPage onLoginSuccess={handleLoginSuccess} onNavigateLanding={() => setView('landing')} />;
  }

  // ── AUTHENTICATED EOC SHELL ──────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg-primary)' }}>
      {/* ── LEFT SIDEBAR ── */}
      <aside className="eoc-sidebar" style={{ width: sidebarCollapsed ? 70 : 240 }}>
        <div className="sidebar-brand">
          <div className="brand-logo-icon" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} style={{ cursor: 'pointer' }}>D</div>
          {!sidebarCollapsed && (
            <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
              <div className="brand-title">DISASTER<span style={{ color: 'var(--accent-lime)' }}>OS</span></div>
              <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.6 }}>EOC 2.0 Command</div>
            </div>
          )}
        </div>

        <nav className="sidebar-nav">
          {!sidebarCollapsed && <div className="sidebar-section-header">EOC Command Center</div>}
          <div className={`nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')} title="Command Overview">
            <Icons.Dashboard width={16} height={16} />
            {!sidebarCollapsed && <span>Command Overview</span>}
          </div>
          <div className={`nav-btn ${activeTab === 'map' ? 'active' : ''}`} onClick={() => setActiveTab('map')} title="Live Operations Map">
            <Icons.LiveMap width={16} height={16} />
            {!sidebarCollapsed && <span>Live Operations Map</span>}
          </div>
          <div className={`nav-btn ${activeTab === 'incidents' ? 'active' : ''}`} onClick={() => setActiveTab('incidents')} title="Incidents Feed">
            <Icons.Incident width={16} height={16} />
            {!sidebarCollapsed && <span>Incidents ({allIncidents.length})</span>}
          </div>
          <div className={`nav-btn ${activeTab === 'fleet' ? 'active' : ''}`} onClick={() => setActiveTab('fleet')} title="Response Fleet">
            <Icons.Fleet width={16} height={16} />
            {!sidebarCollapsed && <span>Response Fleet</span>}
          </div>
          <div className={`nav-btn ${activeTab === 'intel' ? 'active' : ''}`} onClick={() => setActiveTab('intel')} title="Live Intelligence">
            <Icons.Intel width={16} height={16} />
            {!sidebarCollapsed && <span>Intelligence</span>}
          </div>
          <div className={`nav-btn ${activeTab === 'resources' ? 'active' : ''}`} onClick={() => setActiveTab('resources')} title="Hospital & Shelter Capacity">
            <Icons.Resource width={16} height={16} />
            {!sidebarCollapsed && <span>Resources</span>}
          </div>

          {!sidebarCollapsed && <div className="sidebar-section-header" style={{ marginTop: 12 }}>Operations & Telemetry</div>}
          <div className={`nav-btn ${activeTab === 'simulation' ? 'active' : ''}`} onClick={() => setActiveTab('simulation')} title="14-Agent Simulation Pipeline">
            <Icons.Simulation width={16} height={16} />
            {!sidebarCollapsed && <span>Simulation Pipeline</span>}
          </div>
          <div className={`nav-btn ${activeTab === 'analytics' ? 'active' : ''}`} onClick={() => setActiveTab('analytics')} title="Analytics & Export">
            <Icons.Analytics width={16} height={16} />
            {!sidebarCollapsed && <span>Analytics & Reports</span>}
          </div>
          <div className={`nav-btn ${activeTab === 'diagnostics' ? 'active' : ''}`} onClick={() => setActiveTab('diagnostics')} title="Agent Health Diagnostics">
            <Icons.AgentHealth width={16} height={16} />
            {!sidebarCollapsed && <span>Agent Diagnostics</span>}
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="operator-avatar">{currentUser?.name ? currentUser.name[0] : 'O'}</div>
          {!sidebarCollapsed && (
            <div className="operator-details">
              <div className="operator-name">{currentUser?.name || 'Operator'}</div>
              <div className="operator-role">{currentUser?.role || 'operator'} &bull; online</div>
            </div>
          )}
          <button
            onClick={handleLogout}
            title="Sign Out"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center' }}
          >
            <Icons.Exit width={16} height={16} />
          </button>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        {/* ── TOPBAR ── */}
        <header className="eoc-topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div className="topbar-breadcrumb">
              <span>EOC</span>
              <span>/</span>
              <span style={{ color: '#fff', fontWeight: 600 }}>
                {activeTab === 'dashboard' && 'Command Overview'}
                {activeTab === 'map' && 'Live Operations Map'}
                {activeTab === 'incidents' && 'Incident Management'}
                {activeTab === 'fleet' && 'Response Fleet Telematics'}
                {activeTab === 'intel' && 'Live Intelligence Feeds'}
                {activeTab === 'resources' && 'Hospital & Shelter Resources'}
                {activeTab === 'simulation' && '14-Agent Simulation Pipeline'}
                {activeTab === 'analytics' && 'Analytics & Audit Reports'}
                {activeTab === 'diagnostics' && 'Agent Health Diagnostics'}
              </span>
            </div>

            {selectedRun && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg-surface-elevated)', padding: '3px 8px', borderRadius: 4, fontSize: 11, border: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>RUN:</span>
                <span style={{ fontFamily: 'monospace', color: 'var(--accent-lime)', fontWeight: 600 }}>{shortId(selectedRun)}</span>
                <span className={`status-badge ${runStatus.toLowerCase() === 'completed' ? 'healthy' : 'running'}`} style={{ fontSize: 9, padding: '1px 5px' }}>
                  {runStatus}
                </span>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* WebSocket Indicator */}
            <div className={`ws-indicator ${wsConnected ? 'connected' : 'disconnected'}`}>
              <span className={`pulse-dot ${wsConnected ? 'green' : 'red'}`} />
              <span>{wsConnected ? 'LIVE WS' : 'RECONNECTING...'}</span>
            </div>

            {/* Command Palette Trigger */}
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setCmdOpen(true)}
              style={{ fontSize: 11, color: 'var(--text-secondary)' }}
            >
              <Icons.Search width={13} height={13} />
              <span>Search</span>
              <kbd style={{ background: 'rgba(255,255,255,0.08)', padding: '1px 4px', borderRadius: 3, fontSize: 9 }}>Ctrl+K</kbd>
            </button>

            {/* Citizen SOS Trigger */}
            <button
              className="btn btn-danger btn-sm"
              onClick={() => setSosOpen(true)}
              style={{ fontWeight: 700 }}
            >
              <Icons.SOS width={13} height={13} />
              <span>CITIZEN SOS</span>
            </button>

            {/* Notification Center */}
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setNotifOpen(!notifOpen)}
              style={{ padding: '6px 8px' }}
            >
              <Icons.Bell width={15} height={15} />
            </button>
          </div>
        </header>

        {/* ── TAB VIEWS ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '18px 22px' }}>
          {activeTab === 'dashboard' && (
            <EOCDashboard
              metrics={eocMetrics}
              runId={selectedRun}
              incidents={allIncidents}
              sourceHealth={sourceHealth}
              earthquakes={earthquakes}
              disasters={disasters}
              fleetData={fleetData}
              facilityData={facilityData}
              aiTacticalGuidance={aiTacticalGuidance}
              onNavigateTab={setActiveTab}
            />
          )}

          {activeTab === 'map' && (
            <div style={{ height: 'calc(100vh - 100px)', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
              <LiveMap runId={selectedRun} onDataChange={() => loadRunData(selectedRun)} />
            </div>
          )}

          {activeTab === 'incidents' && (
            <IncidentFeed
              incidents={allIncidents}
              facilities={facilityData}
              earthquakes={earthquakes}
              onUpdateStatus={handleIncidentStatusChange}
              onRefresh={() => loadRunData(selectedRun)}
            />
          )}

          {activeTab === 'fleet' && (
            <FleetPanel
              fleet={fleetData}
              resources={fleetData}
              runId={selectedRun}
              onRefresh={() => loadRunData(selectedRun)}
              onNavigateToMap={() => setActiveTab('map')}
            />
          )}

          {activeTab === 'intel' && (
            <IntelligencePanel
              sourceHealth={sourceHealth}
              earthquakes={earthquakes}
              disasters={disasters}
              incidents={allIncidents}
              onRefresh={loadLiveIntelligence}
            />
          )}

          {activeTab === 'resources' && (
            <ResourcePanel facilities={facilityData} runId={selectedRun} onRefresh={() => loadRunData(selectedRun)} />
          )}

          {activeTab === 'simulation' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="eoc-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <h3 style={{ fontSize: 16, marginBottom: 4 }}>14-Agent Operational Simulation Controller</h3>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Execute autonomous multi-agent disaster response workflow with full stage telemetry.</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <label style={{ fontSize: 11, color: 'var(--text-secondary)' }}>SEED:</label>
                    <input
                      type="number"
                      className="input-control"
                      value={seed}
                      onChange={(e) => setSeed(e.target.value)}
                      style={{ width: 80, padding: '4px 8px', fontSize: 12 }}
                    />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <label style={{ fontSize: 11, color: 'var(--text-secondary)' }}>STRATEGY:</label>
                    <select
                      className="input-control"
                      value={strategy}
                      onChange={(e) => setStrategy(e.target.value)}
                      style={{ width: 110, padding: '4px 8px', fontSize: 12 }}
                    >
                      <option value="smart">Smart AI</option>
                      <option value="baseline">Baseline FIFO</option>
                    </select>
                  </div>
                  <button
                    className="btn btn-primary"
                    onClick={handleTriggerRun}
                    disabled={loading}
                  >
                    <Icons.Simulation width={14} height={14} />
                    <span>{loading ? 'Executing...' : 'Run Simulation'}</span>
                  </button>
                </div>
              </div>

              {/* 14-Stage Progress Grid */}
              <div className="eoc-card">
                <h4 style={{ fontSize: 13, marginBottom: 14, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Pipeline Execution Stages</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 10 }}>
                  {FOURTEEN_STAGES.map((stg) => {
                    const isCompleted = history.some((h) => h.state === stg.state);
                    const isCurrent = latestState === stg.state;
                    return (
                      <div
                        key={stg.id}
                        style={{
                          background: isCurrent ? 'var(--accent-lime-muted)' : isCompleted ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-card)',
                          border: isCurrent ? '1px solid var(--accent-lime)' : isCompleted ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid var(--border-subtle)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '10px 8px',
                          textAlign: 'center',
                        }}
                      >
                        <div style={{ fontSize: 10, fontWeight: 700, color: isCurrent ? 'var(--accent-lime)' : isCompleted ? 'var(--color-success)' : 'var(--text-muted)' }}>
                          STAGE {stg.id}
                        </div>
                        <div style={{ fontSize: 11, fontWeight: 600, color: '#fff', margin: '3px 0' }}>{stg.label}</div>
                        <div style={{ fontSize: 9, color: 'var(--text-secondary)' }}>{stg.desc}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Telemetry Log */}
              <div className="eoc-card">
                <h4 style={{ fontSize: 13, marginBottom: 12, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Execution Telemetry Logs ({history.length})</h4>
                <div style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'monospace', fontSize: 11 }}>
                  {history.length === 0 ? (
                    <div className="empty-state">No simulation steps recorded for this run.</div>
                  ) : (
                    history.map((step, idx) => (
                      <div key={idx} style={{ background: 'var(--bg-surface-elevated)', padding: '6px 10px', borderRadius: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: 'var(--accent-lime)' }}>[{fmtTime(step.timestamp)}]</span>
                        <span style={{ color: '#fff', fontWeight: 600 }}>{step.state}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{step.agent_name || 'System'}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'analytics' && (
            <AnalyticsPanel
              runs={runs}
              selectedRun={selectedRun}
              onSelectRun={(rId) => {
                setSelectedRun(rId);
                loadRunData(rId);
              }}
              authFetch={authFetch}
            />
          )}

          {activeTab === 'diagnostics' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="eoc-card">
                <h3 style={{ fontSize: 16, marginBottom: 4 }}>14 Operational Response Agents + 1 Evaluation Service Diagnostics</h3>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Live telemetry and latency metrics across 14 operational response agents and 1 post-mission evaluation service.</p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {agentHealth.length === 0 ? (
                  <div className="empty-state" style={{ gridColumn: 'span 3' }}>Awaiting agent telemetry from active simulation runs...</div>
                ) : (
                  agentHealth.map((ag, idx) => (
                    <div key={idx} className="eoc-card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: '#fff' }}>{ag.agent_name}</span>
                        <span className={`status-badge ${ag.status === 'healthy' ? 'healthy' : 'error'}`} style={{ fontSize: 9 }}>
                          {ag.status}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)' }}>
                        <span>Messages Processed:</span>
                        <strong style={{ color: '#fff' }}>{ag.messages_processed}</strong>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)' }}>
                        <span>Avg Latency:</span>
                        <strong style={{ color: 'var(--accent-lime)' }}>{ag.avg_latency_ms} ms</strong>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ── MODALS ── */}
      {cmdOpen && (
        <CommandPalette
          isOpen={cmdOpen}
          onClose={() => setCmdOpen(false)}
          onNavigate={(tab) => { setActiveTab(tab); setCmdOpen(false); }}
        />
      )}

      {sosOpen && (
        <CitizenReportModal
          isOpen={sosOpen}
          onClose={() => setSosOpen(false)}
          onSubmitted={() => {
            loadRunData(selectedRun);
            setSosOpen(false);
          }}
        />
      )}
    </div>
  );
}
