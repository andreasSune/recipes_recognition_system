# Plan de Conception : Pipeline de Construction de Graphes de Recettes

##  Objectif Global

Construire **1 graphe orienté pondéré par recette** à partir des variantes, puis stocker dans SQLite pour usage ultérieur (reconnaissance, ML/GNN).

---

##  1. Structure des Données

### Input (Dataset)
- **Format** : DataFrame pandas
- **Colonnes** :
  - `id` : identifiant unique de la recette (plusieurs lignes = même id)
  - `title` : nom de la recette
  - `actions` : liste Python de gestes culinaires
  - `type_2` : type de variante (`variante_principale`, `variante_ingredients`, `variante_permutation`)

### Contraintes
- Toutes les recettes ont **1 variante principale** (obligatoire)
- Variantes ingrédients et permutations sont **optionnelles**
- Groupement par `id` pour fusionner les variantes

---

##  2. Structure du Graphe

### Définition
- **Type** : Graphe orienté pondéré `G = (V, E)`
- **Bibliothèque** : NetworkX
- **Propriétés** :
  - Connexe (grâce au nœud START)
  - Cycles possibles (ex: `stir → transfer → stir`)
  - Pas de nœud END (recettes finissent de manière homogène)

### Nœuds (V)
- **Nœud START** : virtuel, point d'entrée unique
- **Nœuds d'actions** : gestes culinaires uniques

**Attributs des nœuds** :
```python
{
    'action': str,              # Nom du geste (ex: 'chop')
    'occurrence_count': int,    # Nombre total d'occurrences dans toutes variantes
    'is_virtual': bool          # True si START, False sinon
}
```

### Arêtes (E)
- **Arêtes orientées** : transitions séquentielles `A → B`

**Attributs des arêtes** :
```python
{
    'source': str,    # Nœud de départ
    'target': str,    # Nœud d'arrivée
    'weight': int     # Nombre total d'occurrences de cette transition
}
```

### Poids des arêtes
- **Définition** : Nombre total de fois que la transition apparaît dans **toutes les variantes combinées**
- **Exemple** : Si `fry → add` apparaît 1× dans variante principale, 1× dans variante ingrédients, 2× dans permutations → `weight = 4`

---

##  3. Algorithme de Construction

### Phase 1 : Préparation
1. Charger le DataFrame
2. Grouper par `id` → obtenir toutes les variantes d'une recette
3. Valider la présence de `variante_principale`

### Phase 2 : Initialisation du graphe
1. Créer graphe vide NetworkX (`nx.DiGraph()`)
2. Ajouter nœud virtuel START

### Phase 3 : Construction des nœuds
1. Parcourir toutes les variantes de la recette
2. Pour chaque action dans chaque variante :
   - Ajouter le nœud si nouveau
   - Incrémenter `occurrence_count` si existe déjà

### Phase 4 : Construction des arêtes
1. Pour chaque variante :
   - Créer arête `START → première_action`
   - Pour chaque paire consécutive `(action[i], action[i+1])` :
     - Ajouter arête si nouvelle
     - Incrémenter `weight` si existe déjà

### Phase 5 : Métadonnées
1. Calculer statistiques du graphe :
   - Nombre de nœuds
   - Nombre d'arêtes
   - Points d'entrée (successeurs de START)
   - Détection de cycles
   - Nombre de variantes utilisées

---

##  4. Stockage (SQLite)

### Structure de la base de données

**Fichier unique** : `recipe_graphs.db`

#### Table 1 : `nodes`
```sql
CREATE TABLE nodes (
    recipe_id TEXT,
    action TEXT,
    occurrence_count INTEGER,
    is_virtual INTEGER,  -- 0 ou 1 (pour START)
    PRIMARY KEY (recipe_id, action)
);

CREATE INDEX idx_nodes_recipe ON nodes(recipe_id);
```

#### Table 2 : `edges`
```sql
CREATE TABLE edges (
    recipe_id TEXT,
    source TEXT,
    target TEXT,
    weight INTEGER,
    PRIMARY KEY (recipe_id, source, target)
);

CREATE INDEX idx_edges_recipe ON edges(recipe_id);
```

#### Table 3 : `metadata` (optionnelle)
```sql
CREATE TABLE metadata (
    recipe_id TEXT PRIMARY KEY,
    title TEXT,
    num_nodes INTEGER,
    num_edges INTEGER,
    num_variants INTEGER,
    has_cycles INTEGER,
    entry_points TEXT  -- JSON ou séparé par virgules
);
```

### Opérations de base
- **Sauvegarder** : Convertir NetworkX → tables SQL
- **Charger** : Query SQL → reconstruire NetworkX
- **Rechercher** : Query par `recipe_id`

---

##  5. Pipeline de Traitement

### Workflow global
```
INPUT : DataFrame complet (toutes les recettes)
    ↓
ÉTAPE 1 : Grouper par recipe_id
    ↓
ÉTAPE 2 : Pour chaque recette (traitement par batch)
    ├─ Extraire variantes
    ├─ Construire graphe NetworkX
    ├─ Valider structure
    └─ Sauvegarder dans SQLite
    ↓
OUTPUT : recipe_graphs.db
```

### Gestion de la mémoire
- **Traitement par batch** : 10 000 recettes à la fois
- Libération mémoire entre chaque batch
- Pas de chargement complet du dataset en RAM

### Gestion des erreurs
- Validation de chaque graphe avant sauvegarde :
  - Au moins 1 nœud (hors START)
  - Au moins 1 arête depuis START
  - Pas de nœuds isolés
- Log des recettes problématiques
- Possibilité de reprendre après interruption

---

##  6. Fonction de Visualisation

### Spécifications

**Fonction** : `visualize_graph(recipe_id)`

**Paramètre** :
- `recipe_id` : identifiant de la recette à visualiser

**Comportement** :
1. Charger le graphe depuis SQLite
2. Générer visualisation avec mise en forme :
   - **Nœud START** : couleur distincte (ex: vert)
   - **Autres nœuds** : taille proportionnelle à `occurrence_count`
   - **Arêtes** : épaisseur proportionnelle au `weight`
   - **Labels** : noms des actions
3. Layout intelligent (ex: layout hiérarchique depuis START)
4. Affichage ou sauvegarde (PNG/SVG)

**Options supplémentaires** :
- Colorier les nœuds par catégorie culinaire (découpe, mélange, etc.)
- Afficher/masquer les poids
- Mettre en évidence les cycles
- Export en format interactif (HTML avec D3.js ou Plotly)

**Librairies** :
- `matplotlib` (visualisation statique)
- `plotly` (visualisation interactive)

---

##  7. Validation

### Tests unitaires
- Construction de graphe sur 1 recette simple
- Vérification des poids (comptage manuel vs automatique)
- Détection de cycles
- Conversion NetworkX ↔ SQLite (aller-retour)

### Tests d'intégration
- Pipeline complet sur 100 recettes
- Vérification cohérence (nombre de graphes = nombre de recipe_id uniques)
- Performance (temps de traitement)

### Validation visuelle
- Visualiser 10 recettes aléatoires
- Vérifier que les graphes font sens culinairement
- Identifier anomalies potentielles

---

##  8. Modules et Organisation

### Structure du code
```
projet/
├── data/
│   └── recipe_graphs.db          # Base de données SQLite
│
├── src/
│   ├── graph_builder.py          # Construction du graphe
│   ├── db_manager.py             # Interface SQLite
│   ├── visualizer.py             # Visualisation
│   └── utils.py                  # Fonctions utilitaires
│
├── notebooks/
│   ├── 01_exploration.ipynb      # Exploration dataset
│   ├── 02_graph_construction.ipynb  # Construction graphes
│   └── 03_visualization.ipynb    # Tests de visualisation
│
└── tests/
    ├── test_graph_builder.py
    ├── test_db_manager.py
    └── test_visualizer.py
```

### Modules principaux

#### Module 1 : `graph_builder.py`
- Classe `RecipeGraphBuilder`
- Méthode `build_graph(recipe_id, variantes)` → NetworkX Graph
- Validation du graphe

#### Module 2 : `db_manager.py`
- Classe `GraphDatabase`
- Méthodes :
  - `save_graph(recipe_id, graph)`
  - `load_graph(recipe_id)` → NetworkX Graph
  - `delete_graph(recipe_id)`
  - `list_all_recipes()` → liste des IDs
  - `get_statistics()` → stats globales

#### Module 3 : `visualizer.py`
- Fonction `visualize_graph(recipe_id, **options)`
- Fonction `compare_graphs(recipe_id_1, recipe_id_2)` (bonus)
- Fonction `export_to_html(recipe_id)` (interactif)

#### Module 4 : `utils.py`
- Fonctions de validation
- Calcul de métriques (densité, cycles, etc.)
- Helpers divers

---

##  9. Extensibilité Future

### Prêt pour ML/GNN
- Graphes facilement convertibles en PyTorch Geometric
- Ajout futur de features sur nœuds/arêtes
- Export vers formats ML (matrices, embeddings)

### Scalabilité
- Architecture batch permet passage à l'échelle
- SQLite peut gérer millions de graphes
- Migration vers PostgreSQL possible si nécessaire

### Enrichissements possibles
- Ajout de features textuelles (Word2Vec des actions)
- Catégorisation automatique des nœuds
- Calcul de similarité entre graphes
- Système de requêtes complexes (graphes contenant X et Y)






---

##  Notes de Configuration

### Dataset
- **Format actions** : Liste Python
- **Colonnes** : `id`, `title`, `actions`, `type_2`
- **Groupement** : Par `id`

### Visualisation
- **Librairies** : matplotlib (statique) + plotly (interactif)
- **Export** : PNG, SVG, HTML

### Traitement
- **Batch size** : 10 000 recettes
- **Tests initiaux** : 100-1000 recettes

---

*Document créé le : 2026-01-26*  
*Projet : Reconnaissance de recettes par gestes culinaires - Laboratoire Liara, UQAC*