# Rapport de Validation Structurelle - Stratégie 2

**Date de génération** : 2026-01-08 04:50:18

---

## Introduction

Ce rapport présente les résultats de la validation structurelle des graphes de recettes.
La validation comprend 6 tests automatisés vérifiant la cohérence et la qualité des données.

---

## Test 1 : Calcul de la Taille des Listes d'Actions

Le Test 1 a été exécuté sur les **3 datasets** pour comparer l'évolution des statistiques.

### 📊 Dataset BRUT (Avant Nettoyage)

#### Statistiques Globales

- **Total de graphes** : 4,073,652
- **Longueur moyenne** : 11.22 ± 6.54 actions
- **Médiane** : 10.0
- **Min** : 0, **Max** : 1455
- **Quartiles** : Q1=7.0, Q3=14.0
- **Outliers** : 22,398 (0.55%)
- **Bornes outliers** : [-14.0, 35.0]

#### Statistiques par Variante

| Variante | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|----------|-------|----------------------|---------|---------|-------|----------|------------|
| variante_ingredients | 1,018,412 | 11.85 ± 7.07 | 11.0 | [0, 1455] | [7.0, 15.0] | 3,630 | 0.36% |
| variante_permutation | 2,036,908 | 11.12 ± 6.35 | 10.0 | [0, 130] | [7.0, 14.0] | 10,621 | 0.52% |
| variante_principale | 1,018,332 | 10.78 ± 6.34 | 10.0 | [0, 932] | [6.0, 14.0] | 2,993 | 0.29% |

#### Statistiques par Catégorie de Cuisine

| Catégorie | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|-----------|-------|----------------------|---------|---------|-------|----------|------------|
| bakery | 1,130,538 | 12.07 ± 6.48 | 11.0 | [0, 102] | [8.0, 15.0] | 6,926 | 0.61% |
| other | 1,881,639 | 11.28 ± 6.53 | 10.0 | [0, 835] | [7.0, 14.0] | 10,666 | 0.57% |
| quick_prep | 654,723 | 9.04 ± 6.26 | 8.0 | [0, 1455] | [5.0, 12.0] | 1,871 | 0.29% |
| stew | 406,752 | 12.10 ± 6.41 | 11.0 | [0, 843] | [8.0, 15.0] | 1,946 | 0.48% |

#### Statistiques par Niveau de Complexité

| Complexité | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|------------|-------|----------------------|---------|---------|-------|----------|------------|
| simple | 2,467,226 | 7.88 ± 3.69 | 8.0 | [0, 676] | [5.0, 10.0] | 1,168 | 0.05% |
| moyenne | 1,295,786 | 14.66 ± 4.71 | 14.0 | [0, 955] | [12.0, 17.0] | 2,892 | 0.22% |
| elevee | 310,640 | 23.43 ± 8.59 | 22.0 | [0, 1455] | [18.0, 27.0] | 1,519 | 0.49% |


### 📊 Dataset AVEC Non-Gestes

#### Statistiques Globales

- **Total de graphes** : 2,749,491
- **Longueur moyenne** : 11.25 ± 6.15 actions
- **Médiane** : 10.0
- **Min** : 0, **Max** : 128
- **Quartiles** : Q1=7.0, Q3=14.0
- **Outliers** : 13,449 (0.49%)
- **Bornes outliers** : [-14.0, 35.0]

#### Statistiques par Variante

| Variante | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|----------|-------|----------------------|---------|---------|-------|----------|------------|
| variante_ingredients | 617,859 | 12.89 ± 6.45 | 12.0 | [0, 128] | [8.0, 16.0] | 2,144 | 0.35% |
| variante_permutation | 1,113,319 | 10.87 ± 5.68 | 10.0 | [0, 95] | [7.0, 14.0] | 3,881 | 0.35% |
| variante_principale | 1,018,313 | 10.68 ± 6.27 | 10.0 | [0, 126] | [6.0, 14.0] | 2,975 | 0.29% |

#### Statistiques par Catégorie de Cuisine

| Catégorie | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|-----------|-------|----------------------|---------|---------|-------|----------|------------|
| bakery | 732,681 | 12.00 ± 6.27 | 11.0 | [0, 102] | [8.0, 15.0] | 4,005 | 0.55% |
| other | 1,272,517 | 11.40 ± 6.21 | 10.0 | [0, 128] | [7.0, 14.0] | 6,547 | 0.51% |
| quick_prep | 449,552 | 9.21 ± 5.40 | 8.0 | [0, 81] | [5.0, 12.0] | 1,136 | 0.25% |
| stew | 294,741 | 11.93 ± 5.99 | 11.0 | [0, 82] | [8.0, 15.0] | 1,170 | 0.40% |

#### Statistiques par Niveau de Complexité

| Complexité | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|------------|-------|----------------------|---------|---------|-------|----------|------------|
| simple | 1,667,382 | 8.10 ± 3.50 | 8.0 | [0, 71] | [6.0, 10.0] | 2,089 | 0.13% |
| moyenne | 890,627 | 14.59 ± 4.44 | 14.0 | [0, 65] | [12.0, 17.0] | 1,712 | 0.19% |
| elevee | 191,482 | 23.25 ± 7.84 | 22.0 | [1, 128] | [18.0, 27.0] | 869 | 0.45% |


### 📊 Dataset SANS Non-Gestes

#### Statistiques Globales

- **Total de graphes** : 2,241,617
- **Longueur moyenne** : 7.53 ± 4.42 actions
- **Médiane** : 7.0
- **Min** : 0, **Max** : 97
- **Quartiles** : Q1=4.0, Q3=10.0
- **Outliers** : 5,527 (0.25%)
- **Bornes outliers** : [-14.0, 28.0]

#### Statistiques par Variante

| Variante | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|----------|-------|----------------------|---------|---------|-------|----------|------------|
| variante_ingredients | 586,067 | 8.61 ± 4.57 | 8.0 | [0, 97] | [5.0, 11.0] | 1,652 | 0.28% |
| variante_permutation | 644,066 | 7.73 ± 4.13 | 7.0 | [0, 81] | [5.0, 10.0] | 2,694 | 0.42% |
| variante_principale | 1,011,484 | 6.78 ± 4.37 | 6.0 | [0, 95] | [4.0, 9.0] | 4,878 | 0.48% |

#### Statistiques par Catégorie de Cuisine

| Catégorie | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|-----------|-------|----------------------|---------|---------|-------|----------|------------|
| bakery | 593,926 | 8.30 ± 4.68 | 7.0 | [0, 85] | [5.0, 10.0] | 4,331 | 0.73% |
| other | 1,032,021 | 7.50 ± 4.41 | 7.0 | [0, 97] | [4.0, 10.0] | 2,502 | 0.24% |
| quick_prep | 378,276 | 6.67 ± 4.00 | 6.0 | [0, 58] | [4.0, 9.0] | 1,016 | 0.27% |
| stew | 237,394 | 7.12 ± 4.10 | 6.0 | [0, 54] | [4.0, 9.0] | 890 | 0.37% |

#### Statistiques par Niveau de Complexité

| Complexité | Count | Moyenne ± Écart-type | Médiane | Min-Max | Q1-Q3 | Outliers | % Outliers |
|------------|-------|----------------------|---------|---------|-------|----------|------------|
| simple | 1,341,046 | 5.42 ± 2.61 | 5.0 | [0, 49] | [4.0, 7.0] | 1,605 | 0.12% |
| moyenne | 736,254 | 9.58 ± 3.51 | 9.0 | [0, 42] | [7.0, 12.0] | 295 | 0.04% |
| elevee | 164,317 | 15.59 ± 6.00 | 15.0 | [0, 97] | [12.0, 19.0] | 535 | 0.33% |


### 📊 Comparaison des 3 Datasets (Test 1)

| Métrique | Brut | Avec Non-Gestes | Sans Non-Gestes |
|----------|------|-----------------|-----------------|
| Longueur moyenne | 11.22 | 11.25 | 7.53 |
| Écart-type | 6.54 | 6.15 | 4.42 |
| Médiane | 10.0 | 10.0 | 7.0 |
| Outliers (%) | 0.55% | 0.49% | 0.25% |

---

## Test 2 : Comparaison Variante Principale vs Nombre d'Instructions

- **Total variantes principales** : 1,018,313
- **Ratio moyen (actions/instructions)** : 1.10
- **Ratio médian** : 1.00

### Distribution des Flags

| Flag | Count | Pourcentage |
|------|-------|-------------|
| ✅ CONFORME | 844,879 | 82.97% |
| ⚠️ FLAG_RATIO_FAIBLE | 166,901 | 16.39% |
| ⚠️ FLAG_RATIO_ELEVE | 6,533 | 0.64% |
| ❌ FLAG_CRITIQUE | 0 | 0.00% |

---

## Test 3 : Validation Variante Ingrédients

- **Total paires principale-ingredient** : 617,668
- **Delta moyen (ingredient - principale)** : 1.52 actions
- **Delta médian** : 1.0
- **Delta min** : -86, **Delta max** : 43

### Distribution des Flags

| Flag | Count | Pourcentage |
|------|-------|-------------|
| ✅ CONFORME (1-10 ajouts) | 537,127 | 86.96% |
| ⚠️ FLAG_AUCUN_AJOUT | 55,183 | 8.93% |
| ⚠️ FLAG_TROP_AJOUT (>10) | 341 | 0.06% |
| ❌ FLAG_CRITIQUE_NEGATIF | 25,017 | 4.05% |

---

## Test 4A : Comparaison Permutations vs Principale

- **Total permutations** : 1,113,110
- **Overlap moyen** : 0.947
- **Distance Levenshtein moyenne** : 0.93

### Distribution des Flags

| Flag | Count | Pourcentage |
|------|-------|-------------|
| ✅ CONFORME (overlap 0.6-1.0) | 731,163 | 65.69% |
| ⚠️ FLAG_SIMILARITE_BASSE (<0.6) | 339,663 | 30.51% |
| ⚠️ FLAG_IDENTIQUE (=1.0) | 42,284 | 3.80% |

---

## Test 4B : Variante Ingrédients vs Principale (Similarité)

- **Total paires** : 617,668
- **Overlap moyen** : 0.836
- **Gestes ajoutés (moyenne)** : 1.49
- **Gestes ajoutés (médiane)** : 1.0

### Distribution des Flags

| Flag | Count | Pourcentage |
|------|-------|-------------|
| ✅ CONFORME | 474,002 | 76.74% |
| ⚠️ FLAG_SIMILARITE_BASSE (<0.7) | 65,967 | 10.68% |
| ⚠️ FLAG_AUCUN_AJOUT | 77,623 | 12.57% |
| ⚠️ FLAG_GESTES_INCORRECTS (>10) | 76 | 0.01% |

---

## Test 5 : Comparaison des 3 Datasets

- **Total recettes communes** : 1,011,484

### Taille Moyenne des Séquences (variante principale)

| Dataset | Moyenne | Médiane |
|---------|---------|---------|
| D1 (brut/avant nettoyage) | 10.84 | 10.0 |
| D2 (avec non-gestes) | 10.74 | 10.0 |
| D3 (sans non-gestes) | 6.78 | 6.0 |

### Ratios Moyens

| Ratio | Valeur |
|-------|--------|
| R1 (D2/D1) | 0.990 |
| R2 (D3/D2) | 0.635 |
| R3 (D3/D1) | 0.629 |

### Flags

| Flag | Count | Pourcentage |
|------|-------|-------------|
| ❌ FLAG_ORDRE_INCOHERENT (D1<D2 ou D2<D3) | 64213 | 6.35% |
| ✅ CONFORME | - | 93.65% |

---

## Test 6 : Cohérence Globale par Recette

- **Total recettes analysées** : 1,018,504

### Flags

| Flag | Count |
|------|-------|
| ❌ FLAG_NO_PRINCIPALE | 191 |
| ❌ FLAG_MULTIPLE_PRINCIPALE | 0 |
| ✅ CONFORME | 99.98% |

---

## Conclusion

### Récapitulatif des Flags Critiques

**Total de flags critiques détectés** : 89421

### Recommandations

1. **Examiner les recettes avec flags critiques** : Priorité absolue pour les FLAGS_CRITIQUE détectés dans les tests 2, 3, 5 et 6
2. **Vérifier l'intégrité du pipeline de nettoyage** : Les incohérences dans le Test 5 indiquent des problèmes potentiels
3. **Corriger les variantes avec incohérences structurelles** : Utiliser le dataset_synthese.csv pour identifier et corriger
4. **Analyser les patterns d'erreurs** : Identifier les types de recettes problématiques (par category/complexity)

---

## Fichiers Générés

- **strategy_2_report.md** : Ce rapport
- **dataset_synthese.csv** : Tous les flags détectés par test et par recette
- **dataset_resume.csv** : Nombre d'actions par recette/variante/dataset

---

**Fin du rapport** - Généré le 2026-01-08 à 04:50:18