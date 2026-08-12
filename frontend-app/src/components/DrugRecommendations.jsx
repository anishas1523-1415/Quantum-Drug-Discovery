import { useEffect, useState } from "react";
import client, { extractErrorMessage } from "../api/client";

// Verified against live Open Targets responses: approved drugs come back
// as "APPROVAL" (not "APPROVED"), and combined-phase trials show up as
// e.g. "PHASE_2_3".
const STAGE_LABELS = {
  APPROVAL: "Approved",
  APPROVED: "Approved",
  PHASE_4: "Approved",
  PHASE_3: "Phase 3",
  PHASE_2_3: "Phase 2/3",
  PHASE_2: "Phase 2",
  PHASE_1_2: "Phase 1/2",
  PHASE_1: "Phase 1",
  PHASE_0: "Early phase",
  PRECLINICAL: "Preclinical",
};

const APPROVED_STAGES = new Set(["APPROVAL", "APPROVED", "PHASE_4"]);
const MID_LATE_STAGES = new Set(["PHASE_3", "PHASE_2_3", "PHASE_2"]);

function stageLabel(stage) {
  return STAGE_LABELS[(stage || "").toUpperCase()] || stage || "Unknown stage";
}

function stageBadgeClass(stage) {
  const upper = (stage || "").toUpperCase();
  if (APPROVED_STAGES.has(upper)) return "badge-success";
  if (MID_LATE_STAGES.has(upper)) return "badge-warning";
  return "badge-neutral";
}

export default function DrugRecommendations({ gene, cancerType }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchRecommendations() {
      setLoading(true);
      setError("");

      try {
        const response = await client.get("/recommend", {
          params: { gene, cancer_type: cancerType },
        });
        if (!cancelled) setResult(response.data);
      } catch (err) {
        if (!cancelled) setError(extractErrorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchRecommendations();

    return () => {
      cancelled = true;
    };
  }, [gene, cancerType]);

  if (loading) {
    return (
      <div className="recommend-panel">
        <span className="spinner" />
        <span>Querying Open Targets for {gene} + {cancerType}...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="recommend-panel recommend-error">
        Couldn&apos;t fetch drug evidence: {error}
      </div>
    );
  }

  const matches = result?.matched_candidates || [];

  return (
    <div className="recommend-panel">
      <div className="recommend-header">
        <span>
          Live evidence for <strong>{result.target_name || gene}</strong> in{" "}
          <strong>{cancerType}</strong>
        </span>
        <span className="recommend-source">{result.source}</span>
      </div>

      {matches.length === 0 ? (
        <div className="recommend-empty">
          No drugs directly targeting {result.target_name || gene} have documented evidence
          in {cancerType} in Open Targets right now
          {result.total_direct_candidates > 0
            ? ` (${result.total_direct_candidates} candidates exist for other indications).`
            : "."}{" "}
          This is common for genes like tumor-suppressors (e.g. BRCA1/BRCA2) that aren't
          direct drug targets themselves — the relevant drugs (e.g. PARP inhibitors) work
          through a different target via synthetic lethality, not by binding this gene.
        </div>
      ) : (
        <>
        {result.truncated && (
          <div className="recommend-truncated-note">
            Showing the top {matches.length} of {result.total_matches} matches with documented
            evidence in {cancerType}, ranked by clinical stage specific to this cancer type.
          </div>
        )}
        <div className="drug-card-grid">
          {matches.map((drug, index) => (
            <div className="drug-card" key={index}>
              <div className="drug-card-top">
                <span className="drug-name">{drug.drug_name}</span>
                <span className={`badge ${stageBadgeClass(drug.stage)}`}>{stageLabel(drug.stage)}</span>
              </div>
              <div className="drug-type">{drug.drug_type}</div>
              {drug.description && <div className="drug-description">{drug.description}</div>}
              <div className="drug-evidence">Evidence: {drug.matched_disease}</div>
            </div>
          ))}
        </div>
        </>
      )}
    </div>
  );
}
