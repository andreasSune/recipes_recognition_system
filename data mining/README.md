# Pattern Mining — FSM + MBA sur les Graphes de Recettes

**Laboratoire Liara, UQAC**  
Projet : Reconnaissance automatique de recettes par analyse de gestes culinaires

---

## Problème résolu dans cette branche

Le pipeline principal du projet (Pipelines 1–3) a produit plus d'un million de
recettes modélisées comme des **graphes dirigés pondérés** stockés dans
`recipe_graphs.db`. Chaque nœud est un geste culinaire physique observable
(couper, mélanger, verser…), chaque arête est une transition séquentielle
pondérée par son nombre d'occurrences cumulées sur toutes les variantes.

**Le problème** : avec plus d'un million de recettes, la reconnaissance en
temps réel ne peut pas comparer naïvement chaque séquence de gestes observée
contre l'intégralité du corpus. Il faut une structure intermédiaire qui
organise les recettes en groupes cohérents et identifie les gestes les plus
discriminants pour filtrer rapidement.

**Ce que ce module résout** : avant d'entraîner un GNN, on cherche à
comprendre la structure intrinsèque des données en répondant à trois questions :

1. **Quels enchaînements de gestes reviennent dans de nombreuses recettes ?**
   → *Frequent Subgraph Mining (FSM)*

2. **Si un geste est observé, lequel prédit le plus fortement la suite ?**
   → *Market Basket Analysis séquentiel (MBA / PrefixSpan)*

3. **Peut-on regrouper les recettes en familles culinaires cohérentes
   en se basant uniquement sur leurs patterns de gestes communs ?**
   → *Clustering sur vecteurs FSM*

---

## Questions soulevées par cette analyse

| Question | Méthode | Sortie exploitable |
|----------|---------|-------------------|
| Quels sous-graphes de gestes sont universels ? | FSM | Patterns fréquents + support |
| Quels gestes co-occurent souvent ? | Apriori (MBA) | Règles {X} ⟹ {Y} avec lift |
| Quel geste prédit le mieux la suite ? | PrefixSpan (SPM) | Gestes déclencheurs (lift max) |
| Les recettes forment-elles des familles naturelles ? | Clustering (K-Means) | Assignations cluster par recette |
| Un cluster est-il cohérent culinairement ? | MBA intra-cluster | Règles internes à lift élevé |

---

## Comment cette analyse prépare l'étape GNN

Le passage au GNN nécessite de résoudre deux problèmes préalables que
FSM + MBA adressent directement :

### 1. Initialisation des features (matrice X)

Un GNN a besoin d'une représentation initiale pour chaque nœud et chaque
graphe. Les vecteurs binaires produits par `fsm.vectorize_recipes()` fournissent
une **matrice de features globales** par graphe : chaque recette est représentée
par les patterns fréquents qu'elle contient. Cette matrice sert de point de
départ pour l'entraînement ou de baseline de comparaison.

### 2. Réduction de l'espace de classes

Avec 1M+ de recettes, une classification directe par GNN est inenvisageable.
Le clustering FSM organise les recettes en N familles (N << 1M). Le GNN
opère alors en deux niveaux :
- **Niveau 1** : identifier le cluster (N classes, petit espace)
- **Niveau 2** : recherche fine dans le cluster (K recettes, espace réduit)

### 3. Validation des représentations apprises

Les patterns FSM constituent une **vérité terrain interprétable** : si le GNN
apprend des embeddings, on peut vérifier que des recettes partageant les mêmes
patterns FSM se retrouvent proches dans l'espace latent GNN. C'est un critère
de validation sans étiquettes.

### 4. Gestes déclencheurs pour la reconnaissance temps réel

Les gestes à fort lift (identifiés par PrefixSpan) alimentent directement la
logique de reconnaissance incrémentale : dès qu'un premier geste est observé
par le capteur, les règles MBA filtrent agressivement l'espace de recettes
candidates avant même que le GNN soit sollicité.

---

## Structure du programme

```
pattern_mining/
├── data_preparation.py   ← chargement depuis recipe_graphs.db
├── mba_sequential.py     ← Apriori + PrefixSpan
├── fsm_recipes.py        ← FSM + clustering
├── run_pipeline.py       ← script principal
└── README.md             ← ce fichier
```

---

## Description des 4 fichiers principaux

### `data_preparation.py`

Point d'entrée unique vers `recipe_graphs.db`. Contient :

- `load_graphs_from_db(db_path, limit)` — charge les graphes NetworkX en
  excluant automatiquement le nœud virtuel START et ses arêtes. Les poids
  des arêtes (occurrences cumulées sur toutes les variantes) sont conservés.

- `load_sequences_from_db(db_path, limit)` — reconstruit la séquence
  principale de chaque recette en suivant le chemin de poids maximum depuis
  START dans le graphe stocké.

- `load_metadata_from_db(db_path, limit)` — charge titres, statistiques
  structurelles, détection de cycles et points d'entrée.

- `describe_corpus(graphs, sequences, metadata)` — statistiques descriptives :
  gestes uniques, transitions les plus fréquentes, longueurs moyennes.

- `make_synthetic_data(n)` — génère un corpus jouet pour tester le pipeline
  sans avoir besoin de `recipe_graphs.db`.

---

### `mba_sequential.py`

Analyse des associations entre gestes. Contient deux classes :

**`AprioriMBA`** — co-occurrence sans ordre  
Répond à : *"Quels gestes apparaissent ensemble dans les mêmes recettes ?"*  
Produit des règles du type `{marinate, slice} ⟹ {saute}` avec support,
confiance et lift. Utile pour détecter des familles de gestes
indépendamment de leur séquence.

**`PrefixSpanSPM`** — patterns séquentiels ordonnés  
Répond à : *"Si ce geste est observé, quel geste suivant est le plus probable ?"*  
La méthode `trigger_gestures()` retourne les gestes dont la présence en
antécédent prédit le plus fortement la suite (lift maximum). Ce sont les
gestes à surveiller en priorité dans le pipeline de reconnaissance temps réel.

`analyze_clusters_with_mba(assignments, sequences)` applique PrefixSpan
séparément sur chaque cluster pour valider sa cohérence interne.

---

### `fsm_recipes.py`

Mining de sous-graphes fréquents sur les graphes de recettes. Contient :

**`RecipeFSM`** — classe principale  
Paramètre clé : `min_support` (ex. 0.05 = pattern présent dans ≥5% des
recettes). Utilise l'anti-monotonie d'Apriori pour élaguer efficacement :
si `A → B` est rare, toute extension `A → B → C` l'est aussi.

Le paramètre `min_edge_weight` (recommandé : 2 sur vraies données) filtre
les transitions instables vues dans une seule variante de recette.

`fsm.vectorize_recipes()` est la sortie principale : une matrice binaire
(n_recettes × n_patterns) directement utilisable pour le clustering et
comme features initiales pour le GNN.

**`cluster_recipes_from_fsm(fsm)`** — clustering sur les vecteurs binaires  
Supporte K-Means (nombre de clusters fixé) et HDBSCAN (automatique).

**`describe_clusters(assignments, metadata, fsm)`** — résumé lisible des
clusters : taille, patterns dominants, exemples de titres de recettes.

---

### `run_pipeline.py`

Orchestre les 5 étapes dans l'ordre :

```
Étape 1 — MBA Apriori       : règles de co-occurrence
Étape 2 — SPM PrefixSpan   : règles séquentielles + gestes déclencheurs
Étape 3 — FSM              : sous-graphes fréquents
Étape 4 — Clustering       : familles de recettes
Étape 5 — MBA intra-cluster: validation de la cohérence des clusters
```

---

## Démarrage rapide

### Prérequis

```bash
pip install networkx pandas numpy scikit-learn
# Optionnel pour clustering automatique :
pip install hdbscan
```

### Test avec données synthétiques

```bash
python run_pipeline.py --synthetic --limit 500
```

### Exécution sur recipe_graphs.db

```bash
# Début recommandé : sous-ensemble de 10 000 recettes
python run_pipeline.py \
    --db /chemin/vers/recipe_graphs.db \
    --limit 10000 \
    --min_support 0.05 \
    --min_edge_weight 2

# Corpus complet (1M recettes) — prévoir 30–60 min
python run_pipeline.py \
    --db /chemin/vers/recipe_graphs.db \
    --min_support 0.01 \
    --min_edge_weight 2 \
    --min_lift 1.5
```

### Utilisation dans un notebook

```python
from data_preparation import load_graphs_from_db, load_sequences_from_db, \
                              load_metadata_from_db, describe_corpus
from fsm_recipes import RecipeFSM, cluster_recipes_from_fsm, describe_clusters
from mba_sequential import PrefixSpanSPM

DB = "recipe_graphs.db"

graphs    = load_graphs_from_db(DB, limit=5000)
sequences = load_sequences_from_db(DB, limit=5000)
metadata  = load_metadata_from_db(DB, limit=5000)

describe_corpus(graphs, sequences, metadata)

# FSM
fsm = RecipeFSM(min_support=0.05, min_edge_weight=2)
fsm.fit(graphs)
print(fsm.to_dataframe().head(20))

# Clustering
assignments = cluster_recipes_from_fsm(fsm, method="kmeans")
print(describe_clusters(assignments, metadata, fsm))

# MBA séquentiel
spm = PrefixSpanSPM(min_support=0.05)
spm.fit(list(sequences.values()))
print(spm.to_dataframe().head(20))
print("Gestes déclencheurs :", spm.trigger_gestures(5))

# Matrice de features pour GNN
matrix, recipe_ids, pattern_labels = fsm.vectorize_recipes()
# → matrix.shape = (n_recettes, n_patterns)
# → utilisable directement comme features dans PyTorch Geometric
```

---

## Conseils de paramétrage

| Corpus | `min_support` | `min_edge_weight` | `max_pattern_length` |
|--------|--------------|-------------------|----------------------|
| Test (< 1 000 recettes) | 0.08–0.15 | 1 | 3–4 |
| Moyen (10 000–100 000) | 0.03–0.08 | 2 | 3–4 |
| Complet (1M+) | 0.01–0.03 | 2–3 | 3 |

Un `min_support` trop bas produit des milliers de patterns redondants et
ralentit le clustering. Un `min_support` trop haut ne retient que les gestes
banals (mix, add) qui ne discriminent pas entre familles de recettes.

---

*Document rédigé dans le cadre du projet de reconnaissance de recettes par
gestes culinaires — Laboratoire Liara, UQAC, 2026.*
