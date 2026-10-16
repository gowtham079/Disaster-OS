import React from 'react';

export default function NotificationCenter({ isOpen, onClose, notifications = [], onClear }) {
  return (
    <aside className={`notif-drawer ${isOpen ? 'open' : ''}`}>
      <div className="notif-header">
        <div className="notif-title">
          <span>🔔 Inter-Agent Notification Feed</span>
          <span className="notif-count">{notifications.length}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {notifications.length > 0 && (
            <button className="notif-clear-btn" onClick={onClear}>Clear</button>
          )}
          <button className="notif-close-btn" onClick={onClose}>✕</button>
        </div>
      </div>

      <div className="notif-body">
        {notifications.length === 0 ? (
          <div className="notif-empty">
            <span>📡</span>
            <p>No active agent alerts</p>
            <small>Live WebSocket broadcasts will appear here</small>
          </div>
        ) : (
          notifications.map((item) => (
            <div key={item.id} className={`notif-card ${item.type || 'info'}`}>
              <div className="notif-card-head">
                <span className="notif-card-time">{item.time}</span>
                <span className="notif-card-tag">{item.type || 'SYSTEM'}</span>
              </div>
              <div className="notif-card-text">{item.text}</div>
            </div>
          ))
        )}
      </div>

      <style>{`
        .notif-drawer {
          position: fixed; top: 0; right: -360px; width: 340px; height: 100vh;
          background: #0f172a; border-left: 1px solid rgba(255, 255, 255, 0.1);
          z-index: 9999; display: flex; flex-direction: column;
          transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
        }
        .notif-drawer.open { right: 0; }
        .notif-header {
          padding: 16px; border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          display: flex; justify-content: space-between; align-items: center;
        }
        .notif-title { font-weight: 700; font-size: 13px; color: #fff; display: flex; align-items: center; gap: 8px; }
        .notif-count { background: #6366f1; color: #fff; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 99px; }
        .notif-close-btn, .notif-clear-btn { background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 6px; padding: 4px 8px; font-size: 11px; cursor: pointer; }
        .notif-close-btn:hover { color: #fff; background: #334155; }
        .notif-body { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
        .notif-empty { text-align: center; color: #64748b; padding: 40px 16px; }
        .notif-empty span { font-size: 28px; display: block; margin-bottom: 8px; }
        .notif-card { background: #151c2c; border: 1px solid #1e293b; border-left: 3px solid #6366f1; border-radius: 8px; padding: 10px; font-size: 11px; }
        .notif-card.warning { border-left-color: #f59e0b; }
        .notif-card.error { border-left-color: #ef4444; }
        .notif-card-head { display: flex; justify-content: space-between; margin-bottom: 4px; }
        .notif-card-time { color: #64748b; font-size: 10px; font-family: monospace; }
        .notif-card-tag { font-size: 9px; font-weight: 700; color: #818cf8; text-transform: uppercase; }
        .notif-card-text { color: #f8fafc; line-height: 1.4; }
      `}</style>
    </aside>
  );
}
