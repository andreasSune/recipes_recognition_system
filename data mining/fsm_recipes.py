"""
MODULE : fsm_recipes.py
========================
Frequent Subgraph Mining (FSM) sur les graphes de recettes.

Les graphes sources viennent de recipe_graphs.db :
  - Nœuds  : gestes culinaires physiques (START exclu)
  - Arêtes : transitions séquentielles avec weight = occurrences
             cumulées sur toutes les variantes (principale +
             ingrédients + permutations)

Stratégie d'implémentation
--------------------------
gSpan complet est NP-hard. Sur des graphes de recettes (5–15 nœuds),
on utilise une énumération de chemins dirigés qui est :
  - exacte (pas d'approximation)
  - efficace grâce à la propriété d'anti-monotonie d'Apriori :
    support(A→B→C) ≤ support(A→B) ≤ support(A)
    → on élague dès qu'un préfixe est sous le seuil

Les poids des arêtes servent de filtre optionnel (min_edge_weight) :
ne conserver que les transitions "stables" à travers les variantes.

Sortie principale : vecteurs binaires recette × patterns
  → directement utilisables pour le clustering (K-Means, HDBSCAN)
  → et pour initialiser les embeddings GNN (feature matrix X)

Auteur : Laboratoire Liara, UQAC
"""

from collections import defaultdict
from dataclasses import dataclass, field
import networkx as nx
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Structure de données
# ---------------------------------------------------------------------------

@dataclass
class FrequentPattern:
    edges     : list   # [(src, dst), ...]  chemin dirigé
    support   : float  # fréquence dans le corpus
    n_recipes : int
    recipe_ids: set = field(default_factory=set, repr=False)

    @property
    def length(self) -> int:
        return len(self.edges)

    @property
    def nodes(self) -> list:
        seen = []
        for src, dst in self.edges:
            if src not in seen: seen.append(src)
            if dst not in seen: seen.append(dst)
        return seen

    def __repr__(self):
        path = " → ".join(self.nodes)
        return f"[sup={self.support:.3f}  n={self.n_recipes}]  {path}"


# ---------------------------------------------------------------------------
# FSM principal
# ---------------------------------------------------------------------------

class RecipeFSM:
    """
    Frequent Subgraph Mining pour graphes de recettes.

    Paramètres clés
    ---------------
    min_support      : seuil de fréquence (0–1). Sur 1M recettes,
                       0.01 = pattern présent dans ≥10 000 recettes.
    max_pattern_length: longueur max des chemins minés. 3–4 suffit
                       en pratique ; au-delà les patterns deviennent
                       trop spécifiques pour être utiles au clustering.
    min_edge_weight  : filtre les arêtes instables (présentes dans
                       une seule variante). Recommandé : 2 sur les
                       vraies données (variante principale + au moins
                       une variante ingrédients/permutation).
    """

    def __init__(self, min_support: float = 0.1,
                 max_pattern_length: int = 4,
                 min_edge_weight: int = 1):
        self.min_support       = min_support
        self.max_pattern_length = max_pattern_length
        self.min_edge_weight   = min_edge_weight
        self.patterns_         : list = []
        self._n                : int  = 0
        self._graphs           : dict = {}

    def fit(self, graphs: dict) -> "RecipeFSM":
        """
        graphs : { recipe_id: nx.DiGraph }  (sans nœud START)
        """
        self._graphs = graphs
        self._n      = len(graphs)
        min_count    = max(1, int(self.min_support * self._n))

        print(f"[FSM] {self._n} graphes  min_support={self.min_support} "
              f"({min_count} recettes min)  min_edge_weight={self.min_edge_weight}")

        edge_index = self._build_edge_index()
        print(f"[FSM] {len(edge_index)} arêtes distinctes dans le corpus")

        # Patterns de longueur 1 (arêtes fréquentes)
        freq_edges = {e: rids for e, rids in edge_index.items()
                      if len(rids) >= min_count}
        print(f"[FSM] {len(freq_edges)} arêtes fréquentes (longueur 1)")

        for (src, dst), rids in freq_edges.items():
            self.patterns_.append(FrequentPattern(
                edges=[(src, dst)],
                support=round(len(rids) / self._n, 4),
                n_recipes=len(rids),
                recipe_ids=rids.copy()
            ))

        # Extension en chemins plus longs
        current = {((src, dst),): rids for (src, dst), rids in freq_edges.items()}
        for length in range(2, self.max_pattern_length + 1):
            extended = self._extend_paths(current, edge_index, min_count)
            if not extended:
                break
            print(f"[FSM] {len(extended)} patterns de longueur {length}")
            for path, rids in extended.items():
                self.patterns_.append(FrequentPattern(
                    edges=list(path),
                    support=round(len(rids) / self._n, 4),
                    n_recipes=len(rids),
                    recipe_ids=rids.copy()
                ))
            current = extended

        self.patterns_.sort(key=lambda p: (-p.support, -p.length))
        print(f"[FSM] Total : {len(self.patterns_)} patterns fréquents")
        return self

    def _build_edge_index(self) -> dict:
        """Index inversé : (src, dst) → set(recipe_ids) — filtre min_edge_weight."""
        idx = defaultdict(set)
        for rid, G in self._graphs.items():
            for src, dst, data in G.edges(data=True):
                if data.get("weight", 1) >= self.min_edge_weight:
                    idx[(src, dst)].add(rid)
        return idx

    def _extend_paths(self, current: dict, edge_index: dict,
                      min_count: int) -> dict:
        """
        Étend chaque chemin d'une arête supplémentaire.
        Anti-monotonie : si le préfixe est sous le seuil, on élague.
        """
        extended = {}
        for path, path_rids in current.items():
            last_node = path[-1][1]
            for (src, dst), edge_rids in edge_index.items():
                if src != last_node:
                    continue
                # Évite les cycles simples (option conservative)
                path_nodes = {n for e in path for n in e}
                if dst in path_nodes:
                    continue
                shared = path_rids & edge_rids
                if len(shared) >= min_count:
                    new_path = path + ((src, dst),)
                    if new_path not in extended or len(shared) > len(extended[new_path]):
                        extended[new_path] = shared
        return extended

    # -----------------------------------------------------------------------
    # Accesseurs
    # -----------------------------------------------------------------------

    def top_patterns(self, n: int = 20) -> list:
        return self.patterns_[:n]

    def patterns_by_length(self, length: int) -> list:
        return [p for p in self.patterns_ if p.length == length]

    def patterns_containing(self, gesture: str) -> list:
        """Retourne les patterns qui contiennent un geste donné."""
        return [p for p in self.patterns_ if gesture in p.nodes]

    # -----------------------------------------------------------------------
    # Vectorisation pour clustering et GNN
    # -----------------------------------------------------------------------

    def vectorize_recipes(self) -> tuple:
        """
        Représente chaque recette comme vecteur binaire :
          matrix[i, j] = 1  si recette i contient pattern j

        Retourne (matrix, recipe_ids, pattern_labels)

        Usage clustering :
          kmeans.fit(matrix)  ou  hdbscan.fit(matrix)

        Usage GNN (feature matrix X) :
          Peut servir de features initiales sur les nœuds ou de
          représentation globale du graphe pour l'initialisation
          des embeddings avant l'entraînement GNN.
        """
        recipe_ids = list(self._graphs.keys())
        rid_idx    = {rid: i for i, rid in enumerate(recipe_ids)}

        matrix = np.zeros((len(recipe_ids), len(self.patterns_)), dtype=np.uint8)
        labels = []

        for j, p in enumerate(self.patterns_):
            labels.append(" → ".join(p.nodes))
            for rid in p.recipe_ids:
                if rid in rid_idx:
                    matrix[rid_idx[rid], j] = 1

        density = matrix.mean() if matrix.size > 0 else 0
        print(f"[FSM] Matrice vectorisation : {matrix.shape}  densité={density:.3f}")
        return matrix, recipe_ids, labels

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "pattern"  : " → ".join(p.nodes),
            "length"   : p.length,
            "support"  : p.support,
            "n_recipes": p.n_recipes,
        } for p in self.patterns_])


# ---------------------------------------------------------------------------
# Clustering sur vecteurs FSM
# ---------------------------------------------------------------------------

def cluster_recipes_from_fsm(fsm: RecipeFSM,
                              n_clusters: int = None,
                              method: str = "kmeans") -> dict:
    """
    Applique un clustering sur les vecteurs binaires FSM.

    method : 'kmeans'  — nombre de clusters fixé (défaut auto)
             'hdbscan' — nombre de clusters automatique

    Retourne { recipe_id: cluster_id }
    """
    matrix, recipe_ids, _ = fsm.vectorize_recipes()

    if matrix.shape[1] == 0:
        print("[Clustering] Aucun pattern — fallback cluster unique")
        return {rid: 0 for rid in recipe_ids}

    if method == "hdbscan":
        try:
            import hdbscan
            min_size = max(5, len(recipe_ids) // 20)
            clf = hdbscan.HDBSCAN(min_cluster_size=min_size, metric="hamming")
            labels = clf.fit_predict(matrix)
        except ImportError:
            print("[Clustering] hdbscan non disponible → kmeans")
            method = "kmeans"

    if method == "kmeans":
        from sklearn.cluster import KMeans
        k = n_clusters or max(3, int(len(recipe_ids) ** 0.35))
        clf = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = clf.fit_predict(matrix)

    assignments   = {rid: int(labels[i]) for i, rid in enumerate(recipe_ids)}
    n_found       = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise       = sum(1 for l in labels if l == -1)
    print(f"[Clustering] {n_found} clusters  ({n_noise} recettes non assignées)")
    return assignments


def describe_clusters(assignments: dict, metadata: dict,
                      fsm: RecipeFSM) -> pd.DataFrame:
    """
    Décrit chaque cluster :
      - taille
      - patterns FSM les plus représentatifs
      - exemples de titres de recettes
    """
    from collections import defaultdict
    cluster_data = defaultdict(list)
    for rid, cid in assignments.items():
        cluster_data[cid].append(rid)

    rows = []
    for cid, rids in sorted(cluster_data.items()):
        if cid == -1:
            continue
        # Patterns dominants dans ce cluster
        hit_counts = defaultdict(int)
        for p in fsm.patterns_:
            hits = len(p.recipe_ids & set(rids))
            if hits > 0:
                hit_counts[" → ".join(p.nodes)] = hits
        top3 = sorted(hit_counts.items(), key=lambda x: -x[1])[:3]

        titles = [metadata[rid]["title"]
                  for rid in rids[:3] if rid in metadata]
        rows.append({
            "cluster"    : cid,
            "n_recettes" : len(rids),
            "top_patterns": " | ".join(p for p, _ in top3),
            "exemples"   : " | ".join(titles),
        })

    if not rows:
        return pd.DataFrame(columns=["cluster", "n_recettes",
                                      "top_patterns", "exemples"])
    return pd.DataFrame(rows).sort_values("n_recettes", ascending=False)
