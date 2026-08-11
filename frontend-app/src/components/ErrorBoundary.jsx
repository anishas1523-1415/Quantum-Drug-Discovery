import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled UI error:", error, info);
  }

  handleReload = () => {
    this.setState({ hasError: false });
    window.location.assign("/dashboard");
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="app-shell" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="glass-panel" style={{ padding: "48px 40px", textAlign: "center", maxWidth: 440 }}>
          <h1 style={{ fontSize: 20, margin: "0 0 8px", color: "var(--text-hi)" }}>Something went wrong</h1>
          <p style={{ color: "var(--text-mid)", fontSize: 14.5, margin: "0 0 24px" }}>
            An unexpected error occurred. You can try reloading the page.
          </p>
          <button className="btn btn-primary" onClick={this.handleReload}>
            Reload
          </button>
        </div>
      </div>
    );
  }
}
