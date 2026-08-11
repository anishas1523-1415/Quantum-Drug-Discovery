import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthBrandPanel from "../components/AuthBrandPanel";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import "../styles/Auth.css";

export default function ResetPassword() {
  const { resetPassword } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  function validate() {
    const next = {};

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

    if (!token) {
      toast.error("This reset link is missing its token");
      return;
    }

    if (!validate()) return;

    setSubmitting(true);
    const result = await resetPassword(token, password);
    setSubmitting(false);

    if (result.ok) {
      toast.success("Password updated — please sign in");
      navigate("/login");
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
            title="Set a new password"
            description="Choose a strong password you haven't used before on this account."
          />

          <div className="auth-form-side">
            <h1>New password</h1>
            <p className="auth-tagline">
              {token ? "Enter and confirm your new password below." : "This link is missing a reset token."}
            </p>

            <form onSubmit={handleSubmit} noValidate>
              <div className="neu-field">
                <label htmlFor="password">New password</label>
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
                <label htmlFor="confirmPassword">Confirm new password</label>
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

              <button type="submit" className="btn btn-primary" disabled={submitting || !token}>
                {submitting && <span className="spinner" />}
                {submitting ? "Updating..." : "Update password"}
              </button>
            </form>

            <div className="auth-footnote">
              <Link className="link" to="/login">Back to sign in</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
