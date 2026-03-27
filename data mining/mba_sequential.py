"""
MODULE : mba_sequential.py
===========================
Market Basket Analysis séquentiel sur les gestes culinaires.

Contexte : les séquences analysées ici sont extraites des graphes de
recipe_graphs.db (nœuds physiques uniquement, START exclu).

Deux niveaux d'analyse complémentaires :

  1. AprioriMBA — co-occurrence sans ordre
     Question : "Quels gestes apparaissent ensemble dans les mêmes recettes ?"
     Utile pour détecter des familles de gestes indépendamment de leur séquence.

  2. PrefixSpanSPM — patterns séquentiels ordonnés
     Question : "Si ce geste est observé, quel geste suivant est le plus probable ?"
     Directement exploitable dans le pipeline de reconnaissance en temps réel :
     dès qu'un geste est observé par le capteur, les règles à fort lift permettent
     de restreindre immédiatement l'espace de recettes candidates.

Métriques clés :
  - support    : fréquence du pattern dans le corpus (0–1)
  - confiance  : P(Y | X) — probabilité conditionnelle
  - lift       : confiance / P(Y)
                 > 1  → association positive (X attire Y, non trivial)
                 = 1  → indépendance (association banale)
                 < 1  → répulsion (X et Y s'évitent)

  Un geste "déclencheur" = lift élevé comme antécédent
  → sa présence réduit drastiquement l'espace de recherche.

Auteur : Laboratoire Liara, UQAC
"""

from collections import defaultdict
from itertools import combinations
from dataclasses import dataclass, field
import pandas as pd


# ---------------------------------------------------------------------------
# Structure de données partagée
# ---------------------------------------------------------------------------

@dataclass
class AssociationRule:
    antecedent : tuple
    consequent : tuple
    support    : float
    confidence : float
    lift       : float
    n_recipes  : int      # nombre absolu de recettes concernées

    def __repr__(self):
        ant = " → ".join(self.antecedent)
        con = " → ".join(self.consequent)
        return (f"{ant}  ⟹  {con}  "
                f"[sup={self.support:.3f}  conf={self.confidence:.3f}  lift={self.lift:.2f}"
                f"  n={self.n_recipes}]")


# ---------------------------------------------------------------------------
# MBA classique (Apriori) — co-occurrence
# ---------------------------------------------------------------------------

class AprioriMBA:
    """
    Apriori sur des transactions (ensembles de gestes sans ordre).
    Produit des règles du type :
        {marinate, slice} ⟹ {saute}  lift=3.2
    """

    def __init__(self, min_support: float = 0.1,
                 min_confidence: float = 0.5,
                 min_lift: float = 1.0,
                 max_itemset_size: int = 3):
        self.min_support      = min_support
        self.min_confidence   = min_confidence
        self.min_lift         = min_lift
        self.max_itemset_size = max_itemset_size
        self.frequent_itemsets_ : dict = {}
        self.rules_            : list  = []

    def fit(self, transactions: list) -> "AprioriMBA":
        n = len(transactions)
        print(f"[Apriori] {n} transactions  min_support={self.min_support}")

        # Fréquences des singletons
        counts = defaultdict(int)
        for t in transactions:
            for item in set(t):
                counts[frozenset([item])] += 1

        freq = {k: v / n for k, v in counts.items()
                if v / n >= self.min_support}
        self.frequent_itemsets_.update(freq)

        current = list(freq.keys())
        for size in range(2, self.max_itemset_size + 1):
            items = set()
            for fs in current:
                items.update(fs)
            candidates = [frozenset(c) for c in combinations(sorted(items), size)]

            batch = defaultdict(int)
            for t in transactions:
                t_set = frozenset(t)
                for c in candidates:
                    if c.issubset(t_set):
                        batch[c] += 1

            new_freq = {k: v / n for k, v in batch.items()
                        if v / n >= self.min_support}
            if not new_freq:
                break
            self.frequent_itemsets_.update(new_freq)
            current = list(new_freq.keys())

        self.rules_ = self._generate_rules(n)
        print(f"[Apriori] {len(self.frequent_itemsets_)} itemsets fréquents  "
              f"{len(self.rules_)} règles")
        return self

    def _generate_rules(self, n: int) -> list:
        rules = []
        for itemset, sup in self.frequent_itemsets_.items():
            if len(itemset) < 2:
                continue
            for size in range(1, len(itemset)):
                for ant in combinations(sorted(itemset), size):
                    ant_fs = frozenset(ant)
                    con_fs = itemset - ant_fs
                    if not con_fs:
                        continue
                    ant_sup = self.frequent_itemsets_.get(ant_fs, 0)
                    con_sup = self.frequent_itemsets_.get(con_fs, 0)
                    if ant_sup == 0 or con_sup == 0:
                        continue
                    conf = sup / ant_sup
                    lift = conf / con_sup
                    if conf >= self.min_confidence and lift >= self.min_lift:
                        rules.append(AssociationRule(
                            antecedent=tuple(sorted(ant_fs)),
                            consequent=tuple(sorted(con_fs)),
                            support=round(sup, 4),
                            confidence=round(conf, 4),
                            lift=round(lift, 4),
                            n_recipes=int(sup * n)
                        ))
        return sorted(rules, key=lambda r: -r.lift)

    def top_rules(self, n: int = 20) -> list:
        return self.rules_[:n]

    def rules_for_gesture(self, gesture: str) -> list:
        return [r for r in self.rules_
                if gesture in r.antecedent or gesture in r.consequent]

    def to_dataframe(self) -> pd.DataFrame:
        rows = [{"antecedent": " + ".join(r.antecedent),
                 "consequent": " + ".join(r.consequent),
                 "support": r.support, "confidence": r.confidence,
                 "lift": r.lift, "n_recipes": r.n_recipes}
                for r in self.rules_]
        return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# SPM séquentiel (PrefixSpan) — ordre respecté
# ---------------------------------------------------------------------------

class PrefixSpanSPM:
    """
    PrefixSpan : mining de patterns séquentiels ordonnés.
    Exploite l'ordre des gestes tel qu'il existe dans les graphes.

    Connexion directe au pipeline de reconnaissance :
      Les règles à fort lift identifient les gestes "déclencheurs" —
      ceux dont la présence au début d'une séquence observée permet
      d'éliminer le plus de recettes candidates immédiatement.
    """

    def __init__(self, min_support: float = 0.1, max_pattern_length: int = 4):
        self.min_support        = min_support
        self.max_pattern_length = max_pattern_length
        self.patterns_          : list = []   # [(support, [actions])]
        self.rules_             : list = []
        self._n                 : int  = 0

    def fit(self, sequences: list) -> "PrefixSpanSPM":
        self._n      = len(sequences)
        min_count    = max(1, int(self.min_support * self._n))
        print(f"[PrefixSpan] {self._n} séquences  "
              f"min_support={self.min_support} ({min_count} recettes min)")

        self.patterns_ = []
        self._mine([], sequences, min_count)
        self.patterns_.sort(key=lambda x: -x[0])
        self.rules_ = self._build_rules()
        print(f"[PrefixSpan] {len(self.patterns_)} patterns  "
              f"{len(self.rules_)} règles séquentielles")
        return self

    def _mine(self, prefix: list, projected: list, min_count: int):
        if len(prefix) >= self.max_pattern_length:
            return
        counts = defaultdict(int)
        for seq in projected:
            seen = set()
            for item in seq:
                if item not in seen:
                    counts[item] += 1
                    seen.add(item)
        for item, cnt in counts.items():
            if cnt < min_count:
                continue
            new_prefix = prefix + [item]
            self.patterns_.append((round(cnt / self._n, 4), new_prefix))
            new_proj = []
            for seq in projected:
                for i, s in enumerate(seq):
                    if s == item:
                        suffix = seq[i + 1:]
                        if suffix:
                            new_proj.append(suffix)
                        break
            if new_proj:
                self._mine(new_prefix, new_proj, min_count)

    def _build_rules(self) -> list:
        pat_sup = {tuple(p): s for s, p in self.patterns_}
        rules   = []
        for sup, pattern in self.patterns_:
            if len(pattern) < 2:
                continue
            ant = tuple(pattern[:-1])
            con = (pattern[-1],)
            ant_sup = pat_sup.get(ant, 0)
            con_sup = pat_sup.get(con, 0)
            if ant_sup == 0 or con_sup == 0:
                continue
            conf = sup / ant_sup
            lift = conf / con_sup
            rules.append(AssociationRule(
                antecedent=ant,
                consequent=con,
                support=round(sup, 4),
                confidence=round(conf, 4),
                lift=round(lift, 4),
                n_recipes=int(sup * self._n)
            ))
        return sorted(rules, key=lambda r: -r.lift)

    def top_patterns(self, n: int = 20) -> list:
        return self.patterns_[:n]

    def top_rules(self, n: int = 20) -> list:
        return self.rules_[:n]

    def trigger_gestures(self, top_n: int = 10) -> list:
        """
        Identifie les gestes déclencheurs : ceux dont la présence en
        antécédent prédit le plus fortement la suite (lift max).

        Directement utile pour la reconnaissance en temps réel :
        dès qu'un geste déclencheur est observé → filtre agressif
        sur l'espace de recettes candidates.
        """
        best = defaultdict(float)
        best_rule = {}
        for rule in self.rules_:
            for g in rule.antecedent:
                if rule.lift > best[g]:
                    best[g]      = rule.lift
                    best_rule[g] = rule
        ranked = sorted(best.items(), key=lambda x: -x[1])[:top_n]
        return [{"gesture": g, "max_lift": lift,
                 "best_rule": best_rule[g]} for g, lift in ranked]

    def to_dataframe(self) -> pd.DataFrame:
        rows = [{"antecedent": " → ".join(r.antecedent),
                 "consequent": r.consequent[0],
                 "support": r.support, "confidence": r.confidence,
                 "lift": r.lift, "n_recipes": r.n_recipes}
                for r in self.rules_]
        return pd.DataFrame(rows).sort_values("lift", ascending=False)


# ---------------------------------------------------------------------------
# Analyse MBA intra-cluster (validation des clusters FSM)
# ---------------------------------------------------------------------------

def analyze_clusters_with_mba(cluster_assignments: dict,
                               sequences: dict,
                               min_support: float = 0.2) -> dict:
    """
    Applique PrefixSpan sur chaque cluster séparément.
    Permet de valider la cohérence des clusters FSM :
    un bon cluster doit présenter des règles internes à lift élevé.

    Args:
        cluster_assignments : { recipe_id: cluster_id }
        sequences           : { recipe_id: [action, ...] }
        min_support         : seuil intra-cluster

    Retourne { cluster_id: PrefixSpanSPM }
    """
    cluster_seqs = defaultdict(list)
    for rid, cid in cluster_assignments.items():
        if rid in sequences:
            cluster_seqs[cid].append(sequences[rid])

    results = {}
    for cid, seqs in sorted(cluster_seqs.items()):
        if cid == -1:
            continue
        print(f"\n[Cluster {cid}] {len(seqs)} recettes")
        spm = PrefixSpanSPM(min_support=min_support, max_pattern_length=3)
        spm.fit(seqs)
        results[cid] = spm
    return results
