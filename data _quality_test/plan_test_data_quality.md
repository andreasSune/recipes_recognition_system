# Plan Complet de Test de Qualité des Données - Projet de Reconnaissance de Recettes par Graphes

---

## **STRATÉGIE 1 : Annotations Manuelles + Ré-annotation LLM**

### Objectif
Triple validation des séquences d'actions générées : comparaison entre annotation manuelle (gold standard), annotation LLM ancienne (graphs_recipes actuel), et ré-annotation LLM nouvelle.

---

### 1.1 Échantillonnage Stratifié (Minimum 50 recettes)

#### Critères de stratification

**Par complexité (distribution recommandée sur 50 recettes) :**
- **15 recettes SIMPLES** : 3-5 instructions, 5-8 ingrédients
- **20 recettes MOYENNES** : 6-10 instructions, 9-15 ingrédients  
- **15 recettes COMPLEXES** : >10 instructions, >15 ingrédients

**Par type culinaire (diversité à respecter) :**
- **15-20 recettes de pâtisserie** : séquences précises, ordre critique (gâteaux, cookies, pains)
- **15-20 recettes de plats mijotés** : temps d'attente importants, ordre partiellement flexible (ragoûts, soupes)
- **10-15 recettes de préparations rapides** : beaucoup de parallélisme possible (salades, sandwichs, smoothies)
- **5-10 recettes avec ingrédients pré-transformés** : pour tester la génération de variantes ingredients (ex: "fromage râpé", "oignons hachés")

**Méthode de sélection :**
1. Filtrer le dataset `recipes.csv` selon les critères de complexité
2. Échantillonner aléatoirement dans chaque strate
3. Vérifier manuellement la diversité culinaire
4. Ajuster si nécessaire pour respecter la distribution par type

---

### 1.2 Extraction et Structuration des Données

#### Structure du fichier Excel de sortie

**Nom du fichier :** `echantillon_annotation_manuelle_[DATE].xlsx`

**Colonnes :**

| id | title | number_of_steps | number_of_ingredients | complexity_category | cuisine_type | has_pretransformed_ingredients | instructions | ingredients | actions_llm_ancien | annotations_manuelles |
|---|---|---|---|---|---|---|---|---|---|---|
| 12345 | Macaroni au fromage | 8 | 6 | moyenne | confort_food | TRUE | ["Boil water...", "Add pasta..."] | ["pasta", "cheese", "milk"] | ["boil", "add", "cook", "drain", "mix", "pour", "bake", "serve"] | |

**Description des colonnes :**

- `id` : Identifiant unique de la recette
- `title` : Titre de la recette
- `number_of_steps` : Nombre d'instructions (depuis recipes.csv)
- `number_of_ingredients` : Nombre d'ingrédients (depuis recipes.csv)
- `complexity_category` : SIMPLE / MOYENNE / COMPLEXE
- `cuisine_type` : pâtisserie / plat_mijoté / préparation_rapide / autre
- `has_pretransformed_ingredients` : TRUE/FALSE (détection d'ingrédients comme "râpé", "haché", "coupé")
- `instructions` : Liste complète des instructions (depuis recipe_instructions.csv)
- `ingredients` : Liste complète des ingrédients (depuis recipe_ingredients.csv)
- `actions_llm_ancien` : Séquence d'actions de la variante principale dans graphs_recipes
- `annotations_manuelles` : **COLONNE VIDE** à remplir manuellement

---

### 1.3 Grille d'Annotation Manuelle Standardisée

#### Instructions pour l'annotateur

Pour chaque recette, lire attentivement les instructions et les ingrédients, puis générer la séquence d'actions manuellement.

**Consignes d'annotation :**

1. **Extraction des verbes** :
   - Identifier le verbe d'action principal de chaque instruction
   - Utiliser la liste de référence des verbes culinaires quand possible
   - Si un verbe approprié n'existe pas dans la liste, en choisir un nouveau

2. **Une instruction peut générer 0 à 3 actions** :
   - 0 action : instructions non-culinaires ou purement informatives
   - 1 action : instruction simple (ex: "Chop the onions" → "chop")
   - 2-3 actions : instruction complexe (ex: "Beat eggs and pour into pan" → "beat", "pour")

3. **Gestes implicites à capturer** :
   - Si un ingrédient est mentionné sous forme transformée (ex: "fromage râpé") alors qu'il apparaît non-transformé dans la liste d'ingrédients, ajouter le geste de transformation
   - Exemple : Liste d'ingrédients = "fromage", Instruction = "ajouter le fromage râpé" → actions = "grate", "add"

4. **Actions passives (idle)** :
   - Pour les instructions de type "laisser reposer", "préchauffer le four", "cuire pendant 30 min", utiliser les verbes de cuisson passive appropriés (bake, simmer, etc.) ou "idle" si aucune action

5. **Format de sortie** :
   - Séquence d'actions séparées par des virgules dans la colonne `annotations_manuelles`
   - Format : `action1, action2, action3, ...`
   - Exemple : `wash, chop, heat, pour, stir, simmer, drain, serve`

#### Feuille de travail supplémentaire (optionnelle)

Créer un second onglet "Notes" dans le fichier Excel pour documenter :
- **Ambiguïtés rencontrées** : instructions difficiles à interpréter
- **Décisions d'annotation** : justification des choix non-évidents
- **Gestes implicites ajoutés** : liste des ingrédients transformés détectés
- **Niveau de confiance** : 1-5 pour chaque recette

---

### 1.4 Ré-annotation LLM

Après l'annotation manuelle, repasser les 50 recettes au LLM avec un prompt optimisé (potentiellement amélioré).

**Objectif** : Générer une nouvelle séquence d'actions (`actions_llm_nouveau`) pour chaque recette.

**Méthodologie** :
1. Utiliser le même format de prompt que le pipeline original (ou une version améliorée)
2. Traiter les 50 recettes en batch
3. Extraire uniquement la séquence d'actions de la variante principale
4. Ajouter une colonne `actions_llm_nouveau` au fichier Excel

---

### 1.5 Méthodologie de Comparaison Tripartite

#### A) Métriques de similarité de séquences

Pour chaque recette, comparer les trois séquences d'actions :
- **S_manuel** : Séquence annotée manuellement (gold standard)
- **S_ancien** : Séquence LLM ancienne (graphs_recipes)
- **S_nouveau** : Séquence LLM nouvelle (ré-annotation)

**Métriques à calculer :**

1. **Exact Match** :
   - S_ancien == S_manuel ? (TRUE/FALSE)
   - S_nouveau == S_manuel ? (TRUE/FALSE)

2. **Précision des verbes (Accuracy)** :
   - Proportion de verbes identiques en position identique
   - Formule : `nombre_actions_identiques / max(len(S1), len(S2))`

3. **Jaccard Similarity (similarité d'ensemble)** :
   - Mesure l'overlap sans tenir compte de l'ordre
   - Formule : `|S1 ∩ S2| / |S1 ∪ S2|`

4. **Levenshtein Distance (distance d'édition)** :
   - Nombre minimal d'opérations (insertion, suppression, substitution) pour transformer S1 en S2
   - Plus la distance est faible, plus les séquences sont similaires

5. **Longest Common Subsequence (LCS)** :
   - Longueur de la plus longue sous-séquence commune
   - Formule : `LCS(S1, S2) / max(len(S1), len(S2))`

6. **Différence de longueur** :
   - `|len(S1) - len(S2)|`
   - Identifier les cas où beaucoup d'actions sont manquantes ou en trop

#### B) Comparaisons à effectuer

**Comparaison 1 : Manuelle vs LLM_ancien**
- Mesurer la qualité du pipeline actuel par rapport au gold standard
- Métriques : Accuracy, Jaccard, Levenshtein, LCS
- Identifier les types d'erreurs du LLM ancien

**Comparaison 2 : Manuelle vs LLM_nouveau**
- Mesurer l'amélioration (ou régression) du nouveau prompt
- Mêmes métriques que Comparaison 1
- Objectif : Accuracy > 85%, Jaccard > 0.80

**Comparaison 3 : LLM_ancien vs LLM_nouveau**
- Analyser l'évolution entre les deux versions LLM
- Catégoriser les changements :
  - **Corrections** : `S_ancien ≠ S_manuel` ET `S_nouveau == S_manuel`
  - **Régressions** : `S_ancien == S_manuel` ET `S_nouveau ≠ S_manuel`
  - **Changements latéraux** : `S_ancien ≠ S_manuel` ET `S_nouveau ≠ S_manuel` ET `S_ancien ≠ S_nouveau`
  - **Stables corrects** : `S_ancien == S_nouveau == S_manuel`
  - **Stables incorrects** : `S_ancien == S_nouveau ≠ S_manuel`

#### C) Analyse qualitative

**Pour chaque type d'erreur détectée, documenter :**

1. **Actions manquantes** :
   - Quelles actions sont absentes dans S_LLM mais présentes dans S_manuel ?
   - Patrons linguistiques associés (ex: instructions implicites)

2. **Actions erronées** :
   - Quelles actions sont différentes entre S_LLM et S_manuel ?
   - Types de confusions (ex: "mix" vs "stir", "chop" vs "dice")

3. **Actions en trop** :
   - Quelles actions sont présentes dans S_LLM mais absentes de S_manuel ?
   - Sur-interprétation du LLM ?

4. **Problèmes d'ordre** :
   - Les bonnes actions sont présentes mais dans le mauvais ordre
   - Distance de Levenshtein élevée malgré Jaccard élevé

5. **Gestes implicites non capturés** :
   - Ingrédients transformés non détectés par le LLM
   - Cas où la variante principale devrait inclure des gestes de transformation

#### D) Agrégation des résultats

**Tableaux de synthèse à produire :**

1. **Tableau de métriques moyennes** :

| Comparaison | Exact Match (%) | Accuracy (%) | Jaccard | Levenshtein (moy) | LCS (%) |
|---|---|---|---|---|---|
| Manuel vs Ancien | X% | X% | X | X | X% |
| Manuel vs Nouveau | X% | X% | X | X | X% |
| Ancien vs Nouveau | X% | X% | X | X | X% |

2. **Tableau de distribution des changements** (pour Ancien vs Nouveau) :

| Catégorie | Nombre | Pourcentage |
|---|---|---|
| Corrections | X | X% |
| Régressions | X | X% |
| Changements latéraux | X | X% |
| Stables corrects | X | X% |
| Stables incorrects | X | X% |

3. **Top 10 des erreurs les plus fréquentes** :
   - Lister les confusions de verbes les plus communes
   - Exemple : "mix" confondu avec "stir" dans 15 cas

4. **Analyse par complexité** :
   - Métriques moyennes pour recettes SIMPLES, MOYENNES, COMPLEXES
   - Identifier si la qualité se dégrade avec la complexité

5. **Analyse par type culinaire** :
   - Métriques moyennes pour pâtisserie, plats mijotés, préparations rapides
   - Identifier les types de recettes problématiques

---

### 1.6 Questions d'Investigation Supplémentaires

Au-delà des métriques quantitatives, explorer qualitativement :

1. **Cohérence avec les variantes** :
   - Les recettes avec variantes ingredients bien générées ont-elles de meilleures annotations principales ?
   - Les gestes de transformation d'ingrédients sont-ils correctement détectés ?

2. **Patterns d'instructions problématiques** :
   - Quels types de formulations linguistiques causent le plus d'erreurs ?
   - Exemples : instructions multi-actions, instructions implicites, instructions avec conditionnelles

3. **Performance du LLM sur cas limites** :
   - Instructions très courtes (< 3 mots)
   - Instructions très longues (> 20 mots)
   - Instructions avec mesures et temps ("cuire 30 min à 180°C")

4. **Suggestions d'amélioration du prompt** :
   - Basé sur les erreurs observées, comment reformuler le prompt ?
   - Exemples additionnels à inclure dans le prompt

---

## **STRATÉGIE 2 : Validation Structurelle des Graphes**

### Objectif
Vérifier automatiquement la cohérence structurelle des graphes générés en utilisant des contraintes quantitatives et des comparaisons inter-variantes.

---

### 2.1 Test 1 : Calcul de la Taille de Chaque Liste d'Actions

#### Métriques à calculer

**Pour l'ensemble du dataset :**
- **Distribution globale** :
  - Nombre total de graphes (toutes variantes confondues)
  - Longueur minimale, maximale, moyenne, médiane
  - Écart-type de la longueur
  - Quartiles (Q1, Q3)
  - Histogramme de distribution

**Par type de variante :**
- Mêmes statistiques pour :
  - `variante_principale`
  - `variante_ingredients`
  - `variante_permutation`

**Identification des outliers :**
- Graphes avec longueur > Q3 + 3×IQR (Inter-Quartile Range)
- Graphes avec longueur < Q1 - 3×IQR
- Liste des recettes concernées pour investigation manuelle

**Output attendu :**
```
Dataset: graphs_recipes
- Total graphes : 150,000
- Longueur moyenne : 8.5 actions
- Écart-type : 4.2
- Outliers détectés : 1,200 (0.8%)

Par type de variante :
- variante_principale : moyenne = 7.8, écart-type = 3.5
- variante_ingredients : moyenne = 9.2, écart-type = 4.8
- variante_permutation : moyenne = 7.8, écart-type = 3.5
```

---

### 2.2 Test 2 : Variante Principale vs Nombre d'Instructions

#### Hypothèse
Une instruction peut contenir entre 0.5 et 3 actions en moyenne.

#### Règles de validation

Pour chaque recette, comparer :
- `taille_variante_principale` (nombre d'actions dans le graphe)
- `number_of_steps` (nombre d'instructions depuis recipes.csv)

**Bornes théoriques :**
- **Borne inférieure** : `taille_variante_principale ≥ number_of_steps × 0.5`
  - Justification : Chaque instruction contient au minimum 1 action tous les 2 steps (certaines instructions sont passives)
  
- **Borne supérieure** : `taille_variante_principale ≤ number_of_steps × 3`
  - Justification : Maximum 3 actions par instruction

**Flags à lever :**

1. **FLAG_CRITIQUE** : `taille_variante_principale < number_of_steps`
   - Moins d'actions que d'instructions = suspect
   - Indique probablement des instructions non-annotées ou erreurs LLM

2. **FLAG_BORNE_BASSE** : `taille_variante_principale < number_of_steps × 0.5`
   - Trop peu d'actions par rapport au nombre d'instructions
   - Recette trop passive ou erreurs d'annotation

3. **FLAG_BORNE_HAUTE** : `taille_variante_principale > number_of_steps × 3`
   - Trop d'actions par rapport au nombre d'instructions
   - Sur-décomposition ou erreurs multiples

**Métriques à calculer :**
- Ratio moyen : `taille_variante_principale / number_of_steps`
- Distribution du ratio (histogramme)
- Nombre et pourcentage de recettes par type de flag
- Liste des recettes flaggées pour investigation

**Output attendu :**
```
Test 2 : Variante principale vs nombre d'instructions

Ratio moyen : 1.35 actions/instruction
Médiane : 1.2

Flags détectés :
- FLAG_CRITIQUE : 450 recettes (0.5%)
- FLAG_BORNE_BASSE : 1,200 recettes (1.2%)
- FLAG_BORNE_HAUTE : 800 recettes (0.8%)

Total recettes conformes : 97.5%
```

---

### 2.3 Test 3 : Variante Ingredients vs Taille Théorique Maximale

#### Hypothèse
La variante ingredients ajoute des gestes de transformation d'ingrédients à la variante principale.

#### Règles de validation

Pour chaque recette avec variante ingredients, comparer :
- `taille_variante_ingredients`
- `taille_variante_principale`
- `number_of_ingredients`

**Calcul du delta :**
```
delta = taille_variante_ingredients - taille_variante_principale
```

**Bornes théoriques pour delta :**
- **Borne inférieure** : `delta ≥ 0`
  - Justification : On ne peut pas avoir moins d'actions en ajoutant des transformations d'ingrédients
  
- **Borne supérieure** : `delta ≤ number_of_ingredients × 2`
  - Justification : Chaque ingrédient ajoute au maximum 2 gestes de transformation (ex: peel + chop)
  - Facteur 2 est conservateur (la plupart des ingrédients sont déjà transformés)

**Flags à lever :**

1. **FLAG_CRITIQUE_NEGATIF** : `delta < 0`
   - Variante ingredients plus courte que variante principale = impossible
   - Erreur grave dans la génération des variantes

2. **FLAG_AUCUN_AJOUT** : `delta == 0`
   - Variante ingredients identique à variante principale
   - Aucun ingrédient transformable détecté (peut être valide)

3. **FLAG_TROP_AJOUTS** : `delta > number_of_ingredients × 2`
   - Trop de gestes ajoutés par rapport au nombre d'ingrédients
   - Possibles erreurs de génération ou sur-décomposition

**Borne supérieure alternative (stricte) :**
```
taille_variante_ingredients ≤ (number_of_steps × 3) + (number_of_ingredients × 2)
```
- Flag si dépassement : erreur structurelle majeure

**Métriques à calculer :**
- Delta moyen et médian
- Distribution du delta (histogramme)
- Pourcentage de recettes par type de flag
- Corrélation entre number_of_ingredients et delta (graphique scatter)

**Output attendu :**
```
Test 3 : Variante ingredients

Delta moyen : 2.1 actions ajoutées
Médiane : 1.0

Flags détectés :
- FLAG_CRITIQUE_NEGATIF : 25 recettes (0.05%)
- FLAG_AUCUN_AJOUT : 15,000 recettes (30%) [peut être normal]
- FLAG_TROP_AJOUTS : 450 recettes (0.9%)

Distribution du delta :
- delta = 0 : 30%
- delta = 1-2 : 50%
- delta = 3-5 : 15%
- delta > 5 : 5%
```

---

### 2.4 Test 4 : Similarité des Actions entre Variantes

#### Objectif
Vérifier que les variantes d'une même recette partagent un socle commun d'actions cohérent.

#### Test 4A : Permutations vs Variante Principale (Seuil 90%)

**Pour chaque variante_permutation, calculer :**

1. **Jaccard Index** :
   ```
   Jaccard = |actions_permutation ∩ actions_principale| / |actions_permutation ∪ actions_principale|
   ```
   - Mesure la similarité d'ensemble (sans tenir compte de l'ordre)

2. **Overlap Coefficient** :
   ```
   Overlap = |actions_permutation ∩ actions_principale| / min(|actions_permutation|, |actions_principale|)
   ```
   - Mesure le pourcentage d'actions communes

**Règles de validation :**

- **Seuil attendu** : Overlap ≥ 0.90 (90%)
- **FLAG_SIMILARITE_BASSE** : Overlap < 0.90
  - Variante permutation trop différente de la principale
  - Possible erreur de génération

**Vérification supplémentaire : Ordre différent**

Pour les variantes passant le seuil de similarité, vérifier que l'ordre est effectivement différent :

- **Distance de Levenshtein** : Nombre de modifications pour transformer une séquence en l'autre
- **Positions différentes** : Nombre de gestes en position différente

**Flags :**
- **FLAG_IDENTIQUE** : Levenshtein == 0
  - Permutation identique à la principale (erreur de génération)
  
- **FLAG_TROP_DIFFERENTE** : Levenshtein > len(actions) / 3
  - Trop de changements, ce n'est plus vraiment une permutation

**Métriques à calculer :**
- Overlap moyen entre permutations et principale
- Distribution des distances de Levenshtein
- Pourcentage de variantes conformes (Overlap ≥ 0.90 ET Levenshtein > 0)

**Output attendu :**
```
Test 4A : Permutations vs Principale

Overlap moyen : 0.96
Levenshtein moyen : 3.2 modifications

Flags détectés :
- FLAG_SIMILARITE_BASSE : 120 variantes (0.3%)
- FLAG_IDENTIQUE : 45 variantes (0.1%)
- FLAG_TROP_DIFFERENTE : 80 variantes (0.2%)

Variantes conformes : 99.4%
```

---

#### Test 4B : Variante Ingredients vs Variante Principale (Seuil 70%)

**Pour chaque variante_ingredients, calculer :**

1. **Jaccard Index** :
   ```
   Jaccard = |actions_ingredients ∩ actions_principale| / |actions_ingredients ∪ actions_principale|
   ```

2. **Overlap Coefficient** :
   ```
   Overlap = |actions_ingredients ∩ actions_principale| / |actions_principale|
   ```
   - Mesure combien de la variante principale est conservée dans la variante ingredients

**Règles de validation :**

- **Seuil attendu** : Overlap ≥ 0.70 (70%)
- **FLAG_SIMILARITE_BASSE** : Overlap < 0.70
  - Variante ingredients trop différente de la principale
  - Possible erreur de génération ou recette complètement transformée

**Analyse des gestes ajoutés :**

Identifier les actions présentes dans `actions_ingredients` mais absentes de `actions_principale` :
```
actions_ajoutées = actions_ingredients - actions_principale
```

**Vérification sémantique des gestes ajoutés :**

Les gestes ajoutés doivent être des **gestes de transformation d'ingrédients** :
- Liste de référence : `chop, dice, slice, cut, mince, grate, peel, crush, mash, grind, shred, julienne, etc.`

**Flags :**
- **FLAG_GESTES_INCORRECTS** : Si actions_ajoutées contiennent des verbes qui ne sont PAS des gestes de transformation
  - Exemple : ajout de "bake", "serve" dans variante ingredients = incohérent

- **FLAG_RETRAIT_ACTIONS** : `taille_ingredients < taille_principale`
  - On ne devrait jamais retirer des actions en ajoutant des transformations

**Métriques à calculer :**
- Overlap moyen entre variante ingredients et principale
- Nombre moyen de gestes ajoutés
- Distribution des types de gestes ajoutés (comptage par verbe)
- Pourcentage de variantes avec gestes ajoutés valides

**Output attendu :**
```
Test 4B : Variante ingredients vs Principale

Overlap moyen : 0.78
Gestes ajoutés (moyenne) : 2.1 par variante

Top 5 gestes ajoutés :
1. chop : 12,000 occurrences
2. grate : 8,500 occurrences
3. dice : 6,200 occurrences
4. peel : 5,800 occurrences
5. slice : 4,100 occurrences

Flags détectés :
- FLAG_SIMILARITE_BASSE : 890 variantes (1.8%)
- FLAG_GESTES_INCORRECTS : 150 variantes (0.3%)
- FLAG_RETRAIT_ACTIONS : 25 variantes (0.05%)

Variantes conformes : 97.9%
```

---

### 2.5 Test 5 : Comparaison des 3 Datasets (Brut, Nettoyé avec Non-Gestes, Nettoyé sans Non-Gestes)

#### Objectif
Vérifier la cohérence du processus de nettoyage en comparant les tailles des graphes à travers les 3 versions du dataset.

#### Datasets concernés
- **D1** : `graphs_recipes` (brut, avant nettoyage)
- **D2** : `graphs_recipes_cleaned_with_non_gestures` (nettoyé, conserve non-gestes)
- **D3** : `graphs_recipes_cleaned_without_non_gestures` (nettoyé, uniquement gestes)

#### Méthodologie

**Pour chaque recette, pour chaque variante, calculer :**

1. **Tailles absolues** :
   - `T1` = taille dans D1 (graphs_recipes)
   - `T2` = taille dans D2 (graphs_cleaned_with_gestures)
   - `T3` = taille dans D3 (graphs_cleaned_without_non_gestures)

2. **Relations attendues** :
   ```
   T3 ≤ T2 ≤ T1
   ```
   - Justification : On retire progressivement des éléments (doublons, puis non-gestes)

3. **Ratios à analyser** :
   - **R1 = T2 / T1** : Taux de conservation après nettoyage
     - Idéal : 0.85 - 1.0 (on retire surtout les doublons)
   
   - **R2 = T3 / T2** : Proportion de gestes purs
     - Idéal : 0.5 - 0.8 (équilibre gestes/non-gestes)
   
   - **R3 = T3 / T1** : Taux de gestes dans le brut
     - Idéal : 0.4 - 0.7

#### Flags à lever

**FLAGS CRITIQUES (erreur de pipeline) :**

1. **FLAG_ORDRE_INCOHERENT** :
   - Si `T3 > T2` OU `T2 > T1`
   - Violation de la relation T3 ≤ T2 ≤ T1
   - Indique une erreur grave dans le processus de nettoyage

2. **FLAG_DISPARITION_TOTALE** :
   - Si `T3 == 0` alors que `T1 > 0`
   - Recette sans aucun geste après nettoyage
   - Suspect : recette entièrement passive ou erreur d'annotation

3. **FLAG_AUCUN_NETTOYAGE** :
   - Si `T1 == T2 == T3`
   - Aucune action retirée par le nettoyage
   - Suspect si T1 > 10 (statistiquement improbable)

**FLAGS D'ALERTE (à investiguer) :**

4. **FLAG_NETTOYAGE_EXCESSIF** :
   - Si `R1 < 0.70` (plus de 30% d'actions retirées au nettoyage)
   - Trop de doublons détectés ou erreur de dédoublonnage

5. **FLAG_TROP_GESTES** :
   - Si `R2 > 0.95` (plus de 95% de gestes purs)
   - Recette presque sans actions passives (cuisson, repos) = suspect

6. **FLAG_TROP_NON_GESTES** :
   - Si `R2 < 0.30` (moins de 30% de gestes purs)
   - Recette très passive ou erreurs de classification geste/non-geste

7. **FLAG_PERTE_EXCESSIVE** :
   - Si `R3 < 0.30` (moins de 30% du brut conservé)
   - Trop d'actions retirées globalement

#### Analyse des éléments retirés

**Pour chaque transition (D1→D2 et D2→D3), identifier :**

1. **Actions supprimées D1 → D2** :
   - Lister les verbes présents dans D1 mais absents de D2
   - Vérifier que ce sont bien des doublons consécutifs
   - Comptage des types d'actions retirées

2. **Actions supprimées D2 → D3** :
   - Lister les verbes présents dans D2 mais absents de D3
   - Vérifier que ce sont bien des non-gestes (bake, simmer, idle, etc.)
   - Comptage des types de non-gestes retirés

**Distribution attendue des non-gestes retirés :**
- `bake, roast, boil, simmer, broil, steam, idle, rest, cool, chill, marinate, rise`

**Flags si actions suspectes retirées :**
- **FLAG_GESTE_RETIRE** : Si un geste (chop, stir, mix) est présent dans D2 mais absent de D3
  - Erreur de classification ou bug de pipeline

#### Métriques agrégées

**Statistiques globales :**

```
Dataset D1 (brut) :
- Taille moyenne : 8.5 actions
- Total actions : 1,275,000

Dataset D2 (nettoyé avec non-gestes) :
- Taille moyenne : 7.8 actions (-8%)
- Total actions : 1,170,000
- Actions retirées : 105,000 (doublons)

Dataset D3 (nettoyé sans non-gestes) :
- Taille moyenne : 5.2 actions (-33% vs D2)
- Total actions : 780,000
- Actions retirées : 390,000 (non-gestes)

Ratios moyens :
- R1 (D2/D1) : 0.92
- R2 (D3/D2) : 0.67
- R3 (D3/D1) : 0.61
```

**Distribution des flags :**

| Flag | Nombre | Pourcentage |
|---|---|---|
| FLAG_ORDRE_INCOHERENT | 15 | 0.01% |
| FLAG_DISPARITION_TOTALE | 450 | 0.45% |
| FLAG_AUCUN_NETTOYAGE | 1,200 | 1.2% |
| FLAG_NETTOYAGE_EXCESSIF | 800 | 0.8% |
| FLAG_TROP_GESTES | 350 | 0.35% |
| FLAG_TROP_NON_GESTES | 620 | 0.62% |
| FLAG_PERTE_EXCESSIVE | 280 | 0.28% |
| FLAG_GESTE_RETIRE | 8 | 0.008% |
| **Graphes conformes** | **96,277** | **96.3%** |

**Visualisations recommandées :**

1. **Histogrammes de distribution** des tailles T1, T2, T3
2. **Scatter plots** : T1 vs T2, T2 vs T3, T1 vs T3
3. **Boxplots** des ratios R1, R2, R3 par type de variante
4. **Heatmap** : Comptage des actions retirées par type de verbe

---

### 2.6 Test 6 : Cohérence Globale par Recette

#### Objectif
Vérifier que chaque recette possède l'ensemble cohérent de variantes attendues.

#### Règles de validation

**Pour chaque recette (identifiée par `id`), vérifier :**

1. **Présence obligatoire** :
   - **Exactement 1 variante_principale**
   - FLAG si 0 ou >1 variante principale

2. **Cohérence des variantes secondaires** :
   - **0 ou plusieurs variante_ingredients**
   - **0 ou plusieurs variante_permutation**
   - Si variante_ingredients existe : delta > 0 avec principale (Test 3)

3. **Présence tri-dataset** :
   - Pour chaque variante d'une recette, vérifier présence dans D1, D2, D3
   - FLAG si variante manquante dans un dataset

4. **Nombre total de variantes** :
   - Calculer : `nb_variantes = 1 (principale) + nb_ingredients + nb_permutations`
   - Identifier les recettes avec 1 seule variante (pas de diversité)
   - Identifier les recettes avec >10 variantes (suspect)

**Métriques à calculer :**

```
Distribution du nombre de variantes par recette :
- 1 variante (principale uniquement) : X%
- 2-3 variantes : X%
- 4-5 variantes : X%
- >5 variantes : X%

Recettes sans variantes secondaires : X%
Recettes avec variantes ingredients : X%
Recettes avec variantes permutations : X%
```

**Output attendu :**
```
Test 6 : Cohérence globale par recette

Total recettes : 100,000

Distribution des variantes :
- 1 variante : 45,000 (45%)
- 2-3 variantes : 35,000 (35%)
- 4-5 variantes : 15,000 (15%)
- >5 variantes : 5,000 (5%)

Flags détectés :
- Recettes sans variante principale : 12 (0.01%)
- Recettes avec >1 variante principale : 5 (0.005%)
- Variantes manquantes dans D2/D3 : 28 (0.03%)
```

---

## **STRATÉGIE 3 : Détection des Successions Illogiques**

### Objectif
Identifier les séquences d'actions sémantiquement incohérentes en utilisant une taxonomie culinaire et des règles de succession.

---

### 3.1 Taxonomie des Verbes par Catégorie Fonctionnelle

#### Classification des verbes

**CATÉGORIE 1 : PRÉPARATION INITIALE** (début de recette)
- **Gestes** : `wash, rinse, clean, peel, trim, core, pit, bone, devein, scale`
- **Caractéristiques** : Actions de nettoyage et préparation des ingrédients bruts
- **Position typique** : Début de séquence

**CATÉGORIE 2 : TRANSFORMATION MÉCANIQUE**
- **Gestes** : `chop, dice, slice, cut, mince, julienne, cube, halve, quarter, grate, shred, crush, grind, pound, tenderize, mash, puree`
- **Caractéristiques** : Modification de la forme/texture par action physique
- **Position typique** : Après préparation initiale, avant combinaison

**CATÉGORIE 3 : MÉLANGE / COMBINAISON**
- **Gestes** : `mix, stir, combine, whisk, beat, whip, fold, blend, toss, incorporate, emulsify, cream`
- **Caractéristiques** : Union de plusieurs ingrédients
- **Position typique** : Après transformations, avant cuisson

**CATÉGORIE 4 : TRANSFERT / MANIPULATION**
- **Gestes** : `pour, add, place, put, transfer, spread, layer, arrange, fill, stuff, wrap, coat, brush, drizzle, sprinkle, dust, top`
- **Caractéristiques** : Déplacement ou application d'ingrédients
- **Position typique** : Transition entre étapes

**CATÉGORIE 5 : CUISSON ACTIVE** (nécessite surveillance)
- **Gestes** : `sauté, stir-fry, pan-fry, sear, brown, caramelize, reduce, flip, turn, baste`
- **Non-gestes** : (aucun, car ces actions sont actives)
- **Caractéristiques** : Cuisson avec intervention continue
- **Position typique** : Milieu/fin de séquence

**CATÉGORIE 6 : CUISSON PASSIVE** (période d'attente)
- **Non-gestes** : `bake, roast, boil, simmer, steam, broil, grill, poach, braise, slow-cook, pressure-cook, smoke`
- **Caractéristiques** : Cuisson sans intervention, temps d'attente
- **Position typique** : Milieu/fin de séquence

**CATÉGORIE 7 : TRANSFORMATION THERMIQUE SANS CUISSON**
- **Non-gestes** : `cool, chill, freeze, refrigerate, thaw, defrost, warm, heat, reheat, melt`
- **Caractéristiques** : Changement de température
- **Position typique** : Variable selon recette

**CATÉGORIE 8 : ATTENTE / REPOS**
- **Non-gestes** : `idle, rest, set, settle, rise, proof, ferment, marinate, pickle, cure, age`
- **Caractéristiques** : Passage du temps sans action
- **Position typique** : Variable selon recette

**CATÉGORIE 9 : EXTRACTION / SÉPARATION**
- **Gestes** : `drain, strain, press, squeeze, filter, sift, separate, skim, extract`
- **Caractéristiques** : Retrait de liquide ou séparation de composants
- **Position typique** : Après cuisson ou trempage

**CATÉGORIE 10 : FINITION / SERVICE**
- **Gestes** : `garnish, plate, serve, decorate, present, cut (pour servir), slice (pour servir)`
- **Caractéristiques** : Dernières actions avant consommation
- **Position typique** : Fin de séquence

**CATÉGORIE 11 : ACTIONS SPÉCIALES**
- **Gestes** : `knead, roll, shape, form, mold, score, pierce, prick, skewer`
- **Caractéristiques** : Techniques spécifiques (pâtisserie, boulangerie)
- **Position typique** : Variable selon type de recette

---

### 3.2 Règles de Succession Impossibles

#### Type A : RÈGLES D'ORDRE STRICT (Violations = Erreur certaine)

**Règle A1 : Irréversibilité temporelle**
```
FINITION → PRÉPARATION INITIALE
```
- **Exemple invalide** : `serve → wash` (on ne sert pas puis on lave)
- **Exemple invalide** : `plate → peel` (on ne dresse pas puis on épluche)
- **Justification** : Les actions de finition sont par définition finales

**Règle A2 : Irréversibilité physique**
```
CUISSON (passive ou active) → TRANSFORMATION MÉCANIQUE (sur même ingrédient)
```
- **Exemple invalide** : `bake → chop` (on ne cuit pas puis on coupe)
- **Exemple invalide** : `sauté → dice` (on ne fait pas sauter puis on coupe en dés)
- **Exception** : Changement d'ingrédient (cuire A, puis couper B)
- **Justification** : On ne peut pas couper/hacher après cuisson (sauf cas très spécifiques)

**Règle A3 : Illogisme fonctionnel de finition**
```
FINITION → MÉLANGE
FINITION → CUISSON
```
- **Exemple invalide** : `serve → mix` (on ne sert pas puis on mélange)
- **Exemple invalide** : `garnish → bake` (on ne garnit pas puis on cuit)
- **Justification** : Après service, la recette est terminée

**Règle A4 : État incompatible de récipient**
```
TRANSFERT (remplissage) → PRÉPARATION INITIALE (dans même récipient)
```
- **Exemple invalide** : `pour_into_bowl → wash_bowl` (on ne verse pas puis on lave le bol)
- **Justification** : Contradiction d'état du récipient

---

#### Type B : RÈGLES DE SUSPICION (Violations = À investiguer)

**Règle B1 : Sauts de phase inhabituels**
```
PRÉPARATION INITIALE → FINITION (sans étapes intermédiaires)
```
- **Exemple suspect** : `chop → serve` (salade crue? ou étapes manquantes?)
- **Cas valides** : Salades, carpaccios, sushis (pas de cuisson)
- **Action** : Vérifier le type de recette

**Règle B2 : Répétitions suspectes**
```
Même action >3 fois consécutives (après dédoublonnage)
```
- **Exemple suspect** : `stir, stir, stir, stir` (possible pour risotto, mais vérifier)
- **Action** : Vérifier si répétition légitime ou erreur de dédoublonnage

**Règle B3 : Ordre inverse typique**
```
TRANSFERT → TRANSFORMATION MÉCANIQUE
```
- **Exemple suspect** : `pour → chop` (généralement on coupe puis on verse)
- **Exception** : Recettes multi-phases (faire une sauce, puis préparer garniture)
- **Action** : Vérifier le contexte (ingrédients multiples)

**Règle B4 : Cuisson sans préparation**
```
CUISSON comme première action (sans PRÉPARATION INITIALE)
```
- **Exemple suspect** : Séquence commence par `bake` ou `boil`
- **Cas valides** : Ingrédients pré-préparés ou pré-emballés
- **Action** : Vérifier liste d'ingrédients (sont-ils déjà transformés?)

**Règle B5 : Mélange après cuisson passive**
```
CUISSON PASSIVE → MÉLANGE (sans EXTRACTION entre)
```
- **Exemple suspect** : `bake → mix` (on ne mélange généralement pas après cuisson au four)
- **Exception** : `boil_pasta → drain → mix` (le drain intermédiaire rend la séquence valide)
- **Action** : Vérifier présence d'actions d'extraction

**Règle B6 : Transformation après transfert final**
```
TRANSFERT (vers plat de service) → TRANSFORMATION MÉCANIQUE
```
- **Exemple suspect** : `plate → slice` (on dresse puis on coupe?)
- **Cas valides** : `plate → slice` peut signifier "dresser en tranches" (ambiguïté sémantique)
- **Action** : Vérifier instruction originale

---

### 3.3 Patterns Valides mais Rares (Liste Blanche)

Certaines successions sont contre-intuitives mais légitimes :

**Pattern 1 : Cuisson multiple**
```
bake → cool → slice → toast
```
- **Contexte** : Pain ou gâteau (cuire, refroidir, trancher, griller)
- **Validité** : ✅ VALIDE

**Pattern 2 : Re-transformation**
```
cook → mash → mix → cook
```
- **Contexte** : Purées ou préparations cuites deux fois
- **Validité** : ✅ VALIDE

**Pattern 3 : Alternance cuisson-préparation (multitasking)**
```
boil_pasta → chop_vegetables → drain_pasta → sauté_vegetables → combine
```
- **Contexte** : Préparation parallèle de plusieurs composants
- **Validité** : ✅ VALIDE si les verbes s'appliquent à des ingrédients différents

**Pattern 4 : Déconstruction pour service**
```
bake → cool → slice → arrange → serve
```
- **Contexte** : Gâteaux, pains, tartes
- **Validité** : ✅ VALIDE

**Pattern 5 : Extraction répétée**
```
drain → rinse → drain
```
- **Contexte** : Pâtes, légumineuses (égoutter, rincer, ré-égoutter)
- **Validité** : ✅ VALIDE

---

### 3.4 Analyse Contextuelle (Fenêtres)

#### Problème
Une même paire d'actions peut être valide ou invalide selon le **contexte**.

#### Solution : Fenêtres contextuelles

**Pour chaque paire suspecte (action_i, action_i+1), examiner :**

1. **Fenêtre locale** : `[action_i-2, action_i-1, action_i, action_i+1, action_i+2]`
   - Identifier le "flux" de la recette autour de la paire

2. **Distance de la fin** :
   - Si `action_i` est dans les 2 dernières actions : probablement finition

3. **Distance du début** :
   - Si `action_i` est dans les 2 premières actions : probablement préparation

**Exemple d'analyse contextuelle :**

```
Séquence : [mix, pour_into_pan, bake, chop, serve]
Paire suspecte : (bake, chop)

Contexte :
- Actions avant : mix, pour_into_pan
- Actions après : serve
- Position : 3/5 (milieu-fin)

Analyse :
- bake (cuisson) suivi de chop (transformation) = SUSPECT
- Mais serve immédiatement après chop = chop pourrait être pour garniture
- Verdict : AMBIGU → Vérifier liste d'ingrédients

Si ingrédients contiennent "parsley" ou "garnish" : VALIDE (on coupe la garniture)
Sinon : ERREUR (on ne coupe pas le plat cuit)
```

---

### 3.5 Méthodologie de Détection

#### Algorithme conceptuel

**PHASE 1 : Annotation des catégories**
```
Pour chaque recette dans le dataset :
    Pour chaque action dans la séquence :
        Assigner la catégorie fonctionnelle (1-11)
    Stocker : [action1, cat1, action2, cat2, ..., actionN, catN]
```

**PHASE 2 : Détection des violations**
```
Pour chaque recette annotée :
    Pour chaque paire consécutive (action_i, action_i+1) :
        
        # Vérifier Règles Type A (erreurs certaines)
        Si (cat_i, cat_i+1) viole une règle Type A :
            FLAG "ERREUR_CERTAINE"
            Stocker : recette_id, position, paire, règle_violée
        
        # Vérifier Règles Type B (suspicions)
        Si (cat_i, cat_i+1) viole une règle Type B :
            FLAG "SUSPECT"
            Extraire contexte (fenêtre ±2)
            Stocker : recette_id, position, paire, règle_violée, contexte
```

**PHASE 3 : Vérification liste blanche**
```
Pour chaque paire flaggée "SUSPECT" :
    Si la paire correspond à un pattern de la liste blanche :
        RETIRER le flag
        Marquer : "VALIDE_EXCEPTIONNEL"
```

**PHASE 4 : Analyse contextuelle automatique**
```
Pour chaque paire flaggée "SUSPECT" restante :
    Analyser fenêtre contextuelle :
        - Identifier flux avant/après
        - Calculer distance début/fin
        - Vérifier présence d'actions intermédiaires explicatives
    
    Classifier :
        - ERREUR_PROBABLE (contexte confirme l'incohérence)
        - AMBIGU (nécessite vérification manuelle)
        - FAUX_POSITIF (contexte explique la succession)
```

**PHASE 5 : Génération du rapport**
```
Produire :
    1. Liste des ERREURS_CERTAINES (priorité haute)
    2. Liste des ERREURS_PROBABLES (priorité moyenne)
    3. Liste des AMBIGUS (nécessite investigation manuelle)
    4. Statistiques des patterns détectés
    5. Top 10 des successions problématiques les plus fréquentes
```

---

### 3.6 Métriques et Outputs

#### Métriques quantitatives

**Globales :**
- Nombre total de paires d'actions analysées
- Nombre de violations détectées (Type A + Type B)
- Taux de recettes avec au moins une anomalie
- Distribution des violations par règle

**Par catégorie de flag :**
```
ERREUR_CERTAINE : X occurrences (Y% des paires)
ERREUR_PROBABLE : X occurrences (Y% des paires)
SUSPECT : X occurrences (Y% des paires)
AMBIGU : X occurrences (Y% des paires)
VALIDE_EXCEPTIONNEL : X occurrences (Y% des paires)
```

**Top 10 des successions problématiques :**
```
1. bake → chop : 450 occurrences
2. serve → mix : 280 occurrences
3. pour → wash : 190 occurrences
4. plate → dice : 150 occurrences
...
```

**Distribution par catégorie de transition :**
```
Transitions FINITION → PRÉPARATION : X occurrences
Transitions CUISSON → TRANSFORMATION : X occurrences
Transitions FINITION → MÉLANGE : X occurrences
...
```

#### Outputs détaillés

**Fichier 1 : Rapport des erreurs certaines**
```csv
recipe_id, title, position, action_i, cat_i, action_i+1, cat_i+1, règle_violée, contexte
12345, "Gâteau chocolat", 8, "serve", "FINITION", "mix", "MÉLANGE", "A3", "[bake, cool, serve, mix, refrigerate]"
...
```

**Fichier 2 : Rapport des suspicions**
```csv
recipe_id, title, position, action_i, action_i+1, règle_violée, classification, contexte
67890, "Pâtes carbonara", 5, "pour", "chop", "B3", "AMBIGU", "[boil, drain, pour, chop, mix]"
...
```

**Fichier 3 : Statistiques par recette**
```csv
recipe_id, title, nb_actions, nb_erreurs_certaines, nb_suspects, score_qualité
12345, "Gâteau chocolat", 12, 2, 1, 0.75
...
```

**Score de qualité suggéré :**
```
score_qualité = 1 - (2×nb_erreurs_certaines + nb_suspects) / nb_actions
```

#### Visualisations recommandées

1. **Heatmap des transitions** :
   - Axe X : Catégories de départ
   - Axe Y : Catégories d'arrivée
   - Couleur : Nombre d'occurrences (ou taux d'erreur)

2. **Graphe de flux** (Sankey diagram) :
   - Visualiser les transitions les plus fréquentes entre catégories
   - Mettre en évidence les transitions problématiques

3. **Distribution des erreurs par complexité de recette** :
   - Boxplot : Score de qualité vs nombre d'actions
   - Identifier si les recettes complexes ont plus d'erreurs

---

### 3.7 Validation Manuelle sur Échantillon

#### Méthodologie

**Sélection de l'échantillon (100 recettes) :**
- **30 recettes flaggées "ERREUR_CERTAINE"** : Valider que ce sont de vraies erreurs
- **50 recettes flaggées "SUSPECT/AMBIGU"** : Classifier manuellement (erreur / valide)
- **20 recettes sans flag** : S'assurer qu'il n'y a pas de faux négatifs

**Processus de validation :**
1. Pour chaque recette, lire :
   - Séquence d'actions complète
   - Instructions originales
   - Liste d'ingrédients
2. Pour chaque paire flaggée, juger :
   - VRAI POSITIF : Flag correct, c'est bien une erreur
   - FAUX POSITIF : Flag incorrect, la succession est valide
   - INCERTAIN : Cas ambigu nécessitant plus de contexte
3. Documenter les raisons des faux positifs

**Calcul de la précision des règles :**
```
Précision = Vrais Positifs / (Vrais Positifs + Faux Positifs)

Objectif : Précision ≥ 80% pour Type A, ≥ 60% pour Type B
```

**Affinage des règles :**
- Identifier les patrons de faux positifs
- Ajouter des exceptions à la liste blanche
- Raffiner les règles contextuelles
- Ré-exécuter la détection avec règles améliorées

---

## **INTÉGRATION DES STRATÉGIES**

### Ordre d'exécution recommandé

**Phase 1 : Validation structurelle (Stratégie 2)**
- Durée estimée : 1-2 jours
- Output : Dataset filtré avec flags structurels
- Bénéfice : Élimine les erreurs grossières avant analyses fines

**Phase 2 : Détection sémantique (Stratégie 3)**
- Durée estimée : 2-3 jours
- Input : Dataset filtré de Phase 1
- Output : Flags de cohérence sémantique
- Bénéfice : Identification automatique des erreurs de logique culinaire

**Phase 3 : Validation manuelle (Stratégie 1)**
- Durée estimée : 3-5 jours
- Input : Échantillon stratifié + recettes problématiques des Phases 1-2
- Output : Gold standard + métriques de qualité du pipeline
- Bénéfice : Étalonnage final et mesure de la qualité globale

### Synergie entre stratégies

**Stratégie 2 → Stratégie 1 :**
- Sélectionner pour annotation manuelle :
  - 15 recettes "parfaites" (aucun flag structurel)
  - 20 recettes avec 1-2 flags structurels
  - 15 recettes avec ≥3 flags structurels

**Stratégie 3 → Stratégie 1 :**
- Inclure dans l'échantillon manuel :
  - 10 recettes avec erreurs certaines détectées
  - 10 recettes avec successions suspectes

**Stratégies 2+3 → Décisions de nettoyage :**
- Recettes avec flags critiques multiples : Ré-annotation prioritaire
- Recettes avec successions impossibles : Investigation approfondie
- Patterns d'erreurs systématiques : Amélioration du prompt LLM

---

## **LIVRABLES FINAUX**

### Documentation

**Rapport 1 : Stratégie 1 - Validation manuelle**
- Métriques de similarité (Accuracy, Jaccard, Levenshtein)
- Analyse des erreurs du LLM (ancien et nouveau)
- Recommandations d'amélioration du prompt
- Annexe : Fichier Excel des 50 recettes annotées

**Rapport 2 : Stratégie 2 - Validation structurelle**
- Statistiques de distribution des tailles
- Résultats des 6 tests avec flags
- Analyse de cohérence tri-dataset
- Recommandations de corrections

**Rapport 3 : Stratégie 3 - Détection sémantique**
- Taxonomie des verbes finalisée
- Règles de succession validées
- Liste des erreurs détectées (par priorité)
- Précision des règles (après validation manuelle)

**Rapport de synthèse : Qualité globale du dataset**
- Score de qualité global
- Distribution de la qualité par complexité/type de recette
- Plan d'action priorisé pour corrections
- Recommandations pour améliorer le pipeline

### Datasets nettoyés

- `graphs_recipes_validated.csv` : Dataset avec flags de qualité
- `graphs_recipes_high_quality.csv` : Sous-ensemble de haute qualité (sans flags)
- `recipes_to_reannotate.csv` : Liste des recettes nécessitant ré-annotation

---

**Fin du plan de test**