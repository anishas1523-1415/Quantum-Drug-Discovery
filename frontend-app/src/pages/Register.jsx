import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthBrandPanel from "../components/AuthBrandPanel";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import "../styles/Auth.css";

export default function Register() {
  const { register } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState("doctor");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  function validate() {
    const next = {};

    if (!name.trim()) next.name = "Name is required";

    if (!email.trim()) {
      next.email = "Email is required";
    } else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      next.email = "Enter a valid email address";
    }

    if (!password) {
      next.password = "Password is required";
    } else if (password.length < 6) {
      next.password = "Use at least 6 characters";
    }

    if (confirmPassword !== password) {
      next.confirmPassword = "Passwords do not match";
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (!validate()) return;

    setSubmitting(true);
    const result = await register(name.trim(), email.trim(), password, role);
    setSubmitting(false);

    if (result.ok) {
      toast.success("Account created — welcome aboard!");
      navigate("/dashboard");
    } else {
      toast.error(result.message);
    }
  }

  return (
    <div className="app-shell">
      <div className="orb" style={{ width: 380, height: 380, top: -120, right: -120, background: "#22d3ee" }} />
      <div className="orb" style={{ width: 320, height: 320, bottom: -100, left: -100, background: "#8b5cf6" }} />

      <div className="auth-shell">
        <div className="auth-frame glass-panel">
          <AuthBrandPanel
            title="Join the analysis console"
            description="Create a doctor account to start uploading patient datasets and generating quantum-enhanced drug response insights."
          />

          <div className="auth-form-side">
            <h1>Create account</h1>
            <p className="auth-tagline">It only takes a minute to get started.</p>

            <form onSubmit={handleSubmit} noValidate>
              <div className="neu-field">
                <label htmlFor="name">Full name</label>
                <div className="neu-input-wrap">
                  <span className="field-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="8" r="3.4" stroke="currentColor" strokeWidth="1.5" />
                      <path d="M5 20c1.2-3.6 4-5.5 7-5.5s5.8 1.9 7 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                    </svg>
                  </span>
                  <input
                    id="name"
                    type="text"
                    placeholder="Dr. Jane Smith"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    autoComplete="name"
                  />
                </div>
                {errors.name && <div className="field-error">{errors.name}</div>}
              </div>

              <div className="neu-field">
                <label htmlFor="role">Role</label>
                <div className="role-picker">
                  <button
                    type="button"
                    className={`role-option ${role === "doctor" ? "role-option-active" : ""}`}
                    onClick={() => setRole("doctor")}
                  >
                    Doctor
                  </button>
                  <button
                    type="button"
                    className={`role-option ${role === "researcher" ? "role-option-active" : ""}`}
                    onClick={() => setRole("researcher")}
                  >
                    Researcher
                  </button>
                </div>
              </div>

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
                    placeholder="At least 6 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
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
              </div>

              <div className="neu-field">
                <label htmlFor="confirmPassword">Confirm password</label>
                <div className="neu-input-wrap">
                  <span className="field-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                      <path d="M5 12.5l4.5 4.5L19 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                  <input
                    id="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    placeholder="Re-enter password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
                {errors.confirmPassword && <div className="field-error">{errors.confirmPassword}</div>}
              </div>

              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting && <span className="spinner" />}
                {submitting ? "Creating account..." : "Create account"}
              </button>
            </form>

            <div className="auth-footnote">
              Already have an account? <Link className="link" to="/login">Sign in</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
