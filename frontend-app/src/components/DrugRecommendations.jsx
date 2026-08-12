import { stageBadgeClass, stageLabel } from "../utils/drugStage";

export default function DrugRecommendations({ gene, cancerType, loading, error, result }) {
  if (error) {
    return (
      <div className="recommend-panel recommend-error">
        Couldn&apos;t fetch drug evidence: {error}
      </div>
    );
  }

  if (loading || !result) {
    return (
      <div className="recommend-panel">
        <span className="spinner" />
        <span>Querying Open Targets for {gene} + {cancerType}...</span>
      </div>
    );
  }

  const matches = result.matched_candidates || [];

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
            <div className={`drug-card ${index === 0 ? "drug-card-best" : ""}`} key={index}>
              <div className="drug-card-top">
                <span className="drug-name">
                  {index === 0 && <span className="best-pill">BEST MATCH</span>}
                  {drug.drug_name}
                </span>
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
