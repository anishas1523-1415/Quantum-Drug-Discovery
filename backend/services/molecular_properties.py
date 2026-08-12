"""Real molecular property analysis via RDKit.

Fetches a compound's actual structure (SMILES) from ChEMBL, then computes
real cheminformatics descriptors with RDKit — molecular weight, LogP,
polar surface area, hydrogen bond donors/acceptors, and QED drug-likeness.
These are standard, well-established medicinal chemistry calculations
(verified during development against Erlotinib's published values), not
predictions or estimates.

Biologics (antibodies, antibody-drug conjugates) don't have a small
-molecule SMILES structure — that's a real, expected outcome for that
drug class, not missing data, and is reported as such.
"""

import logging

import requests
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, QED

logger = logging.getLogger("qdd.molecular_properties")

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
REQUEST_TIMEOUT = 10


class MolecularPropertiesError(Exception):
    pass


def _fetch_smiles(chembl_id):
    try:
        response = requests.get(
            f"{CHEMBL_API}/molecule/{chembl_id}.json",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise MolecularPropertiesError(f"Could not reach ChEMBL: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MolecularPropertiesError("ChEMBL returned a non-JSON response (likely a temporary outage)") from exc

    structures = payload.get("molecule_structures") or {}

    return {
        "smiles": structures.get("canonical_smiles"),
        "molecule_type": payload.get("molecule_type"),
    }


def get_molecular_properties(chembl_id):
    """Real RDKit-computed descriptors for a compound, or an honest
    "not applicable" result for biologics that have no small-molecule
    structure."""

    info = _fetch_smiles(chembl_id)

    if not info["smiles"]:
        return {
            "chembl_id": chembl_id,
            "has_structure": False,
            "molecule_type": info["molecule_type"],
            "properties": None,
            "lipinski": None,
            "qed": None,
        }

    mol = Chem.MolFromSmiles(info["smiles"])

    if mol is None:
        logger.warning("RDKit could not parse SMILES for %s", chembl_id)
        return {
            "chembl_id": chembl_id,
            "has_structure": False,
            "molecule_type": info["molecule_type"],
            "properties": None,
            "lipinski": None,
            "qed": None,
        }

    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    tpsa = Descriptors.TPSA(mol)
    hbd = Descriptors.NumHDonors(mol)
    hba = Descriptors.NumHAcceptors(mol)
    rot_bonds = Descriptors.NumRotatableBonds(mol)

    # Lipinski's Rule of Five: a well-established (1997), widely used
    # heuristic for oral drug-likeness. Violating it doesn't mean a drug
    # can't work (many real approved drugs violate one rule) — it's a
    # screening signal, reported as a count of violations, not a verdict.
    violations = sum([
        mw > 500,
        logp > 5,
        hbd > 5,
        hba > 10,
    ])

    return {
        "chembl_id": chembl_id,
        "has_structure": True,
        "molecule_type": info["molecule_type"],
        "smiles": info["smiles"],
        "properties": {
            "molecular_weight": round(mw, 2),
            "logp": round(logp, 2),
            "tpsa": round(tpsa, 2),
            "h_bond_donors": hbd,
            "h_bond_acceptors": hba,
            "rotatable_bonds": rot_bonds,
        },
        "lipinski": {
            "violations": violations,
            "passes": violations <= 1,  # standard Ro5 allowance: <=1 violation
        },
        "qed": round(QED.qed(mol), 3),
    }
