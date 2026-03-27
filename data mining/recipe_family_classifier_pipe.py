"""
Pipeline de Classification des Recettes par Famille et Type
============================================================
Laboratoire Liara - UQAC
Objectif : Classifier automatiquement les recettes en familles d'ingrédients
           et types de plats via LLM (OpenRouter) pour la création de macro-graphes.

Flux :
  Passe 1 : Titre seul → JSON {type, famille, confiance}
  Passe 2 : Titre + ingrédients (pour les NA/basse confiance de la Passe 1)
  Résidu  : Recettes non classifiables → flaggées AUTRE

Paramètres configurables :
  - batch_size     : nombre de titres par appel LLM (défaut=50)
  - max_retries    : tentatives en cas d'erreur serveur (défaut=5)
  - retry_delay_m  : multiplicateur de pause entre tentatives (défaut=3 min)
  - pause_10       : pause après 10 batches (défaut=30s)
  - pause_50       : pause après 50 batches (défaut=60s)
"""
from __future__ import annotations
import json
import time
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from openai import OpenAI

# ─────────────────────────────────────────────
# TAXONOMIE
# ─────────────────────────────────────────────

TYPES_PLATS = [
    "SOUPE",             # Soupes, bouillons, bisques, gazpacho, velouté
    "SALADE",            # Salades froides ou tièdes
    "PATE_NOUILLE",      # Pâtes, nouilles, ramen, spaghetti, lasagne
    "RIZ_CEREALE",       # Riz, risotto, quinoa, couscous, pilaf
    "VIANDE_GRILLEE",    # Grillades, rôtis, BBQ, skewers, brochettes
    "RAGOUT_MIJOTE",     # Ragoûts, currys, chili, pot-au-feu, stew
    "FOUR",              # Casseroles, gratins, quiches, pot pies, bakes
    "SAUTE_FRITURE",     # Stir-fry, friture, poêlée, tempura
    "SANDWICH_WRAP",     # Sandwichs, wraps, burgers, burritos, tacos
    "DESSERT_PATISSERIE",# Gâteaux, tartes, cookies, crèmes, muffins, cupcakes
    "PETIT_DEJ",         # Pancakes, omelettes, granola, waffles, french toast
    "SAUCE_CONDIMENT",   # Sauces, dips, vinaigrettes, pestos, marinades, guacamole
    "BOISSON",           # Smoothies, cocktails, jus, slushies, thés
    "SNACK_APERO",       # Snacks salés, apéros, popcorn nature, trail mix, biscotti
    "ACCOMPAGNEMENT",    # Purées, sides, stuffing, farces, garnitures, gratins de légumes
    "CONFISERIE",        # Bonbons, caramels, pralines, popcorn sucré, candy, confiseries japonaises
    "PLAT_ASIATIQUE",    # Sushi, dim sum, plats asiatiques culturellement spécifiques
    "COMPOSANT_BASE",    # Pâte à tarte, fond de sauce, base de recette, croûte
    "NON_CULINAIRE",     # Recettes pour animaux (dog treats), cosmétiques DIY, produits ménagers
    "AUTRE",             # Inclassifiable même avec les ingrédients
]

FAMILLES_INGREDIENTS = [
    "POULET",            # Poulet, dinde, canard, volaille
    "BOEUF",             # Bœuf, veau, steak, bœuf haché
    "PORC",              # Porc, bacon, jambon, saucisse, lard
    "AGNEAU",            # Agneau, mouton, gigot, kefta
    "POISSON",           # Saumon, thon, cabillaud, truite, halibut
    "FRUITS_MER",        # Crevettes, moules, crabe, homard, calamar
    "PATES",             # Spaghetti, penne, lasagne, macaroni, fettuccine
    "RIZ",               # Riz blanc, riz brun, risotto, fried rice
    "RIZ_CEREALE",       # Quinoa, couscous, orge, blé, muesli
    "LEGUMES",           # Légumes variés, courgette, brocoli, épinards, avocat
    "POMME_TERRE",       # Pommes de terre, patate douce, gnocchi
    "MAIS",              # Popcorn, maïs soufflé, masa, tortillas maïs, corn
    "LEGUMINEUSES",      # Lentilles, pois chiches, haricots, fèves
    "OEUFS",             # Œufs comme ingrédient principal
    "FROMAGE",           # Fromage, mozzarella, parmesan, cream cheese
    "LAITAGE",           # Yaourt, crème, lait, beurre comme principal
    "TOFU_SOJA",         # Tofu, tempeh, seitan, edamame
    "FRUITS",            # Fruits frais ou secs comme principal
    "CHOCOLAT",          # Chocolat, cacao, nutella
    "FARINE_PAIN",       # Farine, pain, pâte, brioche, pizza
    "CHAMPIGNON",        # Champignons comme ingrédient principal
    "FRUITS_SECS",       # Noix, amandes, pistaches, cacahuètes, peanut butter
    "AUTRE",             # Ingrédient principal non identifiable
]

NIVEAUX_CONFIANCE = ["haute", "moyenne", "basse"]

# ─────────────────────────────────────────────
# DESCRIPTIONS POUR LES PROMPTS
# ─────────────────────────────────────────────

_TYPE_DESC = {
    "SOUPE":              "soupes, bouillons, bisques, gazpacho, velouté",
    "SALADE":             "salades froides ou tièdes",
    "PATE_NOUILLE":       "pâtes, nouilles, ramen, spaghetti, lasagne",
    "RIZ_CEREALE":        "riz, risotto, quinoa, couscous, pilaf",
    "VIANDE_GRILLEE":     "grillades, rôtis, BBQ, skewers, brochettes",
    "RAGOUT_MIJOTE":      "ragoûts, currys, chili, pot-au-feu, stew",
    "FOUR":               "casseroles, gratins, quiches, pot pies, bakes au four",
    "SAUTE_FRITURE":      "stir-fry, friture, poêlée, tempura",
    "SANDWICH_WRAP":      "sandwichs, wraps, burgers, burritos, tacos",
    "DESSERT_PATISSERIE": "gâteaux, tartes, cookies, crèmes, muffins, cupcakes",
    "PETIT_DEJ":          "pancakes, omelettes, granola, waffles, french toast",
    "SAUCE_CONDIMENT":    "sauces, dips, vinaigrettes, pestos, marinades, guacamole",
    "BOISSON":            "smoothies, cocktails, jus, slushies, thés",
    "SNACK_APERO":        "snacks salés, apéros, popcorn nature, trail mix, biscotti",
    "ACCOMPAGNEMENT":     "purées, sides, stuffing, farces, garnitures — jamais plat principal",
    "CONFISERIE":         "bonbons, caramels, pralines, popcorn sucré, candy, confiseries japonaises (karintou)",
    "PLAT_ASIATIQUE":     "sushi, dim sum, plats asiatiques culturellement spécifiques",
    "COMPOSANT_BASE":     "pâte à tarte, fond de sauce, base de recette, croûte seule",
    "NON_CULINAIRE":      "recettes pour animaux (dog treats, pet food), cosmétiques DIY",
    "AUTRE":              "vraiment inclassifiable même avec les ingrédients",
}

_FAMILLE_DESC = {
    "POULET":       "poulet, dinde, canard, volaille",
    "BOEUF":        "bœuf, veau, steak, bœuf haché",
    "PORC":         "porc, bacon, jambon, saucisse, lard, hot dogs",
    "AGNEAU":       "agneau, mouton, gigot, kefta",
    "POISSON":      "saumon, thon, cabillaud, truite, halibut",
    "FRUITS_MER":   "crevettes, moules, crabe, homard, calamar",
    "PATES":        "spaghetti, penne, lasagne, macaroni, fettuccine",
    "RIZ":          "riz blanc, riz brun, risotto, fried rice",
    "RIZ_CEREALE":  "quinoa, couscous, orge, blé, muesli, wheat berry",
    "LEGUMES":      "légumes variés, courgette, brocoli, épinards, avocat, tomate",
    "POMME_TERRE":  "pommes de terre, patate douce, gnocchi",
    "MAIS":         "popcorn, maïs soufflé, masa, tortillas maïs, corn",
    "LEGUMINEUSES": "lentilles, pois chiches, haricots, fèves",
    "OEUFS":        "œufs comme ingrédient principal",
    "FROMAGE":      "fromage, mozzarella, parmesan, cream cheese",
    "LAITAGE":      "yaourt, crème, lait, beurre comme principal",
    "TOFU_SOJA":    "tofu, tempeh, seitan, edamame",
    "FRUITS":       "fruits frais ou secs comme principal",
    "CHOCOLAT":     "chocolat, cacao, nutella",
    "FARINE_PAIN":  "farine, pain, pâte, brioche, pizza, pretzels",
    "CHAMPIGNON":   "champignons comme ingrédient principal",
    "FRUITS_SECS":  "noix, amandes, pistaches, cacahuètes, peanut butter",
    "AUTRE":        "ingrédient principal non identifiable",
}

# ─────────────────────────────────────────────
# CHECKPOINT — REPRISE SUR INTERRUPTION
# ─────────────────────────────────────────────

def _checkpoint_path(output_path: Path, subset: str) -> Path:
    return output_path / f"checkpoint_{subset}.json"


def _save_checkpoint(output_path: Path, subset: str, passe: int,
                     last_batch: int, results_pass1: dict, results_pass2: dict):
    """Sauvegarde l'état courant pour permettre une reprise."""
    cp = {
        "subset":           subset,
        "passe":            passe,
        "last_batch":       last_batch,
        "timestamp":        datetime.now().isoformat(),
        "results_pass1":    results_pass1,
        "results_pass2":    results_pass2,
    }
    path = _checkpoint_path(output_path, subset)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cp, f, ensure_ascii=False)
    print(f"  💾 Checkpoint → {path.name}  (passe {passe}, batch {last_batch})")


def _load_checkpoint(output_path: Path, subset: str) -> dict | None:
    """Charge le checkpoint s'il existe, sinon retourne None."""
    path = _checkpoint_path(output_path, subset)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        cp = json.load(f)
    print(f"  🔄 Checkpoint trouvé → reprise passe {cp['passe']}, batch {cp['last_batch']+1}")
    print(f"     ({len(cp['results_pass1'])} résultats P1, {len(cp['results_pass2'])} résultats P2 déjà sauvegardés)")
    return cp


def _delete_checkpoint(output_path: Path, subset: str):
    """Supprime le checkpoint après un traitement réussi."""
    path = _checkpoint_path(output_path, subset)
    if path.exists():
        path.unlink()
        print(f"  🗑️  Checkpoint supprimé (traitement terminé proprement)")



# ─────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un expert en classification culinaire. Ton rôle est de classifier des recettes de cuisine en assignant à chacune un TYPE DE PLAT et une FAMILLE D'INGRÉDIENT PRINCIPAL, ainsi qu'un niveau de confiance.

RÈGLES STRICTES :
1. Tu dois retourner UNIQUEMENT un objet JSON valide, sans texte avant ni après, sans balises markdown.
2. Chaque recette doit recevoir exactement un type et une famille parmi les listes fournies.
3. Si le titre est trop ambigu ou générique pour classifier avec certitude, utilise "AUTRE" et confiance "basse".
4. Le TYPE décrit la forme du plat (comment il est préparé/servi).
5. La FAMILLE décrit l'ingrédient principal autour duquel tourne la recette.
6. Si plusieurs ingrédients sont importants, choisis celui qui est le plus central/dominant.

NIVEAUX DE CONFIANCE :
- "haute"   : Classification évidente depuis le titre, sans ambiguïté
- "moyenne" : Classification probable mais une autre interprétation est possible
- "basse"   : Titre trop générique ou culturellement spécifique, nécessite les ingrédients"""

def build_prompt_pass1(batch):  # list[dict]
    """Prompt Passe 1 : titre seul — liste brute sans descriptions pour économiser les tokens."""
    types_str    = "\n".join(f"  - {t}" for t in TYPES_PLATS)
    familles_str = "\n".join(f"  - {f}" for f in FAMILLES_INGREDIENTS)

    recipes_str = ",\n".join(
        f'  {{"id": "{r["id"]}", "titre": "{r["titre"]}"}}'
        for r in batch
    )

    return f"""Classifie les recettes suivantes en utilisant UNIQUEMENT les valeurs des listes ci-dessous.

TYPES DE PLATS AUTORISÉS :
{types_str}

FAMILLES D'INGRÉDIENTS AUTORISÉES :
{familles_str}

RECETTES À CLASSIFIER :
[
{recipes_str}
]

Retourne un JSON avec cette structure exacte (tableau, un objet par recette) :
[
  {{
    "id": "id_de_la_recette",
    "type": "TYPE_CHOISI",
    "famille": "FAMILLE_CHOISIE",
    "confiance": "haute|moyenne|basse"
  }},
  ...
]

RAPPEL : JSON pur uniquement, aucun texte autour."""


def build_prompt_pass2(batch):  # list[dict]
    """Prompt Passe 2 : titre + ingrédients pour les cas ambigus."""
    types_str    = "\n".join(f"  - {t:<25} # {_TYPE_DESC.get(t,'')}"    for t in TYPES_PLATS)
    familles_str = "\n".join(f"  - {f:<25} # {_FAMILLE_DESC.get(f,'')}" for f in FAMILLES_INGREDIENTS)

    recipes_str = ",\n".join(
        f'  {{"id": "{r["id"]}", "titre": "{r["titre"]}", "ingredients": "{r.get("ingredient", "")[:200]}"}}'
        for r in batch
    )

    return f"""Classifie les recettes suivantes. Ces recettes ont été difficiles à classifier avec le titre seul,
les ingrédients sont fournis pour t'aider. Utilise UNIQUEMENT les valeurs des listes ci-dessous.

TYPES DE PLATS AUTORISÉS :
{types_str}

FAMILLES D'INGRÉDIENTS AUTORISÉES :
{familles_str}

RECETTES À CLASSIFIER (avec ingrédients) :
[
{recipes_str}
]

Retourne un JSON avec cette structure exacte :
[
  {{
    "id": "id_de_la_recette",
    "type": "TYPE_CHOISI",
    "famille": "FAMILLE_CHOISIE",
    "confiance": "haute|moyenne|basse"
  }},
  ...
]

RAPPEL : JSON pur uniquement, aucun texte autour."""


# ─────────────────────────────────────────────
# APPEL LLM AVEC RETRY + BINARY SPLITTING
# ─────────────────────────────────────────────

def _call_llm_single(
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_retries: int,
    retry_delay_m: int,
    batch_label: str,
) -> None:  # returns list[dict] or None
    """
    Appel LLM brut sur un prompt donné, avec retries sur erreurs serveur.
    Retourne la liste parsée ou None si tous les retries échouent.
    """
    for attempt in range(1, max_retries + 1):
        try:
            completion = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "recipe_family_classifier",
                    "X-Title": "Recipe Family Classification Pipeline",
                },
                model=model_name,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            )

            raw = completion.choices[0].message.content.strip()

            # Nettoyage des balises markdown si présentes
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            parsed = json.loads(raw)

            if not isinstance(parsed, list):
                raise ValueError("Réponse LLM inattendue : pas un tableau JSON")

            return parsed

        except json.JSONDecodeError as e:
            print(f"    ⚠️  [{batch_label}] Tentative {attempt}/{max_retries} — JSON invalide : {e}")
        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in ["rate limit", "429", "503", "502", "unavailable", "timeout"]):
                wait = retry_delay_m * attempt * 60
                print(f"    ⚠️  [{batch_label}] Tentative {attempt}/{max_retries} — Erreur serveur : {e}")
                print(f"        ⏳ Pause {retry_delay_m * attempt} min avant retry...")
                time.sleep(wait)
            else:
                # Erreur non-serveur (ex: token limit) → pas la peine de retry
                print(f"    ⚠️  [{batch_label}] Erreur non-serveur : {e} → binary split si possible")
                return None  # Déclenche le split immédiatement

    print(f"    ❌  [{batch_label}] Échec après {max_retries} tentatives.")
    return None


def _validate_response(batch: list, response: list, batch_label: str):
    """
    Vérifie que tous les IDs envoyés sont présents dans la réponse.
    Retourne (ids_manquants, ids_inconnus).
    - ids_manquants : envoyés au LLM mais absents de la réponse
    - ids_inconnus  : présents dans la réponse mais pas dans le batch (hallucinations)
    """
    ids_envoyes = {str(r["id"]) for r in batch}
    ids_recus   = {str(item.get("id", "")) for item in response}

    ids_manquants = ids_envoyes - ids_recus
    ids_inconnus  = ids_recus - ids_envoyes

    if ids_manquants:
        print(f"    ⚠️  [{batch_label}] {len(ids_manquants)}/{len(batch)} IDs manquants → retraitement")
    if ids_inconnus:
        print(f"    ⚠️  [{batch_label}] {len(ids_inconnus)} IDs inconnus (hallucinations) → ignorés")

    return ids_manquants, ids_inconnus


def call_llm_recursive(
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    batch,           # list[dict]
    pass_number: int,
    max_retries: int = 5,
    retry_delay_m: int = 3,
    batch_label: str = "batch",
    depth: int = 0,
):  # returns list[dict]
    """
    Appel LLM récursif avec binary splitting et validation des IDs.

    1. Appel LLM sur le batch complet
    2. Validation : tous les IDs envoyés sont-ils dans la réponse ?
       - IDs manquants → retraitement récursif des recettes manquantes
       - IDs inconnus  → filtrés (hallucinations du LLM)
    3. Si l'appel échoue → binary split jusqu'aux recettes unitaires

    Args:
        batch        : Liste de dicts recettes à classifier
        pass_number  : 1 (titre seul) ou 2 (titre + ingrédients)
        depth        : Profondeur de récursion (pour logging)

    Returns:
        Liste de résultats classifiés, garantie couvrir tous les IDs du batch
    """
    if not batch:
        return []

    indent = "  " * depth
    label  = f"{batch_label}[{len(batch)}]"

    # Construction du prompt selon la passe
    if pass_number == 1:
        prompt = build_prompt_pass1(batch)
    else:
        prompt = build_prompt_pass2(batch)

    result = _call_llm_single(
        client, model_name,
        system_prompt, prompt,
        max_retries, retry_delay_m,
        batch_label=label,
    )

    # ── Succès → validation des IDs ─────────────────────────────
    if result is not None:
        if depth > 0:
            print(f"  {indent}✅ [{label}] Succès après split (profondeur {depth})")

        ids_manquants, ids_inconnus = _validate_response(batch, result, label)

        # Filtrer les IDs inconnus (hallucinations)
        if ids_inconnus:
            result = [r for r in result if str(r.get("id", "")) not in ids_inconnus]

        # Retraiter récursivement les IDs manquants
        if ids_manquants:
            sous_batch = [r for r in batch if str(r["id"]) in ids_manquants]
            result_manquants = call_llm_recursive(
                client, model_name, system_prompt,
                sous_batch, pass_number, max_retries, retry_delay_m,
                batch_label=f"{batch_label}M", depth=depth + 1,
            )
            result = result + result_manquants

        return result

    # ── Échec → Binary Split ────────────────────────────────────
    if len(batch) == 1:
        r = batch[0]
        print(f"  {indent}❌ Recette unitaire échouée : id={r['id']} → AUTRE/AUTRE")
        return [{
            "id": str(r["id"]),
            "type": "AUTRE",
            "famille": "AUTRE",
            "confiance": "basse",
        }]

    mid = len(batch) // 2
    left  = batch[:mid]
    right = batch[mid:]

    print(f"  {indent}✂️  [{label}] Split → [{len(left)}] + [{len(right)}] (profondeur {depth+1})")

    results_left  = call_llm_recursive(
        client, model_name, system_prompt,
        left,  pass_number, max_retries, retry_delay_m,
        batch_label=f"{batch_label}L", depth=depth + 1,
    )
    results_right = call_llm_recursive(
        client, model_name, system_prompt,
        right, pass_number, max_retries, retry_delay_m,
        batch_label=f"{batch_label}R", depth=depth + 1,
    )

    return results_left + results_right


# ─────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────

def classify_recipes_pipeline(
    # Sources de données
    titles_source,                      # DataFrame avec colonnes [id, title] OU chemin SQLite
    ingredients_source=None,            # DataFrame avec colonnes [id, title, ingredient] OU chemin CSV/SQLite
    sqlite_table: str = "recipes",      # Nom de la table si SQLite
    # OpenRouter
    api_key: str = "",
    model_name: str = "mistralai/mistral-7b-instruct",
    # Identification du subset
    subset: str = "1",                  # Identifiant du subset/exécuteur (ex: "1", "2", "exec1"…)
    # Batch & pauses
    batch_size: int = 50,
    pause_10: int = 30,                 # secondes après 10 batches
    pause_50: int = 60,                 # secondes après 50 batches
    # Retry
    max_retries: int = 5,
    retry_delay_m: int = 3,
    # Sortie
    output_dir: str = "./output_classification",
    save_intermediary: bool = True,
    save_every_n_batches: int = 200,     # fréquence de sauvegarde intermédiaire
):
    """
    Pipeline complet de classification des recettes en 2 passes.

    Passe 1 : title seul
    Passe 2 : title + ingredient pour les AUTRE/basse confiance

    Args:
        titles_source         : DataFrame [id, title] ou chemin .db SQLite
        ingredients_source    : DataFrame [id, title, ingredient] ou chemin CSV/.db
        sqlite_table          : Nom de table si SQLite
        api_key               : Clé OpenRouter
        model_name            : Modèle LLM à utiliser
        subset                : Identifiant du subset traité (ex: "1" pour exécuteur 1)
        batch_size            : Nombre de titres par appel LLM
        pause_10              : Pause en secondes après chaque 10 batches
        pause_50              : Pause en secondes après chaque 50 batches
        max_retries           : Tentatives max par batch en cas d'erreur
        retry_delay_m         : Multiplicateur (minutes) pour les pauses entre retries
        output_dir            : Répertoire de sortie
        save_intermediary     : Active les sauvegardes intermédiaires
        save_every_n_batches  : Fréquence de sauvegarde (défaut=20 batches)
    """

    start_time = datetime.now()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  PIPELINE DE CLASSIFICATION DES FAMILLES DE RECETTES")
    print("  Laboratoire Liara — UQAC")
    print("=" * 60)
    print(f"  Subset      : {subset}")
    print(f"  Modèle      : {model_name}")
    print(f"  Batch size  : {batch_size}")
    print(f"  Save every  : {save_every_n_batches} batches")
    print(f"  Max retries : {max_retries} (délai x{retry_delay_m} min)")
    print(f"  Pause 10b   : {pause_10}s | Pause 50b : {pause_50}s")
    print(f"  Sortie      : {output_dir}")
    print("=" * 60)

    # ── Chargement checkpoint éventuel ─────────────────────────
    cp = _load_checkpoint(output_path, subset)
    resume_passe      = cp["passe"]       if cp else 1
    resume_from_batch = cp["last_batch"]  if cp else -1  # -1 = from scratch
    results_pass1     = cp["results_pass1"] if cp else {}
    results_pass2     = cp["results_pass2"] if cp else {}
    if cp:
        print(f"  ▶️  Reprise depuis passe {resume_passe}, batch {resume_from_batch + 1}\n")
    else:
        print(f"  🆕 Démarrage from scratch\n")

    # ── Chargement des données ──────────────────────────────────
    print("\n📂 Chargement des données...")

    if isinstance(titles_source, pd.DataFrame):
        df_titles = titles_source[["id", "title"]].copy()
    elif isinstance(titles_source, str) and titles_source.endswith(".db"):
        conn = sqlite3.connect(titles_source)
        df_titles = pd.read_sql_query(f"SELECT id, title FROM {sqlite_table}", conn)
        conn.close()
    else:
        raise ValueError("titles_source doit être un DataFrame ou un chemin .db SQLite")

    df_titles["id"] = df_titles["id"].astype(str)
    total_recipes = len(df_titles)
    print(f"  ✅ {total_recipes} recettes chargées (subset {subset})")

    df_ingredients = None
    if ingredients_source is not None:
        if isinstance(ingredients_source, pd.DataFrame):
            df_ingredients = ingredients_source[["id", "title", "ingredient"]].copy()
        elif isinstance(ingredients_source, str) and ingredients_source.endswith(".csv"):
            df_ingredients = pd.read_csv(ingredients_source)[["id", "title", "ingredient"]]
        elif isinstance(ingredients_source, str) and ingredients_source.endswith(".db"):
            conn = sqlite3.connect(ingredients_source)
            df_ingredients = pd.read_sql_query("SELECT id, title, ingredient FROM ingredients", conn)
            conn.close()
        df_ingredients["id"] = df_ingredients["id"].astype(str)
        print(f"  ✅ Dataset ingrédients chargé : {len(df_ingredients)} entrées")
    else:
        print("  ⚠️  Pas de dataset ingrédients fourni (Passe 2 désactivée)")

    # ── Client OpenRouter ───────────────────────────────────────
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # ── PASSE 1 : Titre seul ────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  PASSE 1 — Classification par titre seul")
    print(f"{'─'*60}")

    records = df_titles.rename(columns={"title": "titre"}).to_dict("records")
    total_batches = (total_recipes + batch_size - 1) // batch_size
    print(f"  {total_recipes} recettes → {total_batches} batches de {batch_size}\n")

    # results_pass1/pass2 déjà initialisés depuis le checkpoint (ou {})
    # Note : avec le binary splitting récursif, il n'y a plus de "batch échoué"
    # Les recettes unitaires impossibles reçoivent AUTRE/AUTRE automatiquement

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end   = min(start + batch_size, total_recipes)
        batch = records[start:end]

        # ── Skip des batches déjà traités (reprise checkpoint) ──
        if resume_passe == 1 and batch_idx <= resume_from_batch:
            print(f"  [Batch {batch_idx+1}/{total_batches}] ⏭️  déjà traité — skip")
            continue

        print(f"  [Batch {batch_idx+1}/{total_batches}] recettes {start+1}–{end}... ", end="", flush=True)

        response = call_llm_recursive(
            client, model_name,
            SYSTEM_PROMPT, batch,
            pass_number=1,
            max_retries=max_retries,
            retry_delay_m=retry_delay_m,
            batch_label=f"P1-{batch_idx+1}",
            depth=0,
        )

        # Validation et stockage (call_llm_recursive retourne toujours une liste)
        valid = 0
        for item in response:
            rid = str(item.get("id", ""))
            t   = item.get("type", "AUTRE")
            f   = item.get("famille", "AUTRE")
            c   = item.get("confiance", "basse")

            if t not in TYPES_PLATS:          t = "AUTRE"
            if f not in FAMILLES_INGREDIENTS: f = "AUTRE"
            if c not in NIVEAUX_CONFIANCE:    c = "basse"

            results_pass1[rid] = {"type": t, "famille": f, "confiance": c}
            valid += 1

        print(f"✅ {valid}/{len(batch)} classifiés")

        # ── Pauses et sauvegardes inter-batches ────────────────
        batch_num = batch_idx + 1
        if batch_num % 50 == 0:
            print(f"\n  ⏸️  PAUSE {pause_50}s après {batch_num} batches...")
            if save_intermediary:
                _save_results(results_pass1, output_path,
                              f"sauvegarde_intermediaire_{subset}_p1_batch{batch_num}")
            _save_checkpoint(output_path, subset, 1, batch_idx, results_pass1, results_pass2)
            time.sleep(pause_50)
            print()
        elif batch_num % 10 == 0:
            print(f"\n  ⏸️  PAUSE {pause_10}s après {batch_num} batches...")
            if save_intermediary and batch_num % save_every_n_batches == 0:
                _save_results(results_pass1, output_path,
                              f"sauvegarde_intermediaire_{subset}_p1_batch{batch_num}")
            _save_checkpoint(output_path, subset, 1, batch_idx, results_pass1, results_pass2)
            time.sleep(pause_10)
            print()
        elif save_intermediary and batch_num % save_every_n_batches == 0:
            _save_results(results_pass1, output_path,
                          f"sauvegarde_intermediaire_{subset}_p1_batch{batch_num}")
            _save_checkpoint(output_path, subset, 1, batch_idx, results_pass1, results_pass2)

    # Stats Passe 1
    nb_haute   = sum(1 for v in results_pass1.values() if v["confiance"] == "haute")
    nb_moyenne = sum(1 for v in results_pass1.values() if v["confiance"] == "moyenne")
    nb_basse   = sum(1 for v in results_pass1.values() if v["confiance"] == "basse")
    nb_autre_t = sum(1 for v in results_pass1.values() if v["type"] == "AUTRE")
    nb_autre_f = sum(1 for v in results_pass1.values() if v["famille"] == "AUTRE")

    print(f"\n  📊 RÉSULTATS PASSE 1 :")
    print(f"     Classifiés        : {len(results_pass1)}/{total_recipes}")
    print(f"     Confiance haute   : {nb_haute} ({nb_haute/total_recipes*100:.1f}%)")
    print(f"     Confiance moyenne : {nb_moyenne} ({nb_moyenne/total_recipes*100:.1f}%)")
    print(f"     Confiance basse   : {nb_basse} ({nb_basse/total_recipes*100:.1f}%)")
    print(f"     Type=AUTRE        : {nb_autre_t}")
    print(f"     Famille=AUTRE     : {nb_autre_f}")

    # ── PASSE 2 : Titre + ingrédients (si disponible) ──────────
    results_pass2 = {}
    ids_for_pass2 = []

    # Candidats : confiance basse OU type/famille = AUTRE
    for rid, res in results_pass1.items():
        if res["confiance"] == "basse" or res["type"] == "AUTRE" or res["famille"] == "AUTRE":
            ids_for_pass2.append(rid)
    ids_for_pass2 = list(set(ids_for_pass2))

    if ids_for_pass2 and df_ingredients is not None:
        print(f"\n{'─'*60}")
        print(f"  PASSE 2 — Enrichissement avec ingrédients")
        print(f"  {len(ids_for_pass2)} recettes à reclassifier")
        print(f"{'─'*60}\n")

        # Construction du batch enrichi
        ingr_lookup  = dict(zip(df_ingredients["id"].astype(str),
                                df_ingredients["ingredient"].astype(str)))
        title_lookup = dict(zip(df_titles["id"].astype(str),
                                df_titles["title"].astype(str)))

        batch_p2 = [
            {
                "id": rid,
                "titre": title_lookup.get(rid, ""),
                "ingredient": ingr_lookup.get(rid, ""),
            }
            for rid in ids_for_pass2
        ]

        total_batches_p2 = (len(batch_p2) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches_p2):
            start = batch_idx * batch_size
            end   = min(start + batch_size, len(batch_p2))
            batch = batch_p2[start:end]

            # ── Skip des batches déjà traités (reprise checkpoint) ──
            if resume_passe == 2 and batch_idx <= resume_from_batch:
                print(f"  [Batch {batch_idx+1}/{total_batches_p2}] ⏭️  déjà traité — skip")
                continue

            print(f"  [Batch {batch_idx+1}/{total_batches_p2}] recettes {start+1}–{end}... ", end="", flush=True)

            response = call_llm_recursive(
                client, model_name,
                SYSTEM_PROMPT, batch,
                pass_number=2,
                max_retries=max_retries,
                retry_delay_m=retry_delay_m,
                batch_label=f"P2-{batch_idx+1}",
                depth=0,
            )

            valid = 0
            for item in response:
                rid = str(item.get("id", ""))
                t   = item.get("type", "AUTRE")
                f   = item.get("famille", "AUTRE")
                c   = item.get("confiance", "basse")
                if t not in TYPES_PLATS:          t = "AUTRE"
                if f not in FAMILLES_INGREDIENTS: f = "AUTRE"
                if c not in NIVEAUX_CONFIANCE:    c = "basse"
                results_pass2[rid] = {"type": t, "famille": f, "confiance": c, "passe": 2}
                valid += 1
            print(f"✅ {valid}/{len(batch)} reclassifiés")

            batch_num = batch_idx + 1
            if batch_num % 50 == 0:
                print(f"\n  ⏸️  PAUSE {pause_50}s après {batch_num} batches...")
                if save_intermediary:
                    _save_results(results_pass2, output_path,
                                  f"sauvegarde_intermediaire_{subset}_p2_batch{batch_num}")
                _save_checkpoint(output_path, subset, 2, batch_idx, results_pass1, results_pass2)
                time.sleep(pause_50)
                print()
            elif batch_num % 10 == 0:
                print(f"\n  ⏸️  PAUSE {pause_10}s après {batch_num} batches...")
                if save_intermediary and batch_num % save_every_n_batches == 0:
                    _save_results(results_pass2, output_path,
                                  f"sauvegarde_intermediaire_{subset}_p2_batch{batch_num}")
                _save_checkpoint(output_path, subset, 2, batch_idx, results_pass1, results_pass2)
                time.sleep(pause_10)
                print()
            elif save_intermediary and batch_num % save_every_n_batches == 0:
                _save_results(results_pass2, output_path,
                              f"sauvegarde_intermediaire_{subset}_p2_batch{batch_num}")
                _save_checkpoint(output_path, subset, 2, batch_idx, results_pass1, results_pass2)

    elif ids_for_pass2 and df_ingredients is None:
        print(f"\n  ⚠️  {len(ids_for_pass2)} recettes nécessitent la Passe 2 mais aucun dataset ingrédients fourni.")
        print(f"     Ces recettes garderont leur classification Passe 1 (AUTRE/basse).")

    # ── FUSION DES RÉSULTATS ────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  FUSION DES RÉSULTATS")
    print(f"{'─'*60}")

    final_results = {}
    for rid in df_titles["id"].astype(str):
        if rid in results_pass2:
            final_results[rid] = results_pass2[rid]
        elif rid in results_pass1:
            r = results_pass1[rid].copy()
            r["passe"] = 1
            final_results[rid] = r
        else:
            final_results[rid] = {
                "type": "AUTRE", "famille": "AUTRE",
                "confiance": "basse", "passe": 0
            }

    # ── CONSTRUCTION DU DATAFRAME FINAL ────────────────────────
    rows = []
    for rid, res in final_results.items():
        title = df_titles.loc[df_titles["id"].astype(str) == rid, "title"]
        title = title.values[0] if len(title) > 0 else ""
        rows.append({
            "id": rid,
            "title": title,
            "type": res["type"],
            "famille": res["famille"],
            "confiance": res["confiance"],
            "passe": res["passe"],
        })

    df_final = pd.DataFrame(rows)

    # ── SAUVEGARDE ──────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path  = output_path / f"recipe_classifications_subset{subset}.csv"
    #json_path = output_path / f"recipe_classifications_subset{subset}_{timestamp}.json"

    df_final.to_csv(csv_path, index=False, encoding="utf-8")

    metadata = {
        "subset": subset,
        "timestamp": timestamp,
        "model": model_name,
        "total_recipes": total_recipes,
        "batch_size": batch_size,
        "passe1_count": sum(1 for r in final_results.values() if r["passe"] == 1),
        "passe2_count": sum(1 for r in final_results.values() if r["passe"] == 2),
        "non_classes":  sum(1 for r in final_results.values() if r["passe"] == 0),
        "duration_sec": (datetime.now() - start_time).total_seconds(),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "classifications": final_results}, f,
                  indent=2, ensure_ascii=False)

    # Checkpoint supprimé — traitement terminé proprement
    _delete_checkpoint(output_path, subset)

    # ── STATISTIQUES FINALES ────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  RÉSULTATS FINAUX")
    print(f"{'='*60}")
    print(f"  Total recettes    : {total_recipes}")
    print(f"  Classifiés Passe1 : {metadata['passe1_count']} ({metadata['passe1_count']/total_recipes*100:.1f}%)")
    print(f"  Classifiés Passe2 : {metadata['passe2_count']} ({metadata['passe2_count']/total_recipes*100:.1f}%)")
    print(f"  Non classifiés    : {metadata['non_classes']} ({metadata['non_classes']/total_recipes*100:.1f}%)")
    print(f"  Durée totale      : {metadata['duration_sec']:.1f}s")
    print(f"\n  📁 Fichiers générés :")
    print(f"     CSV  → {csv_path}")
    print(f"     JSON → {json_path}")
    print(f"{'='*60}\n")

    # Top familles
    print("  🏆 Top 10 familles :")
    top_familles = df_final["famille"].value_counts().head(10)
    for famille, count in top_familles.items():
        print(f"     {famille:<20} : {count:>6} recettes")

    print("\n  🏆 Distribution des types :")
    top_types = df_final["type"].value_counts()
    for t, count in top_types.items():
        print(f"     {t:<25} : {count:>6} recettes")

    return df_final, metadata


# ─────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────

def _save_results(results: dict, output_path: Path, name: str):
    """Sauvegarde intermédiaire en JSON."""
    path = output_path / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  💾 Sauvegarde intermédiaire → {path.name}")


def load_classification_results(csv_path: str) -> pd.DataFrame:
    """Charge les résultats d'une classification précédente."""
    return pd.read_csv(csv_path)


def get_recipes_by_family(df: pd.DataFrame, famille: str, type_plat: str = None) -> pd.DataFrame:
    """Filtre les recettes par famille et optionnellement par type."""
    mask = df["famille"] == famille
    if type_plat:
        mask &= df["type"] == type_plat
    return df[mask]


def get_na_recipes(df: pd.DataFrame) -> pd.DataFrame:
    """Retourne les recettes non classifiées (AUTRE dans type ET famille)."""
    return df[(df["type"] == "AUTRE") & (df["famille"] == "AUTRE")]


