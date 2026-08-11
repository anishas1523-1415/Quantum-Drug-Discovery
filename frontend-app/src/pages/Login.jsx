import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthBrandPanel from "../components/AuthBrandPanel";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import "../styles/Auth.css";

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  function validate() {
    const next = {};

    if (!email.trim()) next.email = "Email is required";
    if (!password) next.password = "Password is required";

    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (!validate()) return;

    setSubmitting(true);
    const result = await login(email.trim(), password);
    setSubmitting(false);

    if (result.ok) {
      toast.success("Welcome back!");
      navigate("/dashboard");
    } else {
      toast.error(result.message);
    }
  }

  return (
    <div className="app-shell">
      <div className="orb" style={{ width: 380, height: 380, top: -120, left: -120, background: "#8b5cf6" }} />
      <div className="orb" style={{ width: 320, height: 320, bottom: -100, right: -100, background: "#22d3ee" }} />

      <div className="auth-shell">
        <div className="auth-frame glass-panel">
          <AuthBrandPanel
            title="Precision oncology, quantum-accelerated"
            description="Sign in to upload patient datasets, run quantum feature analysis, and generate AI-backed drug response predictions."
          />

          <div className="auth-form-side">
            <h1>Doctor Login</h1>
            <p className="auth-tagline">Enter your credentials to access the analysis console.</p>

            <form onSubmit={handleSubmit} noValidate>
              <div className="neu-field">
                <label htmlFor="email">Email address</label>
                <div className="neu-input-wrap">
                  <span className="field-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <path d="M4 6h16v12H4z" stroke="currentColor" strokeWidth="1.5" />
                      <path d="M4 7l8 6 8-6" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  </span>
                  <input
                    id="email"
                    type="email"
                    placeholder="doctor@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                </div>
                {errors.email && <div className="field-error">{errors.email}</div>}
              </div>

              <div className="neu-field">
                <label htmlFor="password">Password</label>
                <div className="neu-input-wrap">
                  <span className="field-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <rect x="5" y="10" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5" />
                      <path d="M8 10V7a4 4 0 118 0v3" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  </span>
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="field-action"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
                {errors.password && <div className="field-error">{errors.password}</div>}
                <div className="forgot-link-row">
                  <Link className="link" to="/forgot-password">Forgot password?</Link>
                </div>
              </div>

              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting && <span className="spinner" />}
                {submitting ? "Signing in..." : "Sign in"}
              </button>
            </form>

            <div className="demo-hint">
              <strong>Demo account:</strong> doctor@gmail.com / password123
            </div>

            <div className="auth-footnote">
              Don&apos;t have an account? <Link className="link" to="/register">Create one</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
