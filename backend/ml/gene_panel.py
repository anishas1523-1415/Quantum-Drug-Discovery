"""A curated panel of well-established cancer driver genes.

This is a real, literature-grounded gene list (cf. the COSMIC Cancer Gene
Census and standard oncology gene panels), not an arbitrary selection —
it's the set of genes the effectiveness model is trained to recognize as
mutation features. It intentionally does not attempt to be exhaustive
(the full damaging-mutation matrix has ~19,500 genes; most carry no
generalizable signal for drug sensitivity and would only add noise and
overfitting risk to a training set of this size).
"""

DRIVER_GENE_PANEL = sorted([
    "TP53", "KRAS", "PIK3CA", "PTEN", "BRCA1", "BRCA2", "EGFR", "ERBB2",
    "BRAF", "NRAS", "HRAS", "MYC", "RB1", "APC", "VHL", "MET", "ALK",
    "ROS1", "IDH1", "IDH2", "STK11", "KEAP1", "CDKN2A", "SMAD4", "FBXW7",
    "ATM", "ATR", "ARID1A", "NF1", "SMARCA4", "CTNNB1", "GATA3", "NOTCH1",
    "KIT", "PDGFRA", "JAK2", "FLT3", "NPM1", "DNMT3A", "TET2", "ASXL1",
    "CREBBP", "EP300", "KMT2D", "MSH2", "MLH1", "MSH6", "PMS2", "CDH1",
    "GNAS", "MAP2K1", "RET", "TSC1", "TSC2", "AKT1", "ESR1", "AR",
])
