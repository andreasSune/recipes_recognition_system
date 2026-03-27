"""
MODULE : data_preparation.py
=============================
Chargement et transformation des graphes depuis la base SQLite recipe_graphs.db
produite par le pipeline de construction (graph_builder.py + pipeline.py).

Structure attendue de recipe_graphs.db :
  - Table nodes    : (recipe_id, action, occurrence_count, is_virtual)
  - Table edges    : (recipe_id, source, target, weight)
  - Table metadata : (recipe_id, title, num_nodes, num_edges,
                      num_variants, has_cycles, entry_points)

Le nœud virtuel START (is_virtual=1) est systématiquement exclu
des séquences et des graphes produits ici — on ne travaille que
sur les gestes physiques observables.

Auteur : Laboratoire Liara, UQAC
"""

import sqlite3
import json
import ast
from pathlib import Path
from collections import defaultdict
import networkx as nx


# ---------------------------------------------------------------------------
# Chargement depuis recipe_graphs.db
# ---------------------------------------------------------------------------

def load_graphs_from_db(db_path: str,
                         limit: int = None,
                         exclude_virtual: bool = True) -> dict:
    """
    Charge les graphes NetworkX directement depuis recipe_graphs.db.

    Retourne { recipe_id: nx.DiGraph } sans le nœud START
    (les arêtes START → X sont supprimées, ne conserve que les
    transitions entre gestes physiques réels).

    Args:
        db_path        : chemin vers recipe_graphs.db
        limit          : nombre max de recettes (None = toutes)
        exclude_virtual: si True, supprime le nœud START et ses arêtes
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Récupère la liste des recipe_ids
    query = "SELECT recipe_id FROM metadata ORDER BY recipe_id"
    if limit:
        query += f" LIMIT {limit}"
    cursor.execute(query)
    recipe_ids = [row["recipe_id"] for row in cursor.fetchall()]

    graphs = {}
    for recipe_id in recipe_ids:
        G = nx.DiGraph()

        # Nœuds (hors START si exclude_virtual)
        cursor.execute("""
            SELECT action, occurrence_count, is_virtual
            FROM nodes WHERE recipe_id = ?
        """, (recipe_id,))
        for row in cursor.fetchall():
            if exclude_virtual and row["is_virtual"]:
                continue
            G.add_node(row["action"],
                       occurrence_count=row["occurrence_count"],
                       is_virtual=bool(row["is_virtual"]))

        # Arêtes (hors arêtes depuis START si exclude_virtual)
        cursor.execute("""
            SELECT source, target, weight
            FROM edges WHERE recipe_id = ?
        """, (recipe_id,))
        for row in cursor.fetchall():
            if exclude_virtual and row["source"] == "START":
                continue
            if row["source"] in G.nodes and row["target"] in G.nodes:
                G.add_edge(row["source"], row["target"], weight=row["weight"])

        if G.number_of_edges() >= 1:
            graphs[recipe_id] = G

    conn.close()
    print(f"[Chargement] {len(graphs)} graphes chargés depuis {db_path}")
    return graphs


def load_sequences_from_db(db_path: str, limit: int = None) -> dict:
    """
    Charge les séquences depuis la variante principale uniquement,
    en suivant les arêtes de poids maximum depuis START.
    Filtre les graphes cycliques pour ne garder que le chemin principal.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT recipe_id FROM metadata ORDER BY recipe_id"
    if limit:
        query += f" LIMIT {limit}"
    cursor.execute(query)
    recipe_ids = [row["recipe_id"] for row in cursor.fetchall()]

    sequences = {}
    for recipe_id in recipe_ids:
        # Charge uniquement les arêtes depuis START (premier geste)
        cursor.execute("""
            SELECT target, weight FROM edges
            WHERE recipe_id = ? AND source = 'START'
            ORDER BY weight DESC LIMIT 1
        """, (recipe_id,))
        row = cursor.fetchone()
        if not row:
            continue

        # Reconstruit la séquence en suivant le poids max,
        # sans jamais revisiter un nœud (évite les cycles)
        seq = [row["target"]]
        visited = {"START", row["target"]}
        current = row["target"]

        for _ in range(50):  # garde-fou contre les cycles infinis
            cursor.execute("""
                SELECT target, weight FROM edges
                WHERE recipe_id = ? AND source = ?
                AND target != 'START'
                ORDER BY weight DESC LIMIT 5
            """, (recipe_id, current))
            candidates = [r for r in cursor.fetchall()
                         if r["target"] not in visited]
            if not candidates:
                break
            next_node = candidates[0]["target"]
            seq.append(next_node)
            visited.add(next_node)
            current = next_node

        if len(seq) >= 2:
            sequences[recipe_id] = seq

    conn.close()
    print(f"[Séquences] {len(sequences)} séquences extraites depuis {db_path}")
    return sequences

def _extract_sequence_from_graph(G: nx.DiGraph) -> list:
    """
    Extrait la séquence principale d'un graphe en suivant
    le chemin de poids maximum depuis START.
    Gère les cycles en limitant les visites à 1 par nœud.
    """
    if "START" not in G or G.out_degree("START") == 0:
        return []

    seq = []
    visited = set()
    current = "START"

    while True:
        successors = [(n, G[current][n].get("weight", 1))
                      for n in G.successors(current)
                      if n not in visited and n != "START"]
        if not successors:
            break
        # Suit l'arête de poids maximum (variante la plus fréquente)
        next_node = max(successors, key=lambda x: x[1])[0]
        if next_node != "START":
            seq.append(next_node)
            visited.add(next_node)
        current = next_node

    return seq


def load_metadata_from_db(db_path: str, limit: int = None) -> dict:
    """
    Charge les métadonnées de toutes les recettes.
    Retourne { recipe_id: {title, num_nodes, num_edges, ...} }
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM metadata ORDER BY recipe_id"
    if limit:
        query += f" LIMIT {limit}"
    cursor.execute(query)

    metadata = {}
    for row in cursor.fetchall():
        metadata[row["recipe_id"]] = {
            "title": row["title"],
            "num_nodes": row["num_nodes"],
            "num_edges": row["num_edges"],
            "num_variants": row["num_variants"],
            "has_cycles": bool(row["has_cycles"]),
            "entry_points": json.loads(row["entry_points"]) if row["entry_points"] else [],
        }

    conn.close()
    return metadata


# ---------------------------------------------------------------------------
# Transformations pour MBA et FSM
# ---------------------------------------------------------------------------

def sequences_to_list(sequences: dict) -> list:
    """Convertit { recipe_id: [actions] } en liste de listes pour PrefixSpan."""
    return list(sequences.values())


def sequences_to_transactions(sequences: dict) -> list:
    """
    Version 'sac de gestes' sans ordre — pour Apriori classique.
    Chaque recette devient un ensemble d'actions uniques.
    """
    return [list(set(seq)) for seq in sequences.values()]


def build_edge_index(graphs: dict, min_weight: int = 1) -> dict:
    """
    Construit un index inversé : (src, dst) → set(recipe_ids).
    Filtre les arêtes sous min_weight.
    Utilisé par le FSM pour calculer le support rapidement.
    """
    edge_index = defaultdict(set)
    for recipe_id, G in graphs.items():
        for src, dst, data in G.edges(data=True):
            if data.get("weight", 1) >= min_weight:
                edge_index[(src, dst)].add(recipe_id)
    return edge_index


# ---------------------------------------------------------------------------
# Statistiques descriptives
# ---------------------------------------------------------------------------

def describe_corpus(graphs: dict, sequences: dict, metadata: dict = None) -> dict:
    """Affiche et retourne des statistiques descriptives sur le corpus."""
    from collections import Counter

    all_actions = []
    for seq in sequences.values():
        all_actions.extend(seq)

    action_counts = Counter(all_actions)
    seq_lengths   = [len(s) for s in sequences.values()]
    node_counts   = [G.number_of_nodes() for G in graphs.values()]
    edge_counts   = [G.number_of_edges() for G in graphs.values()]

    # Arêtes les plus fréquentes
    edge_freq = defaultdict(int)
    for G in graphs.values():
        for src, dst, d in G.edges(data=True):
            edge_freq[(src, dst)] += d.get("weight", 1)
    top_edges = sorted(edge_freq.items(), key=lambda x: -x[1])[:10]

    stats = {
        "n_recettes"           : len(graphs),
        "n_gestes_uniques"     : len(action_counts),
        "top_10_gestes"        : action_counts.most_common(10),
        "top_10_transitions"   : top_edges,
        "longueur_seq_moyenne" : round(sum(seq_lengths) / max(len(seq_lengths), 1), 2),
        "longueur_seq_max"     : max(seq_lengths) if seq_lengths else 0,
        "noeuds_graphe_moyen"  : round(sum(node_counts) / max(len(node_counts), 1), 2),
        "aretes_graphe_moyen"  : round(sum(edge_counts) / max(len(edge_counts), 1), 2),
    }

    if metadata:
        cycles = sum(1 for m in metadata.values() if m.get("has_cycles"))
        stats["recettes_avec_cycles"] = cycles
        stats["pct_cycles"] = round(cycles / len(metadata) * 100, 1)

    print("\n--- Statistiques corpus ---")
    print(f"  Recettes              : {stats['n_recettes']}")
    print(f"  Gestes uniques        : {stats['n_gestes_uniques']}")
    print(f"  Longueur moy. séq.    : {stats['longueur_seq_moyenne']}")
    print(f"  Nœuds moy. graphe     : {stats['noeuds_graphe_moyen']}")
    print(f"  Arêtes moy. graphe    : {stats['aretes_graphe_moyen']}")
    print(f"  Top gestes  : {[g for g, _ in stats['top_10_gestes']]}")
    print(f"  Top transitions : {[(f'{s}→{d}', w) for (s,d), w in stats['top_10_transitions'][:5]]}")
    if metadata:
        print(f"  Recettes avec cycles  : {stats['recettes_avec_cycles']} ({stats['pct_cycles']}%)")

    return stats


# ---------------------------------------------------------------------------
# Données synthétiques (tests sans SQLite)
# ---------------------------------------------------------------------------

def make_synthetic_data(n: int = 500, seed: int = 42):
    """
    Génère un corpus synthétique qui mime la structure de recipe_graphs.db.
    Retourne (graphs, sequences, metadata) — même format que les fonctions
    de chargement réelles.
    """
    import random
    random.seed(seed)

    gesture_pools = {
        "salad"    : ["cut", "mix", "add", "season", "toss", "serve"],
        "sauce"    : ["chop", "saute", "mix", "season", "reduce", "stir"],
        "pastry"   : ["sift", "mix", "fold", "whisk", "pour", "spread"],
        "meat"     : ["slice", "marinate", "saute", "season", "serve"],
        "soup"     : ["cut", "saute", "pour", "mix", "season", "stir"],
    }

    graphs, sequences, metadata = {}, {}, {}
    categories = list(gesture_pools.keys())

    for i in range(n):
        rid = f"recipe_{i:04d}"
        cat = random.choice(categories)
        pool = gesture_pools[cat]

        # Séquence de 3 à 7 gestes
        length = random.randint(3, 7)
        seq = []
        for _ in range(length):
            g = random.choice(pool)
            if not seq or seq[-1] != g:
                seq.append(g)
        if len(seq) < 2:
            continue

        # Graphe NetworkX (sans START — même format que load_graphs_from_db)
        G = nx.DiGraph()
        for j, action in enumerate(seq):
            if action not in G:
                G.add_node(action, occurrence_count=1, is_virtual=False)
            else:
                G.nodes[action]["occurrence_count"] += 1
            if j > 0:
                src, dst = seq[j - 1], action
                if G.has_edge(src, dst):
                    G[src][dst]["weight"] += 1
                else:
                    G.add_edge(src, dst, weight=1)

        graphs[rid]    = G
        sequences[rid] = seq
        metadata[rid]  = {
            "title"      : f"{cat.capitalize()} #{i}",
            "num_nodes"  : G.number_of_nodes(),
            "num_edges"  : G.number_of_edges(),
            "num_variants": random.randint(1, 4),
            "has_cycles" : False,
            "entry_points": [seq[0]],
            "category"   : cat,
        }

    print(f"[Synthétique] {len(graphs)} recettes générées")
    return graphs, sequences, metadata
