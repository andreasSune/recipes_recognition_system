"""
MODULE : run_pipeline.py
=========================
Script principal — exécute le pipeline FSM + MBA complet
sur les graphes stockés dans recipe_graphs.db.

Usage
-----
# Données réelles (recipe_graphs.db)
python run_pipeline.py --db /chemin/vers/recipe_graphs.db --limit 50000

# Données synthétiques (test sans BD)
python run_pipeline.py --synthetic --limit 500

# Ajustement des seuils
python run_pipeline.py --db recipe_graphs.db \
    --min_support 0.05 --min_confidence 0.5 --min_lift 1.2 \
    --min_edge_weight 2

Conseils seuils pour les vraies données (1M recettes)
------------------------------------------------------
  min_support      = 0.01  → pattern présent dans ≥10 000 recettes
  min_edge_weight  = 2     → filtre les transitions vues une seule fois
  min_lift         = 1.5   → règles non triviales seulement

Auteur : Laboratoire Liara, UQAC
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict
from results_persistence import save_results, load_results


sys.path.insert(0, str(Path(__file__).parent))

from data_preparation import (
    load_graphs_from_db, load_sequences_from_db, load_metadata_from_db,
    sequences_to_list, sequences_to_transactions,
    describe_corpus, make_synthetic_data
)
from mba_sequential import AprioriMBA, PrefixSpanSPM, analyze_clusters_with_mba
from fsm_recipes import RecipeFSM, cluster_recipes_from_fsm, describe_clusters


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def run_pipeline(graphs: dict, sequences: dict, metadata: dict,
                 min_support: float = 0.1,
                 min_confidence: float = 0.5,
                 min_lift: float = 1.2,
                 min_edge_weight: int = 1):

    print("\n" + "=" * 65)
    print("  PIPELINE FSM + MBA — Reconnaissance de Recettes")
    print("  Laboratoire Liara, UQAC")
    print("=" * 65)

    seq_list = sequences_to_list(sequences)
    tx_list  = sequences_to_transactions(sequences)

    describe_corpus(graphs, sequences, metadata)

    # -------------------------------------------------------------------
    # ÉTAPE 1 — MBA Apriori (co-occurrence sans ordre)
    # -------------------------------------------------------------------
    print("\n" + "-" * 50)
    print("ÉTAPE 1 — MBA Apriori (co-occurrence)")
    print("-" * 50)

    apriori = AprioriMBA(
        min_support    = min_support,
        min_confidence = min_confidence,
        min_lift       = min_lift,
        max_itemset_size = 3
    )
    apriori.fit(tx_list)

    print(f"\nTop 10 règles par lift :")
    for r in apriori.top_rules(10):
        print(f"  {r}")

    # -------------------------------------------------------------------
    # ÉTAPE 2 — SPM PrefixSpan (séquentiel, ordre respecté)
    # -------------------------------------------------------------------
    print("\n" + "-" * 50)
    print("ÉTAPE 2 — SPM PrefixSpan (séquentiel)")
    print("-" * 50)

    spm = PrefixSpanSPM(min_support=min_support, max_pattern_length=4)
    spm.fit(seq_list)

    print(f"\nTop 10 patterns séquentiels :")
    for sup, pattern in spm.top_patterns(10):
        print(f"  sup={sup:.3f}  {' → '.join(pattern)}")

    print(f"\nTop 10 règles séquentielles par lift :")
    for r in spm.top_rules(10):
        print(f"  {r}")

    print(f"\nGestes déclencheurs (fort pouvoir prédictif) :")
    for item in spm.trigger_gestures(8):
        print(f"  {item['gesture']:22s}  lift_max={item['max_lift']:.2f}"
              f"  →  {item['best_rule']}")

    # -------------------------------------------------------------------
    # ÉTAPE 3 — FSM sur graphes dirigés
    # -------------------------------------------------------------------
    print("\n" + "-" * 50)
    print("ÉTAPE 3 — FSM (sous-graphes fréquents)")
    print("-" * 50)

    fsm = RecipeFSM(
        min_support        = min_support,
        max_pattern_length = 4,
        min_edge_weight    = min_edge_weight
    )
    fsm.fit(graphs)

    print(f"\nTop 15 patterns FSM :")
    for p in fsm.top_patterns(15):
        print(f"  {p}")

    if fsm.patterns_by_length(3):
        print(f"\nPatterns de longueur 3 :")
        for p in fsm.patterns_by_length(3)[:8]:
            print(f"  {p}")

    # -------------------------------------------------------------------
    # ÉTAPE 4 — Clustering sur vecteurs FSM
    # -------------------------------------------------------------------
    print("\n" + "-" * 50)
    print("ÉTAPE 4 — Clustering sur vecteurs FSM")
    print("-" * 50)

    assignments = cluster_recipes_from_fsm(fsm, method="kmeans")
    df_clusters = describe_clusters(assignments, metadata, fsm)

    print("\nDescription des clusters :")
    if not df_clusters.empty:
        print(df_clusters.to_string(index=False))
    else:
        print("  (aucun cluster formé — ajuste min_support)")

    # -------------------------------------------------------------------
    # ÉTAPE 5 — MBA par cluster (validation croisée)
    # -------------------------------------------------------------------
    print("\n" + "-" * 50)
    print("ÉTAPE 5 — MBA intra-cluster (validation)")
    print("-" * 50)

    cluster_mba = analyze_clusters_with_mba(
        assignments, sequences,
        min_support=min(min_support * 2, 0.5)
    )
    for cid, cspm in sorted(cluster_mba.items()):
        rules = cspm.top_rules(1)
        if rules:
            print(f"\n  Cluster {cid} — règle la plus forte :")
            print(f"    {rules[0]}")

    # -------------------------------------------------------------------
    # Résumé
    # -------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("RÉSUMÉ")
    print("=" * 65)
    n_clusters = len(set(v for v in assignments.values() if v != -1))
    print(f"  Recettes analysées     : {len(graphs)}")
    print(f"  Patterns FSM trouvés   : {len(fsm.patterns_)}")
    print(f"  Règles MBA (Apriori)   : {len(apriori.rules_)}")
    print(f"  Règles SPM séquentiel  : {len(spm.rules_)}")
    print(f"  Clusters formés        : {n_clusters}")

    if spm.trigger_gestures(3):
        trig = spm.trigger_gestures(3)
        print(f"  Top gestes déclencheurs: "
              f"{', '.join(t['gesture'] for t in trig)}")

    print("=" * 65)

    # --- Sauvegarde des résultats ---
    save_results(
        output_dir = "graph_mining_results",
        fsm        = fsm,
        apriori    = apriori,
        spm        = spm,
        assignments= assignments,
        graphs     = graphs,
        run_params = {
            "min_support"    : min_support,
            "min_confidence" : min_confidence,
            "min_lift"       : min_lift,
            "min_edge_weight": min_edge_weight,
            "n_recipes"      : len(graphs),
        }
    )

    return {
        "apriori"    : apriori,
        "spm"        : spm,
        "fsm"        : fsm,
        "assignments": assignments,
        "cluster_mba": cluster_mba,
    }


