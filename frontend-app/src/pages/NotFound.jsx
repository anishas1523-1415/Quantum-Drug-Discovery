import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="app-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="glass-panel" style={{ padding: "48px 40px", textAlign: "center", maxWidth: 420 }}>
        <div style={{ fontSize: 48, fontWeight: 700, background: "var(--accent-gradient)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
          404
        </div>
        <h1 style={{ fontSize: 20, margin: "10px 0 8px", color: "var(--text-hi)" }}>Page not found</h1>
        <p style={{ color: "var(--text-mid)", fontSize: 14.5, margin: "0 0 24px" }}>
          The page you're looking for doesn't exist or has moved.
        </p>
        <Link to="/dashboard" className="btn btn-primary" style={{ textDecoration: "none", display: "inline-flex" }}>
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
