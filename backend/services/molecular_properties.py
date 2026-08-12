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

from services.molecular_descriptors import compute_descriptors

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

    descriptors = compute_descriptors(info["smiles"])

    if descriptors is None:
        logger.warning("RDKit could not parse SMILES for %s", chembl_id)
        return {
            "chembl_id": chembl_id,
            "has_structure": False,
            "molecule_type": info["molecule_type"],
            "properties": None,
            "lipinski": None,
            "qed": None,
        }

    return {
        "chembl_id": chembl_id,
        "has_structure": True,
        "molecule_type": info["molecule_type"],
        "smiles": info["smiles"],
        "properties": {
            "molecular_weight": descriptors["molecular_weight"],
            "logp": descriptors["logp"],
            "tpsa": descriptors["tpsa"],
            "h_bond_donors": descriptors["h_bond_donors"],
            "h_bond_acceptors": descriptors["h_bond_acceptors"],
            "rotatable_bonds": descriptors["rotatable_bonds"],
        },
        "lipinski": {
            "violations": descriptors["lipinski_violations"],
            "passes": descriptors["lipinski_violations"] <= 1,  # standard Ro5 allowance: <=1 violation
        },
        "qed": descriptors["qed"],
    }
