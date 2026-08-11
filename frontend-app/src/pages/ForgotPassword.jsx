import { useState } from "react";
import { Link } from "react-router-dom";
import AuthBrandPanel from "../components/AuthBrandPanel";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import "../styles/Auth.css";

export default function ForgotPassword() {
  const { forgotPassword } = useAuth();
  const toast = useToast();

  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();

    if (!email.trim()) {
      toast.error("Enter your email address");
      return;
    }

    setSubmitting(true);
    const result = await forgotPassword(email.trim());
    setSubmitting(false);

    if (result.ok) {
      setSent(true);
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
            title="Forgot your password?"
            description="Enter the email on your account and we'll send you a link to set a new password."
          />

          <div className="auth-form-side">
            <h1>Reset password</h1>
            <p className="auth-tagline">
              {sent
                ? "Check your inbox for the reset link."
                : "We'll email you a link that's valid for 30 minutes."}
            </p>

            {sent ? (
              <div className="demo-hint">
                If an account exists for <strong>{email.trim()}</strong>, a reset link is on its way.
              </div>
            ) : (
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
                </div>

                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting && <span className="spinner" />}
                  {submitting ? "Sending..." : "Send reset link"}
                </button>
              </form>
            )}

            <div className="auth-footnote">
              <Link className="link" to="/login">Back to sign in</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
