"""Rule-based ADMET / drug-likeness risk screening.

Honesty note, read before touching this file: this is deliberately NOT a
trained toxicity classifier. Building one honestly would require labeled
toxicity data (e.g. Tox21, ClinTox) that hasn't been sourced for this
project — faking one would be exactly the kind of fabricated-evidence
result this whole build has been avoiding.

What's here instead is real, standard, decades-old medicinal chemistry
screening: Lipinski's Rule of Five (Lipinski et al., 1997) and QED
drug-likeness (Bickerton et al., 2012), applied to the real descriptors
computed by molecular_properties.py. This is a legitimate early-stage
screening method used throughout real drug discovery — it flags
structural risk factors, it does not predict actual toxicity in humans.
The output says so explicitly so nobody downstream mistakes it for more
than it is.
"""

# QED bands as informally referenced in Bickerton et al. 2012 — not a
# regulatory or clinical threshold, just a common rule-of-thumb grouping.
QED_BANDS = [
    (0.67, "Low"),
    (0.40, "Moderate"),
]


def _qed_band(qed):
    for threshold, label in QED_BANDS:
        if qed >= threshold:
            return label
    return "Higher"


def assess_admet_risk(molecular_properties_result):
    """Rule-based risk screening from an already-computed
    molecular_properties result (see molecular_properties.py)."""

    if not molecular_properties_result["has_structure"]:
        molecule_type = molecular_properties_result.get("molecule_type") or "This therapy"
        return {
            "method": "not_applicable",
            "risk_band": "N/A",
            "flags": [],
            "explanation": (
                f"{molecule_type} therapies are large biologics — small-molecule "
                "drug-likeness rules (Lipinski/QED) don't apply to them. Their "
                "safety profile is characterized differently (immunogenicity, "
                "infusion reactions, etc.), which this screening doesn't cover."
            ),
        }

    props = molecular_properties_result["properties"]
    qed = molecular_properties_result["qed"]
    lipinski = molecular_properties_result["lipinski"]

    flags = []
    if props["molecular_weight"] > 500:
        flags.append(f"Molecular weight {props['molecular_weight']} Da exceeds 500 (Lipinski threshold)")
    if props["logp"] > 5:
        flags.append(f"LogP {props['logp']} exceeds 5 — high lipophilicity")
    if props["h_bond_donors"] > 5:
        flags.append(f"{props['h_bond_donors']} H-bond donors exceeds 5")
    if props["h_bond_acceptors"] > 10:
        flags.append(f"{props['h_bond_acceptors']} H-bond acceptors exceeds 10")
    if props["tpsa"] > 140:
        flags.append(f"Polar surface area {props['tpsa']} exceeds 140 — may limit oral absorption")

    risk_band = _qed_band(qed)

    return {
        "method": "rule_based_screening",
        "risk_band": risk_band,
        "qed": qed,
        "lipinski_violations": lipinski["violations"],
        "flags": flags,
        "explanation": (
            f"QED drug-likeness score {qed} ({risk_band.lower()} structural risk band), "
            f"{lipinski['violations']} Lipinski Rule-of-Five violation(s). "
            "This is rule-based structural screening, not a trained toxicity "
            "prediction — it flags properties historically associated with "
            "poor absorption or higher attrition, not confirmed adverse effects."
        ),
    }
