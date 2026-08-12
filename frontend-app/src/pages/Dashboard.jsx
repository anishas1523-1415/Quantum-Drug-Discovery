import { Fragment, useMemo, useState } from "react";
import client, { extractErrorMessage } from "../api/client";
import Navbar from "../components/Navbar";
import Dropzone from "../components/Dropzone";
import AnalysisReport from "../components/AnalysisReport";
import Pagination from "../components/Pagination";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { stageBadgeClass, stageLabel } from "../utils/drugStage";
import "../styles/Dashboard.css";

const PAGE_SIZE = 10;

function recKey(gene, cancerType) {
  return `${(gene || "").trim().toUpperCase()}::${(cancerType || "").trim().toLowerCase()}`;
}

export default function Dashboard() {
  const { user } = useAuth();
  const toast = useToast();

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [prediction, setPrediction] = useState([]);
  const [quantumResult, setQuantumResult] = useState([]);
  const [hasRun, setHasRun] = useState(false);
  const [page, setPage] = useState(1);
  const [expandedPatientId, setExpandedPatientId] = useState(null);
  const [recommendCache, setRecommendCache] = useState({});

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

  async function fetchBestMatches(rows) {
    const pairs = new Map();

    rows.forEach((row) => {
      if (row.GeneticMutation && row.CancerType) {
        const key = recKey(row.GeneticMutation, row.CancerType);
        if (!pairs.has(key)) {
          pairs.set(key, { gene: row.GeneticMutation, cancerType: row.CancerType });
        }
      }
    });

    if (pairs.size === 0) return;

    setRecommendCache((prev) => {
      const next = { ...prev };
      pairs.forEach((_, key) => {
        next[key] = { status: "loading" };
      });
      return next;
    });

    await Promise.all(
      Array.from(pairs.entries()).map(async ([key, { gene, cancerType }]) => {
        try {
          const response = await client.get("/recommend", {
            params: { gene, cancer_type: cancerType },
          });
          setRecommendCache((prev) => ({ ...prev, [key]: { status: "done", data: response.data } }));
        } catch (error) {
          setRecommendCache((prev) => ({
            ...prev,
            [key]: { status: "error", message: extractErrorMessage(error) },
          }));
        }
      })
    );
  }

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

      const predictionRows = response.data.prediction || [];

      setPrediction(predictionRows);
      setQuantumResult(response.data.quantum_result || []);
      setHasRun(true);
      setPage(1);
      setExpandedPatientId(null);
      setRecommendCache({});
      toast.success(response.data.message || "Analysis complete");

      fetchBestMatches(predictionRows);
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
                    <th>Cancer Type / Gene</th>
                    <th>Quantum Score</th>
                    <th>Drug Response Prediction</th>
                    <th>Best Drug Match</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedPrediction.map((row, index) => {
                    const score = quantumById.get(String(row.PatientID));
                    const scorePct = score != null ? Math.min(100, Math.max(0, score * 100)) : null;
                    const gene = row.GeneticMutation;
                    const cancerType = row.CancerType;
                    const canRecommend = Boolean(gene && cancerType);
                    const isExpanded = expandedPatientId === row.PatientID;
                    const rec = canRecommend ? recommendCache[recKey(gene, cancerType)] : null;
                    const topMatch = rec?.data?.matched_candidates?.[0];
                    const extraCount = rec?.data ? rec.data.total_matches - (topMatch ? 1 : 0) : 0;

                    return (
                      <Fragment key={row.PatientID || index}>
                        <tr>
                          <td>{row.PatientID}</td>
                          <td>
                            <div className="gene-cell">
                              <span>{cancerType || "—"}</span>
                              <span className="gene-tag">{gene || "no mutation recorded"}</span>
                            </div>
                          </td>
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
                          <td>
                            {!canRecommend ? (
                              <span className="best-match-muted">No mutation recorded</span>
                            ) : !rec || rec.status === "loading" ? (
                              <span className="best-match-loading">
                                <span className="spinner" /> Checking...
                              </span>
                            ) : rec.status === "error" ? (
                              <span className="best-match-muted" title={rec.message}>
                                Lookup failed
                              </span>
                            ) : !topMatch ? (
                              <div className="best-match-cell">
                                <span className="best-match-muted">No direct match</span>
                                <button
                                  type="button"
                                  className="best-match-link"
                                  onClick={() => setExpandedPatientId(isExpanded ? null : row.PatientID)}
                                >
                                  {isExpanded ? "Hide" : "Why? / Full report"}
                                </button>
                              </div>
                            ) : (
                              <div className="best-match-cell">
                                <div className="best-match-drug">
                                  <span className="best-match-name">{topMatch.drug_name}</span>
                                  <span className={`badge ${stageBadgeClass(topMatch.stage)}`}>
                                    {stageLabel(topMatch.stage)}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  className="best-match-link"
                                  onClick={() => setExpandedPatientId(isExpanded ? null : row.PatientID)}
                                >
                                  {isExpanded ? "Hide" : extraCount > 0 ? `+${extraCount} more · Full report` : "Full report"}
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="recommend-row">
                            <td colSpan={5}>
                              <AnalysisReport key={`${gene}::${cancerType}`} gene={gene} cancerType={cancerType} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
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
