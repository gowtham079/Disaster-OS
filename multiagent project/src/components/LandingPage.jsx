import React from 'react';

export default function LandingPage({ onNavigateLogin }) {
  return (
    <div className="landing-shell">
      {/* ── HEADER ── */}
      <header className="landing-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="brand-logo-icon">D</div>
          <div>
            <span className="brand-title">DISASTER<span style={{ color: 'var(--accent-lime)' }}>OS</span></span>
            <span className="brand-badge" style={{ marginLeft: 8 }}>EOC 2.0</span>
          </div>
        </div>

        <nav className="landing-nav">
          <a href="#capabilities">Capabilities</a>
          <a href="#intelligence">Live Intelligence</a>
          <a href="#provenance">Data Provenance</a>
          <a href="#operations">Operations</a>
          <a href="#security">Security</a>
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-outline btn-sm" onClick={onNavigateLogin}>
            Sign In
          </button>
          <button className="btn btn-primary btn-sm" onClick={onNavigateLogin}>
            Enter Command Center &rarr;
          </button>
        </div>
      </header>

      {/* ── HERO SECTION ── */}
      <section className="landing-hero">
        <div className="hero-tag">
          <span className="pulse-dot green" />
          Mission-Critical Emergency Operations Platform
        </div>
        
        <h1 className="hero-headline">
          Command Disaster Response<br />
          With Real-Time Intelligence.
        </h1>

        <p className="hero-subtext">
          Disaster OS unifies multi-agent AI orchestration, live seismic & meteorological feeds, 
          11-layer GIS mapping, real-time fleet telematics, and medical triage to empower 
          first responders with zero-latency operational decision support.
        </p>

        <div className="hero-cta-group">
          <button className="btn btn-primary btn-lg" onClick={onNavigateLogin}>
            Enter Command Center &rarr;
          </button>
          <a href="#capabilities" className="btn btn-secondary btn-lg">
            Explore Capabilities
          </a>
        </div>

        {/* ── HERO VISUAL / EOC COMMAND INTERFACE PREVIEW ── */}
        <div className="eoc-card-highlight" style={{ textAlign: 'left', padding: '24px', boxShadow: 'var(--shadow-lg)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 14, marginBottom: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="pulse-dot green" />
              <span style={{ fontFamily: 'Outfit', fontWeight: 700, fontSize: 13, color: '#fff' }}>EOC SITUATION ROOM PREVIEW</span>
              <span className="op-badge op-badge-sim" style={{ fontSize: 9 }}>DEMO VISUALIZATION</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <span className="op-badge op-badge-live">USGS LIVE FEED</span>
              <span className="op-badge op-badge-live">GDACS RED ALERTS</span>
              <span className="op-badge op-badge-db">SQLITE PERSISTED</span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 18 }}>
            <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Active Incidents</span>
                <span className="op-badge op-badge-db">DATABASE</span>
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--color-danger)' }}>7</div>
              <div className="kpi-sub-v2">3 High Criticality Sectors</div>
            </div>

            <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Citizens Rescued</span>
                <span className="op-badge op-badge-calc">CALCULATED</span>
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--accent-lime)' }}>11,901</div>
              <div className="kpi-sub-v2">Dynamic Simulation Metric</div>
            </div>

            <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Ready Fleet Units</span>
                <span className="op-badge op-badge-db">DATABASE</span>
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--color-success)' }}>35 / 35</div>
              <div className="kpi-sub-v2">100% Operational Readiness</div>
            </div>

            <div className="kpi-card-v2" style={{ background: 'var(--bg-surface-elevated)' }}>
              <div className="kpi-top-row">
                <span className="kpi-label-v2">Live Seismic Quakes</span>
                <span className="op-badge op-badge-live">LIVE</span>
              </div>
              <div className="kpi-value-v2" style={{ color: 'var(--color-info)' }}>12</div>
              <div className="kpi-sub-v2">USGS M4.5+ Monitored</div>
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface-card)', borderRadius: 'var(--radius-sm)', padding: '14px', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 32, height: 32, borderRadius: 6, background: 'var(--accent-lime-muted)', color: 'var(--accent-lime)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}>AI</div>
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#fff' }}>Gemini Tactical Decision Support Engine</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Automated hazard triage, route blockage avoidance via OSRM, and capacity load balancing.</div>
              </div>
            </div>
            <button className="btn btn-lime-outline btn-sm" onClick={onNavigateLogin}>
              Access Dashboard &rarr;
            </button>
          </div>
        </div>
      </section>

      {/* ── CAPABILITIES ── */}
      <section id="capabilities" className="landing-section">
        <div className="section-title-wrap">
          <h2 className="section-title">Engineered For Emergency Operations Centers</h2>
          <p className="section-subtitle">A multi-layered architecture designed to eliminate operational blind spots during extreme disaster response.</p>
        </div>

        <div className="capabilities-grid">
          <div className="capability-card">
            <div className="capability-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            </div>
            <h3 className="capability-title">Live Disaster Intelligence</h3>
            <p className="capability-desc">Continuous real-time ingestion from USGS seismic feeds, GDACS global disaster alerts, OpenWeather observations, and Nominatim geospatial indexes.</p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            </div>
            <h3 className="capability-title">Incident Management & Triage</h3>
            <p className="capability-desc">Multi-parameter severity classification, citizen emergency SOS intake, and strict lifecycle status tracking (NEW &rarr; ASSESSED &rarr; RESPONDING &rarr; CONTAINED &rarr; RESOLVED).</p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>
            </div>
            <h3 className="capability-title">Response Fleet Telematics</h3>
            <p className="capability-desc">Dynamic allocation across 7 specialized unit classes including ambulances, fire engines, police cruisers, rescue boats, helicopters, and reconnaissance drones.</p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
            </div>
            <h3 className="capability-title">11-Layer GIS Operations Map</h3>
            <p className="capability-desc">High-precision Leaflet map with OSRM roadblock rerouting, danger zone heatmaps, hospital proximity cones, and weather overlay inspection.</p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
            </div>
            <h3 className="capability-title">Hospital & Shelter Capacity</h3>
            <p className="capability-desc">Automated bed census monitoring, relief shelter headcounts, and emergency transfer load-balancing with real-time saturation alerts.</p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <h3 className="capability-title">AI Tactical Decision Support</h3>
            <p className="capability-desc">Powered by evaluation agents that synthesize simulation telemetry to generate actionable evacuation directives and resource reallocation protocols.</p>
          </div>
        </div>
      </section>

      {/* ── DATA PROVENANCE MODEL ── */}
      <section id="provenance" className="landing-section" style={{ background: 'rgba(10, 14, 21, 0.6)', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="section-title-wrap">
          <h2 className="section-title">Strict Data Provenance Model</h2>
          <p className="section-subtitle">Every number, metric, and visual marker in Disaster OS is explicitly tagged with its authentic data classification.</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14 }}>
          <div className="eoc-card" style={{ textAlign: 'center' }}>
            <span className="op-badge op-badge-live" style={{ marginBottom: 10 }}>LIVE</span>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 6 }}>External Live Feeds</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Directly queried external APIs (USGS, GDACS, OpenWeather, Nominatim).</div>
          </div>

          <div className="eoc-card" style={{ textAlign: 'center' }}>
            <span className="op-badge op-badge-db" style={{ marginBottom: 10 }}>DATABASE</span>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 6 }}>Persisted State</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Audited operational records stored in SQLite with full foreign-key integrity.</div>
          </div>

          <div className="eoc-card" style={{ textAlign: 'center' }}>
            <span className="op-badge op-badge-calc" style={{ marginBottom: 10 }}>CALCULATED</span>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 6 }}>Deterministic Math</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Computed mathematical derivations (utilization %, capacities, ETAs, triage).</div>
          </div>

          <div className="eoc-card" style={{ textAlign: 'center' }}>
            <span className="op-badge op-badge-sim" style={{ marginBottom: 10 }}>SIMULATED</span>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 6 }}>Multi-Agent Telemetry</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Generated by the 14-agent simulation pipeline for operational readiness drills.</div>
          </div>

          <div className="eoc-card" style={{ textAlign: 'center' }}>
            <span className="op-badge op-badge-unavail" style={{ marginBottom: 10 }}>UNAVAILABLE</span>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 6 }}>Offline Fallback</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Explicitly reported when upstream providers fail; zero fabricated mock data.</div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="landing-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="brand-logo-icon" style={{ width: 22, height: 22, fontSize: 11 }}>D</div>
          <span><strong>DISASTER OS</strong> &mdash; Emergency Operations Platform</span>
        </div>

        <div style={{ display: 'flex', gap: 24, fontSize: 12 }}>
          <span>System Status: <span style={{ color: 'var(--color-success)', fontWeight: 700 }}>● Operational</span></span>
          <span>Security: <strong>EOC Tier-4 Hardened</strong></span>
          <span>Documentation</span>
          <span>Contact EOC</span>
        </div>
      </footer>
    </div>
  );
}
