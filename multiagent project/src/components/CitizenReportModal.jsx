import React, { useState } from 'react';

import { API_BASE } from '../config';

export default function CitizenReportModal({ isOpen, onClose, onSuccess }) {
  const [location, setLocation] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [disasterType, setDisasterType] = useState('flood');
  const [peopleAffected, setPeopleAffected] = useState(1);
  const [severity, setSeverity] = useState('high');
  const [sosType, setSosType] = useState('SOS Alert');
  const [mediaUrl, setMediaUrl] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  if (!isOpen) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setMessage('');

    const latNum = Number(latitude);
    const lngNum = Number(longitude);
    const affectedNum = Number(peopleAffected);

    if (!Number.isFinite(latNum) || latNum < -90.0 || latNum > 90.0) {
      setMessage('Error: Latitude must be a finite number between -90 and 90 degrees.');
      setSubmitting(false);
      return;
    }

    if (!Number.isFinite(lngNum) || lngNum < -180.0 || lngNum > 180.0) {
      setMessage('Error: Longitude must be a finite number between -180 and 180 degrees.');
      setSubmitting(false);
      return;
    }

    if (!Number.isInteger(affectedNum) || affectedNum < 1 || !Number.isFinite(affectedNum)) {
      setMessage('Error: People affected must be a positive whole integer (minimum 1).');
      setSubmitting(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/incidents/citizen-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location,
          latitude: latNum,
          longitude: lngNum,
          disaster_type: disasterType,
          people_affected: affectedNum,
          severity,
          sos_type: sosType,
          media_url: mediaUrl,
          description,
        }),
      });

      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setMessage('🚨 SOS Report Verified by IncidentAgent! Auto-Dispatch Initiated.');
        setTimeout(() => {
          if (onSuccess) onSuccess();
          onClose();
        }, 1500);
      } else {
        setMessage(`Error: ${data.message || 'Failed to submit SOS report'}`);
      }
    } catch {
      setMessage('Error submitting SOS report to server');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="sos-backdrop" onClick={onClose}>
      <div className="sos-modal glass-card" onClick={e => e.stopPropagation()}>
        <div className="sos-header">
          <div className="sos-title">
            <span style={{ fontSize: 20 }}>📢</span> Citizen Emergency SOS Reporting
          </div>
          <button className="sos-close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="sos-form">
          {message && <div className="sos-alert">{message}</div>}

          <div className="sos-grid">
            <div className="sos-field">
              <label>Incident Sector Location</label>
              <input type="text" value={location} onChange={e => setLocation(e.target.value)} required />
            </div>

            <div className="sos-field">
              <label>Disaster Category</label>
              <select value={disasterType} onChange={e => setDisasterType(e.target.value)}>
                <option value="flood">🌊 Flood Inundation</option>
                <option value="building_collapse">🏗️ Building Collapse</option>
                <option value="road_accident">🚗 Road Damage & Accident</option>
                <option value="chemical_leak">☣️ Chemical Leak & HAZMAT</option>
                <option value="wildfire">🔥 Wildfire & Heavy Smoke</option>
                <option value="earthquake">🌋 Earthquake Damage</option>
                <option value="landslide">🏔️ Landslide Blockage</option>
              </select>
            </div>

            <div className="sos-field">
              <label>Latitude Coordinate</label>
              <input type="number" step="0.0001" value={latitude} onChange={e => setLatitude(e.target.value)} required />
            </div>

            <div className="sos-field">
              <label>Longitude Coordinate</label>
              <input type="number" step="0.0001" value={longitude} onChange={e => setLongitude(e.target.value)} required />
            </div>

            <div className="sos-field">
              <label>Trapped / Affected Citizens</label>
              <input type="number" min="1" value={peopleAffected} onChange={e => setPeopleAffected(e.target.value)} required />
            </div>

            <div className="sos-field">
              <label>Priority Severity</label>
              <select value={severity} onChange={e => setSeverity(e.target.value)}>
                <option value="high">🔴 CRITICAL HIGH</option>
                <option value="medium">🟡 MEDIUM</option>
                <option value="low">🟢 LOW</option>
              </select>
            </div>
          </div>

          <div className="sos-field" style={{ marginTop: 10 }}>
            <label>Photo / Video Attachment URL (Optional)</label>
            <input type="url" placeholder="https://images.unsplash.com/photo-1547683905-f686c993aae5" value={mediaUrl} onChange={e => setMediaUrl(e.target.value)} />
          </div>

          <div className="sos-field" style={{ marginTop: 10 }}>
            <label>Field Situation Report / SOS Description</label>
            <textarea rows="3" value={description} onChange={e => setDescription(e.target.value)} required />
          </div>

          <button type="submit" className="btn btn-primary sos-submit-btn" disabled={submitting}>
            {submitting ? 'Validating SOS Report...' : '🚨 TRANSMIT SOS ALERT & DISPATCH TEAMS'}
          </button>
        </form>
      </div>

      <style>{`
        .sos-backdrop {
          position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(7, 10, 18, 0.8); backdrop-filter: blur(10px);
          z-index: 10000; display: flex; align-items: center; justify-content: center;
          padding: 20px;
        }
        .sos-modal {
          width: 580px; max-width: 95vw; background: #0f172a; border: 1px solid rgba(255,255,255,0.12);
          border-radius: 14px; padding: 24px; box-shadow: 0 20px 50px rgba(0,0,0,0.7);
        }
        .sos-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
        .sos-title { font-size: 16px; font-weight: 800; color: #fff; font-family: 'Outfit', sans-serif; display: flex; align-items: center; gap: 8px; }
        .sos-close-btn { background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; cursor: pointer; }
        .sos-form { display: flex; flex-direction: column; }
        .sos-alert { background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #fca5a5; padding: 10px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; margin-bottom: 14px; }
        .sos-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .sos-field label { display: block; font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px; }
        .sos-field input, .sos-field select, .sos-field textarea {
          width: 100%; background: #0f172a; border: 1px solid #334155; color: #fff;
          padding: 8px 10px; border-radius: 6px; font-size: 12px; font-family: 'Inter', sans-serif;
        }
        .sos-submit-btn { margin-top: 18px; padding: 12px 0; font-size: 13px; font-weight: 800; background: #ef4444; }
        .sos-submit-btn:hover { background: #dc2626; }
      `}</style>
    </div>
  );
}
