export default function AuthBrandPanel({ title, description }) {
  return (
    <div className="auth-brand">
      <div className="auth-brand-top">
        <span className="brand-mark">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="3.2" fill="currentColor" />
            <ellipse cx="12" cy="12" rx="10" ry="4" stroke="currentColor" strokeWidth="1.6" />
            <ellipse cx="12" cy="12" rx="10" ry="4" stroke="currentColor" strokeWidth="1.6" transform="rotate(60 12 12)" />
            <ellipse cx="12" cy="12" rx="10" ry="4" stroke="currentColor" strokeWidth="1.6" transform="rotate(120 12 12)" />
          </svg>
        </span>
        Quantum Drug Discovery
      </div>

      <div className="orbit-scene" aria-hidden="true">
        <svg viewBox="0 0 200 200">
          <defs>
            <linearGradient id="orbitGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#22d3ee" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
          </defs>

          <circle cx="100" cy="100" r="10" fill="url(#orbitGrad)" />

          <g className="orbit-ring">
            <ellipse cx="100" cy="100" rx="90" ry="34" fill="none" stroke="rgba(255,255,255,0.28)" strokeWidth="1.2" />
            <circle cx="190" cy="100" r="5" fill="#22d3ee" />
          </g>

          <g className="orbit-ring reverse" transform="rotate(60 100 100)">
            <ellipse cx="100" cy="100" rx="90" ry="34" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.2" />
            <circle cx="10" cy="100" r="4.5" fill="#8b5cf6" />
          </g>

          <g className="orbit-ring slow" transform="rotate(120 100 100)">
            <ellipse cx="100" cy="100" rx="90" ry="34" fill="none" stroke="rgba(255,255,255,0.16)" strokeWidth="1.2" />
            <circle cx="100" cy="66" r="4" fill="#eef1fb" />
          </g>
        </svg>
      </div>

      <div className="auth-brand-copy">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
  );
}
