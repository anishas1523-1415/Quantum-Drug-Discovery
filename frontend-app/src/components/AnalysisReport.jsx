import { useEffect, useState } from "react";
import client, { extractErrorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import { stageBadgeClass, stageLabel } from "../utils/drugStage";

const COMPONENT_LABELS = {
  clinical_evidence: "Clinical Evidence",
  dti_potency: "Target Potency",
  drug_likeness: "Drug-Likeness (QED)",
  admet_safety: "ADMET Safety",
};

function riskBadgeClass(band) {
  if (band === "Low") return "badge-success";
  if (band === "Moderate") return "badge-warning";
  if (band === "Higher") return "badge-danger";
  return "badge-neutral";
}

function ComponentBar({ label, value }) {
  return (
    <div className="component-bar-row">
      <span className="component-bar-label">{label}</span>
      <div className="component-bar-track">
        <div className="component-bar-fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="component-bar-value">{Math.round(value * 100)}%</span>
    </div>
  );
}

async function extractBlobErrorMessage(error) {
  // With responseType: "blob", axios parses even an error's JSON body as
  // an opaque Blob rather than a plain object, so the normal
  // extractErrorMessage(error.response.data.message) sees nothing there
  // and falls back to a generic/misleading message. Re-read the blob as
  // text and parse it as JSON to recover the real server message.
  const blob = error.response?.data;

  if (blob instanceof Blob) {
    try {
      const text = await blob.text();
      const parsed = JSON.parse(text);
      if (parsed?.message) return parsed.message;
    } catch {
      // fall through to the generic extractor below
    }
  }

  return extractErrorMessage(error);
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export default function AnalysisReport({ gene, cancerType }) {
  const toast = useToast();
  const [state, setState] = useState({ status: "loading" });
  const [exportingPdf, setExportingPdf] = useState(false);

  async function exportPdf() {
    setExportingPdf(true);
    try {
      const response = await client.get("/analyze/report", {
        params: { gene, cancer_type: cancerType },
        responseType: "blob",
      });
      downloadBlob(response.data, `qdd-report-${gene}-${cancerType}.pdf`.toLowerCase());
    } catch (error) {
      toast.error(await extractBlobErrorMessage(error));
    } finally {
      setExportingPdf(false);
    }
  }

  function exportJson() {
    if (state.status !== "done") return;
    const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: "application/json" });
    downloadBlob(blob, `qdd-report-${gene}-${cancerType}.json`.toLowerCase());
  }

  useEffect(() => {
    let cancelled = false;

    client
      .get("/analyze", { params: { gene, cancer_type: cancerType } })
      .then((response) => {
        if (!cancelled) setState({ status: "done", data: response.data });
      })
      .catch((error) => {
        if (!cancelled) setState({ status: "error", message: extractErrorMessage(error) });
      });

    return () => {
      cancelled = true;
    };
  }, [gene, cancerType]);

  if (state.status === "loading") {
    return (
      <div className="analysis-report analysis-loading">
        <span className="spinner spinner-lg" />
        <div>
          <div className="analysis-loading-title">Running full multi-factor analysis...</div>
          <div className="analysis-loading-sub">
            Drug-target interaction, molecular properties, ADMET screening, and
            quantum-optimized ranking — this can take up to a minute on the first
            lookup for this gene (cached instantly after that).
          </div>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return <div className="analysis-report recommend-error">Analysis failed: {state.message}</div>;
  }

  const { data } = state;

  if (!data.candidates || data.candidates.length === 0) {
    return (
      <div className="analysis-report">
        <div className="recommend-empty">{data.message}</div>
        <div className="analysis-export-buttons">
          <button type="button" className="btn btn-ghost export-btn" onClick={exportJson}>
            Export JSON
          </button>
          <button type="button" className="btn btn-ghost export-btn" onClick={exportPdf} disabled={exportingPdf}>
            {exportingPdf && <span className="spinner" />}
            {exportingPdf ? "Generating..." : "Export PDF"}
          </button>
        </div>
      </div>
    );
  }

  const panelIds = new Set((data.diverse_panel || []).map((c) => c.chembl_id));

  return (
    <div className="analysis-report">
      <div className="analysis-header">
        <span>
          Full evidence-based analysis for <strong>{data.target_name || data.gene}</strong> in{" "}
          <strong>{data.cancer_type}</strong>
        </span>
        <div className="analysis-header-right">
          <span className="recommend-source">{data.source}</span>
          <div className="analysis-export-buttons">
            <button type="button" className="btn btn-ghost export-btn" onClick={exportJson}>
              Export JSON
            </button>
            <button type="button" className="btn btn-ghost export-btn" onClick={exportPdf} disabled={exportingPdf}>
              {exportingPdf && <span className="spinner" />}
              {exportingPdf ? "Generating..." : "Export PDF"}
            </button>
          </div>
        </div>
      </div>

      {data.quantum_optimization && (
        <div className="quantum-panel-note">
          <strong>Quantum-optimized diverse panel</strong> ({data.quantum_optimization.method}) is
          highlighted below.
          {!data.quantum_optimization.qaoa_found_optimum &&
            " QAOA's own sample landed near-optimal but not exact — classical verification (cheap at this scale) confirmed and used the true optimum for the final panel."}
        </div>
      )}

      <div className="candidate-report-grid">
        {data.candidates.map((c, index) => {
          const isPanel = panelIds.has(c.chembl_id);
          return (
            <div key={index} className={`candidate-report-card ${isPanel ? "candidate-report-panel" : ""}`}>
              <div className="candidate-report-top">
                <div className="candidate-report-name-wrap">
                  {isPanel && <span className="best-pill">QUANTUM PANEL</span>}
                  <span className="candidate-report-name">{c.drug_name}</span>
                </div>
                <div className="candidate-report-score">
                  {c.composite_score}
                  <span className="score-max">/100</span>
                </div>
              </div>

              <div className="candidate-report-badges">
                <span className={`badge ${riskBadgeClass(c.admet_risk_band)}`}>Risk: {c.admet_risk_band}</span>
                <span className="badge badge-neutral">Confidence: {Math.round(c.confidence * 100)}%</span>
                <span className="badge badge-neutral">{c.drug_type}</span>
                {c.evidence?.clinical_evidence?.stage && (
                  <span className={`badge ${stageBadgeClass(c.evidence.clinical_evidence.stage)}`}>
                    {stageLabel(c.evidence.clinical_evidence.stage)}
                  </span>
                )}
              </div>

              <div className="component-bars">
                {Object.entries(c.component_scores).map(([key, value]) => (
                  <ComponentBar key={key} label={COMPONENT_LABELS[key] || key} value={value} />
                ))}
              </div>

              <p className="candidate-report-explanation">{c.explanation}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
