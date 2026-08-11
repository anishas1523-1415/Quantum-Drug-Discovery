import { useAuth } from "../context/AuthContext";

function initials(name) {
  if (!name) return "DR";
  const parts = name.trim().split(/\s+/);
  return parts
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export default function Navbar() {
  const { user, logout } = useAuth();

  return (
    <header className="navbar glass-panel">
      <div className="navbar-brand">
        <span className="brand-mark" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="3.2" fill="currentColor" />
            <ellipse cx="12" cy="12" rx="10" ry="4" stroke="currentColor" strokeWidth="1.4" />
            <ellipse cx="12" cy="12" rx="10" ry="4" stroke="currentColor" strokeWidth="1.4" transform="rotate(60 12 12)" />
            <ellipse cx="12" cy="12" rx="10" ry="4" stroke="currentColor" strokeWidth="1.4" transform="rotate(120 12 12)" />
          </svg>
        </span>
        <div>
          <div className="brand-title">Quantum Drug Discovery</div>
          <div className="brand-subtitle">Precision Oncology Console</div>
        </div>
      </div>

      <div className="navbar-user">
        <div className="user-info">
          <div className="user-name">{user?.name || "Doctor"}</div>
          <div className="user-email">{user?.email}</div>
        </div>
        <div className="user-avatar">{initials(user?.name)}</div>
        <button className="btn btn-danger-ghost logout-btn" onClick={logout}>
          Log out
        </button>
      </div>
    </header>
  );
}
