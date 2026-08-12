import { useEffect, useState } from "react";
import client, { extractErrorMessage } from "../api/client";
import Navbar from "../components/Navbar";
import { useToast } from "../context/ToastContext";
import "../styles/Dashboard.css";
import "../styles/AdminAuditLog.css";

const PAGE_SIZE = 25;

export default function AdminAuditLog() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  // `page` on the result tells us which page this result belongs to, so
  // "loading" is derived (result.page !== page) rather than a separate
  // piece of state that has to be reset synchronously inside the effect.
  const [result, setResult] = useState({ page: null, status: "idle", data: null });

  useEffect(() => {
    let cancelled = false;

    client
      .get("/admin/audit-logs", { params: { page, page_size: PAGE_SIZE } })
      .then((response) => {
        if (!cancelled) setResult({ page, status: "done", data: response.data });
      })
      .catch((error) => {
        if (!cancelled) {
          setResult({ page, status: "error", data: null });
          toast.error(extractErrorMessage(error));
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const isLoading = result.page !== page;
  const status = isLoading ? "loading" : result.status;
  const totalPages = result.data ? Math.max(1, Math.ceil(result.data.total / PAGE_SIZE)) : 1;

  return (
    <div className="app-shell">
      <div className="orb" style={{ width: 420, height: 420, top: -160, left: -140, background: "#8b5cf6" }} />
      <div className="orb" style={{ width: 360, height: 360, top: 300, right: -160, background: "#22d3ee" }} />

      <div className="dashboard-shell">
        <Navbar />

        <div className="page-header">
          <h1>Audit Log</h1>
          <p>
            Every upload, recommendation lookup, and analysis run recorded for traceability —
            admin-only. No patient data is stored here, only that an action happened, when, and
            by whom.
          </p>
        </div>

        <section className="result-section glass-panel">
          {status === "loading" && (
            <div className="audit-loading">
              <span className="spinner spinner-lg" />
            </div>
          )}

          {status === "error" && (
            <div className="empty-state">
              <h3>Couldn&apos;t load the audit log</h3>
              <p>Check the toast notification for details, or try again.</p>
            </div>
          )}

          {status === "done" && result.data.entries.length === 0 && (
            <div className="empty-state">
              <h3>No audit entries yet</h3>
              <p>Actions will appear here as doctors and researchers use the platform.</p>
            </div>
          )}

          {status === "done" && result.data.entries.length > 0 && (
            <>
              <div className="table-scroll">
                <table className="table-glass">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>User</th>
                      <th>Action</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.data.entries.map((entry) => (
                      <tr key={entry.id}>
                        <td className="audit-timestamp">{new Date(entry.created_at).toLocaleString()}</td>
                        <td>{entry.user ? `${entry.user.name} (${entry.user.email})` : "—"}</td>
                        <td>
                          <span className={`badge ${entry.action.includes("failed") ? "badge-danger" : "badge-neutral"}`}>
                            {entry.action}
                          </span>
                        </td>
                        <td className="audit-detail">{entry.detail || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="audit-pagination">
                <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </button>
                <span>
                  Page {page} of {totalPages} &middot; {result.data.total} total entries
                </span>
                <button className="btn btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  Next
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
