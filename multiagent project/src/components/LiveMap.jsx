import React, { memo, useCallback, useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

import { API_BASE, getWebSocketUrl, getAuthHeaders } from '../config';
const DEFAULT_CENTER = [20.5937, 78.9629]; // Neutral India centroid map viewport
const SEVERITY_COLORS = { high: '#ef4444', medium: '#f59e0b', low: '#10b981' };

const MAJOR_CITIES = [
  { name: 'All India', lat: 20.5937, lng: 78.9629, zoom: 5 },
  { name: 'Mumbai', lat: 19.0760, lng: 72.8777, zoom: 12 },
  { name: 'Delhi NCR', lat: 28.6139, lng: 77.2090, zoom: 12 },
  { name: 'Bengaluru', lat: 12.9716, lng: 77.5946, zoom: 12 },
  { name: 'Kolkata', lat: 22.5726, lng: 88.3639, zoom: 12 },
  { name: 'Chennai', lat: 13.0827, lng: 80.2707, zoom: 12 },
  { name: 'Hyderabad', lat: 17.3850, lng: 78.4867, zoom: 12 },
];

const ENTITY_SYMBOLS = {
  flood: '<path d="M4 13c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1M6 9l6-6 6 6a6 6 0 0 1-12 0Z"/>',
  fire: '<path d="M12 22c4 0 7-3 7-7 0-5-4-8-5-12-3 2-5 5-5 8-1-1-2-2-2-3-2 2-3 4-3 7 0 4 4 7 8 7Zm0-3c-2 0-3-1-3-3 0-1 1-3 3-5 0 2 3 3 3 5s-1 3-3 3Z"/>',
  earthquake: '<path d="m3 12 4-2 2 3 3-8 3 10 2-4 4 1M4 19h16"/>',
  cyclone: '<path d="M12 7a5 5 0 1 1-5 5c0-5 4-8 9-8M12 17a5 5 0 1 1 5-5c0 5-4 8-9 8"/>',
  tsunami: '<path d="M2 12c3-3 6-3 9 0s6 3 9 0M2 16c3-3 6-3 9 0s6 3 9 0M2 20c3-3 6-3 9 0s6 3 9 0"/>',
  wildfire: '<path d="M12 22c4 0 7-3 7-7 0-5-4-8-5-12-3 2-5 5-5 8-1-1-2-2-2-3-2 2-3 4-3 7 0 4 4 7 8 7Z"/>',
  chemical_leak: '<path d="M12 2v6m0 0a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm-6 4a6 6 0 1 0 12 0 6 6 0 0 0-12 0z"/>',
  building_collapse: '<path d="M4 22h16M4 2v20M20 2v20M8 6h3M13 6h3M8 10h3M13 10h3M8 14h3M13 14h3"/>',
  road_accident: '<path d="M5 17h14M5 12h14M7 7l10 10"/>',
  landslide: '<path d="M2 20l8-16 4 8 6-4 2 12H2z"/>',
  incident: '<path d="M12 9v4m0 4h.01M10 3 2 19a2 2 0 0 0 2 3h16a2 2 0 0 0 2-3L14 3a2 2 0 0 0-4 0Z"/>',

  ambulance: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-1.1 0-2 .9-2 2v7c0 .6.4 1 1 1h2m2 0a2 2 0 1 0 4 0 2 2 0 1 0-4 0zm8 0a2 2 0 1 0 4 0 2 2 0 1 0-4 0zM7 11h4m-2-2v4"/>',
  fire_truck: '<path d="M1 14h15v4H1zm15-4h4l3 3v1h-7zM6 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM4 10h8v4H4z"/>',
  police_car: '<path d="M5 11l2-4h10l2 4M3 11h18v6H3zm4 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM10 6h4v2h-4z"/>',
  rescue_boat: '<path d="M2 16l3 4h14l3-4M4 12l8-8 8 8M12 4v8"/>',
  helicopter: '<path d="M3 12h18M12 3v18M6 8l12 8M6 16l12-8"/>',
  drone: '<path d="M12 2a4 4 0 0 0-4 4v2H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h4v2a4 4 0 0 0 8 0v-2h4a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2h-4V6a4 4 0 0 0-4-4z"/>',
  supply_truck: '<path d="M3 6h12v11H3zm12 5h5l3 3v3h-8zM6 17a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm11 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>',

  hospital: '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10h-4v4h-2v-4H7v-2h4V7h2v4h4v2z"/>',
  shelter: '<path d="M12 2L2 12h3v8h14v-8h3L12 2zm0 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/>',
  police_station: '<path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-1 6h2v2h-2V7zm0 4h2v6h-2v-6z"/>',
  fire_station: '<path d="M12 2a7 7 0 0 0-7 7c0 5.25 7 13 7 13s7-7.75 7-13a7 7 0 0 0-7-7zm-1 4h2v3h-2V6zm0 5h2v2h-2v-2z"/>',
};

function isValidLatLng(lat, lng) {
  return Number.isFinite(lat) && Number.isFinite(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180 && lat !== 0 && lng !== 0;
}

function createCustomIcon(symbolKey, color = '#6366f1', extraClass = '', badgeText = '') {
  const symbol = ENTITY_SYMBOLS[symbolKey] || ENTITY_SYMBOLS.incident;
  const badgeHtml = badgeText ? `<span class="eoc-badge">${badgeText}</span>` : '';
  return L.divIcon({
    className: `eoc-marker-wrap ${extraClass}`,
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -22],
    html: `<span class="eoc-marker" style="--marker:${color}">
      <svg viewBox="0 0 24 24">${symbol}</svg>
      ${badgeHtml}
    </span>`,
  });
}

function parseRouteCoordinates(raw) {
  if (!raw) return [];
  let coords = raw;
  if (typeof coords === 'string') {
    try { coords = JSON.parse(coords); } catch { return []; }
  }
  if (!Array.isArray(coords)) return [];
  return coords
    .filter(pt => Array.isArray(pt) && pt.length >= 2)
    .map(pt => [Number(pt[0]), Number(pt[1])])
    .filter(pt => isValidLatLng(pt[0], pt[1]));
}

function getDistanceKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function findNearestResources(incLat, incLng, fleetList, facilityList) {
  const nearest = {
    fleet: [],
    hospitals: [],
    shelters: [],
  };

  if (Array.isArray(fleetList)) {
    nearest.fleet = fleetList
      .filter(f => isValidLatLng(Number(f.latitude), Number(f.longitude)))
      .map(f => ({
        ...f,
        distKm: getDistanceKm(incLat, incLng, Number(f.latitude), Number(f.longitude)),
      }))
      .sort((a, b) => a.distKm - b.distKm)
      .slice(0, 3);
  }

  if (Array.isArray(facilityList)) {
    const valid = facilityList
      .filter(f => isValidLatLng(Number(f.latitude), Number(f.longitude)))
      .map(f => ({
        ...f,
        distKm: getDistanceKm(incLat, incLng, Number(f.latitude), Number(f.longitude)),
      }))
      .sort((a, b) => a.distKm - b.distKm);

    nearest.hospitals = valid.filter(f => f.facility_type === 'hospital').slice(0, 2);
    nearest.shelters = valid.filter(f => f.facility_type === 'shelter').slice(0, 2);
  }

  return nearest;
}

function buildPopupHtml(title, category, rows, classification = 'LIVE', footerNote = '', extraHtml = '') {
  const badgeClass = `op-badge-${(classification || 'LIVE').toLowerCase()}`;
  const rowsHtml = rows.map(([label, value, colorClass]) => (
    `<div class="pop-row"><span>${label}:</span><strong class="${colorClass || ''}">${value}</strong></div>`
  )).join('');

  return `<div class="eoc-popup">
    <div class="pop-cat-header">
      <span class="pop-cat">${category}</span>
      <span class="op-badge ${badgeClass}">${classification}</span>
    </div>
    <h4>${title}</h4>
    <div class="pop-grid">${rowsHtml}</div>
    ${extraHtml ? `<div class="pop-extra">${extraHtml}</div>` : ''}
    ${footerNote ? `<div class="pop-footer">${footerNote}</div>` : ''}
  </div>`;
}

function formatAgeSeconds(ageSec) {
  if (ageSec == null || Number.isNaN(ageSec)) return 'Just now';
  if (ageSec < 60) return `${Math.round(ageSec)}s ago`;
  if (ageSec < 3600) return `${Math.round(ageSec / 60)}m ago`;
  return `${(ageSec / 3600).toFixed(1)}h ago`;
}

const LiveMap = memo(function LiveMap({ incidents = [], runId = 'demo', activeTab }) {
  const mapNodeRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const vehicleLayerRef = useRef(null);
  const vehicleMarkersRef = useRef({});
  const trailsRef = useRef({});
  const animFrameRef = useRef(null);

  // Layer Toggles
  const [showEarthquakes, setShowEarthquakes] = useState(true);
  const [showDisasters, setShowDisasters] = useState(true);
  const [showVehicles, setShowVehicles] = useState(true);
  const [showHospitals, setShowHospitals] = useState(true);
  const [showShelters, setShowShelters] = useState(true);
  const [showRealFacilities, setShowRealFacilities] = useState(true);
  const [showIncidentsLayer, setShowIncidentsLayer] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showImpactIsoseismals, setShowImpactIsoseismals] = useState(true);
  const [showCorridors, setShowCorridors] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showTrails, setShowTrails] = useState(true);

  const [panelOpen, setPanelOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Live Intelligence State
  const [earthquakes, setEarthquakes] = useState([]);
  const [disasters, setDisasters] = useState([]);
  const [sourceHealth, setSourceHealth] = useState([]);
  const [impactAssessments, setImpactAssessments] = useState([]);
  const [selectedEntity, setSelectedEntity] = useState(null); // For slide-out Detail Panel
  const [weatherInspection, setWeatherInspection] = useState(null); // For point weather click card
  const [isoseismalInspection, setIsoseismalInspection] = useState(null); // Persistent isoseismal circle inspector
  const [selectedCity, setSelectedCity] = useState('All India');

  // Dynamic entities
  const [resources, setResources] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [realFacilities, setRealFacilities] = useState([]);
  const [zones, setZones] = useState([]);
  const [blockedRoads, setBlockedRoads] = useState([]);
  const [evacuationCorridors, setEvacuationCorridors] = useState([]);

  // Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchPin, setSearchPin] = useState(null);

  // Fetch Live Intelligence & Calculated Impact Assessments
  const fetchIntelligence = useCallback(async () => {
    try {
      const [eqResp, disResp, stResp, impactResp] = await Promise.all([
        fetch(`${API_BASE}/api/intelligence/earthquakes`),
        fetch(`${API_BASE}/api/intelligence/disasters`),
        fetch(`${API_BASE}/api/intelligence/status`),
        fetch(`${API_BASE}/api/impact/assessments`),
      ]);

      if (eqResp.ok) { const d = await eqResp.json(); setEarthquakes(d.events || []); }
      if (disResp.ok) { const d = await disResp.json(); setDisasters(d.events || []); }
      if (stResp.ok) { const d = await stResp.json(); setSourceHealth(d.sources || []); }
      if (impactResp?.ok) { const d = await impactResp.json(); setImpactAssessments(d.assessments || []); }
    } catch { /* ignore optional fetch errors */ }
  }, []);

  // Compute / request mathematical impact assessment on demand
  const handleAssessImpact = useCallback(async (item, type = 'earthquake') => {
    try {
      const lat = item.latitude;
      const lng = item.longitude;
      if (!isValidLatLng(lat, lng)) return;

      const payload = {
        latitude: lat,
        longitude: lng,
        disaster_type: type,
        magnitude: item.magnitude || (type === 'earthquake' ? 6.0 : null),
        depth_km: item.depth_km || 10.0,
        rainfall_mm: item.rainfall_mm != null ? item.rainfall_mm : null,
        wind_speed_kmh: item.wind_speed_kmh != null ? item.wind_speed_kmh : null,
        event_id: item.event_id || item.incident_id || `EVT-${Date.now()}`,
      };

      const token = localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token');
      const res = await fetch(`${API_BASE}/api/impact/assess`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success' && data.assessment) {
          setImpactAssessments(prev => [data.assessment, ...prev.filter(a => a.assessment_id !== data.assessment.assessment_id)]);
          setSelectedEntity({ type: 'IMPACT_ASSESSMENT', data: data.assessment });
          if (mapRef.current) {
            mapRef.current.flyTo([lat, lng], 10, { duration: 1.2 });
          }
        }
      }
    } catch (err) {
      console.error('Impact assessment calculation error:', err);
    }
  }, []);

  // Handle City & Scenario Focus Selector
  const handleCitySelect = useCallback(async (cityName) => {
    setSelectedCity(cityName);
    const city = MAJOR_CITIES.find(c => c.name === cityName);
    if (!city || !mapRef.current) return;

    mapRef.current.flyTo([city.lat, city.lng], city.zoom, { duration: 1.2 });

    if (cityName !== 'All India') {
      try {
        const resp = await fetch(`${API_BASE}/api/intelligence/facilities?lat=${city.lat}&lng=${city.lng}&radius_km=25`);
        if (resp.ok) {
          const d = await resp.json();
          setRealFacilities(d.facilities || []);
        }
      } catch { /* ignore */ }
    }
  }, []);

  // Fetch dynamic operational entities
  const fetchEntities = useCallback(async () => {
    if (!runId) return;
    try {
      const authOpts = { headers: getAuthHeaders(), credentials: 'include' };
      const [resResp, facResp, zoneResp, blockResp, corrResp] = await Promise.all([
        fetch(`${API_BASE}/api/run/${runId}/resources`, authOpts),
        fetch(`${API_BASE}/api/run/${runId}/facilities`, authOpts),
        fetch(`${API_BASE}/api/run/${runId}/zones`, authOpts),
        fetch(`${API_BASE}/api/run/${runId}/blocked-roads`, authOpts),
        fetch(`${API_BASE}/api/corridors/active`),
      ]);

      if (resResp.ok) { const d = await resResp.json(); setResources(d.resources || []); }
      if (facResp.ok) { const d = await facResp.json(); setFacilities(d.facilities || []); }
      if (zoneResp.ok) { const d = await zoneResp.json(); setZones(d.zones || []); }
      if (blockResp.ok) { const d = await blockResp.json(); setBlockedRoads(d.blocked_roads || []); }
      if (corrResp?.ok) { const d = await corrResp.json(); setEvacuationCorridors(d.corridors || []); }

      // Fetch Real OpenStreetMap Emergency Infrastructure (Phase P3.1)
      let centerLat = (incidents && incidents.length > 0 && isValidLatLng(incidents[0].latitude, incidents[0].longitude))
        ? incidents[0].latitude
        : null;
      let centerLng = (incidents && incidents.length > 0 && isValidLatLng(incidents[0].latitude, incidents[0].longitude))
        ? incidents[0].longitude
        : null;

      if (!centerLat && facilities && facilities.length > 0 && isValidLatLng(facilities[0].latitude, facilities[0].longitude)) {
        centerLat = facilities[0].latitude;
        centerLng = facilities[0].longitude;
      }

      if (centerLat != null && centerLng != null) {
        try {
          const realFacResp = await fetch(`${API_BASE}/api/intelligence/facilities?lat=${centerLat}&lng=${centerLng}&radius_km=25`);
          if (realFacResp.ok) {
            const d = await realFacResp.json();
            setRealFacilities(d.facilities || []);
          }
        } catch { /* ignore */ }
      } else {
        setRealFacilities([]);
      }
    } catch { /* ignore optional fetch errors */ }
  }, [runId, incidents]);

  useEffect(() => {
    fetchIntelligence();
    fetchEntities();
    const interval = setInterval(fetchIntelligence, 30000); // 30s auto-refresh
    return () => clearInterval(interval);
  }, [fetchIntelligence, fetchEntities]);

  // Handle Nominatim Location Search
  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const resp = await fetch(`${API_BASE}/api/intelligence/search?q=${encodeURIComponent(searchQuery)}`);
      if (resp.ok) {
        const data = await resp.json();
        setSearchResults(data.results || []);
        if (data.results && data.results.length > 0) {
          const top = data.results[0];
          setSearchPin(top);
          if (mapRef.current && isValidLatLng(top.latitude, top.longitude)) {
            mapRef.current.setView([top.latitude, top.longitude], 12);
          }
        }
      }
    } catch { /* ignore search errors */ }
    setIsSearching(false);
  };

  // WebSocket Live Updates Handler
  useEffect(() => {
    const wsUrl = getWebSocketUrl('/ws/simulation');
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'VEHICLE_POSITION_UPDATE' && data.vehicle) {
            const v = data.vehicle;
            if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
            animFrameRef.current = requestAnimationFrame(() => {
              const marker = vehicleMarkersRef.current[v.resource_id];
              if (marker && isValidLatLng(v.latitude, v.longitude)) {
                marker.setLatLng([v.latitude, v.longitude]);
              }

              if (isValidLatLng(v.latitude, v.longitude)) {
                const rId = v.resource_id;
                if (!trailsRef.current[rId]) trailsRef.current[rId] = [];
                trailsRef.current[rId].push([v.latitude, v.longitude]);
                if (trailsRef.current[rId].length > 25) trailsRef.current[rId].shift();
              }
            });
          } else if (data.event_type === 'INTELLIGENCE_NEW' || data.event_type === 'INTELLIGENCE_UPDATED') {
            fetchIntelligence();
          } else if (data.event_type === 'SOURCE_STATUS_CHANGED') {
            fetchIntelligence();
          }
        } catch { /* ignore */ }
      };
    } catch { /* ignore */ }

    return () => {
      if (ws) ws.close();
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [fetchIntelligence]);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapNodeRef.current || mapRef.current) return undefined;

    const map = L.map(mapNodeRef.current, {
      center: DEFAULT_CENTER,
      zoom: 5,
      zoomControl: false,
      preferCanvas: true,
    });

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // High-performance Esri Dark Gray canvas - Zero watermarks, zero API keys required
    L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 16,
      attribution: '&copy; Esri, HERE, Garmin, &copy; OpenStreetMap | Disaster OS EOC GIS',
    }).addTo(map);

    // Esri reference typography overlay for crystal-clear labels & transport networks
    L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 16,
      opacity: 0.9,
    }).addTo(map);

    // Map Point Click Handler for Weather Inspection
    map.on('click', async (e) => {
      const { lat, lng } = e.latlng;
      if (!isValidLatLng(lat, lng)) return;
      try {
        const resp = await fetch(`${API_BASE}/api/intelligence/weather/${lat.toFixed(4)}/${lng.toFixed(4)}`);
        if (resp.ok) {
          const data = await resp.json();
          if (data.observation) {
            setWeatherInspection(data.observation);
          }
        }
      } catch { /* ignore */ }
    });

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    vehicleLayerRef.current = L.layerGroup().addTo(map);

    const invalidate = () => {
      if (map) map.invalidateSize();
    };
    const t1 = setTimeout(invalidate, 100);
    const t2 = setTimeout(invalidate, 400);
    const t3 = setTimeout(invalidate, 1000);

    const resizeObserver = new ResizeObserver(() => {
      if (map) map.invalidateSize();
    });
    if (mapNodeRef.current) {
      resizeObserver.observe(mapNodeRef.current);
    }

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      vehicleLayerRef.current = null;
    };
  }, []);

  // Ensure tiles seamlessly expand and invalidate on tab switches or fullscreen toggle
  useEffect(() => {
    if (mapRef.current) {
      const t = setTimeout(() => {
        if (mapRef.current) mapRef.current.invalidateSize();
      }, 150);
      return () => clearTimeout(t);
    }
  }, [activeTab, isFullscreen]);

  // Dynamic Auto-Centering on active scenario disaster incidents
  useEffect(() => {
    if (!mapRef.current) return;
    const valid = (incidents || []).filter(inc => isValidLatLng(Number(inc.latitude), Number(inc.longitude)));
    if (valid.length > 0) {
      const b = valid.map(inc => [Number(inc.latitude), Number(inc.longitude)]);
      mapRef.current.fitBounds(L.latLngBounds(b), { padding: [50, 50], maxZoom: 12 });
    }
  }, [incidents, runId]);

  // Render Map Layers & Entities
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    vehicleMarkersRef.current = {};
    const bounds = [];

    // 1. Render USGS Live Earthquakes
    if (showEarthquakes) {
      earthquakes.forEach(eq => {
        const lat = Number(eq.latitude);
        const lng = Number(eq.longitude);
        if (!isValidLatLng(lat, lng)) return;

        const pos = [lat, lng];
        bounds.push(pos);
        const mag = eq.magnitude || 4.5;
        const color = mag >= 6.0 ? '#ef4444' : mag >= 5.0 ? '#f97316' : '#eab308';
        const ageStr = formatAgeSeconds(eq.age_seconds);

        const marker = L.marker(pos, {
          icon: createCustomIcon('earthquake', color, 'pulse', `M${mag.toFixed(1)}`),
        }).bindPopup(buildPopupHtml(
          eq.place || 'Earthquake Epicenter',
          `USGS SEISMIC EVENT (Mag ${mag.toFixed(1)})`,
          [
            ['Magnitude', `${mag.toFixed(1)} M_w`, 'text-red-400'],
            ['Depth', `${eq.depth_km || 10.0} km`],
            ['Coordinates', `${lat.toFixed(3)}, ${lng.toFixed(3)}`],
            ['Freshness', ageStr],
            ['Source Provider', eq.source],
          ],
          eq.classification || 'LIVE',
          'Click marker to view full provenance detail panel'
        )).addTo(layer);

        marker.on('click', () => setSelectedEntity({ type: 'EARTHQUAKE', data: eq }));
      });
    }

    // 2. Render GDACS Live Disaster Alerts
    if (showDisasters) {
      disasters.forEach(gd => {
        const lat = Number(gd.latitude);
        const lng = Number(gd.longitude);
        if (!isValidLatLng(lat, lng)) return;

        const pos = [lat, lng];
        bounds.push(pos);
        const dtype = String(gd.event_type || 'incident').toLowerCase();
        const sev = String(gd.severity || 'medium').toLowerCase();
        const color = SEVERITY_COLORS[sev] || SEVERITY_COLORS.medium;
        const ageStr = formatAgeSeconds(gd.age_seconds);

        const marker = L.marker(pos, {
          icon: createCustomIcon(dtype, color, 'pulse'),
        }).bindPopup(buildPopupHtml(
          gd.place || `${dtype.toUpperCase()} Alert`,
          `GDACS GLOBAL DISASTER`,
          [
            ['Category', dtype.toUpperCase()],
            ['Alert Level', sev.toUpperCase(), color === '#ef4444' ? 'text-red-400' : 'text-amber-400'],
            ['Coordinates', `${lat.toFixed(3)}, ${lng.toFixed(3)}`],
            ['Freshness', ageStr],
            ['Source Provider', 'GDACS'],
          ],
          gd.classification || 'LIVE',
          'Click marker to view full provenance detail panel'
        )).addTo(layer);

        marker.on('click', () => setSelectedEntity({ type: 'DISASTER', data: gd }));
      });
    }

    // 3. Render Incidents
    if (showIncidentsLayer) {
      (incidents || []).forEach(inc => {
        const lat = Number(inc.latitude);
        const lng = Number(inc.longitude);
        if (!isValidLatLng(lat, lng)) return;

        const dtype = String(inc.disaster_type || 'incident').toLowerCase();
        const sev = String(inc.severity || 'low').toLowerCase();
        const pos = [lat, lng];
        bounds.push(pos);
        const color = SEVERITY_COLORS[sev] || SEVERITY_COLORS.low;
        const classification = inc.classification || (inc.run_id === 'demo' ? 'SIMULATED' : 'DATABASE');
        const nearest = findNearestResources(lat, lng, resources, facilities);
        const affectedCount = inc.people_affected || 1;
        const injuredCount = inc.injured_count != null
          ? inc.injured_count
          : (sev === 'high' ? Math.round(affectedCount * 0.22) : Math.round(affectedCount * 0.08));
        const casualtiesCount = inc.fatalities != null ? inc.fatalities : (inc.casualties || 0);

        let nearbyHtml = '<div class="pop-nearby-section">';
        nearbyHtml += '<div class="pop-nearby-title">🚑 NEARBY EMERGENCY RESOURCES:</div>';
        if (nearest.fleet.length > 0) {
          nearest.fleet.slice(0, 2).forEach(f => {
            const eta = Math.max(2, Math.round((f.distKm / 35) * 60));
            nearbyHtml += `<div class="pop-nearby-row">` +
              `<span>${(f.resource_type || 'unit').replace('_', ' ').toUpperCase()}: <strong>${f.resource_name || 'Unit'}</strong></span>` +
              `<strong>${f.distKm.toFixed(1)} km (~${eta}m)</strong>` +
              `</div>`;
          });
        }
        if (nearest.hospitals.length > 0) {
          const h = nearest.hospitals[0];
          nearbyHtml += `<div class="pop-nearby-row">` +
            `<span>🏥 ${h.facility_name || 'Hospital'}</span>` +
            `<strong>${h.distKm.toFixed(1)} km &bull; ${h.available_capacity ?? 'N/A'} beds</strong>` +
            `</div>`;
        }
        if (nearest.shelters.length > 0) {
          const s = nearest.shelters[0];
          nearbyHtml += `<div class="pop-nearby-row">` +
            `<span>⛺ ${s.facility_name || 'Shelter'}</span>` +
            `<strong>${s.distKm.toFixed(1)} km &bull; ${s.available_capacity ?? 'N/A'} cap</strong>` +
            `</div>`;
        }
        if (nearest.fleet.length === 0 && nearest.hospitals.length === 0) {
          nearbyHtml += '<div style="color:#94a3b8;font-size:10px;">Dispatching primary fleet to sector...</div>';
        }
        const incTooltipHtml = `<div style="font-size:11px;line-height:1.4;min-width:170px;">` +
          `<strong style="color:${color};font-size:12px;">${dtype.toUpperCase()} DISASTER</strong><br/>` +
          `<span>Location: <strong>${inc.location || 'Incident Sector'}</strong></span><br/>` +
          `<span>Citizens in Hazard Area: <strong>${affectedCount.toLocaleString()}</strong></span><br/>` +
          `<span>Injured: <strong style="color:#f59e0b">${injuredCount.toLocaleString()}</strong> | Casualties: <strong style="color:${casualtiesCount > 0 ? '#ef4444' : '#94a3b8'}">${casualtiesCount.toLocaleString()}</strong></span><br/>` +
          `<span style="color:#38bdf8;font-size:9px;">Click marker for triage & nearby resources</span>` +
          `</div>`;

        L.marker(pos, { icon: createCustomIcon(dtype, color) })
          .bindTooltip(incTooltipHtml, { sticky: true, direction: 'top', offset: [0, -15] })
          .bindPopup(buildPopupHtml(
            inc.location || 'Incident Sector',
            `${dtype.toUpperCase()} DISASTER INCIDENT`,
            [
              ['Disaster Type', dtype.toUpperCase(), 'text-red-400 font-bold'],
              ['Severity Level', sev.toUpperCase(), color === '#ef4444' ? 'text-red-400' : 'text-amber-400'],
              ['Triage Status', inc.status || 'NEW', 'text-sky-400 font-bold'],
              ['People in Hazard Area', `${affectedCount.toLocaleString()} citizens`],
              ['Injured / Requiring Care', `${injuredCount.toLocaleString()} injured`],
              ['Fatalities / Casualties', `${casualtiesCount.toLocaleString()} casualties`, casualtiesCount > 0 ? 'text-red-500' : 'text-slate-400'],
              ['Assigned Dispatch', inc.assigned_team_id || 'Dispatching...'],
              ['Coordinates', `${lat.toFixed(4)}, ${lng.toFixed(4)}`],
            ],
            classification,
            'Click incident to view tactical response protocol',
            nearbyHtml
          ))
          .addTo(layer);

        // Routes
        if (showRoutes && inc.route_coordinates) {
          const routePts = parseRouteCoordinates(inc.route_coordinates);
          if (routePts.length >= 2) {
            const isOsrm = inc.route_provider === 'OSRM';
            const isLocalAstar = inc.route_provider === 'LOCAL_ASTAR';
            const isDirect = inc.route_provider === 'DIRECT_GEOMETRIC';
            const routeColor = isOsrm ? '#38bdf8' : isLocalAstar ? '#a78bfa' : '#94a3b8';
            const providerName = isOsrm
              ? 'OSRM (ROAD_ROUTE)'
              : isLocalAstar
              ? 'LOCAL_ASTAR (GRAPH_ESTIMATE)'
              : isDirect
              ? 'DIRECT_GEOMETRIC (STRAIGHT_LINE_ESTIMATE)'
              : (inc.route_provider || 'UNAVAILABLE');
            L.polyline(routePts, {
              color: routeColor,
              weight: 3.5,
              opacity: 0.85,
              dashArray: isOsrm ? undefined : '6 6',
            }).bindPopup(buildPopupHtml(
              `Route to ${inc.location || 'Incident'}`,
              `ROUTE PROVENANCE: ${providerName}`,
              [
                ['Route Provider', inc.route_provider || 'UNAVAILABLE'],
                ['Route Type', isOsrm ? 'ROAD_ROUTE' : isLocalAstar ? 'GRAPH_ESTIMATE' : 'ESTIMATE'],
                ['Distance', inc.route_distance_km != null ? `${inc.route_distance_km} km` : 'N/A'],
                ['PLANNED ROUTE ETA', inc.route_eta_hours != null ? `${Math.round(inc.route_eta_hours * 60)} min` : 'N/A'],
                ['Assigned Unit', inc.assigned_team_id || 'Dispatching...'],
              ],
              isOsrm ? 'LIVE' : (inc.route_provider === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'CALCULATED'),
              isOsrm ? 'Verified OSRM road network route' : 'Calculated estimate (not a verified road route)'
            )).addTo(layer);
          }
        }
      });
    }

    // 4. Render Fleet Vehicles into vehicleLayer
    const vLayer = vehicleLayerRef.current || layer;
    if (vehicleLayerRef.current) vehicleLayerRef.current.clearLayers();
    if (showVehicles) {
      resources.forEach(v => {
        const lat = Number(v.latitude);
        const lng = Number(v.longitude);
        if (!isValidLatLng(lat, lng)) return;

        const pos = [lat, lng];
        bounds.push(pos);
        const vtype = v.resource_type || 'ambulance';
        const color = v.marker_color || (vtype === 'ambulance' ? '#ef4444' : vtype === 'fire_truck' ? '#f97316' : vtype === 'police_car' ? '#3b82f6' : vtype === 'rescue_boat' ? '#06b6d4' : vtype === 'helicopter' ? '#a855f7' : vtype === 'drone' ? '#10b981' : '#eab308');

        const marker = L.marker(pos, { icon: createCustomIcon(vtype, color) })
          .bindPopup(buildPopupHtml(
            v.resource_name,
            `${vtype.replace('_', ' ').toUpperCase()} FLEET`,
            [
              ['Lifecycle State', (v.status || 'available').toUpperCase()],
              ['Specialization', v.specialization || 'general'],
              ['Capacity', `${v.victims_onboard || 0} / ${v.capacity || 4}`],
              ['Base Sector', v.city || 'EOC Central'],
            ],
            'SIMULATED'
          ))
          .addTo(vLayer);

        vehicleMarkersRef.current[v.resource_id] = marker;

        if (showTrails && trailsRef.current[v.resource_id] && trailsRef.current[v.resource_id].length >= 2) {
          L.polyline(trailsRef.current[v.resource_id], {
            color: color,
            weight: 2,
            opacity: 0.5,
            dashArray: '3 3',
          }).addTo(vLayer);
        }
      });
    }

    // 5. Render Facilities (Hospitals & Shelters)
    facilities.forEach(fac => {
      const lat = Number(fac.latitude);
      const lng = Number(fac.longitude);
      if (!isValidLatLng(lat, lng)) return;

      const ftype = fac.facility_type || 'hospital';
      if (ftype === 'hospital' && !showHospitals) return;
      if (ftype === 'shelter' && !showShelters) return;

      const pos = [lat, lng];
      bounds.push(pos);
      const color = ftype === 'hospital' ? '#ec4899' : '#10b981';

      L.marker(pos, { icon: createCustomIcon(ftype, color) })
        .bindPopup(buildPopupHtml(
          fac.facility_name,
          ftype.replace('_', ' ').toUpperCase(),
          [
            ['Capacity Available', `${fac.available_capacity} / ${fac.total_capacity}`],
            ['Status', fac.status || 'operational'],
            ['City Sector', fac.city || 'Emergency Zone'],
          ],
          'DATABASE'
        ))
        .addTo(layer);
    });

    // 5b. Render Real OpenStreetMap Facilities (Phase P3.1)
    if (showRealFacilities) {
      realFacilities.forEach(fac => {
        const lat = Number(fac.latitude);
        const lng = Number(fac.longitude);
        if (!isValidLatLng(lat, lng)) return;

        const ftype = fac.facility_type || 'hospital';
        const pos = [lat, lng];
        bounds.push(pos);
        const color = ftype === 'hospital' ? '#f43f5e' : ftype === 'fire_station' ? '#ea580c' : ftype === 'police_station' ? '#2563eb' : '#059669';

        const capDisplay = fac.capacity != null ? `${fac.capacity} Units (VERIFIED)` : 'UNAVAILABLE (Sensor Offline)';
        const capClass = fac.capacity != null ? 'text-emerald-400' : 'text-slate-400';

        const marker = L.marker(pos, { icon: createCustomIcon(ftype, color, '', 'OSM') })
          .bindPopup(buildPopupHtml(
            fac.name,
            `REAL ${ftype.replace('_', ' ').toUpperCase()} (OSM)`,
            [
              ['Infrastructure Source', 'OpenStreetMap (LIVE)'],
              ['Capacity Status', capDisplay, capClass],
              ['Coordinates', `${lat.toFixed(4)}, ${lng.toFixed(4)}`],
              ['Address', fac.address || 'Geocoded Location'],
              ['Emergency Service', fac.emergency_service ? 'YES' : 'NO'],
            ],
            fac.classification || 'LIVE',
            'Click marker to view infrastructure provenance panel'
          ))
          .addTo(layer);

        marker.on('click', () => setSelectedEntity({ type: 'REAL_FACILITY', data: fac }));
      });
    }

    // 6. Render Scenario Impact Zones & Joyner-Boore Empirical Isoseismals (Phase P3.2)
    if (showZones && zones.length > 0) {
      zones.forEach(z => {
        const lat = Number(z.center_latitude);
        const lng = Number(z.center_longitude);
        if (!isValidLatLng(lat, lng)) return;

        const circle = L.circle([lat, lng], {
          radius: z.radius_meters || 15000,
          color: z.color || '#38bdf8',
          fillColor: z.color || '#38bdf8',
          fillOpacity: z.opacity || 0.22,
          weight: 1.5,
        });

        circle.bindTooltip(z.zone_name, { permanent: false, direction: 'center' });
        let zTimer = null;
        circle.on('mouseover', () => {
          if (zTimer) { clearTimeout(zTimer); zTimer = null; }
          circle.openTooltip();
        });
        circle.on('mouseout', () => {
          if (zTimer) clearTimeout(zTimer);
          zTimer = setTimeout(() => { circle.closeTooltip(); }, 12000); // 12 seconds persistence
        });
        circle.addTo(layer);
      });
    }

    if (showImpactIsoseismals && impactAssessments.length > 0) {
      // Filter isoseismals relevant to active incident region or selected city focus
      const relevantAssessments = impactAssessments.filter(a => {
        const aLat = Number(a.epicenter_latitude || a.epicenter_lat);
        const aLng = Number(a.epicenter_longitude || a.epicenter_lng);
        if (!isValidLatLng(aLat, aLng)) return false;

        if (selectedCity !== 'All India') {
          const cityObj = MAJOR_CITIES.find(c => c.name === selectedCity);
          if (cityObj) {
            return getDistanceKm(cityObj.lat, cityObj.lng, aLat, aLng) <= 150;
          }
        }

        if (incidents && incidents.length > 0) {
          return incidents.some(inc => {
            const d = getDistanceKm(Number(inc.latitude), Number(inc.longitude), aLat, aLng);
            return d <= 350;
          });
        }
        return true;
      });

      // Deduplicate assessments so multiple historical calculations for the same location do not stack
      const uniqueAssessments = [];
      const seenLocs = new Set();
      for (const a of relevantAssessments) {
        const aLat = Number(a.epicenter_latitude || a.epicenter_lat);
        const aLng = Number(a.epicenter_longitude || a.epicenter_lng);
        if (!isValidLatLng(aLat, aLng)) continue;
        const key = `${aLat.toFixed(3)}_${aLng.toFixed(3)}`;
        if (!seenLocs.has(key)) {
          seenLocs.add(key);
          uniqueAssessments.push(a);
        }
      }

      uniqueAssessments.forEach(assessment => {
        const lat = Number(assessment.epicenter_latitude || assessment.epicenter_lat);
        const lng = Number(assessment.epicenter_longitude || assessment.epicenter_lng);
        if (!isValidLatLng(lat, lng)) return;

        const zonesList = assessment.impact_zones || [];
        const sortedZones = [...zonesList].sort((a, b) => (b.radius_meters || b.radius_km * 1000) - (a.radius_meters || a.radius_km * 1000));

        sortedZones.forEach(z => {
          const rMeters = z.radius_meters || (z.radius_km * 1000);
          const circle = L.circle([lat, lng], {
            radius: rMeters,
            color: z.color || '#ef4444',
            fillColor: z.color || '#ef4444',
            fillOpacity: z.opacity || 0.22,
            weight: z.level === 'CRITICAL' ? 2.2 : 1.2,
            dashArray: z.level === 'ADVISORY' ? '5, 5' : null,
            interactive: true,
          });

          const zoneHtml = `<div style="font-size:11px;line-height:1.4;min-width:210px;padding:2px;">` +
            `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;">` +
            `<strong style="color:${z.color || '#fff'};font-size:12px;">${z.name}</strong>` +
            `<span class="op-badge op-badge-calc" style="font-size:8px;">CALCULATED</span>` +
            `</div>` +
            `<div>Radius: <strong>${z.radius_km} km</strong> (${(rMeters / 1000).toFixed(1)} km)</div>` +
            `<div style="color:#94a3b8;font-size:10px;margin-top:2px;">${z.expected_damage || 'Hazard attenuation zone'}</div>` +
            `<div style="margin-top:5px;padding-top:4px;border-top:1px solid rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:space-between;">` +
            `<span style="color:#38bdf8;font-size:9px;">${assessment.methodology || 'Joyner-Boore Attenuation'}</span>` +
            `<span style="color:#64748b;font-size:8px;">Click to pin</span>` +
            `</div>` +
            `</div>`;

          circle.bindTooltip(zoneHtml, {
            sticky: false,
            interactive: true,
            direction: 'top',
            offset: [0, -10],
            opacity: 0.98,
          });

          let circleHideTimer = null;
          circle.on('mouseover', (e) => {
            if (circleHideTimer) {
              clearTimeout(circleHideTimer);
              circleHideTimer = null;
            }
            circle.openTooltip(e.latlng);
            setIsoseismalInspection({
              zone: z,
              assessment: assessment,
              rMeters: rMeters,
              lat: lat,
              lng: lng,
            });
          });

          circle.on('mouseout', () => {
            if (circleHideTimer) clearTimeout(circleHideTimer);
            // Generous 12-second timer so the user has ample time to read the text calmly
            circleHideTimer = setTimeout(() => {
              circle.closeTooltip();
            }, 12000);
          });

          circle.bindPopup(buildPopupHtml(
            z.name,
            `JOYNER-BOORE ATTENUATION ISOSEISMAL (${z.level || 'IMPACT'})`,
            [
              ['Isoseismal Zone', z.name],
              ['Impact Level', z.level || 'MODERATE', z.level === 'CRITICAL' ? 'text-red-400 font-bold' : 'text-amber-400'],
              ['Radius', `${z.radius_km} km (${(rMeters / 1000).toFixed(1)} km)`],
              ['Expected Damage', z.expected_damage || 'Structural distress and shaking'],
              ['Peak Ground Accel (PGA)', z.pga ? `${z.pga} g` : 'Calculated Attenuation'],
              ['Epicenter Coordinates', `${lat.toFixed(4)}, ${lng.toFixed(4)}`],
              ['Attenuation Model', assessment.methodology || 'Joyner-Boore (1981) Empirical'],
            ],
            'CALCULATED',
            'Click anywhere on the map or close popup to dismiss'
          ));

          circle.on('click', () => {
            if (circleHideTimer) {
              clearTimeout(circleHideTimer);
              circleHideTimer = null;
            }
            setSelectedEntity({ type: 'IMPACT_ASSESSMENT', data: assessment });
            setIsoseismalInspection({
              zone: z,
              assessment: assessment,
              rMeters: rMeters,
              lat: lat,
              lng: lng,
              pinned: true,
            });
          });

          circle.addTo(layer);
        });

        // Add a central Epicenter Marker with pulse icon
        const epicenterMarker = L.marker([lat, lng], {
          icon: createCustomIcon('earthquake', '#ef4444', 'pulse', 'EPICENTER'),
        }).bindTooltip(
          `<strong>EPICENTER: ${assessment.incident_id || 'Seismic Event'}</strong><br/>Click to view full Joyner-Boore impact analysis`,
          { sticky: true, direction: 'top' }
        ).bindPopup(buildPopupHtml(
          'Seismic Epicenter',
          'EARTHQUAKE EPICENTER ATTENUATION',
          [
            ['Incident ID', assessment.incident_id || 'Seismic Event'],
            ['Epicenter Lat/Lng', `${lat.toFixed(4)}, ${lng.toFixed(4)}`],
            ['Magnitude', assessment.magnitude ? `M${assessment.magnitude}` : 'Calculated'],
            ['Isoseismal Zones', `${sortedZones.length} concentric zones`],
            ['Methodology', assessment.methodology || 'Joyner-Boore Attenuation'],
          ],
          'CALCULATED'
        ));
        epicenterMarker.addTo(layer);
      });
    }

    // 7. Render Search Pin
    if (searchPin && isValidLatLng(searchPin.latitude, searchPin.longitude)) {
      L.marker([searchPin.latitude, searchPin.longitude], {
        icon: createCustomIcon('incident', '#38bdf8', 'pulse', 'SEARCH'),
      }).bindPopup(buildPopupHtml(
        searchPin.display_name,
        'NOMINATIM SEARCH PIN',
        [
          ['Coordinates', `${searchPin.latitude.toFixed(4)}, ${searchPin.longitude.toFixed(4)}`],
          ['Type', searchPin.type || 'location'],
        ],
        searchPin.classification || 'LIVE'
      )).addTo(layer);
    }

    // 8. Render Evacuation Corridors (Phase P3.4)
    if (showCorridors && evacuationCorridors.length > 0) {
      const relevantCorridors = evacuationCorridors.filter(c => {
        const pts = c.path_coordinates || [];
        if (pts.length < 2) return false;
        if (selectedCity !== 'All India') {
          const cityObj = MAJOR_CITIES.find(ci => ci.name === selectedCity);
          if (cityObj) {
            const d = getDistanceKm(cityObj.lat, cityObj.lng, Number(pts[0][0]), Number(pts[0][1]));
            return d <= 200;
          }
        }
        return true;
      });

      relevantCorridors.forEach(c => {
        const pts = c.path_coordinates || [];
        if (pts.length >= 2) {
          const color = c.safety_tier === 'TIER_1_OPTIMAL' ? '#10b981' : (c.safety_tier === 'TIER_2_RESTRICTED' ? '#f59e0b' : '#ef4444');
          const prov = c.route_provider || c.provider || 'CALCULATED';
          L.polyline(pts, {
            color: color,
            weight: 4.5,
            opacity: 0.9,
            dashArray: c.status === 'HAZARDOUS_IMPEDED' ? '6 6' : null,
          }).bindPopup(buildPopupHtml(
            c.name || 'Evacuation Corridor',
            `EVACUATION CORRIDOR (${(c.profile || 'CAR').toUpperCase()})`,
            [
              ['Safety Tier', c.safety_tier, color === '#10b981' ? 'text-emerald-400' : 'text-amber-400'],
              ['Route Provider', prov],
              ['Route Type', c.route_type || (prov === 'OSRM' ? 'ROAD_ROUTE' : 'GRAPH_ESTIMATE')],
              ['Distance', c.distance_km != null ? `${c.distance_km} km` : 'N/A'],
              ['PLANNED ROUTE ETA', c.transit_time_minutes != null ? `${c.transit_time_minutes} min` : 'N/A'],
              ['Est. Clearance Time', `${c.estimated_clearance_hours} hours (${c.population_to_evacuate} citizens)`],
              ['Throughput', `${c.bottleneck_throughput_per_hour} units/hour`],
            ],
            prov === 'OSRM' ? 'LIVE' : 'CALCULATED',
            c.hazard_intersections?.length > 0 ? `Alert: ${c.hazard_intersections[0]}` : (prov === 'OSRM' ? 'OSRM verified road network' : 'Calculated estimate (not a verified road route)')
          )).addTo(layer);
        }
      });
    }
  }, [earthquakes, disasters, incidents, resources, facilities, realFacilities, zones, impactAssessments, evacuationCorridors, showEarthquakes, showDisasters, showVehicles, showHospitals, showShelters, showRealFacilities, showIncidentsLayer, showZones, showImpactIsoseismals, showCorridors, showRoutes, showTrails, searchPin, selectedCity]);

  // Fit bounds helper functions
  const fitEarthquakes = () => {
    if (!mapRef.current || earthquakes.length === 0) return;
    const bounds = earthquakes.map(eq => [eq.latitude, eq.longitude]).filter(pt => isValidLatLng(pt[0], pt[1]));
    if (bounds.length > 0) mapRef.current.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 7 });
  };

  const fitIncidents = () => {
    if (!mapRef.current || incidents.length === 0) return;
    const bounds = incidents.map(inc => [inc.latitude, inc.longitude]).filter(pt => isValidLatLng(pt[0], pt[1]));
    if (bounds.length > 0) mapRef.current.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 9 });
  };

  const fitFleet = () => {
    if (!mapRef.current || resources.length === 0) return;
    const bounds = resources.map(v => [v.latitude, v.longitude]).filter(pt => isValidLatLng(pt[0], pt[1]));
    if (bounds.length > 0) mapRef.current.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 9 });
  };

  return (
    <div className={`eoc-gis-wrapper ${isFullscreen ? 'fullscreen' : ''}`}>
      <div ref={mapNodeRef} style={{ width: '100%', height: '100%', borderRadius: 'var(--radius-lg)' }} />

      {/* Unified Non-Overlapping GIS Top Navigation Bar */}
      <div className="gis-top-container">
        <div className="gis-header-bar">
          <form className="gis-search-form" onSubmit={handleSearchSubmit}>
            <input
              type="text"
              placeholder="Search city, address, or coordinates via Nominatim..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit" disabled={isSearching}>
              {isSearching ? '...' : '🔍 Search'}
            </button>
          </form>

          {/* Source Health Matrix Indicator Pill */}
          <div className="source-health-pill" title="Live External Intelligence Providers Health Matrix">
            <span className="pill-title">PROVIDERS:</span>
            {sourceHealth.map(s => (
              <span key={s.name} className={`health-dot ${s.status.toLowerCase()}`} title={`${s.name}: ${s.status} (${s.response_time_ms}ms, ${s.freshness_seconds != null ? s.freshness_seconds + 's' : 'N/A'})`}>
                ● {s.name}
              </span>
            ))}
          </div>
        </div>

        {/* GIS Floating Toolbar Buttons */}
        <div className="gis-toolbar">
          <div className="gis-city-selector" title="Focus map viewport on major disaster scenario hubs">
            <span className="city-selector-label">📍 HUB:</span>
            {MAJOR_CITIES.map(c => (
              <button
                key={c.name}
                type="button"
                className={`gis-city-btn ${selectedCity === c.name ? 'active' : ''}`}
                onClick={() => handleCitySelect(c.name)}
                title={`Focus map on ${c.name} and load regional infrastructure`}
              >
                {c.name}
              </button>
            ))}
          </div>

          <button className="gis-btn" onClick={fitIncidents} title="Fit map to active disaster incidents">
            🔥 Fit Disaster
          </button>
          <button className="gis-btn" onClick={fitFleet} title="Fit map to fleet units">
            🚑 Fit Fleet
          </button>
          <button className="gis-btn" onClick={fitEarthquakes} title="Fit map to live USGS Earthquakes">
            🌋 Fit Quakes
          </button>
          <button className={`gis-btn ${showRealFacilities ? 'active' : ''}`} onClick={() => setShowRealFacilities(v => !v)} title="Toggle Real OpenStreetMap Emergency Facilities">
            🏥 Real OSM ({realFacilities.length})
          </button>
          <button className={`gis-btn ${showImpactIsoseismals ? 'active' : ''}`} onClick={() => setShowImpactIsoseismals(v => !v)} title="Toggle Joyner-Boore Impact Isoseismals">
            💥 Isoseismals
          </button>
          <button className="gis-btn" onClick={() => setPanelOpen(v => !v)} title="Toggle Map Layers">
            ⚙️ Layers
          </button>
          <button className="gis-btn" onClick={() => setIsFullscreen(v => !v)} title="Toggle Fullscreen">
            {isFullscreen ? '📉 Exit' : '📈 Fullscreen'}
          </button>
        </div>
      </div>

      {/* Persistent Data Provenance Legend */}
      <div className="gis-legend">
        <div className="legend-head">EOC DATA PROVENANCE LEGEND</div>
        <div className="legend-grid">
          <div className="legend-item"><span className="op-badge op-badge-live">LIVE</span> External APIs (USGS/GDACS/Weather)</div>
          <div className="legend-item"><span className="op-badge op-badge-db">DATABASE</span> Persisted Facilities & Roads</div>
          <div className="legend-item"><span className="op-badge op-badge-calc">CALCULATED</span> Joyner-Boore Isoseismals & OSRM</div>
          <div className="legend-item"><span className="op-badge op-badge-sim">SIMULATED</span> Scenario Fleet & Incidents</div>
          <div className="legend-item"><span className="op-badge op-badge-unavail">UNAVAILABLE</span> Unreported / Missing (Never Invented)</div>
        </div>
      </div>

      {/* Floating Weather Inspection Card Overlay */}
      {weatherInspection && (
        <div className="weather-card-overlay">
          <div className="weather-card-head">
            <span>🌦️ Point Weather Observation</span>
            <button onClick={() => setWeatherInspection(null)}>✕</button>
          </div>
          <div className="weather-card-body">
            <div className="temp-val">{weatherInspection.temperature != null ? `${weatherInspection.temperature}°C` : 'UNAVAILABLE'}</div>
            <div className="weather-cond">{weatherInspection.weather_condition || 'UNAVAILABLE'}</div>
            <div className="weather-meta">
              <div>Wind: {weatherInspection.wind_speed_kmh != null ? `${weatherInspection.wind_speed_kmh} km/h` : 'UNAVAILABLE'}</div>
              <div>Humidity: {weatherInspection.humidity_pct != null ? `${weatherInspection.humidity_pct}%` : (weatherInspection.humidity != null ? `${weatherInspection.humidity}%` : 'UNAVAILABLE')}</div>
              <div>Rainfall: {weatherInspection.precipitation_mm != null ? `${weatherInspection.precipitation_mm} mm` : 'UNAVAILABLE'}</div>
              <div>Provider: <strong className="text-sky-400">{weatherInspection.provider || 'UNAVAILABLE'}</strong></div>
              <div>Classification: <span className={`op-badge op-badge-${(weatherInspection.classification || 'unavailable').toLowerCase()}`}>{weatherInspection.classification || 'UNAVAILABLE'}</span></div>
              <div>Freshness: {formatAgeSeconds(weatherInspection.freshness_seconds)}</div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Isoseismal Hazard Inspector Overlay */}
      {isoseismalInspection && (
        <div className="weather-card-overlay" style={{ bottom: 20, left: 24, zIndex: 1000, maxWidth: 330, borderLeft: `4px solid ${isoseismalInspection.zone?.color || '#38bdf8'}` }}>
          <div className="weather-card-head" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: isoseismalInspection.zone?.color || '#38bdf8' }}>
                💥 {isoseismalInspection.zone?.name}
              </span>
              <span className="op-badge op-badge-calc" style={{ fontSize: 9 }}>CALCULATED</span>
            </div>
            <button onClick={() => setIsoseismalInspection(null)} title="Dismiss inspector">✕</button>
          </div>
          <div className="weather-card-body" style={{ marginTop: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#f8fafc', marginBottom: 4 }}>
              Radius: {isoseismalInspection.zone?.radius_km} km <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 400 }}>({((isoseismalInspection.rMeters || 0) / 1000).toFixed(1)} km)</span>
            </div>
            <div style={{ fontSize: 11, color: '#cbd5e1', lineHeight: 1.4, marginBottom: 8, background: 'rgba(255,255,255,0.04)', padding: '6px 8px', borderRadius: 4 }}>
              {isoseismalInspection.zone?.expected_damage || 'Hazard attenuation threshold zone'}
            </div>
            <div className="weather-meta" style={{ fontSize: 11, gap: 4 }}>
              <div>Impact Level: <strong className={isoseismalInspection.zone?.level === 'CRITICAL' ? 'text-red-400 font-bold' : 'text-amber-400'}>{isoseismalInspection.zone?.level || 'MODERATE'}</strong></div>
              <div>Ground Motion (PGA): <strong style={{ color: '#38bdf8' }}>{isoseismalInspection.zone?.pga ? `${isoseismalInspection.zone.pga} g` : 'Attenuation Model'}</strong></div>
              <div>Epicenter Location: <span style={{ fontFamily: 'monospace' }}>{isoseismalInspection.lat?.toFixed(4)}, {isoseismalInspection.lng?.toFixed(4)}</span></div>
              <div>Model: <span style={{ color: '#94a3b8', fontSize: 10 }}>{isoseismalInspection.assessment?.methodology || 'Joyner-Boore (1981) Empirical'}</span></div>
            </div>
            <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10, color: '#64748b' }}>
              <span>Auto-remains visible for inspection</span>
              <button
                className="btn-secondary"
                onClick={() => {
                  setSelectedEntity({ type: 'IMPACT_ASSESSMENT', data: isoseismalInspection.assessment });
                }}
                style={{ fontSize: 10, padding: '2px 8px' }}
              >
                Full Assessment Drawer →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Slide-Out Event Detail Panel Drawer */}
      {selectedEntity && (
        <div className="entity-detail-drawer">
          <div className="drawer-head">
            <h3>
              {selectedEntity.type === 'REAL_FACILITY'
                ? 'REAL OSM INFRASTRUCTURE'
                : selectedEntity.type === 'IMPACT_ASSESSMENT'
                ? 'DISASTER IMPACT MODEL'
                : `${selectedEntity.type} EVENT PROVENANCE`}
            </h3>
            <button onClick={() => setSelectedEntity(null)}>✕</button>
          </div>
          <div className="drawer-body">
            <div className="detail-title">
              {selectedEntity.data.name || selectedEntity.data.place || selectedEntity.data.title || selectedEntity.data.assessment_id}
            </div>

            {selectedEntity.type === 'IMPACT_ASSESSMENT' ? (
              <div className="impact-detail-content">
                <div className="detail-row">
                  <span>Classification:</span>
                  <span className="op-badge op-badge-calc">CALCULATED</span>
                </div>
                <div className="detail-row"><span>Methodology:</span> <strong>{selectedEntity.data.methodology}</strong></div>
                <div className="detail-row"><span>Confidence:</span> <strong className="text-sky-400">{selectedEntity.data.confidence}</strong></div>
                <div className="detail-row"><span>Road Access:</span> <strong className={selectedEntity.data.route_accessibility_status === 'CLEAR' ? 'text-emerald-400' : 'text-amber-400'}>{selectedEntity.data.route_accessibility_status}</strong></div>
                <div className="detail-row"><span>Epicenter:</span> <code>{Number(selectedEntity.data.epicenter_latitude || selectedEntity.data.epicenter_lat).toFixed(4)}, {Number(selectedEntity.data.epicenter_longitude || selectedEntity.data.epicenter_lng).toFixed(4)}</code></div>
                {selectedEntity.data.magnitude && <div className="detail-row"><span>Magnitude:</span> <strong>M {selectedEntity.data.magnitude}</strong></div>}
                {selectedEntity.data.depth_km && <div className="detail-row"><span>Focal Depth:</span> <strong>{selectedEntity.data.depth_km} km</strong></div>}

                <h4 style={{ margin: '14px 0 8px 0', fontSize: 11, color: '#38bdf8', letterSpacing: 0.5 }}>MMI ATTENUATION HAZARD ZONES</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
                  {(selectedEntity.data.impact_zones || []).map(z => (
                    <div key={z.zone_id} style={{ background: 'rgba(255,255,255,0.04)', borderLeft: `3px solid ${z.color}`, padding: '6px 8px', borderRadius: 4, fontSize: 11 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <strong style={{ color: z.color }}>{z.name}</strong>
                        <span>{z.radius_km} km</span>
                      </div>
                      <div style={{ color: '#94a3b8', fontSize: 10, marginTop: 2 }}>{z.expected_damage}</div>
                    </div>
                  ))}
                </div>

                <h4 style={{ margin: '14px 0 8px 0', fontSize: 11, color: '#38bdf8', letterSpacing: 0.5 }}>
                  EXPOSED INFRASTRUCTURE ({(selectedEntity.data.facilities_in_impact_zone || selectedEntity.data.facilities || []).length})
                </h4>
                <div style={{ maxHeight: 180, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {(selectedEntity.data.facilities_in_impact_zone || selectedEntity.data.facilities || []).map(f => (
                    <div key={f.facility_id || f.name} style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '6px 8px', borderRadius: 4, fontSize: 10, border: '1px solid #334155' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                        <span style={{ color: '#f8fafc' }}>{f.name}</span>
                        <span style={{ color: '#38bdf8' }}>{f.distance_km} km</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', marginTop: 2 }}>
                        <span>{f.facility_type?.replace('_', ' ')} &bull; {f.impact_tier}</span>
                        <span className="op-badge op-badge-unavail">CAP: UNAVAILABLE</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="provenance-notice" style={{ marginTop: 12, padding: 8, background: 'rgba(56, 189, 248, 0.08)', borderRadius: 6, fontSize: 10, color: '#94a3b8' }}>
                  🛡️ <strong>Methodology Note:</strong> Empirical attenuation calculations are analytically derived approximations based on crustal ground motion models. Capacities are strictly unrecorded (UNAVAILABLE).
                </div>
              </div>
            ) : (
              <div className="detail-grid">
                <div className="detail-row">
                  <span>Classification:</span>
                  <span className={`op-badge op-badge-${(selectedEntity.data.classification || 'LIVE').toLowerCase()}`}>
                    {selectedEntity.data.classification || 'LIVE'}
                  </span>
                </div>
                <div className="detail-row"><span>Source Provider:</span> <strong>{selectedEntity.data.source || 'OpenStreetMap'}</strong></div>
                {selectedEntity.data.source_id && <div className="detail-row"><span>Source ID:</span> <code>{selectedEntity.data.source_id}</code></div>}
                {selectedEntity.data.facility_type && <div className="detail-row"><span>Facility Type:</span> <strong style={{ textTransform: 'capitalize' }}>{selectedEntity.data.facility_type.replace('_', ' ')}</strong></div>}
                {selectedEntity.data.capacity != null ? (
                  <div className="detail-row"><span>Bed / Unit Capacity:</span> <strong className="text-emerald-400">{selectedEntity.data.capacity} (VERIFIED)</strong></div>
                ) : selectedEntity.type === 'REAL_FACILITY' ? (
                  <div className="detail-row"><span>Bed Capacity:</span> <span className="op-badge op-badge-unavail">UNAVAILABLE</span> (Live sensors unrecorded in OSM)</div>
                ) : null}
                {selectedEntity.data.magnitude && <div className="detail-row"><span>Magnitude:</span> <strong>M {selectedEntity.data.magnitude}</strong></div>}
                {selectedEntity.data.severity && <div className="detail-row"><span>Severity:</span> <strong>{selectedEntity.data.severity}</strong></div>}
                {selectedEntity.data.depth_km && <div className="detail-row"><span>Depth:</span> <strong>{selectedEntity.data.depth_km} km</strong></div>}
                <div className="detail-row"><span>Latitude:</span> <strong>{selectedEntity.data.latitude}</strong></div>
                <div className="detail-row"><span>Longitude:</span> <strong>{selectedEntity.data.longitude}</strong></div>
                {selectedEntity.data.address && <div className="detail-row"><span>Address:</span> <span>{selectedEntity.data.address}</span></div>}
                {selectedEntity.data.phone && <div className="detail-row"><span>Phone:</span> <span>{selectedEntity.data.phone}</span></div>}
                {selectedEntity.data.observed_at && <div className="detail-row"><span>Observed At:</span> <span>{new Date(selectedEntity.data.observed_at * 1000).toLocaleString()}</span></div>}
                {selectedEntity.data.fetched_at && <div className="detail-row"><span>Fetched At:</span> <span>{new Date(selectedEntity.data.fetched_at * 1000).toLocaleString()}</span></div>}
              </div>
            )}

            {(selectedEntity.type === 'EARTHQUAKE' || selectedEntity.type === 'DISASTER') && (
              <button
                onClick={() => handleAssessImpact(selectedEntity.data, selectedEntity.type === 'EARTHQUAKE' ? 'earthquake' : selectedEntity.data.event_type || 'cyclone')}
                className="source-link-btn"
                style={{ marginTop: 10, background: '#ea580c' }}
              >
                ⚡ Calculate Joyner-Boore Impact Isoseismals
              </button>
            )}

            {selectedEntity.type === 'REAL_FACILITY' && (
              <div className="provenance-notice" style={{ marginTop: 12, padding: 10, background: 'rgba(56, 189, 248, 0.08)', borderRadius: 6, fontSize: 11, color: '#94a3b8' }}>
                🛡️ <strong>Disaster OS Provenance Guarantee:</strong> Facility locations are mapped directly from real OpenStreetMap infrastructure nodes. Capacity is never fabricated; when unavailable, it is explicitly marked UNAVAILABLE.
              </div>
            )}
            {selectedEntity.data.source_url && (
              <a href={selectedEntity.data.source_url} target="_blank" rel="noopener noreferrer" className="source-link-btn">
                🔗 Open Official {selectedEntity.data.source} Event Report Page
              </a>
            )}
          </div>
        </div>
      )}

      {/* Layers Controls Side Drawer */}
      <aside className={`gis-panel ${panelOpen ? 'open' : ''}`}>
        <div className="panel-head">
          <span>EOC Layer Controls</span>
          <button onClick={() => setPanelOpen(false)}>✕</button>
        </div>
        <div className="panel-toggles">
          <label><input type="checkbox" checked={showRealFacilities} onChange={e => setShowRealFacilities(e.target.checked)} /> 🏥 Real OSM Facilities (Live OpenStreetMap)</label>
          <label><input type="checkbox" checked={showImpactIsoseismals} onChange={e => setShowImpactIsoseismals(e.target.checked)} /> 💥 Joyner-Boore Impact Isoseismals (MMI VII/V/III)</label>
          <label><input type="checkbox" checked={showCorridors} onChange={e => setShowCorridors(e.target.checked)} /> 🛣️ Evacuation Corridors ({evacuationCorridors.length})</label>
          <label><input type="checkbox" checked={showEarthquakes} onChange={e => setShowEarthquakes(e.target.checked)} /> 🌋 Live USGS Earthquakes</label>
          <label><input type="checkbox" checked={showDisasters} onChange={e => setShowDisasters(e.target.checked)} /> 🌊 Live GDACS Global Alerts</label>
          <label><input type="checkbox" checked={showIncidentsLayer} onChange={e => setShowIncidentsLayer(e.target.checked)} /> 🔥 Active EOC Incidents</label>
          <label><input type="checkbox" checked={showVehicles} onChange={e => setShowVehicles(e.target.checked)} /> 🚑 Fleet Response Vehicles</label>
          <label><input type="checkbox" checked={showHospitals} onChange={e => setShowHospitals(e.target.checked)} /> 🏥 Scenario Hospitals</label>
          <label><input type="checkbox" checked={showShelters} onChange={e => setShowShelters(e.target.checked)} /> ⛺ Scenario Shelters</label>
          <label><input type="checkbox" checked={showZones} onChange={e => setShowZones(e.target.checked)} /> 🗺️ Scenario Hazard Zones</label>
          <label><input type="checkbox" checked={showRoutes} onChange={e => setShowRoutes(e.target.checked)} /> 🛣️ OSRM Real Road Routes</label>
          <label><input type="checkbox" checked={showTrails} onChange={e => setShowTrails(e.target.checked)} /> 🐾 Fleet Position Trails</label>
        </div>
      </aside>

      <style>{`
        .eoc-gis-wrapper {
          position: relative; width: 100%; height: 100%; min-height: 620px;
          border-radius: var(--radius-lg); overflow: hidden;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: #0f172a;
        }
        .leaflet-container {
          width: 100% !important;
          height: 100% !important;
          background: #0f172a !important;
        }
        .eoc-gis-wrapper.fullscreen {
          position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
          z-index: 99999; border-radius: 0;
        }
        .gis-top-container {
          position: absolute; top: 12px; left: 12px; right: 12px; z-index: 1000;
          display: flex; justify-content: space-between; align-items: center;
          flex-wrap: wrap; gap: 8px; pointer-events: none;
        }
        .gis-header-bar {
          display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
          pointer-events: auto;
        }
        .gis-search-form {
          display: flex; gap: 6px; background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(10px);
          padding: 4px 6px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.15);
        }
        .gis-search-form input {
          background: transparent; border: none; outline: none; color: #fff;
          font-size: 11px; width: 220px; padding: 4px 8px;
        }
        .gis-search-form button {
          background: #38bdf8; color: #0f172a; border: none; font-weight: 700;
          font-size: 11px; padding: 4px 10px; border-radius: 6px; cursor: pointer;
        }
        .source-health-pill {
          display: flex; align-items: center; gap: 8px; background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(10px); padding: 5px 10px; border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.15); font-size: 10px; color: #cbd5e1;
        }
        .pill-title { font-weight: 700; color: #94a3b8; letter-spacing: 0.5px; }
        .health-dot { font-weight: 600; cursor: help; }
        .health-dot.operational { color: #10b981; }
        .health-dot.degraded { color: #f59e0b; }
        .health-dot.unavailable { color: #ef4444; }

        .gis-toolbar {
          display: flex; gap: 6px; flex-wrap: wrap; pointer-events: auto;
        }
        .gis-city-selector {
          display: flex; align-items: center; gap: 3px; background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(10px); padding: 2px 6px; border-radius: 6px;
          border: 1px solid rgba(255, 255, 255, 0.15); box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }
        .city-selector-label {
          font-size: 10px; font-weight: 800; color: #38bdf8; margin-right: 3px; letter-spacing: 0.5px;
        }
        .gis-city-btn {
          background: transparent; color: #cbd5e1; border: none;
          padding: 3px 6px; border-radius: 4px; font-size: 10px; font-weight: 600;
          cursor: pointer; transition: all 0.15s ease;
        }
        .gis-city-btn:hover {
          background: #334155; color: #fff;
        }
        .gis-city-btn.active {
          background: #0284c7; color: #fff; font-weight: 700; box-shadow: 0 0 8px rgba(56, 189, 248, 0.4);
        }
        .gis-btn {
          background: #1e293b; color: #f8fafc; border: 1px solid #334155;
          padding: 6px 10px; border-radius: 6px; font-weight: 600; font-size: 11px;
          cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }
        .gis-btn:hover { background: #334155; }
        .gis-btn.active { background: #0284c7; border-color: #38bdf8; color: #fff; }

        .pop-nearby-section {
          margin-top: 8px; padding-top: 8px;
          border-top: 1px dashed rgba(255, 255, 255, 0.18);
        }
        .pop-nearby-title {
          font-size: 10px; font-weight: 800; color: #38bdf8;
          letter-spacing: 0.5px; margin-bottom: 5px;
        }
        .pop-nearby-row {
          display: flex; justify-content: space-between; align-items: center;
          font-size: 10px; line-height: 1.4; gap: 8px; margin-bottom: 3px;
        }
        .pop-nearby-row span { color: #cbd5e1; }
        .pop-nearby-row strong { color: #34d399; font-weight: 600; white-space: nowrap; }
        .gis-legend {
          position: absolute; bottom: 16px; left: 16px; z-index: 1000;
          background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px;
          padding: 8px 12px; color: #fff; font-size: 10px;
        }
        .legend-head { font-weight: 700; margin-bottom: 4px; color: #94a3b8; letter-spacing: 0.5px; }
        .legend-grid { display: flex; flex-direction: column; gap: 4px; }
        .legend-item { display: flex; align-items: center; gap: 6px; font-size: 10px; color: #cbd5e1; }

        .weather-card-overlay {
          position: absolute; bottom: 16px; right: 16px; z-index: 1000;
          background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(12px);
          border: 1px solid #38bdf8; border-radius: 10px; padding: 12px;
          color: #fff; width: 240px; box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }
        .weather-card-head { display: flex; justify-content: space-between; font-weight: 700; font-size: 11px; color: #38bdf8; margin-bottom: 8px; }
        .weather-card-head button { background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 12px; }
        .temp-val { font-size: 24px; font-weight: 800; color: #f8fafc; }
        .weather-cond { font-size: 12px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px; }
        .weather-meta { font-size: 10px; color: #94a3b8; display: grid; gap: 2px; }

        .entity-detail-drawer {
          position: absolute; top: 0; right: 0; width: 340px; height: 100%;
          background: #0f172a; border-left: 1px solid #334155; z-index: 1002;
          padding: 16px; color: #fff; overflow-y: auto; box-shadow: -8px 0 24px rgba(0,0,0,0.6);
        }
        .drawer-head { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 10px; margin-bottom: 12px; }
        .drawer-head h3 { font-size: 12px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px; margin: 0; }
        .drawer-head button { background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 14px; }
        .detail-title { font-size: 14px; font-weight: 700; color: #f8fafc; margin-bottom: 12px; }
        .detail-grid { display: flex; flex-direction: column; gap: 8px; font-size: 11px; margin-bottom: 16px; }
        .detail-row { display: flex; justify-content: space-between; border-bottom: 1px dashed #1e293b; padding-bottom: 4px; }
        .detail-row span { color: #94a3b8; }
        .source-link-btn { display: block; text-align: center; background: #0284c7; color: #fff; padding: 8px; border-radius: 6px; font-weight: 700; font-size: 11px; text-decoration: none; margin-top: 12px; }

        .gis-panel {
          position: absolute; top: 0; right: -320px; width: 300px; height: 100%;
          background: #0f172a; border-left: 1px solid #1e293b; z-index: 1001;
          padding: 16px; transition: right 0.3s ease; color: #f8fafc; overflow-y: auto;
        }
        .gis-panel.open { right: 0; }
        .panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-weight: 700; }
        .panel-toggles label { display: block; font-size: 11px; margin-bottom: 12px; cursor: pointer; color: #cbd5e1; }

        .pop-cat-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .eoc-badge { position: absolute; top: -6px; right: -6px; background: #0f172a; border: 1px solid #38bdf8; color: #38bdf8; font-size: 8px; font-weight: 800; padding: 1px 3px; border-radius: 4px; }
      `}</style>
    </div>
  );
});

export default LiveMap;
