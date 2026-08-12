"""Pure RDKit descriptor computation, shared by every place that needs
real cheminformatics features from a SMILES string.

Used two ways in this codebase: live, per-candidate scoring in
molecular_properties.py (SMILES fetched from ChEMBL by chembl_id), and
offline model training in ml/train_effectiveness_model.py (SMILES read
from the local GDSC/PortalCompounds reference data). Both paths call
this same function so the features a model was trained on are computed
identically to the features it sees at inference time.
"""

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, QED


def compute_descriptors(smiles):
    """Real RDKit descriptors for a SMILES string, or None if RDKit can't
    parse it (malformed/missing structure — a real, expected outcome, not
    something to silently default)."""

    if not smiles:
        return None

    mol = Chem.MolFromSmiles(smiles)

    if mol is None:
        return None

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
        "molecular_weight": round(mw, 2),
        "logp": round(logp, 2),
        "tpsa": round(tpsa, 2),
        "h_bond_donors": hbd,
        "h_bond_acceptors": hba,
        "rotatable_bonds": rot_bonds,
        "lipinski_violations": violations,
        "qed": round(QED.qed(mol), 3),
    }
