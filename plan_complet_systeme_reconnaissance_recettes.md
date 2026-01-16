# Plan Complet - Système de Reconnaissance de Recettes par Séquence de Gestes

**Projet:** Reconnaissance de recettes de cuisine pour assistance aux personnes vulnérables  
**Laboratoire:** Liara, UQAC  
**Dataset:** 1,029,697 recettes | 31,999,917 instructions  
**Date:** Novembre 2025

---

## Table des Matières

1. [Vue d'ensemble du système](#1-vue-densemble-du-système)
2. [Stratégie 1 : Trie + Scoring Multi-critères](#2-stratégie-1--trie--scoring-multi-critères)
3. [Stratégie 2 : Graph Neural Networks (GNN)](#3-stratégie-2--graph-neural-networks-gnn)
4. [Stratégie 3 : Arbres de Décision](#4-stratégie-3--arbres-de-décision)
5. [Stratégie 4 : Clustering + Prototypes](#5-stratégie-4--clustering--prototypes)
6. [Recommandations d'implémentation](#6-recommandations-dimplémentation)
7. [Métriques d'évaluation](#7-métriques-dévaluation)
8. [Roadmap et Timeline](#8-roadmap-et-timeline)

---

## 1. Vue d'ensemble du système

### 1.1 Contexte et objectifs

**Problématique:**
- Assister des personnes avec capacités restreintes (âgées, Alzheimer) dans la préparation de repas
- Identifier quelle recette est en cours de préparation à partir d'une séquence de gestes observés
- Fournir un suivi et des alertes en temps réel

**Contraintes:**
- Dataset massif : 1M+ recettes
- Reconnaissance en temps réel (gestes arrivent séquentiellement)
- Ressources limitées (pas de fine-tuning coûteux)
- Gestion de multiples variantes par recette

**Input:** Séquence de gestes observés `[a₁, a₂, a₃, ..., aₙ]`  
**Output:** Top-K recettes candidates avec scores de confiance

### 1.2 Représentation des données

**Format des recettes:**
```python
{
    "recipe_id": "R123456",
    "nom": "Omelette aux champignons",
    "ingredients": [...],
    "variante_principale": {
        "actions": ["breakEgg", "whisk", "pour", "add", "fold", "flip"],
        "graph": nx.DiGraph(...)
    },
    "variante_ingredients": {
        "actions": ["slice", "breakEgg", "whisk", "pour", "add", "fold", "flip"],
        "graph": nx.DiGraph(...)
    },
    "variante_permutations": [
        {"actions": [...], "graph": ...},
        ...
    ]
}
```

**Structure des graphes:**
- **Nœuds:** Gestes de cuisine (verbes normalisés)
- **Arêtes:** Transitions séquentielles avec probabilités
- **Propriétés:** Poids, probabilités de transition

### 1.3 Paradigmes d'approche

Les 4 stratégies explorent 3 paradigmes complémentaires:

| Paradigme | Stratégies | Avantages | Inconvénients |
|-----------|-----------|-----------|---------------|
| **Symbolique** | 1, 3 | Interprétable, pas d'entraînement | Peut être rigide |
| **Apprentissage** | 2 | Capture patterns complexes | Nécessite données d'entraînement |
| **Hybride** | 4 | Combine avantages des deux | Plus complexe |

---

## 2. Stratégie 1 : Trie + Scoring Multi-critères

### 2.1 Vue d'ensemble

**Principe:** Structure arborescente des séquences de gestes pour filtrage rapide + scoring sophistiqué pour classement.

**Priorité:** 🥇 **PRIORITÉ ABSOLUE** - À implémenter en premier

**Avantages:**
- ✅ Évolutivité O(m) indépendante du nombre de recettes
- ✅ Gestion naturelle du temps réel
- ✅ Interprétable et debuggable
- ✅ Pas besoin d'entraînement
- ✅ Gère nativement les variantes

### 2.2 Architecture détaillée

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 0 : PREPROCESSING                   │
│  Construction du Trie (offline, one-time)                   │
│  - Parse toutes les recettes et leurs variantes             │
│  - Construit l'arbre préfixe avec métadonnées               │
│  - Sérialisation pour chargement rapide                     │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               ENTRÉE : Séquence de gestes [a₁, a₂, ...]      │
│  Format: List[str] - arrive progressivement en temps réel   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           NIVEAU 1 : NAVIGATION DANS LE TRIE                │
│                                                              │
│  Étape 1.1 : Descente exacte                                │
│    - Pour chaque geste aᵢ, descendre au nœud enfant        │
│    - Accumuler les recettes candidates                      │
│    - Complexité: O(m) où m = longueur de séquence          │
│                                                              │
│  Étape 1.2 : Fuzzy Matching (si chemin bloqué)             │
│    - Recherche de chemins similaires (distance d'édition)   │
│    - Tolérance aux erreurs de détection                     │
│    - Suggestions alternatives                                │
│                                                              │
│  Output : Ensemble de recettes candidates (50-500)          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         NIVEAU 2 : SCORING MULTI-CRITÈRES                   │
│                                                              │
│  Pour chaque recette candidate, calculer 4 scores:         │
│                                                              │
│  Score 1 : COVERAGE (couverture)                            │
│    Formule: coverage = |actions_observées ∩ actions_recette|│
│                        / |actions_recette|                  │
│    Interprétation: % de la recette déjà effectué           │
│                                                              │
│  Score 2 : POSITION (respect de l'ordre)                    │
│    Formule: position = Σ(match_at_correct_index) / n       │
│    Interprétation: Les gestes sont-ils dans le bon ordre?  │
│                                                              │
│  Score 3 : COMPLETION (avancement)                          │
│    Formule: completion = position_moyenne / longueur_recette│
│    Interprétation: Où en est-on dans la recette?           │
│                                                              │
│  Score 4 : TRANSITION (probabilités de graphe)              │
│    Formule: transition = Π P(aᵢ → aᵢ₊₁) ^ (1/n-1)          │
│    Interprétation: Les transitions sont-elles plausibles?  │
│                                                              │
│  Score Final : Combinaison pondérée                         │
│    S = w₁·coverage + w₂·position + w₃·completion +         │
│        w₄·transition                                        │
│    Poids suggérés: [0.3, 0.3, 0.2, 0.2]                   │
│                                                              │
│  Seuil adaptatif selon nombre de gestes:                   │
│    - 1-2 gestes: seuil = 0.3 (exploratoire)               │
│    - 3-5 gestes: seuil = 0.5 (confirmation)               │
│    - 6+ gestes: seuil = 0.7 (haute confiance)             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              NIVEAU 3 : POST-TRAITEMENT                      │
│                                                              │
│  - Tri par score décroissant                                │
│  - Normalisation des scores (softmax optionnel)             │
│  - Détection d'ambiguïté (écart entre top-1 et top-2)      │
│  - Génération d'explications                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  SORTIE : TOP-K RÉSULTATS                    │
│                                                              │
│  Format:                                                     │
│  [                                                           │
│    {                                                         │
│      "recipe_id": "R123",                                   │
│      "nom": "Omelette",                                     │
│      "score": 0.87,                                         │
│      "confidence": "high",                                  │
│      "coverage": 0.85,                                      │
│      "position": 0.90,                                      │
│      "explanation": "8/10 gestes matchés, ordre correct"   │
│    },                                                        │
│    ...                                                       │
│  ]                                                           │
│                                                              │
│  Cas particuliers:                                          │
│  - Score max > seuil → Identification sûre                  │
│  - Ambiguïté → "Continuez, plusieurs recettes possibles"   │
│  - Aucun candidat → "Recette inconnue ou hors dataset"     │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Structure du Trie

**Définition du nœud:**
```python
class TrieNode:
    def __init__(self):
        self.children = {}  # Dict[str, TrieNode] - geste -> nœud enfant
        self.recipes = []   # List[RecipeReference] - recettes passant par ce nœud
        self.depth = 0      # Profondeur dans l'arbre
        self.frequency = 0  # Nombre de recettes passant ici
        self.is_terminal = False  # Fin de séquence
        
class RecipeReference:
    def __init__(self, recipe_id, variant_type, full_sequence, graph):
        self.recipe_id = recipe_id
        self.variant_type = variant_type  # 'principale', 'ingredients', 'permutation'
        self.full_sequence = full_sequence
        self.graph = graph  # Pour calcul du score transition
```

**Exemple de structure:**
```
                    ROOT
                   /  |  \
            breakEgg cut pour
               /       |      \
           whisk    slice   heat
             /         |        \
          pour      fry      stir
          /  \        |         \
       fold  add   season     mix
        |     |       |          |
    [R1,R3] [R2]   [R4]      [R5,R6]
```

### 2.4 Algorithmes clés

**Algorithme 1: Construction du Trie**
```
fonction BUILD_TRIE(recettes):
    root = nouveau TrieNode()
    
    pour chaque recette dans recettes:
        pour chaque variante dans recette.variantes:
            sequence = variante.actions
            nœud_actuel = root
            
            pour chaque geste dans sequence:
                si geste non dans nœud_actuel.children:
                    nœud_actuel.children[geste] = nouveau TrieNode()
                
                nœud_actuel = nœud_actuel.children[geste]
                nœud_actuel.recipes.append(RecipeReference(...))
                nœud_actuel.frequency += 1
            
            nœud_actuel.is_terminal = True
    
    retourner root
```

**Algorithme 2: Recherche exacte**
```
fonction SEARCH_EXACT(root, sequence_observée):
    nœud_actuel = root
    candidats = set()
    
    pour chaque geste dans sequence_observée:
        si geste dans nœud_actuel.children:
            nœud_actuel = nœud_actuel.children[geste]
            candidats.update(nœud_actuel.recipes)
        sinon:
            retourner FUZZY_SEARCH(nœud_actuel, geste, sequence_restante)
    
    retourner candidats
```

**Algorithme 3: Fuzzy Matching**
```
fonction FUZZY_SEARCH(nœud, geste_manquant, tolerance=1):
    candidats_fuzzy = []
    
    pour chaque geste_enfant dans nœud.children:
        distance = edit_distance(geste_manquant, geste_enfant)
        
        si distance <= tolerance:
            candidats_fuzzy.extend(nœud.children[geste_enfant].recipes)
    
    retourner candidats_fuzzy
```

**Algorithme 4: Scoring**
```
fonction CALCULATE_SCORE(recette, sequence_observée):
    # Score 1: Coverage
    gestes_recette = set(recette.full_sequence)
    gestes_observés = set(sequence_observée)
    coverage = len(gestes_recette ∩ gestes_observés) / len(gestes_recette)
    
    # Score 2: Position
    positions_correctes = 0
    pour i, geste dans enumerate(sequence_observée):
        si geste dans recette.full_sequence:
            idx_attendu = recette.full_sequence.index(geste)
            si abs(i - idx_attendu) <= 2:  # tolérance de position
                positions_correctes += 1
    position = positions_correctes / len(sequence_observée)
    
    # Score 3: Completion
    dernière_position = max([recette.full_sequence.index(g) 
                             pour g dans sequence_observée 
                             si g dans recette.full_sequence])
    completion = dernière_position / len(recette.full_sequence)
    
    # Score 4: Transition (depuis le graphe)
    transition = 1.0
    pour i dans range(len(sequence_observée) - 1):
        a1, a2 = sequence_observée[i], sequence_observée[i+1]
        si recette.graph.has_edge(a1, a2):
            transition *= recette.graph[a1][a2]['probability']
        sinon:
            transition *= 0.01  # pénalité transition inconnue
    transition = transition ^ (1 / (len(sequence_observée) - 1))
    
    # Score final
    score = 0.3*coverage + 0.3*position + 0.2*completion + 0.2*transition
    
    retourner score, {coverage, position, completion, transition}
```

### 2.5 Optimisations

**Optimisation mémoire:**
- Compression des nœuds avec un seul enfant (path compression)
- Stockage des références plutôt que copies complètes
- Sérialisation binaire pour chargement rapide

**Optimisation vitesse:**
- Cache des calculs de score récents
- Pré-calcul des statistiques de recettes
- Early stopping si score < seuil minimum

**Gestion des variantes:**
- Insertion de toutes les variantes dans le même Trie
- Tag pour différencier les types de variantes
- Priorité aux variantes principales en cas d'égalité

### 2.6 Complexité

| Opération | Complexité temporelle | Complexité spatiale |
|-----------|----------------------|---------------------|
| Construction | O(N × M × L) | O(N × M × L × V) |
| Recherche | O(m) | O(1) |
| Scoring | O(K × m) | O(K) |

Où:
- N = nombre de recettes (1M)
- M = nombre moyen de variantes par recette (3-5)
- L = longueur moyenne d'une séquence (8-15 gestes)
- V = taille moyenne d'un nœud (dépend du facteur de branchement)
- m = longueur de la séquence observée
- K = nombre de candidats retournés par le Trie (50-500)

### 2.7 Exemple de trace d'exécution

**Input:** `["breakEgg", "whisk", "pour"]`

**Étape 1 - Navigation Trie:**
```
ROOT → breakEgg (142,573 recettes)
     → whisk (45,892 recettes)
     → pour (12,334 recettes)
Candidats: 12,334 recettes
```

**Étape 2 - Scoring (top 5):**
```
1. Omelette classique (R45123)
   - Coverage: 0.60 (3/5 gestes)
   - Position: 0.95 (ordre parfait)
   - Completion: 0.60 (60% avancé)
   - Transition: 0.88 (transitions très probables)
   - SCORE FINAL: 0.76

2. Œufs brouillés (R78456)
   - Coverage: 0.75 (3/4 gestes)
   - Position: 1.00
   - Completion: 0.75
   - Transition: 0.92
   - SCORE FINAL: 0.86

3. Crêpes (R23789)
   - Coverage: 0.43 (3/7 gestes)
   - Position: 0.90
   - Completion: 0.43
   - Transition: 0.75
   - SCORE FINAL: 0.63
...
```

**Étape 3 - Output:**
```json
{
  "status": "ambiguous",
  "message": "Plusieurs recettes possibles. Continuez pour affiner.",
  "top_candidates": [
    {
      "recipe_id": "R78456",
      "nom": "Œufs brouillés",
      "score": 0.86,
      "confidence": "medium",
      "next_expected_gestures": ["stir", "season"]
    },
    {
      "recipe_id": "R45123",
      "nom": "Omelette classique",
      "score": 0.76,
      "confidence": "medium",
      "next_expected_gestures": ["fold", "flip"]
    }
  ]
}
```

---

## 3. Stratégie 2 : Graph Neural Networks (GNN)

### 3.1 Vue d'ensemble

**Principe:** Apprendre des représentations vectorielles (embeddings) des graphes de recettes pour recherche par similarité.

**Priorité:** 🏅 **PHASE 2 ou RECHERCHE** - Après validation de Stratégie 1

**Avantages:**
- ✅ Capture la structure complexe des graphes
- ✅ Apprentissage de patterns non évidents
- ✅ Robuste au bruit et variations
- ✅ Recherche rapide via similarité vectorielle (FAISS)

**Inconvénients:**
- ⚠️ Nécessite données d'entraînement annotées
- ⚠️ Coût computationnel élevé (GPU)
- ⚠️ Moins interprétable (boîte noire)
- ⚠️ Complexité d'implémentation

### 3.2 Architecture détaillée

```
┌─────────────────────────────────────────────────────────────┐
│              PHASE 0 : PRÉPARATION DES DONNÉES               │
│                                                              │
│  1. Dataset de graphes de recettes                          │
│     - 1M+ graphes avec variantes                            │
│     - Features des nœuds: one-hot encoding des gestes       │
│     - Features des arêtes: probabilités de transition       │
│                                                              │
│  2. Dataset d'entraînement (si disponible)                  │
│     - Paires (séquence observée, recette correcte)          │
│     - Sinon: génération synthétique via sampling            │
│                                                              │
│  3. Prétraitement                                            │
│     - Normalisation des graphes                             │
│     - Augmentation de données (permutations, sous-séquences)│
│     - Split train/val/test (70/15/15)                       │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 1 : ENCODAGE DES GRAPHES DE RECETTES          │
│                  (Offline - Preprocessing)                   │
│                                                              │
│  Architecture GNN : Graph Convolutional Network (GCN)       │
│                                                              │
│  Couche 1: GCN Layer (input_dim=|vocabulaire|, hidden=128) │
│    - Agrégation des voisins                                 │
│    - Message passing entre nœuds connectés                  │
│    - Output: représentation 128D par nœud                   │
│                                                              │
│  Couche 2: GCN Layer (hidden=128, hidden=256)               │
│    - Deuxième niveau d'agrégation                           │
│    - Capture patterns à plus longue distance                │
│    - Output: représentation 256D par nœud                   │
│                                                              │
│  Couche 3: Global Pooling                                   │
│    - Agrégation de tous les nœuds du graphe                │
│    - Méthodes: Mean pooling, Max pooling, ou Attention     │
│    - Output: représentation 256D du graphe entier          │
│                                                              │
│  Couche 4: MLP (256 → 128 → 64)                             │
│    - Projection vers espace d'embedding final               │
│    - Output: embedding 64D de la recette                    │
│                                                              │
│  Pour chaque recette R:                                     │
│    embedding_R = GNN(graph_R)                               │
│                                                              │
│  Stockage dans index FAISS pour recherche rapide            │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           PHASE 2 : ENTRAÎNEMENT DU MODÈLE                  │
│                                                              │
│  Approche 1: Metric Learning (Triplet Loss)                │
│    - Triplets: (anchor, positive, negative)                │
│    - Anchor: graphe partiel (séquence observée)            │
│    - Positive: graphe de la vraie recette                  │
│    - Negative: graphe d'une autre recette                  │
│    - Loss: L = max(0, d(a,p) - d(a,n) + margin)           │
│                                                              │
│  Approche 2: Contrastive Learning (SimCLR-style)           │
│    - Augmentations: sous-séquences, permutations           │
│    - Maximiser similarité entre vues positives             │
│    - Minimiser similarité avec vues négatives              │
│                                                              │
│  Approche 3: Classification Multi-classe                    │
│    - Si dataset manageable (<100K classes)                 │
│    - Softmax sur toutes les recettes                       │
│    - Loss: Cross-Entropy                                    │
│                                                              │
│  Hyperparamètres suggérés:                                  │
│    - Learning rate: 0.001                                   │
│    - Batch size: 32-64                                      │
│    - Epochs: 50-100                                         │
│    - Optimizer: Adam                                        │
│    - Dropout: 0.2-0.3                                       │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             PHASE 3 : RECONNAISSANCE (Runtime)               │
│                                                              │
│  Input: Séquence observée [a₁, a₂, ..., aₙ]                │
│                                                              │
│  Étape 1: Construction du graphe partiel                    │
│    - Créer un graphe dirigé avec les gestes observés       │
│    - Arêtes entre gestes consécutifs                        │
│    - Features identiques au format d'entraînement          │
│                                                              │
│  Étape 2: Encodage via GNN                                  │
│    embedding_obs = GNN(graphe_partiel)                      │
│    Output: vecteur 64D                                      │
│                                                              │
│  Étape 3: Recherche de similarité                           │
│    - Query FAISS index avec embedding_obs                   │
│    - Récupérer top-K recettes les plus similaires          │
│    - Métriques: Cosine similarity ou L2 distance           │
│                                                              │
│  Étape 4: Post-processing                                   │
│    - Convertir distances en scores de confiance            │
│    - Filtrer par seuil minimum                              │
│    - Retourner top-K avec métadonnées                      │
│                                                              │
│  Output: Top-K recettes candidates                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Architecture du modèle GNN

**Modèle PyTorch Geometric:**
```python
class RecipeGNN(torch.nn.Module):
    def __init__(self, num_node_features, embedding_dim=64):
        super(RecipeGNN, self).__init__()
        
        # Couches de convolution
        self.conv1 = GCNConv(num_node_features, 128)
        self.conv2 = GCNConv(128, 256)
        
        # Couche de pooling global
        self.global_pool = global_mean_pool  # ou global_max_pool, global_add_pool
        
        # MLP final
        self.fc1 = Linear(256, 128)
        self.fc2 = Linear(128, embedding_dim)
        
        self.dropout = Dropout(0.3)
        
    def forward(self, x, edge_index, batch):
        # x: features des nœuds [num_nodes, num_features]
        # edge_index: connexions [2, num_edges]
        # batch: attribution des nœuds aux graphes [num_nodes]
        
        # Première couche GCN + activation
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)
        
        # Deuxième couche GCN
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        
        # Pooling global: graphe → vecteur
        x = self.global_pool(x, batch)
        
        # MLP final
        x = self.fc1(x)
        x = F.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        
        # L2 normalization pour recherche par similarité
        x = F.normalize(x, p=2, dim=1)
        
        return x
```

### 3.4 Génération de données d'entraînement

**Stratégie de génération synthétique** (si pas de données réelles):

```python
def generate_training_samples(recettes, samples_per_recipe=10):
    """
    Génère des paires (graphe_partiel, recette_complète)
    """
    samples = []
    
    for recette in recettes:
        sequence = recette.variante_principale.actions
        
        for _ in range(samples_per_recipe):
            # 1. Échantillonner une longueur de préfixe (30% à 80% de la recette)
            prefix_length = random.randint(
                int(0.3 * len(sequence)), 
                int(0.8 * len(sequence))
            )
            
            # 2. Extraire le préfixe
            partial_sequence = sequence[:prefix_length]
            
            # 3. Optionnel: ajouter du bruit (omissions, erreurs)
            if random.random() < 0.2:  # 20% de chance
                partial_sequence = add_noise(partial_sequence)
            
            # 4. Créer le graphe partiel
            partial_graph = create_graph_from_sequence(partial_sequence)
            
            # 5. Ajouter aux samples
            samples.append({
                'partial_graph': partial_graph,
                'target_recipe_id': recette.recipe_id,
                'full_graph': recette.graph
            })
    
    return samples
```

### 3.5 Fonction de perte (Triplet Loss)

```python
class TripletLoss(torch.nn.Module):
    def __init__(self, margin=1.0):
        super(TripletLoss, self).__init__()
        self.margin = margin
        
    def forward(self, anchor, positive, negative):
        # Distances euclidiennes
        distance_positive = F.pairwise_distance(anchor, positive)
        distance_negative = F.pairwise_distance(anchor, negative)
        
        # Triplet loss
        losses = F.relu(distance_positive - distance_negative + self.margin)
        
        return losses.mean()
```

### 3.6 Index FAISS pour recherche rapide

```python
import faiss

# Construction de l'index
def build_faiss_index(recipe_embeddings, dimension=64):
    """
    recipe_embeddings: numpy array [N, dimension]
    """
    # Index L2 (peut aussi utiliser Inner Product pour cosine)
    index = faiss.IndexFlatL2(dimension)
    
    # Ajout des embeddings
    index.add(recipe_embeddings.astype('float32'))
    
    return index

# Recherche
def search_similar_recipes(query_embedding, index, k=10):
    """
    Retourne les k recettes les plus similaires
    """
    query = query_embedding.reshape(1, -1).astype('float32')
    distances, indices = index.search(query, k)
    
    return indices[0], distances[0]
```

### 3.7 Pipeline d'entraînement complet

```
1. PRÉPARATION (1 semaine)
   - Convertir graphes en format PyG (PyTorch Geometric)
   - Générer données d'entraînement synthétiques
   - Créer DataLoaders
   - Définir splits train/val/test

2. ENTRAÎNEMENT (2-3 jours avec GPU)
   - Initialiser modèle GNN
   - Boucle d'entraînement avec early stopping
   - Validation régulière
   - Sauvegarde meilleur modèle

3. ÉVALUATION (1 jour)
   - Métriques: Precision@K, Recall@K, MRR
   - Analyse des erreurs
   - Ajustement hyperparamètres si nécessaire

4. DÉPLOIEMENT (2-3 jours)
   - Encoder toutes les recettes → embeddings
   - Construire index FAISS
   - Sérialiser pour production
   - Tests de performance (latence, throughput)
```

### 3.8 Variantes et améliorations

**Variante 1: Graph Attention Networks (GAT)**
- Mécanisme d'attention entre nœuds
- Apprentissage de l'importance relative des gestes
- Plus expressif que GCN

**Variante 2: Temporal GNN**
- Prise en compte explicite de l'aspect séquentiel
- Combinaison GNN + LSTM/GRU
- Meilleure capture de l'ordre temporel

**Variante 3: Hierarchical GNN**
- Encodage à plusieurs niveaux de granularité
- Sous-graphes (étapes) → Graphe complet
- Meilleure scalabilité

### 3.9 Complexité

| Opération | Complexité temporelle | Complexité spatiale |
|-----------|----------------------|---------------------|
| Entraînement | O(E × H × L) par epoch | O(N × H) |
| Encoding (par graphe) | O(E × H) | O(V × H) |
| Recherche FAISS | O(N × d) (brute force) | O(N × d) |

Où:
- E = nombre d'arêtes
- V = nombre de nœuds
- H = dimension cachée (128-256)
- d = dimension embedding final (64)
- L = nombre de couches GNN (2-3)
- N = nombre de recettes (1M)

---

## 4. Stratégie 3 : Arbres de Décision

### 4.1 Vue d'ensemble

**Principe:** Classifier les séquences de gestes en recettes via un arbre de décision ou forêt aléatoire basé sur des features extraites.

**Priorité:** 🥉 **BASELINE DE COMPARAISON** - Rapide à tester

**Avantages:**
- ✅ Simple à implémenter (scikit-learn)
- ✅ Rapide en prédiction
- ✅ Interprétable (visualisation de l'arbre)
- ✅ Pas de GPU nécessaire

**Inconvénients:**
- ⚠️ Perte de l'information séquentielle
- ⚠️ Feature engineering critique
- ⚠️ Difficulté avec le temps réel progressif
- ⚠️ Scalabilité limitée (1M classes)

### 4.2 Architecture détaillée

```
┌─────────────────────────────────────────────────────────────┐
│          PHASE 0 : EXTRACTION DE FEATURES                    │
│                                                              │
│  Pour chaque recette, calculer des features représentatives:│
│                                                              │
│  Catégorie 1: Features de présence (Bag-of-Gestures)       │
│    - Vecteur binaire: geste présent ou non                 │
│    - Dimension: |vocabulaire| (ex: 150 gestes)             │
│    - Exemple: [1,0,1,1,0,...] pour "breakEgg, whisk, pour" │
│                                                              │
│  Catégorie 2: Features de fréquence (TF-IDF style)         │
│    - Compter occurrences de chaque geste                   │
│    - Normalisation par longueur de séquence                │
│    - Pondération par rareté (IDF)                          │
│                                                              │
│  Catégorie 3: Features de bigrammes/trigrammes             │
│    - Paires de gestes consécutifs                          │
│    - Ex: (breakEgg, whisk), (whisk, pour)                  │
│    - Capture ordre local                                    │
│                                                              │
│  Catégorie 4: Features statistiques                        │
│    - Longueur de la séquence                               │
│    - Nombre de gestes uniques                              │
│    - Ratio répétitions                                      │
│    - Entropie de la distribution                           │
│                                                              │
│  Catégorie 5: Features de graphe                           │
│    - Nombre de nœuds                                       │
│    - Nombre d'arêtes                                       │
│    - Degré moyen                                           │
│    - Coefficient de clustering                             │
│    - Longueur du plus long chemin                          │
│                                                              │
│  Vecteur final: concaténation de toutes les features      │
│  Dimension typique: 500-2000                                │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            PHASE 1 : CONSTRUCTION DES DATASETS               │
│                                                              │
│  1. Dataset de recettes complètes                           │
│     X = features extraites de chaque recette               │
│     y = recipe_id (label)                                   │
│     Shape: (1M, ~500-2000) → (1M,)                         │
│                                                              │
│  2. Dataset de préfixes (pour gestion temps réel)          │
│     Pour chaque recette, générer plusieurs préfixes:       │
│     - 30% de la séquence → label = recipe_id               │
│     - 50% de la séquence → label = recipe_id               │
│     - 70% de la séquence → label = recipe_id               │
│     - 100% de la séquence → label = recipe_id              │
│                                                              │
│     Cela crée ~4M samples pour entraînement                │
│                                                              │
│  3. Split train/test (80/20)                                │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         PHASE 2 : ENTRAÎNEMENT DU MODÈLE                    │
│                                                              │
│  Option A: Random Forest Classifier                         │
│    - Ensemble de N arbres de décision                      │
│    - Chaque arbre voté pour une classe                     │
│    - Agrégation par vote majoritaire                       │
│                                                              │
│    Hyperparamètres:                                         │
│      n_estimators = 100-500                                │
│      max_depth = 20-50                                     │
│      min_samples_split = 10                                │
│      min_samples_leaf = 5                                  │
│      max_features = 'sqrt'                                 │
│                                                              │
│  Option B: Gradient Boosting (XGBoost/LightGBM)            │
│    - Construction séquentielle des arbres                  │
│    - Chaque arbre corrige les erreurs du précédent        │
│    - Généralement plus performant                          │
│                                                              │
│    Hyperparamètres:                                         │
│      n_estimators = 100-300                                │
│      learning_rate = 0.1                                   │
│      max_depth = 6-10                                      │
│      subsample = 0.8                                       │
│                                                              │
│  Option C: Arbre de décision simple (baseline)             │
│    - Un seul arbre                                         │
│    - Rapide mais moins précis                              │
│    - Utile pour compréhension                              │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              PHASE 3 : PRÉDICTION (Runtime)                  │
│                                                              │
│  Input: Séquence observée [a₁, a₂, ..., aₙ]                │
│                                                              │
│  Étape 1: Extraction de features                            │
│    features_obs = extract_features(séquence_observée)      │
│                                                              │
│  Étape 2: Prédiction                                        │
│    proba = modèle.predict_proba(features_obs)              │
│    # Retourne distribution de probabilité sur toutes recettes│
│                                                              │
│  Étape 3: Post-processing                                   │
│    - Trier par probabilité décroissante                    │
│    - Retourner top-K                                        │
│    - Calculer entropie pour mesurer confiance              │
│                                                              │
│  Étape 4: Gestion du temps réel                             │
│    - Re-calculer features à chaque nouveau geste           │
│    - Re-prédire                                             │
│    - Tracker évolution des prédictions                     │
│                                                              │
│  Output: Top-K recettes avec probabilités                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Extraction de features détaillée

**Code Python pour extraction:**
```python
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import Counter

class RecipeFeatureExtractor:
    def __init__(self, vocabulary):
        self.vocabulary = vocabulary  # Liste de tous les gestes possibles
        self.vocab_to_idx = {g: i for i, g in enumerate(vocabulary)}
        
    def extract_features(self, sequence):
        features = []
        
        # 1. Bag-of-Gestures (binaire)
        bog = np.zeros(len(self.vocabulary))
        for gesture in sequence:
            if gesture in self.vocab_to_idx:
                bog[self.vocab_to_idx[gesture]] = 1
        features.extend(bog)
        
        # 2. Fréquences normalisées
        freq = np.zeros(len(self.vocabulary))
        counter = Counter(sequence)
        for gesture, count in counter.items():
            if gesture in self.vocab_to_idx:
                freq[self.vocab_to_idx[gesture]] = count / len(sequence)
        features.extend(freq)
        
        # 3. Bigrammes (top 100 bigrammes les plus fréquents)
        bigrams = [f"{sequence[i]}_{sequence[i+1]}" 
                   for i in range(len(sequence)-1)]
        bigram_features = self._encode_ngrams(bigrams, self.top_bigrams)
        features.extend(bigram_features)
        
        # 4. Features statistiques
        stats = [
            len(sequence),  # Longueur
            len(set(sequence)),  # Gestes uniques
            len(sequence) / len(set(sequence)),  # Ratio répétition
            self._calculate_entropy(sequence),  # Entropie
        ]
        features.extend(stats)
        
        # 5. Features de graphe
        graph = self._sequence_to_graph(sequence)
        graph_features = [
            graph.number_of_nodes(),
            graph.number_of_edges(),
            np.mean([d for n, d in graph.degree()]),
            nx.average_clustering(graph.to_undirected()),
        ]
        features.extend(graph_features)
        
        return np.array(features)
```

### 4.4 Gestion du problème multi-classe massif

**Problème:** 1M de classes est trop pour un arbre de décision standard.

**Solutions:**

**Solution 1: Approche hiérarchique**
```
Niveau 1: Classifier en catégories (10-50 catégories)
          - Desserts, Viandes, Soupes, etc.
          
Niveau 2: Pour chaque catégorie, un modèle spécialisé
          - RandomForest pour "Desserts" (10K recettes)
          - RandomForest pour "Viandes" (50K recettes)
          - etc.
```

**Solution 2: Réduction de dimensionnalité des labels**
```
1. Clustériser les recettes similaires
2. Prédire d'abord le cluster (100-1000 clusters)
3. Rechercher dans le cluster pour trouver la recette exacte
```

**Solution 3: Multi-label binaire**
```
Pour chaque feature/attribut de recette:
  - Contient des œufs? (binaire)
  - Nécessite cuisson au four? (binaire)
  - Durée < 30 min? (binaire)
  
Combinaison des prédictions pour identifier la recette
```

### 4.5 Exemple d'utilisation

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# Préparation des données
X = []  # Features de toutes les recettes
y = []  # Labels (recipe_ids)

for recipe in recipes:
    features = feature_extractor.extract_features(recipe.actions)
    X.append(features)
    y.append(recipe.recipe_id)

X = np.array(X)
y = np.array(y)

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y
)

# Entraînement
rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=30,
    min_samples_split=10,
    n_jobs=-1,
    verbose=1
)

rf.fit(X_train, y_train)

# Prédiction
observed_sequence = ["breakEgg", "whisk", "pour"]
features_obs = feature_extractor.extract_features(observed_sequence)
proba = rf.predict_proba([features_obs])[0]

# Top-K
top_k_indices = np.argsort(proba)[-5:][::-1]
top_k_recipes = [(rf.classes_[i], proba[i]) for i in top_k_indices]
```

### 4.6 Avantages et limitations

**Avantages:**
- Implémentation rapide (quelques heures)
- Bonne baseline pour comparaison
- Interprétable (importance des features)
- Pas de GPU nécessaire

**Limitations:**
- Ne capture pas bien les séquences longues
- Sensible au déséquilibre de classes
- Difficulté avec 1M de classes
- Performance inférieure aux méthodes séquentielles

### 4.7 Complexité

| Opération | Complexité | Notes |
|-----------|-----------|-------|
| Extraction features | O(L + V) | L=longueur, V=vocabulaire |
| Entraînement RF | O(N × F × log(N) × T) | T=arbres, F=features |
| Prédiction | O(T × log(N)) | Très rapide |

---

## 5. Stratégie 4 : Clustering + Prototypes

### 5.1 Vue d'ensemble

**Principe:** Réduire l'espace de recherche en regroupant les recettes similaires et en utilisant des représentants (prototypes) pour chaque cluster.

**Priorité:** 🥈 **COMBINAISON AVEC STRATÉGIE 1** - Pré-filtrage avant Trie

**Avantages:**
- ✅ Réduction drastique: 1M → 10K-100K clusters
- ✅ Recherche hiérarchique naturelle
- ✅ Peut combiner avec d'autres stratégies
- ✅ Exploite la redondance naturelle des recettes

**Inconvénients:**
- ⚠️ Qualité dépend du clustering
- ⚠️ Overhead de calcul initial (one-time)
- ⚠️ Choix de la métrique de similarité critique

### 5.2 Architecture détaillée

```
┌─────────────────────────────────────────────────────────────┐
│        PHASE 0 : PRÉPARATION ET REPRÉSENTATION               │
│                                                              │
│  Pour chaque recette, créer une représentation:             │
│                                                              │
│  Option 1: Représentation par séquence                      │
│    - Vecteur de gestes ordonnés                            │
│    - Padding pour longueur uniforme                        │
│                                                              │
│  Option 2: Représentation TF-IDF                            │
│    - Traiter séquence comme "document"                     │
│    - Gestes comme "mots"                                   │
│    - TF-IDF classique                                       │
│                                                              │
│  Option 3: Graph Embeddings (si GNN disponible)             │
│    - Utiliser embeddings de la Stratégie 2                 │
│    - Vecteurs 64D ou 128D                                  │
│                                                              │
│  Option 4: Features manuelles                               │
│    - Même features que Stratégie 3                         │
│    - Vecteurs ~500-2000D                                   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│          PHASE 1 : CALCUL DE SIMILARITÉ                      │
│                                                              │
│  Choisir une métrique de similarité selon représentation:   │
│                                                              │
│  Pour séquences:                                            │
│    - Jaccard similarity sur ensembles de gestes            │
│    - Longest Common Subsequence (LCS)                       │
│    - Edit distance (Levenshtein)                           │
│    - DTW (Dynamic Time Warping) pour séquences temporelles │
│                                                              │
│  Pour graphes:                                              │
│    - Graph Edit Distance (GED) - coûteux mais précis       │
│    - Maximum Common Subgraph (MCS)                          │
│    - Graph kernel similarity                                │
│                                                              │
│  Pour vecteurs (TF-IDF, embeddings):                        │
│    - Cosine similarity - rapide et efficace                │
│    - Euclidean distance                                     │
│    - Manhattan distance                                     │
│                                                              │
│  Construction de matrice de similarité:                     │
│    S[i,j] = similarity(recipe_i, recipe_j)                 │
│    Matrice N×N (potentiellement énorme!)                   │
│                                                              │
│  Optimisation: Calcul par batches + stockage sparse        │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           PHASE 2 : CLUSTERING DES RECETTES                  │
│                                                              │
│  Algorithme A: K-Means (pour vecteurs)                      │
│    Input: Représentations vectorielles                     │
│    Hyperparamètres:                                         │
│      - K = nombre de clusters (10K - 100K)                 │
│      - Distance = euclidienne ou cosine                    │
│      - Iterations = 100-300                                 │
│    Output: Attribution cluster pour chaque recette         │
│    Complexité: O(N × K × d × iterations)                   │
│                                                              │
│  Algorithme B: DBSCAN (density-based)                       │
│    Input: Matrice de distance                               │
│    Hyperparamètres:                                         │
│      - eps = rayon de voisinage                            │
│      - min_samples = minimum de recettes par cluster       │
│    Output: Clusters + outliers                             │
│    Avantage: Nombre de clusters automatique                │
│                                                              │
│  Algorithme C: Hierarchical Clustering                      │
│    Input: Matrice de similarité                             │
│    Méthode: Agglomerative (bottom-up)                      │
│    Linkage: Ward, Average, ou Complete                     │
│    Output: Dendrogramme → couper à hauteur K               │
│    Avantage: Hiérarchie exploitable                        │
│                                                              │
│  Algorithme D: Louvain (pour graphes)                       │
│    Input: Graphe de similarité entre recettes              │
│    Méthode: Community detection                             │
│    Output: Communautés (clusters naturels)                 │
│    Avantage: Détection automatique de structure            │
│                                                              │
│  Résultat: Partition des 1M recettes en K clusters         │
│    cluster_map = {recipe_id: cluster_id}                   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│        PHASE 3 : SÉLECTION DES PROTOTYPES                    │
│                                                              │
│  Pour chaque cluster C, sélectionner un prototype P:        │
│                                                              │
│  Méthode A: Medoid (recette la plus centrale)              │
│    P = argmin_{r ∈ C} Σ_{r' ∈ C} distance(r, r')          │
│    Avantage: Représentant réel du cluster                  │
│                                                              │
│  Méthode B: Centroid (moyenne des représentations)         │
│    P = mean(representations[C])                             │
│    Avantage: Rapide, mais P peut ne pas être une vraie    │
│               recette                                       │
│                                                              │
│  Méthode C: Recette la plus fréquente                       │
│    P = recette avec le plus de vues/utilisations           │
│    Avantage: Représente les préférences utilisateurs      │
│                                                              │
│  Méthode D: Multi-prototypes                                │
│    Sélectionner top-3 ou top-5 recettes par cluster       │
│    Avantage: Meilleure couverture de la diversité         │
│                                                              │
│  Stockage:                                                  │
│    prototypes = {cluster_id: prototype_recipe_id(s)}       │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│          PHASE 4 : INDEXATION MULTI-NIVEAUX                  │
│                                                              │
│  Structure hiérarchique à 2 niveaux:                        │
│                                                              │
│  Niveau 1: Index des prototypes                             │
│    - Trie ou structure de recherche rapide                 │
│    - Seulement K prototypes (10K-100K)                     │
│    - Recherche: O(m) avec Trie                             │
│                                                              │
│  Niveau 2: Index par cluster                                │
│    - Pour chaque cluster, index de ses recettes            │
│    - Structures possibles:                                  │
│      * Trie spécialisé                                     │
│      * Hash table                                           │
│      * KD-tree pour recherche vectorielle                  │
│                                                              │
│  Métadonnées stockées:                                      │
│    - Taille du cluster                                     │
│    - Caractéristiques dominantes (gestes communs)          │
│    - Statistiques (longueur moyenne, etc.)                 │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           PHASE 5 : RECONNAISSANCE (Runtime)                 │
│                                                              │
│  Input: Séquence observée [a₁, a₂, ..., aₙ]                │
│                                                              │
│  ┌────────────────────────────────────────────────┐         │
│  │  ÉTAPE 1: MATCHING CONTRE PROTOTYPES           │         │
│  │  - Rechercher dans l'index de prototypes       │         │
│  │  - Calculer similarité avec chaque prototype   │         │
│  │  - Sélectionner top-M clusters candidats       │         │
│  │    (M = 3-10 selon seuil de similarité)        │         │
│  │  Output: [cluster_1, cluster_5, cluster_23]    │         │
│  └────────────────────────────────────────────────┘         │
│                       ▼                                      │
│  ┌────────────────────────────────────────────────┐         │
│  │  ÉTAPE 2: RECHERCHE DANS CLUSTERS              │         │
│  │  Pour chaque cluster candidat:                 │         │
│  │    - Accéder à l'index du cluster              │         │
│  │    - Rechercher recettes compatibles           │         │
│  │    - Calculer scores détaillés                 │         │
│  │  Agrégation de tous les résultats              │         │
│  │  Output: Liste de recettes candidates          │         │
│  └────────────────────────────────────────────────┘         │
│                       ▼                                      │
│  ┌────────────────────────────────────────────────┐         │
│  │  ÉTAPE 3: SCORING FINAL                        │         │
│  │  - Appliquer scoring multi-critères            │         │
│  │    (comme Stratégie 1)                         │         │
│  │  - Bonus pour recettes dans clusters bien      │         │
│  │    matchés                                      │         │
│  │  - Trier et retourner top-K                    │         │
│  └────────────────────────────────────────────────┘         │
│                                                              │
│  Output: Top-K recettes avec scores et explications         │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Métriques de similarité détaillées

**1. Jaccard Similarity (pour séquences comme ensembles)**
```python
def jaccard_similarity(seq1, seq2):
    set1 = set(seq1)
    set2 = set(seq2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0

# Exemple:
# seq1 = ["breakEgg", "whisk", "pour", "flip"]
# seq2 = ["breakEgg", "whisk", "add", "pour", "fold"]
# jaccard = 3/6 = 0.5
```

**2. Longest Common Subsequence (LCS)**
```python
def lcs_similarity(seq1, seq2):
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n+1) for _ in range(m+1)]
    
    for i in range(1, m+1):
        for j in range(1, n+1):
            if seq1[i-1] == seq2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    lcs_length = dp[m][n]
    # Normaliser par longueur moyenne
    return 2 * lcs_length / (m + n)

# Exemple:
# seq1 = ["breakEgg", "whisk", "pour", "flip"]
# seq2 = ["breakEgg", "pour", "whisk", "fold"]
# LCS = ["breakEgg", "whisk", "pour"] → length = 3
# similarity = 2*3/(4+4) = 0.75
```

**3. Graph Edit Distance (GED) - pour graphes**
```python
import networkx as nx

def graph_edit_distance_normalized(G1, G2):
    # Coûteux! Utiliser approximation pour scalabilité
    ged = nx.graph_edit_distance(G1, G2, timeout=5)
    
    # Normaliser par taille des graphes
    max_size = max(G1.number_of_nodes(), G2.number_of_nodes())
    similarity = 1 - (ged / max_size) if ged is not None else 0
    
    return similarity
```

**4. Cosine Similarity (pour vecteurs)**
```python
from sklearn.metrics.pairwise import cosine_similarity

def cosine_sim(vec1, vec2):
    # vec1, vec2: numpy arrays
    return cosine_similarity([vec1], [vec2])[0][0]
```

### 5.4 Algorithmes de clustering adaptés

**K-Means avec initialisation intelligente:**
```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize

# Représentations vectorielles des recettes
X = np.array([recipe_to_vector(r) for r in recipes])

# Normalisation pour cosine distance
X_normalized = normalize(X)

# K-Means
n_clusters = 50000  # 50K clusters
kmeans = KMeans(
    n_clusters=n_clusters,
    init='k-means++',  # Initialisation intelligente
    n_init=10,
    max_iter=300,
    random_state=42,
    n_jobs=-1,
    verbose=1
)

cluster_labels = kmeans.fit_predict(X_normalized)

# Mapping recette → cluster
recipe_to_cluster = {
    recipes[i].recipe_id: cluster_labels[i] 
    for i in range(len(recipes))
}
```

**Louvain pour détection de communautés:**
```python
import community as community_louvain
import networkx as nx

# Créer graphe de similarité
G = nx.Graph()
for i, recipe_i in enumerate(recipes):
    G.add_node(recipe_i.recipe_id)

# Ajouter arêtes si similarité > seuil
threshold = 0.7
for i in range(len(recipes)):
    for j in range(i+1, len(recipes)):
        sim = similarity(recipes[i], recipes[j])
        if sim > threshold:
            G.add_edge(recipes[i].recipe_id, recipes[j].recipe_id, weight=sim)

# Détection de communautés
partition = community_louvain.best_partition(G)

# partition = {recipe_id: cluster_id}
```

### 5.5 Sélection optimale du nombre de clusters

**Méthode du coude (Elbow Method):**
```python
inertias = []
K_range = [1000, 5000, 10000, 20000, 50000, 100000]

for k in K_range:
    kmeans = KMeans(n_clusters=k, n_init=5)
    kmeans.fit(X_normalized)
    inertias.append(kmeans.inertia_)

# Tracer et trouver le "coude"
plt.plot(K_range, inertias, 'bo-')
plt.xlabel('Number of clusters')
plt.ylabel('Inertia')
plt.show()
```

**Silhouette Score:**
```python
from sklearn.metrics import silhouette_score

for k in K_range:
    kmeans = KMeans(n_clusters=k)
    labels = kmeans.fit_predict(X_normalized)
    score = silhouette_score(X_normalized, labels, sample_size=10000)
    print(f"K={k}: Silhouette={score:.3f}")
```

### 5.6 Architecture combinée: Clustering + Trie

**Intégration optimale:**
```
┌───────────────────────────────────────────┐
│  Séquence observée: [a₁, a₂, ..., aₙ]    │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│  COUCHE 0: Clustering (Pré-filtrage)      │
│  - Match contre 50K prototypes            │
│  - Réduction: 1M → top-5 clusters        │
│  - Output: ~50K recettes candidates       │
│  - Temps: ~50ms                           │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│  COUCHE 1: Trie (Filtrage séquentiel)    │
│  - Navigation dans Trie des candidats     │
│  - Réduction: 50K → 100-500 candidats    │
│  - Output: recettes compatibles           │
│  - Temps: ~20ms                           │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│  COUCHE 2: Scoring (Ranking précis)      │
│  - Calcul multi-critères sur 100-500     │
│  - Output: top-10 avec scores             │
│  - Temps: ~30ms                           │
└──────────────────┬────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────┐
│  RÉSULTAT FINAL: Top-10 en ~100ms        │
└───────────────────────────────────────────┘
```

### 5.7 Complexité et performance

| Phase | Complexité | Temps (estimé) |
|-------|-----------|----------------|
| Construction matrice similarité | O(N²) ou O(N × sample) | 1-7 jours |
| Clustering (K-Means) | O(N × K × d × iter) | 2-6 heures |
| Sélection prototypes | O(K × avg_size) | 10-30 min |
| Construction index | O(N) | 1-2 heures |
| **Runtime - Match prototypes** | O(K) | ~50ms |
| **Runtime - Search cluster** | O(cluster_size) | ~20ms |
| **Runtime - Scoring** | O(candidates) | ~30ms |
| **Total Runtime** | - | **~100ms** |

---

## 6. Recommandations d'implémentation

### 6.1 Ordre de priorité et timeline

#### **PHASE 1: Foundation (4-6 semaines)**
**Objectif:** Système fonctionnel sur échantillon

**Semaine 1-2: Stratégie 1 (Trie) - Prototype**
- Implémenter structure Trie basique
- Tester sur 10K recettes
- Valider les scores multi-critères
- Mesurer performance (temps, mémoire)

**Semaine 3-4: Optimisation et scaling**
- Optimiser mémoire (compression, sérialisation)
- Tester sur 100K recettes
- Implémenter fuzzy matching
- Créer pipeline de batch processing

**Semaine 5-6: Évaluation complète**
- Dataset de test avec ground truth
- Métriques: Precision@K, MRR, temps de réponse
- Identifier bottlenecks
- Documentation

**Livrable:** Système Trie fonctionnel sur dataset complet

---

#### **PHASE 2: Scaling (4-6 semaines)**
**Objectif:** Gérer 1M+ recettes efficacement

**Semaine 1-2: Stratégie 4 (Clustering) - Preprocessing**
- Choisir représentation (TF-IDF ou embeddings simples)
- Implémenter calcul de similarité
- Expérimenter avec différents K (10K, 50K, 100K)
- Sélectionner prototypes

**Semaine 3-4: Intégration Clustering + Trie**
- Construire index hiérarchique
- Trie sur prototypes
- Index par cluster
- Pipeline de recherche en 2 étapes

**Semaine 5-6: Benchmarking et tuning**
- Comparer performance vs Trie seul
- Optimiser nombre de clusters
- Ajuster seuils
- Tests de charge

**Livrable:** Système scalable à 1M+ recettes avec latence <200ms

---

#### **PHASE 3: Baselines et comparaisons (2-3 semaines)**
**Objectif:** Validation scientifique

**Semaine 1: Stratégie 3 (Arbres) - Baseline**
- Extraction features
- Entraînement Random Forest
- Approche hiérarchique (catégories)
- Évaluation

**Semaine 2-3: Analyses comparatives**
- Comparer les 3 stratégies implémentées
- Métriques: Précision, Recall, F1, Latence
- Analyse des erreurs
- Identification des cas difficiles

**Livrable:** Paper-ready benchmarks et analyses

---

#### **PHASE 4 (Optionnelle): Deep Learning (6-8 semaines)**
**Objectif:** État de l'art avec GNN

**Semaine 1-2: Setup infrastructure**
- Environnement PyTorch Geometric
- Conversion graphes → format PyG
- Génération données d'entraînement

**Semaine 3-5: Développement modèle**
- Implémentation architecture GNN
- Expérimentations (GCN, GAT, etc.)
- Hyperparameter tuning
- Entraînement sur GPU

**Semaine 6-7: Intégration et déploiement**
- Construction index FAISS
- API de prédiction
- Optimisation inference
- Tests de performance

**Semaine 8: Évaluation finale**
- Comparaison avec autres stratégies
- Analyse coût/bénéfice
- Décision de déploiement

**Livrable:** Modèle GNN (si bénéfice justifié)

---

### 6.2 Architecture système recommandée

**Architecture finale suggérée (après Phase 2):**

```
┌────────────────────────────────────────────────────────────┐
│                    API REST / Interface                     │
│  Endpoints:                                                 │
│    POST /recognize                                          │
│    GET /recipe/{id}                                         │
│    POST /recognize/stream (temps réel)                     │
└───────────────────────┬────────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────────┐
│              Recognition Engine (Core)                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module 1: Preprocessing                             │  │
│  │  - Validation séquence                               │  │
│  │  - Normalisation gestes                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                    │
│                        ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module 2: Hierarchical Search                       │  │
│  │  - Layer 0: Cluster matching (50K prototypes)       │  │
│  │  - Layer 1: Trie navigation (per cluster)           │  │
│  │  - Output: 100-500 candidates                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                    │
│                        ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module 3: Multi-criteria Scoring                    │  │
│  │  - Coverage, Position, Completion, Transition        │  │
│  │  - Adaptive thresholding                             │  │
│  │  - Confidence estimation                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                        │                                    │
│                        ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module 4: Post-processing & Explanation            │  │
│  │  - Ranking & filtering                               │  │
│  │  - Explanation generation                            │  │
│  │  - Ambiguity detection                               │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬───────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│                   Data Layer                                │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Recipe DB    │  │ Cluster Index│  │  Trie Index  │     │
│  │ (MongoDB/    │  │ (Pickle/     │  │  (Pickle/    │     │
│  │  PostgreSQL) │  │  Redis)      │  │   Redis)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────────────────────────────────────────┘
```

### 6.3 Stack technologique recommandé

**Backend:**
- Python 3.10+
- FastAPI pour l'API REST
- NetworkX pour manipulation graphes
- NumPy/Pandas pour calculs
- Pickle/Joblib pour sérialisation
- Redis (optionnel) pour cache

**Data Processing:**
- Scikit-learn pour clustering et features
- FAISS (si GNN) pour recherche vectorielle
- PyTorch Geometric (si GNN)

**Storage:**
- MongoDB pour recettes (documents JSON)
- PostgreSQL pour métadonnées
- S3/Object Storage pour index sérialisés

**Deployment:**
- Docker pour containerisation
- Kubernetes (optionnel) pour orchestration
- Prometheus + Grafana pour monitoring

### 6.4 Considérations de production

**Performance:**
- Target: <200ms pour reconnaissance
- Cache des résultats récents (Redis)
- Load balancing si haute charge
- Async processing pour batch requests

**Scalabilité:**
- Sharding par catégories de recettes
- Réplication read pour queries
- Batch updates pour index

**Monitoring:**
- Latence P50, P95, P99
- Taux d'identification (avec/sans ambiguïté)
- Distribution des scores
- Erreurs et timeouts

**Maintenance:**
- Pipeline de mise à jour des index (nightly)
- Versioning des modèles
- A/B testing pour nouvelles versions
- Rollback automatique si dégradation

---

## 7. Métriques d'évaluation

### 7.1 Métriques de qualité

**Precision@K:**
```
Precision@K = (Nombre de recettes correctes dans top-K) / K

Exemple:
Top-5 = [R_correct, R_wrong, R_wrong, R_correct, R_wrong]
Precision@5 = 2/5 = 0.4
```

**Recall@K:**
```
Recall@K = (Nombre de recettes correctes dans top-K) / Total_recettes_correctes

Si la vraie recette est en position 3:
Recall@5 = 1/1 = 1.0  (trouvée)
Recall@2 = 0/1 = 0.0  (pas dans top-2)
```

**Mean Reciprocal Rank (MRR):**
```
MRR = Moyenne(1 / rang_de_la_bonne_recette)

Exemple sur 3 queries:
  Query 1: bonne recette en position 1 → 1/1 = 1.0
  Query 2: bonne recette en position 3 → 1/3 = 0.33
  Query 3: bonne recette en position 2 → 1/2 = 0.5
  
MRR = (1.0 + 0.33 + 0.5) / 3 = 0.61
```

**Normalized Discounted Cumulative Gain (NDCG@K):**
```
Mesure la qualité du ranking en tenant compte de la position

NDCG@K = DCG@K / IDCG@K

Où DCG = Σ (relevance_i / log₂(i+1))
```

### 7.2 Métriques de performance

**Latence:**
- P50 (médiane): temps en dessous duquel 50% des requêtes sont traitées
- P95: 95% des requêtes traitées en dessous de ce temps
- P99: 99% des requêtes traitées en dessous de ce temps
- Max: temps maximum observé

**Throughput:**
- Requêtes par seconde (QPS)
- Batch processing: recettes traitées par heure

**Ressources:**
- Utilisation CPU/GPU
- Mémoire RAM utilisée
- Stockage disque nécessaire

### 7.3 Métriques métier

**Taux d'identification:**
```
Taux = (Requêtes avec identification > seuil) / Total_requêtes
```

**Ambiguïté moyenne:**
```
Score d'ambiguïté = 1 - (score_top1 - score_top2)

Faible ambiguïté: écart > 0.2
Haute ambiguïté: écart < 0.1
```

**Évolution temporelle:**
- Précision en fonction du nombre de gestes observés
- Courbe: [1 geste] → [2 gestes] → ... → [N gestes]

### 7.4 Protocole d'évaluation

**Dataset de test:**
```
1. Sélectionner échantillon stratifié:
   - 1000 recettes diverses
   - Couvrant différentes catégories
   - Différentes longueurs de séquences
   
2. Pour chaque recette, générer préfixes:
   - 30% de la séquence
   - 50% de la séquence
   - 70% de la séquence
   - 100% de la séquence
   
3. Ground truth = recipe_id correct

4. Évaluer sur 4000 samples (1000 × 4)
```

**Exemple de résultats attendus:**

| Stratégie | Precision@5 | MRR | Latence P95 | Mémoire |
|-----------|------------|-----|-------------|---------|
| Trie seul | 0.75 | 0.68 | 450ms | 12GB |
| Clustering + Trie | 0.73 | 0.65 | 120ms | 15GB |
| Random Forest | 0.58 | 0.52 | 80ms | 8GB |
| GNN (si impl.) | 0.82 | 0.76 | 100ms | 20GB |

---

## 8. Roadmap et Timeline

### 8.1 Vue d'ensemble

```
Mois 1-2: FOUNDATION
├─ Semaine 1-2: Stratégie 1 (Trie) prototype
├─ Semaine 3-4: Optimisation
├─ Semaine 5-6: Tests sur 100K recettes
└─ Semaine 7-8: Évaluation et documentation

Mois 3-4: SCALING
├─ Semaine 1-2: Stratégie 4 (Clustering)
├─ Semaine 3-4: Intégration hiérarchique
├─ Semaine 5-6: Tests sur 1M recettes
└─ Semaine 7-8: Optimisation finale

Mois 5: BASELINES
├─ Semaine 1-2: Stratégie 3 (Arbres)
├─ Semaine 3: Benchmarks comparatifs
└─ Semaine 4: Analyses et rapport

Mois 6+ (Optionnel): DEEP LEARNING
├─ Semaine 1-3: Infrastructure + Stratégie 2 (GNN)
├─ Semaine 4-6: Entraînement et tuning
└─ Semaine 7-8: Évaluation et intégration
```

### 8.2 Milestones

**M1 (Fin Mois 2): MVP Fonctionnel**
- ✅ Système Trie opérationnel
- ✅ Testé sur 100K+ recettes
- ✅ Précision > 70% @ top-5
- ✅ Latence < 500ms

**M2 (Fin Mois 4): Production-Ready**
- ✅ Système scalable à 1M+ recettes
- ✅ Architecture clustering + Trie
- ✅ Latence < 200ms
- ✅ API déployable

**M3 (Fin Mois 5): Publication-Ready**
- ✅ Benchmarks complets
- ✅ Comparaison 3-4 stratégies
- ✅ Documentation scientifique
- ✅ Analyses statistiques

**M4 (Fin Mois 6+): State-of-the-Art**
- ✅ Modèle GNN (si pertinent)
- ✅ Meilleure précision marché
- ✅ Publications académiques

### 8.3 Risques et mitigation

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Trie trop gourmand en mémoire | Moyenne | Élevé | Compression, sharding |
| Clustering de mauvaise qualité | Faible | Élevé | Tests multiples métriques |
| Latence > objectif | Moyenne | Moyen | Optimisations, cache |
| Dataset avec bruit | Élevée | Moyen | Validation, nettoyage |
| GNN trop coûteux à entraîner | Moyenne | Faible | Approche optionnelle |

### 8.4 Prochaines étapes immédiates

**Cette semaine:**
1. Définir structure exacte du Trie (classes Python)
2. Implémenter insertion de 100 recettes (test)
3. Tester recherche basique
4. Mesurer mémoire utilisée

**Semaine prochaine:**
1. Implémenter scoring multi-critères
2. Tester sur séquences partielles
3. Évaluer sur mini-dataset (1K recettes)
4. Documenter résultats

**Dans 2 semaines:**
1. Scale à 10K recettes
2. Optimiser performance
3. Implémenter fuzzy matching
4. Préparer pipeline batch

---

## 9. Conclusion et décision

### 9.1 Stratégie recommandée

**APPROCHE RECOMMANDÉE: Stratégie 1 + 4 (Hybride)**

**Justification:**
1. **Stratégie 1 (Trie)** = Fondation solide
   - Évolutive, rapide, interprétable
   - Gère naturellement le temps réel
   - Pas d'entraînement nécessaire

2. **Stratégie 4 (Clustering)** = Pré-filtrage intelligent
   - Réduit espace de recherche drastiquement
   - Combine bien avec le Trie
   - Améliore scalabilité

3. **Stratégie 3 (Arbres)** = Baseline de comparaison
   - Rapide à tester
   - Valide l'importance des features
   - Point de référence scientifique

4. **Stratégie 2 (GNN)** = Optionnelle si temps/ressources
   - Potentiel meilleure précision
   - Plus complexe à développer
   - Nécessite infrastructure GPU

### 9.2 Plan d'action

**PHASE 1 (Priorité absolue):**
→ Implémenter Stratégie 1 (Trie + Scoring)
→ Target: 2 mois pour système fonctionnel

**PHASE 2 (Scale-up):**
→ Ajouter Stratégie 4 (Clustering)
→ Target: +2 mois pour gestion 1M+ recettes

**PHASE 3 (Validation):**
→ Implémenter Stratégie 3 (Baseline)
→ Target: +1 mois pour comparaisons

**PHASE 4 (Optionnelle):**
→ Explorer Stratégie 2 (GNN) si pertinent
→ Target: +2 mois si bénéfice démontré

### 9.3 Critères de succès

**Technique:**
- ✅ Précision@5 > 75%
- ✅ Latence P95 < 200ms
- ✅ Scale à 1M+ recettes
- ✅ Mémoire < 20GB

**Scientifique:**
- ✅ Contributions publiables
- ✅ Benchmarks reproductibles
- ✅ Code open-source

**Métier:**
- ✅ Système utilisable en production
- ✅ Assistance effective aux utilisateurs
- ✅ Identification précoce (3-5 gestes)

