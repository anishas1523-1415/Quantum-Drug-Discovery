import { useMemo, useState } from "react";
import client, { extractErrorMessage } from "../api/client";
import Navbar from "../components/Navbar";
import Dropzone from "../components/Dropzone";
import Pagination from "../components/Pagination";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import "../styles/Dashboard.css";

const PAGE_SIZE = 10;

export default function Dashboard() {
  const { user } = useAuth();
  const toast = useToast();

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [prediction, setPrediction] = useState([]);
  const [quantumResult, setQuantumResult] = useState([]);
  const [hasRun, setHasRun] = useState(false);
  const [page, setPage] = useState(1);

  const quantumById = useMemo(() => {
    const map = new Map();
    quantumResult.forEach((row) => map.set(String(row.PatientID), row.QuantumScore));
    return map;
  }, [quantumResult]);

  const stats = useMemo(() => {
    const total = prediction.length;
    const effective = prediction.filter((row) => row.Prediction === "Effective").length;
    const avgScore =
      quantumResult.length > 0
        ? quantumResult.reduce((sum, row) => sum + Number(row.QuantumScore || 0), 0) / quantumResult.length
        : 0;

    return { total, effective, notEffective: total - effective, avgScore };
  }, [prediction, quantumResult]);

  const pageCount = Math.max(1, Math.ceil(prediction.length / PAGE_SIZE));
  const pagedPrediction = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return prediction.slice(start, start + PAGE_SIZE);
  }, [prediction, page]);

  async function handleAnalyze() {
    if (!file) {
      toast.error("Choose a patient CSV file first");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);

    try {
      const response = await client.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setPrediction(response.data.prediction || []);
      setQuantumResult(response.data.quantum_result || []);
      setHasRun(true);
      setPage(1);
      toast.success(response.data.message || "Analysis complete");
    } catch (error) {
      toast.error(extractErrorMessage(error));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="orb" style={{ width: 420, height: 420, top: -160, left: -140, background: "#8b5cf6" }} />
      <div className="orb" style={{ width: 360, height: 360, top: 300, right: -160, background: "#22d3ee" }} />

      <div className="dashboard-shell">
        <Navbar />

        <div className="page-header">
          <h1>Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""}</h1>
          <p>Upload a patient dataset to run quantum feature analysis and AI drug response prediction.</p>
        </div>

        <section className="upload-section glass-panel">
          <h2>Patient Dataset Upload</h2>
          <p className="section-hint">CSV must include PatientID, Age, Gender, TumorSize and Stage columns.</p>

          <div className="upload-row">
            <Dropzone file={file} onFileSelected={setFile} disabled={uploading} />

            <div className="upload-actions">
              <button className="btn btn-primary" onClick={handleAnalyze} disabled={uploading}>
                {uploading && <span className="spinner" />}
                {uploading ? "Analyzing..." : "Run Analysis"}
              </button>
              {file && !uploading && (
                <button className="btn btn-ghost" onClick={() => setFile(null)}>
                  Clear file
                </button>
              )}
            </div>
          </div>
        </section>

        {hasRun && (
          <div className="stat-grid">
            <div className="stat-tile glass-panel">
              <span className="stat-label">Patients Analyzed</span>
              <span className="stat-value">{stats.total}</span>
            </div>
            <div className="stat-tile glass-panel">
              <span className="stat-label">Predicted Effective</span>
              <span className="stat-value accent">{stats.effective}</span>
            </div>
            <div className="stat-tile glass-panel">
              <span className="stat-label">Predicted Not Effective</span>
              <span className="stat-value">{stats.notEffective}</span>
            </div>
            <div className="stat-tile glass-panel">
              <span className="stat-label">Avg Quantum Score</span>
              <span className="stat-value">{stats.avgScore.toFixed(3)}</span>
            </div>
          </div>
        )}

        <section className="result-section glass-panel">
          <h2>Analysis Results</h2>

          {prediction.length === 0 ? (
            <EmptyState hasRun={hasRun} />
          ) : (
            <>
            <div className="table-scroll">
              <table className="table-glass">
                <thead>
                  <tr>
                    <th>Patient ID</th>
                    <th>Quantum Score</th>
                    <th>Drug Response Prediction</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedPrediction.map((row, index) => {
                    const score = quantumById.get(String(row.PatientID));
                    const scorePct = score != null ? Math.min(100, Math.max(0, score * 100)) : null;

                    return (
                      <tr key={index}>
                        <td>{row.PatientID}</td>
                        <td>
                          {score != null ? (
                            <div className="score-bar-wrap">
                              <span>{Number(score).toFixed(4)}</span>
                              <div className="score-bar-track">
                                <div className="score-bar-fill" style={{ width: `${scorePct}%` }} />
                              </div>
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          <span className={`badge ${row.Prediction === "Effective" ? "badge-success" : "badge-danger"}`}>
                            {row.Prediction}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageCount={pageCount} onChange={setPage} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function EmptyState({ hasRun }) {
  return (
    <div className="empty-state">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.4" />
        <path d="M7 9h10M7 13h10M7 17h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
      <h3>{hasRun ? "No results returned" : "No analysis yet"}</h3>
      <p>{hasRun ? "The dataset produced no predictions." : "Upload a patient CSV above and run the analysis to see results here."}</p>
    </div>
  );
}
