import React, { useEffect, useState } from 'react';

export default function CommandPalette({ isOpen, onClose, onSelectAction }) {
  const [query, setQuery] = useState('');

  const commands = [
    { id: 'start_sim', title: '🚀 Launch Automatic Simulation Pipeline', category: 'Actions', action: () => onSelectAction('start_sim') },
    { id: 'nav_dash', title: '📊 Navigate to Live EOC Dashboard', category: 'Navigation', action: () => onSelectAction('tab_dashboard') },
    { id: 'nav_map', title: '🗺️ Navigate to Operations GIS Map', category: 'Navigation', action: () => onSelectAction('tab_map') },
    { id: 'nav_sim', title: '⚙️ Navigate to Simulation Engine', category: 'Navigation', action: () => onSelectAction('tab_simulation') },
    { id: 'nav_health', title: '🩺 Open Multi-Agent Diagnostics (14+1 Agents)', category: 'Navigation', action: () => onSelectAction('tab_health') },
    { id: 'export_csv', title: '📥 Export Current Run Report (CSV)', category: 'Reports', action: () => onSelectAction('export_csv') },
    { id: 'export_pdf', title: '📄 Export Executive Summary (PDF)', category: 'Reports', action: () => onSelectAction('export_pdf') },
    { id: 'toggle_fleet', title: '🚑 Toggle Response Fleet Layer', category: 'GIS Map', action: () => onSelectAction('toggle_fleet') },
    { id: 'toggle_hospitals', title: '🏥 Toggle Hospitals & Shelters Layer', category: 'GIS Map', action: () => onSelectAction('toggle_facilities') },
  ];

  const filtered = commands.filter(c =>
    c.title.toLowerCase().includes(query.toLowerCase()) ||
    c.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose(); else onSelectAction('open_cmd');
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onSelectAction]);

  if (!isOpen) return null;

  return (
    <div className="cmd-backdrop" onClick={onClose}>
      <div className="cmd-modal" onClick={e => e.stopPropagation()}>
        <div className="cmd-header">
          <span style={{ fontSize: 16 }}>🔍</span>
          <input
            type="text"
            placeholder="Type a command or search... (Esc to close)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
          <kbd className="cmd-kbd">ESC</kbd>
        </div>

        <div className="cmd-list">
          {filtered.length === 0 ? (
            <div className="cmd-empty">No matching commands found</div>
          ) : (
            filtered.map((cmd) => (
              <div
                key={cmd.id}
                className="cmd-item"
                onClick={() => {
                  cmd.action();
                  onClose();
                }}
              >
                <div className="cmd-item-title">{cmd.title}</div>
                <div className="cmd-item-cat">{cmd.category}</div>
              </div>
            ))
          )}
        </div>
      </div>

      <style>{`
        .cmd-backdrop {
          position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(7, 10, 18, 0.75);
          backdrop-filter: blur(8px);
          z-index: 10000;
          display: flex; align-items: flex-start; justify-content: center;
          padding-top: 100px;
        }
        .cmd-modal {
          width: 580px; max-width: 90vw;
          background: #0f172a; border: 1px solid rgba(255,255,255,0.12);
          border-radius: 12px; box-shadow: 0 20px 50px rgba(0,0,0,0.7);
          overflow: hidden; animation: cmdPop 0.15s ease-out;
        }
        @keyframes cmdPop {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
        .cmd-header {
          display: flex; align-items: center; gap: 10px;
          padding: 14px 18px; border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .cmd-header input {
          flex: 1; background: transparent; border: none; outline: none;
          color: #fff; font-size: 14px; font-family: 'Inter', sans-serif;
        }
        .cmd-kbd {
          background: #1e293b; color: #94a3b8; font-size: 10px; font-weight: 700;
          padding: 2px 6px; border-radius: 4px; border: 1px solid #334155;
        }
        .cmd-list { max-height: 320px; overflow-y: auto; padding: 8px; }
        .cmd-empty { padding: 24px; text-align: center; color: #64748b; font-size: 13px; }
        .cmd-item {
          display: flex; justify-content: space-between; align-items: center;
          padding: 10px 14px; border-radius: 8px; cursor: pointer;
          transition: background 0.15s ease;
        }
        .cmd-item:hover { background: #1e293b; }
        .cmd-item-title { color: #f8fafc; font-size: 13px; font-weight: 500; }
        .cmd-item-cat { font-size: 10px; font-weight: 700; color: #6366f1; text-transform: uppercase; background: rgba(99,102,241,0.12); padding: 2px 8px; border-radius: 4px; }
      `}</style>
    </div>
  );
}
