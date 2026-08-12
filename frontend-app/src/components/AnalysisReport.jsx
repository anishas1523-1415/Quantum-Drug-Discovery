import { useEffect, useState } from "react";
import client, { extractErrorMessage } from "../api/client";
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

export default function AnalysisReport({ gene, cancerType }) {
  const [state, setState] = useState({ status: "loading" });

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
        <span className="recommend-source">{data.source}</span>
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
