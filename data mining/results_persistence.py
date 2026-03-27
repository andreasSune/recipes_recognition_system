"""
MODULE : results_persistence.py
================================
Sauvegarde et rechargement de tous les résultats du pipeline FSM + MBA.

Structure du dossier de sortie (graph_mining_results/) :
  fsm_patterns.csv          — patterns fréquents + support
  apriori_rules.csv         — règles de co-occurrence
  spm_rules.csv             — règles séquentielles ordonnées
  spm_triggers.json         — gestes déclencheurs (lift max par geste)
  cluster_assignments.csv   — assignation cluster par recette
  fsm_matrix.npz            — matrice de vectorisation compressée (pour GNN)
  run_metadata.json         — paramètres du run + stats + chemins

Rechargement :
  results = load_results("graph_mining_results")
  # → dict avec clés : patterns, apriori_rules, spm_rules,
  #                    triggers, assignments, matrix, metadata

Auteur : Laboratoire Liara, UQAC
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Sauvegarde
# ---------------------------------------------------------------------------

def save_results(output_dir: str,
                 fsm,
                 apriori,
                 spm,
                 assignments: dict,
                 graphs: dict,
                 run_params: dict = None) -> dict:
    """
    Sauvegarde tous les résultats du pipeline dans output_dir.

    Args:
        output_dir   : chemin du dossier de sortie (créé si inexistant)
        fsm          : instance RecipeFSM après fit()
        apriori      : instance AprioriMBA après fit()
        spm          : instance PrefixSpanSPM après fit()
        assignments  : { recipe_id: cluster_id }
        graphs       : { recipe_id: nx.DiGraph } — pour recipe_ids de la matrice
        run_params   : dict de paramètres du run (min_support, etc.)

    Retourne un dict des chemins de fichiers sauvegardés.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}

    # --- 1. Patterns FSM ---
    df_patterns = fsm.to_dataframe()
    p = out / "fsm_patterns.csv"
    df_patterns.to_csv(p, index=False)
    paths["fsm_patterns"] = str(p)
    print(f"[Save] fsm_patterns.csv          ({len(df_patterns)} patterns)")

    # --- 2. Règles Apriori ---
    df_apriori = apriori.to_dataframe()
    p = out / "apriori_rules.csv"
    df_apriori.to_csv(p, index=False)
    paths["apriori_rules"] = str(p)
    print(f"[Save] apriori_rules.csv         ({len(df_apriori)} règles)")

    # --- 3. Règles SPM séquentielles ---
    df_spm = spm.to_dataframe()
    p = out / "spm_rules.csv"
    df_spm.to_csv(p, index=False)
    paths["spm_rules"] = str(p)
    print(f"[Save] spm_rules.csv             ({len(df_spm)} règles)")

    # --- 4. Gestes déclencheurs (JSON — structure imbriquée) ---
    triggers_raw = spm.trigger_gestures(top_n=50)
    triggers_serializable = [
        {
            "gesture"  : t["gesture"],
            "max_lift" : t["max_lift"],
            "best_rule": {
                "antecedent": list(t["best_rule"].antecedent),
                "consequent": list(t["best_rule"].consequent),
                "support"   : t["best_rule"].support,
                "confidence": t["best_rule"].confidence,
                "lift"      : t["best_rule"].lift,
                "n_recipes" : t["best_rule"].n_recipes,
            }
        }
        for t in triggers_raw
    ]
    p = out / "spm_triggers.json"
    p.write_text(json.dumps(triggers_serializable, indent=2, ensure_ascii=False))
    paths["spm_triggers"] = str(p)
    print(f"[Save] spm_triggers.json         ({len(triggers_serializable)} déclencheurs)")

    # --- 5. Assignations cluster ---
    df_assign = pd.DataFrame([
        {"recipe_id": rid, "cluster_id": cid}
        for rid, cid in assignments.items()
    ])
    p = out / "cluster_assignments.csv"
    df_assign.to_csv(p, index=False)
    paths["cluster_assignments"] = str(p)
    print(f"[Save] cluster_assignments.csv   ({len(df_assign)} recettes)")

    # --- 6. Matrice FSM compressée (NPZ) ---
    matrix, recipe_ids, pattern_labels = fsm.vectorize_recipes()
    p = out / "fsm_matrix.npz"
    np.savez_compressed(
        str(p),
        matrix        = matrix,
        recipe_ids    = np.array(recipe_ids, dtype=str),
        pattern_labels= np.array(pattern_labels, dtype=str)
    )
    paths["fsm_matrix"] = str(p)
    print(f"[Save] fsm_matrix.npz            ({matrix.shape} — {matrix.nbytes / 1024:.1f} KB)")

    # --- 7. Métadonnées du run ---
    metadata = {
        "timestamp"      : datetime.now().isoformat(),
        "n_recipes"      : len(graphs),
        "n_patterns_fsm" : len(fsm.patterns_),
        "n_rules_apriori": len(apriori.rules_),
        "n_rules_spm"    : len(spm.rules_),
        "n_clusters"     : len(set(v for v in assignments.values() if v != -1)),
        "matrix_shape"   : list(matrix.shape),
        "params"         : run_params or {},
        "files"          : paths,
    }
    p = out / "run_metadata.json"
    p.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    paths["run_metadata"] = str(p)
    print(f"[Save] run_metadata.json")

    print(f"\n[Save] Tous les résultats sauvegardés dans : {out.resolve()}")
    return paths


# ---------------------------------------------------------------------------
# Rechargement
# ---------------------------------------------------------------------------

def load_results(output_dir: str) -> dict:
    """
    Recharge tous les résultats depuis output_dir.

    Retourne un dict :
      {
        "patterns"   : pd.DataFrame,
        "apriori"    : pd.DataFrame,
        "spm_rules"  : pd.DataFrame,
        "triggers"   : list[dict],
        "assignments": dict { recipe_id: cluster_id },
        "matrix"     : np.ndarray,
        "recipe_ids" : list[str],
        "pattern_labels": list[str],
        "metadata"   : dict,
      }
    """
    out = Path(output_dir)
    if not out.exists():
        raise FileNotFoundError(f"Dossier introuvable : {out}")

    results = {}

    # Patterns FSM
    p = out / "fsm_patterns.csv"
    results["patterns"] = pd.read_csv(p) if p.exists() else None

    # Règles Apriori
    p = out / "apriori_rules.csv"
    results["apriori"] = pd.read_csv(p) if p.exists() else None

    # Règles SPM
    p = out / "spm_rules.csv"
    results["spm_rules"] = pd.read_csv(p) if p.exists() else None

    # Déclencheurs
    p = out / "spm_triggers.json"
    results["triggers"] = json.loads(p.read_text()) if p.exists() else []

    # Assignations cluster
    p = out / "cluster_assignments.csv"
    if p.exists():
        df = pd.read_csv(p)
        results["assignments"] = dict(zip(df["recipe_id"], df["cluster_id"]))
    else:
        results["assignments"] = {}

    # Matrice FSM
    p = out / "fsm_matrix.npz"
    if p.exists():
        npz = np.load(str(p), allow_pickle=True)
        results["matrix"]         = npz["matrix"]
        results["recipe_ids"]     = list(npz["recipe_ids"])
        results["pattern_labels"] = list(npz["pattern_labels"])
    else:
        results["matrix"]         = None
        results["recipe_ids"]     = []
        results["pattern_labels"] = []

    # Métadonnées
    p = out / "run_metadata.json"
    results["metadata"] = json.loads(p.read_text()) if p.exists() else {}

    print(f"[Load] Résultats rechargés depuis : {out.resolve()}")
    if results["metadata"]:
        m = results["metadata"]
        print(f"       Run du {m.get('timestamp', '?')[:10]}")
        print(f"       {m.get('n_recipes')} recettes  "
              f"{m.get('n_patterns_fsm')} patterns FSM  "
              f"{m.get('n_clusters')} clusters")

    return results
