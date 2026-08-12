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

export function stageLabel(stage) {
  return STAGE_LABELS[(stage || "").toUpperCase()] || stage || "Unknown stage";
}

export function stageBadgeClass(stage) {
  const upper = (stage || "").toUpperCase();
  if (APPROVED_STAGES.has(upper)) return "badge-success";
  if (MID_LATE_STAGES.has(upper)) return "badge-warning";
  return "badge-neutral";
}
