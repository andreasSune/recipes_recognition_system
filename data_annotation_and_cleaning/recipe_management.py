import pandas as pd
import json
import requests
import re
import pandas as pd
import json
import time
import os
from typing import List, Dict
from datetime import datetime
from openai import OpenAI
import time
import pandas as pd
import ast
import numpy as np
from pathlib import Path



NOTEBOOK_DIR = Path().resolve()
PROJECT_ROOT = NOTEBOOK_DIR.parent   
DATA_DIR = PROJECT_ROOT / "data"

def create_batch_prompt(batch_instructions: pd.DataFrame,expected_count) -> str:
    """Crée un prompt optimisé pour un lot d'instructions"""
    
    instructions_list = batch_instructions.tolist()
    culinary_verbs = [
    "bake", "boil", "fry", "grill", "roast", "steam", "sauté", "simmer", "broil", "toast",
    "heat", "warm", "cool", "chill", "freeze", "melt", "dissolve", "mix", "stir", "combine",
    "chop", "dice", "slice", "cut", "mince", "grate", "peel", "core", "bone", "fillet",
    "trim", "wash", "clean", "marinate", "season", "salt", "oil", "grease", "coat", "stuff",
    "fill", "wrap", "tie", "arrange", "prepare", "braise", "poach", "blanch", "sear", "brown",
    "caramelize", "glaze", "reduce", "thicken", "whip", "beat", "fold", "knead", "rise", "proof",
    "ferment", "smoke", "cure", "pickle", "preserve", "drain", "strain", "press", "squeeze", "mash",
    "puree", "blend", "whisk", "cream", "emulsify", "separate", "extract", "filter", "sift", "dust",
    "deep fry", "stir fry", "pan fry", "barbecue", "pressure cook", "slow cook", "baste", "flip", "turn", "toss",
    "skewer", "pierce", "prick", "garnish", "plate", "serve", "drizzle", "sprinkle", "brush", "spread",
    "layer", "top", "decorate", "reheat", "taste", "adjust", "finish", "measure", "weigh", "scale"
]


    prompt = f"""You are an expert in cooking and text analysis.

    REFERENCE COOKING VERBS (choose from these when possible): {culinary_verbs}

    TASK: Analyze each instruction and identify the most appropriate cooking verb.

    Instructions to analyze:
    {instructions_list}

    CRITICAL RULES:
    1. For VALID COOKING INSTRUCTIONS: Choose from the reference list when possible
    2. For NON-COOKING content (emoticons like ":)", vague phrases like "set aside", empty strings, numbers only, non-food related text): Use {{"verb": "NA", "geste": "NA"}}
    3. For valid instructions: "geste" = true if it's a direct physical action by the cook (like chop, stir, mix)
    4. For valid instructions: "geste" = false if it's a cooking process/method (like bake, boil, simmer)
    5. ALWAYS return EXACTLY {expected_count} results - one for each input line
    6. Even if an input seems meaningless, still provide a response for it

    EXAMPLES:
    - "Chop the onions" → {{"verb": "chop", "geste": true}}
    - "Bake for 30 minutes" → {{"verb": "bake", "geste": false}}
    - ":)" → {{"verb": "NA", "geste": "NA"}}
    - "set aside" → {{"verb": "NA", "geste": "NA"}}
    - "" → {{"verb": "NA", "geste": "NA"}}
    - "123" → {{"verb": "NA", "geste": "NA"}}

    Return EXACTLY {expected_count} results in this JSON format:
    [
    {{"verb": "verb_name", "geste": true}},
    {{"verb": "NA", "geste": "NA"}},
    {{"verb": "verb_name", "geste": false}},
    ...
    ]

    Respond with ONLY valid JSON, no other text."""

    return prompt



def extract_json_from_response(content: str) -> List[Dict]:
    """Extrait le JSON de la réponse, même s'il y a du texte autour"""
    
    # Chercher un array JSON dans la réponse
    json_pattern = r'\[[\s\S]*?\]'
    matches = re.findall(json_pattern, content)
    
    for match in matches:
        try:
            result = json.loads(match)
            if isinstance(result, list) and all(isinstance(item, dict) for item in result):
                return result
        except json.JSONDecodeError:
            continue
    
    # Si pas d'array trouvé, chercher des objets individuels
    object_pattern = r'\{[^{}]*"verb"[^{}]*\}'
    matches = re.findall(object_pattern, content)
    
    objects = []
    for match in matches:
        try:
            obj = json.loads(match)
            objects.append(obj)
        except json.JSONDecodeError:
            continue
    
    return objects if objects else None

def save_intermediate_results(results: List[Dict], output_dir: str, batch_counter: int, id_subset :str):
    """Sauvegarde les résultats intermédiaires tous les 10 lots"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"intermediate_results_batch_{batch_counter}_subset_{id_subset}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Résultats intermédiaires sauvegardés: {filepath}")
    print(f"Total d'éléments traités: {len(results)}")

def save_final_results(results: List[Dict], output_dir: str, id_subset :str):
    """Sauvegarde les résultats finaux"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Sauvegarde JSON
    json_filename = f"final_results_subset_{id_subset}.json"
    json_filepath = os.path.join(output_dir, json_filename)
    
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Sauvegarde CSV pour faciliter l'analyse
    csv_filename = f"final_results_subset_{id_subset}.csv"
    csv_filepath = os.path.join(output_dir, csv_filename)
    
    #df = pd.DataFrame(results)
    #df.to_csv(csv_filepath, index=False, encoding='utf-8')
    
    print(f"Résultats finaux sauvegardés:")
    print(f"JSON: {json_filepath}")
    #print(f"CSV: {csv_filepath}")
    print(f"Total d'éléments traités: {len(results)}")

def data_cleaning(instructions):
    """
    Nettoie le dataframe en supprimant les lignes avec des instructions trop courtes
    
    Args:
        instructions (pd.DataFrame): DataFrame contenant une colonne 'instruction'
    
    Returns:
        pd.DataFrame: DataFrame nettoyé sans les instructions de moins de 5 caractères
    """
    # Supprimer les lignes où la longueur de la colonne 'instruction' est inférieure à 5
    cleaned_instructions = instructions[instructions['instruction'].str.len() >= 5]
    
    # Réinitialiser l'index après suppression des lignes
    cleaned_instructions = cleaned_instructions.reset_index(drop=True)
    
    print(f"Nombre d'instructions avant nettoyage: {len(instructions)}")
    print(f"Nombre d'instructions après nettoyage: {len(cleaned_instructions)}")
    print(f"Nombre d'instructions supprimées: {len(instructions) - len(cleaned_instructions)}")
    
    return cleaned_instructions


def save_temp_progress(all_results, failed_batch, output_dir, id_subset, batch_counter, current_index):
    """Sauvegarde temporaire des résultats en cours"""
    temp_dir = os.path.join(output_dir, "temp_saves")
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_data = {
        "results": all_results,
        "failed_batches": failed_batch,
        "batch_counter": batch_counter,
        "current_index": current_index,
        "timestamp": time.time(),
        "total_processed": len(all_results)
    }
    
    temp_file = os.path.join(temp_dir, f"temp_progress_{id_subset}_batch_{batch_counter}.json")
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(temp_data, f, indent=2, ensure_ascii=False)
    
    print(f"Sauvegarde temporaire effectuée : {temp_file}")
    return temp_file

def load_temp_progress(output_dir, id_subset):
    """Charge la dernière sauvegarde temporaire disponible"""
    temp_dir = os.path.join(output_dir, "temp_saves")
    if not os.path.exists(temp_dir):
        return None
    
    # Trouver le fichier de sauvegarde le plus récent
    temp_files = [f for f in os.listdir(temp_dir) if f.startswith(f"temp_progress_{id_subset}")]
    if not temp_files:
        return None
    
    # Trier par timestamp dans le nom du fichier
    temp_files.sort(key=lambda x: int(x.split('_batch_')[1].split('.json')[0]), reverse=True)
    latest_file = os.path.join(temp_dir, temp_files[0])
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            temp_data = json.load(f)
        print(f"Sauvegarde temporaire chargée : {latest_file}")
        return temp_data
    except Exception as e:
        print(f"Erreur lors du chargement de la sauvegarde temporaire : {e}")
        return None

class RateLimitExhaustedException(Exception):
    """Exception levée quand tous les essais pour gérer le rate limit ont échoué"""
    pass

def make_api_call_with_retry(
    api_key: str, 
    model_name: str, 
    prompt: str, 
    max_retries: int = 5,
    site_url: str = "",
    site_name: str = "",
    rate_limit_retries: int = 5,
    rate_limit_wait_multiplier: int = 3  
) :
    """Effectue l'appel API avec retry en cas d'erreur - VERSION OPENROUTER avec gestion améliorée du rate limiting"""
    
    # Initialiser le client OpenAI pour OpenRouter
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    # Préparer les headers optionnels
    extra_headers = {}
    if site_url:
        extra_headers["HTTP-Referer"] = site_url
    if site_name:
        extra_headers["X-Title"] = site_name
    
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                extra_headers=extra_headers,
                extra_body={},
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=4000,  # Mistral a une limite plus basse que Claude
                temperature=0.1,
            )
            
            content = completion.choices[0].message.content
            
            # DEBUG: Afficher la réponse brute
            print(f"Réponse brute (100 premiers caractères): {content[:100]}...")
            
            # Essayer d'extraire le JSON
            try:
                # Méthode 1: JSON direct
                result_json = json.loads(content.strip())
                if isinstance(result_json, list):
                    return result_json
            except json.JSONDecodeError:
                # Méthode 2: Extraction avec regex
                extracted = extract_json_from_response(content)
                if extracted:
                    return extracted
                
                print(f"Tentative {attempt + 1}: Impossible de parser le JSON")
                print(f"Contenu reçu: {content}")
                
                if attempt == max_retries - 1:
                    return None
                    
        except Exception as e:
            error_str = str(e)
            print(f"Erreur lors de la tentative {attempt + 1}: {error_str}")
            
            # Vérifier si c'est une erreur de rate limit
            if "429" in error_str or "rate limit" in error_str.lower():
                print(f"Rate limit détecté - Gestion avec {rate_limit_retries} essais")
                
                # Essayer de gérer le rate limit avec plusieurs tentatives
                for rate_attempt in range(rate_limit_retries):
                    wait_time = (rate_attempt + 1) * rate_limit_wait_multiplier * 60  # en secondes
                    print(f"Tentative rate limit {rate_attempt + 1}/{rate_limit_retries} - Attente de {wait_time/60} minutes...")
                    time.sleep(wait_time)
                    
                    try:
                        # Nouvelle tentative d'appel API
                        completion = client.chat.completions.create(
                            extra_headers=extra_headers,
                            extra_body={},
                            model=model_name,
                            messages=[
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            max_tokens=4000,
                            temperature=0.1,
                        )
                        
                        content = completion.choices[0].message.content
                        print(f"Succès après tentative rate limit {rate_attempt + 1}")
                        
                        # Essayer d'extraire le JSON
                        try:
                            result_json = json.loads(content.strip())
                            if isinstance(result_json, list):
                                return result_json
                        except json.JSONDecodeError:
                            extracted = extract_json_from_response(content)
                            if extracted:
                                return extracted
                        
                    except Exception as retry_e:
                        retry_error_str = str(retry_e)
                        print(f"Échec de la tentative rate limit {rate_attempt + 1}: {retry_error_str}")
                        
                        # Si c'est encore un 429, continuer avec la boucle rate limit
                        if "429" in retry_error_str or "rate limit" in retry_error_str.lower():
                            continue
                        else:
                            # Si c'est une autre erreur, sortir de la boucle rate limit
                            break
                
                # Si tous les essais rate limit ont échoué, lever une exception spécialisée
                print(f"Tous les essais rate limit ont échoué après {rate_limit_retries} tentatives")
                raise RateLimitExhaustedException(f"Rate limit non résolu après {rate_limit_retries} essais de {rate_limit_wait_multiplier} minutes chacun")
                
            elif "timeout" in error_str.lower():
                print(f"Timeout lors de la tentative {attempt + 1}")
                if attempt == max_retries - 1:
                    return None
            else:
                if attempt == max_retries - 1:
                    return None
    
    return None

def process_instructions_in_batches(
    sample, 
    api_key: str,
    model_name: str,
    batch_size: int,
    output_dir: str,
    id_subset : str,
    site_url: str = "",  
    site_name: str = "",
    resume_from_temp: bool = True,
    rate_limit_retries: int = 5,
    rate_limit_wait_multiplier: int = 3,
    temps_pause = 200  # temps de pause apres 25lots 
):
    """
    Traite les instructions par lots pour optimiser les coûts et éviter les timeouts
    Version adaptée pour model sur OpenRouter avec Mistral et sauvegarde temporaire
    """
    
    # Créer le dossier de sortie s'il n'existe pas
    os.makedirs(output_dir, exist_ok=True)
    
    # Charger les instructions
    instructions_df = pd.Series(sample)   
    total_instructions = len(instructions_df)
    
    # Variables d'initialisation
    all_results = []
    batch_counter = 0
    failed_batch = []
    start_index = 0
    
    # Vérifier s'il y a une sauvegarde temporaire à reprendre
    if resume_from_temp:
        temp_data = load_temp_progress(output_dir, id_subset)
        if temp_data:
            print(f"Reprise depuis la sauvegarde temporaire...")
            all_results = temp_data["results"]
            failed_batch = temp_data["failed_batches"]
            batch_counter = temp_data["batch_counter"]
            start_index = temp_data["current_index"]
            print(f"Reprise au lot {batch_counter}, index {start_index}")
    
    def process_batch_recursive(batch_instructions, start_index):
        """Fonction récursive pour traiter un lot avec division si nécessaire"""
        expected_size = len(batch_instructions)
        
        # Créer le prompt pour ce lot
        prompt = create_batch_prompt(batch_instructions, expected_size)
        
        # Appel API avec retry
        batch_result = make_api_call_with_retry(
            api_key, model_name, prompt, 5, site_url, site_name, 
            rate_limit_retries, rate_limit_wait_multiplier
        )
        
        if batch_result and len(batch_result) == expected_size:
            # Succès : retourner les résultats
            return batch_result
        else:
            # Échec : diviser le lot en deux si possible
            if len(batch_instructions) > 1:
                mid_point = len(batch_instructions) // 2
                first_half = batch_instructions.iloc[:mid_point]
                second_half = batch_instructions.iloc[mid_point:]
                
                print(f"Division du lot (taille {len(batch_instructions)}) en deux parties : {len(first_half)} + {len(second_half)}")
                
                # Traiter récursivement chaque moitié
                first_results = process_batch_recursive(first_half, start_index)
                second_results = process_batch_recursive(second_half, start_index + mid_point)
                
                return first_results + second_results
            else:
                # Lot de taille 1 qui échoue : ajouter aux échecs et retourner défaut
                print(f"Échec définitif pour l'instruction à l'index {start_index}")
                failed_batch.append(start_index)
                return [{"verb": "unknown", "geste": False}]
    
    # Traiter par lots
    for i in range(start_index, total_instructions, batch_size):
        batch_end = min(i + batch_size, total_instructions)
        batch_instructions = instructions_df.iloc[i:batch_end]
        batch_counter += 1
        
        print(f"Traitement du lot {batch_counter}/{(total_instructions + batch_size - 1)//batch_size}")
        print(f"Instructions {i+1} à {batch_end}")
        
        try:
            # Traiter le lot avec division récursive si nécessaire
            batch_results = process_batch_recursive(batch_instructions, i)
            all_results.extend(batch_results)
            
            print(f"Lot {batch_counter} traité avec succès ({len(batch_results)} résultats)")
            
            # Sauvegarde temporaire après chaque lot réussi
            #save_temp_progress(all_results, failed_batch, output_dir, id_subset, batch_counter, i + batch_size)
            
        except RateLimitExhaustedException as e:
            print(f"ARRÊT DU PROGRAMME - Rate limit non résolu: {str(e)}")
            print(f"Sauvegarde des résultats jusqu'au lot précédent (lot {batch_counter-1})")
            
            # Sauvegarder les résultats jusqu'au lot précédent
            emergency_file = save_temp_progress(
                all_results, failed_batch, output_dir, id_subset, 
                batch_counter-1, i  # On sauvegarde à l'index du lot qui a échoué pour reprendre ici
            )
            print(f"Sauvegarde d'arrêt effectuée dans : {emergency_file}")
            print(f"Pour reprendre, relancez le programme avec resume_from_temp=True")
            print(f"Le programme reprendra au lot {batch_counter} (index {i})")
            
            # Arrêter le programme proprement
            return all_results, failed_batch
            
        except Exception as e:
            error_str = str(e)
            print(f"Erreur critique lors du traitement du lot {batch_counter}: {error_str}")
            
            # Sauvegarde d'urgence en cas d'autres erreurs
            emergency_file = save_temp_progress(all_results, failed_batch, output_dir, id_subset, batch_counter, i)
            print(f"Sauvegarde d'urgence effectuée dans : {emergency_file}")
            raise e
        
        # Pause de 1 minute après chaque lot
        #print("Pause de 1 minute...")
        #time.sleep(60)
        
        # Sauvegarde et pause longue tous les 25 lots
        if batch_counter % 25 == 0:
            pause = temps_pause
            print(f"Pause de {pause} secondes après 25 lots...")
            time.sleep(pause) 
        
        if batch_counter % 250 == 0:
            save_intermediate_results(all_results, output_dir, batch_counter, id_subset)
            time.sleep(60)

        #if batch_counter == 500:
        #   time.sleep(600) 
    
    # Sauvegarde finale
    save_final_results(all_results, output_dir, id_subset)
    with open(os.path.join(output_dir, f"failed_batches_{id_subset}.json"), 'w') as f:
       json.dump(failed_batch, f)
    
    # Nettoyer les fichiers temporaires après succès
    cleanup_temp_files(output_dir, id_subset)
    
    return all_results, failed_batch

def cleanup_temp_files(output_dir, id_subset):
    """Nettoie les fichiers temporaires après traitement réussi"""
    temp_dir = os.path.join(output_dir, "temp_saves")
    if os.path.exists(temp_dir):
        temp_files = [f for f in os.listdir(temp_dir) if f.startswith(f"temp_progress_{id_subset}")]
        for temp_file in temp_files:
            try:
                os.remove(os.path.join(temp_dir, temp_file))
                print(f"Fichier temporaire supprimé : {temp_file}")
            except Exception as e:
                print(f"Erreur lors de la suppression de {temp_file}: {e}")


"""
#######################################             partie II            ################################################
Cette deuxieme partie nous permet de retraiter les instructions qui ont ete mal annotees pas le LLM donc nous allons extraires les lignes annotees NA et les repasser aux LLM

"""

def na_retreatment(subset,api_key, model_name, batch_size =20, resume_from_temp = False):
    
   
    instructions = pd.read_csv(f"Instructions_segments/Instructions_segment_{subset}.csv")
  
    instructions = data_cleaning(instructions)
    
    file_path = f"analysis_results_subset/final_results_subset_{subset}.json"
    with open(file_path, 'r') as f:
        results  = json.load(f)
    results = pd.DataFrame(results)
    #results.drop(columns= {'NA'},inplace= True)
    results['verb'] = results['verb'].replace('Unknown', np.nan)
    results.replace(
        to_replace=["NA", "NaN", "nan", "None", ""],
        value=np.nan,
        inplace=True
    )
    results.loc[(results['verb'] == 'Unknown') & (results['geste'] == False), 'geste'] = np.nan
    # remplacer les lignes de NA retraites dans le dataset final
   

    instructions['verb'] = results["verb"].values 
    instructions['geste'] = results["geste"].values 

    na_retreat = instructions[instructions.isna().any(axis=1)].copy()
    print(f"Nombre d'instructions avec NA: {len(na_retreat)}")

    results_2, failed_batch = process_instructions_in_batches(
        sample=na_retreat["instruction"],
        api_key= api_key,
        model_name= model_name,
        batch_size = batch_size,  
        output_dir="na_retreatment",
        id_subset= subset,
        site_url= "",  
        site_name=""  ,
        resume_from_temp= resume_from_temp,
        temps_pause = 80
    )
    results_2 = pd.DataFrame(results_2)
    #results.drop(columns= {'NA'},inplace= True)
    # Récupérer les index des lignes NaN
    na_index = instructions[instructions.isna().any(axis=1)].index

    # Vérifier que les tailles matchent
    assert len(na_index) == len(results_2), f"Mismatch: {len(na_index)} vs {len(results_2)}"

    # Remplacer seulement les lignes NaN
    instructions.loc[na_index, "verb"] = results_2["verb"].values
    instructions.loc[na_index, "geste"] = results_2["geste"].values

    instructions.to_csv(f'Instructions_segments_treated/Instructions_segment_{subset}.csv')


    return instructions




"""
#######################################             partie III             ################################################

"""



# preparation des donnees pour la prochaine partie
def data_preparation_to_extract_recipes_variants(subset ):

    """
        Cette fonction permet de preparer les donnees pour un 3e passage au LLM. elle se charge de creer la premiere variante des suite d'actions d'une recette en eliminant les non-geste puis ajoute les 
        instructions et les ingredients de chaque recette pour etre reexaminer afin de creer d'autres vairantes de suite d'actions

        subset: indice du segment de donnees a traiter 

        return  data: dataframe contenant les informations a traite
    """

    instructions = pd.read_csv(f'Instructions_segments_treated/Instructions_segment_{subset}.csv', index_col= 0)
    ingredients = pd.read_csv("recipe_ingredients.csv")
    recipes = pd.read_csv("recipes.csv")
    recipes = recipes[['id','title']]
    data = instructions.copy()
    data =  data.dropna()
    # joindre toutes les intructions et les ingredients en un seul bloc
    ingredients["ingredient"] = ingredients["ingredient"].fillna("").astype(str)
    df_instructions = data.groupby(['id'])["instruction"].agg(" ".join).reset_index() # [id, instruction]
    df_ingredients = ingredients.groupby(['id'])["ingredient"].agg(" ".join).reset_index() #[id,ingredient]


    if subset != 1: 
        data.drop(columns={'instruction', 'id_sec','geste'},inplace= True) #supprimer les colonne impertinente et garder [id,step,verb]
    else:
        data.drop(columns={'instruction', 'id_ter','geste'},inplace= True) #supprimer les colonne impertinente et garder [id,step,verb]

    data = pd.merge(recipes, data ,on= 'id', how= 'inner') #[title, id,step,verb]

    graph_recette = data.groupby( ["title",'id'])["verb"].agg(list).reset_index() #creation d'une liste d'actions pour chaque recette
    graph_recette = graph_recette.rename(columns={"verb": "actions"}) #[title, id,actions]
    graph_recette ['actions'] = graph_recette ['actions'].apply(lambda x: [key for key, _ in groupby(x)]) #supprimer dans la liste d'actions les verbes consecutifs egales

    data = pd.merge(graph_recette, df_instructions ,on= 'id', how= 'inner') #[title, id,actions, instructions]

    data = pd.merge(data, df_ingredients ,on= 'id', how= 'inner')  #[title, id,actions, instructions, ingredients]

    return data






def extract_json_from_response(response_text):
    """
    Extrait le JSON d'une réponse qui peut être mal formatée (avec des balises markdown, commentaires, etc.)
    
    Args:
        response_text (str): Texte de réponse brut du LLM
    
    Returns:
        dict: JSON parsé ou None si échec
    """
    try:
        # Méthode 1: JSON direct
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass
    
    try:
        # Méthode 2: Supprimer les balises markdown et les commentaires
        cleaned_text = response_text.strip()
        
        # Enlever les balises de début
        if cleaned_text.startswith('```json'):
            cleaned_text = cleaned_text[7:]
        elif cleaned_text.startswith('```'):
            cleaned_text = cleaned_text[3:]
        
        # Enlever les balises de fin
        if cleaned_text.endswith('```'):
            cleaned_text = cleaned_text[:-3]
        
        cleaned_text = cleaned_text.strip()
        
        # Supprimer les commentaires /* */
        cleaned_text = re.sub(r'/\*.*?\*/', '', cleaned_text, flags=re.DOTALL)
        
        # Supprimer les commentaires //
        cleaned_text = re.sub(r'//.*?$', '', cleaned_text, flags=re.MULTILINE)
        
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        pass
    
    try:
        # Méthode 3: Regex pour extraire tout entre les balises markdown + nettoyage
        markdown_pattern = r'```(?:json)?\s*(.*?)\s*```'
        markdown_match = re.search(markdown_pattern, response_text, re.DOTALL)
        if markdown_match:
            json_text = markdown_match.group(1).strip()
            # Supprimer les commentaires
            json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
            json_text = re.sub(r'//.*?$', '', json_text, flags=re.MULTILINE)
            # Convertir les tuples Python (x, y) en arrays JSON [x, y]
            json_text = re.sub(r'\((\d+),\s*(\d+)\)', r'[\1, \2]', json_text)
            return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    try:
        # Méthode 4: Chercher le JSON complet avec accolades équilibrées + nettoyage
        json_pattern = r'\{.*\}'
        json_match = re.search(json_pattern, response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group()
            # Supprimer les commentaires
            json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
            json_text = re.sub(r'//.*?$', '', json_text, flags=re.MULTILINE)
            return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    try:
        # Méthode 5: Chercher spécifiquement le pattern "recipes"
        recipes_pattern = r'"recipes"\s*:\s*(\[.*\])'
        recipes_match = re.search(recipes_pattern, response_text, re.DOTALL)
        if recipes_match:
            recipes_text = recipes_match.group(1)
            # Supprimer les commentaires
            recipes_text = re.sub(r'/\*.*?\*/', '', recipes_text, flags=re.DOTALL)
            recipes_text = re.sub(r'//.*?$', '', recipes_text, flags=re.MULTILINE)
            minimal_json = f'{{"recipes": {recipes_text}}}'
            return json.loads(minimal_json)
    except json.JSONDecodeError:
        pass
    
    return None

# ================================ ÉTAPE 1: RÉÉVALUATION DE LA VARIANTE PRINCIPALE ================================

def stage_1_reevaluate_main_variant(recipes_batch, api_key, model_name, max_retries=3):
    """
    ÉTAPE 1: Réévalue et corrige la variante principale de chaque recette
    
    Args:
        recipes_batch (list): Liste des recettes avec leurs données
        api_key (str): Clé API OpenRouter
        model_name (str): Nom du modèle à utiliser
        max_retries (int): Nombre maximum de tentatives en cas d'erreur 429
    
    Returns:
        dict: {recipe_id: corrected_main_variant}
    """
    
    # Construction du prompt pour multiple recettes
    recipes_data = []
    for i, recipe in enumerate(recipes_batch):
        actions_str = ", ".join(recipe['actions'])
        recipe_info = f"""
RECIPE {i+1}:
ID: {recipe['id']}
TITLE: {recipe['title']}
CURRENT ACTION SEQUENCE: [{actions_str}]
COMPLETE INSTRUCTIONS: {recipe['instructions']}
INGREDIENTS: {recipe['ingredients']}
"""
        recipes_data.append(recipe_info)
    
    recipes_text = "\n".join(recipes_data)
    
    prompt = f"""
You are a culinary expert specialized in analyzing cooking action sequences.

Here are {len(recipes_batch)} recipes with their current action sequences:

{recipes_text}

TASK: RÉÉVALUATION DE LA SÉQUENCE PRINCIPALE
For EACH recipe, you must:

1. **ANALYZE THE CURRENT SEQUENCE**: Examine if the current action sequence captures ALL the action verbs mentioned in the complete instructions, including both physical gestures AND non-gesture actions.

2. **IDENTIFY MISSING ACTIONS IN INSTRUCTIONS**: Carefully compare each instruction sentence with the current sequence. Look for ALL action verbs (gestures and non-gestures) that are mentioned in the instructions but are missing from the current list.

3. **CORRECT AND COMPLETE**: If actions are missing, add them at their logical position. If the sequence is already complete, return it unchanged.

INCLUDE ALL ACTION TYPES:
- **Physical gestures**: add, mix, stir, cut, chop, slice, dice, pour, season, blend, whip, fold, spread, grate, peel, wash, clean, drain, strain, cube, mince, crush, beat, core, seed, flip, turn, toss, combine, knead, roll, press, squeeze, scrape, sprinkle, garnish, arrange, layer, wrap, unwrap, open, close, etc.
- **Non-gesture actions**: preheat, cool, refrigerate, boil, simmer, bake, broil, freeze, thaw, chill, warm, rest, set, marinate, steep, proof, rise, cook, fry, sauté, roast, grill, steam, poach, braise, sear, brown, reduce, bring, let, etc.

EXAMPLE:
Recipe: Fig Jam
- Current sequence: ["clean", "cut", "mix"]
- Instructions: "clean figs, take off remainder of the stems. cut in halfs in a large pot add sugar, jello, can of strawberries and juice, and figs, bring to a hard boil, stirring mix well. let it boil hard for 10 minutes, reduce heat to simmer boil, stir constantly for 15 minutes. take off heat and let cool to warm temp, now ready to put the jam in a jar."
- Missing actions identified: "add", "bring", "boil", "stir", "reduce", "simmer", "cool"
- Corrected sequence: ["clean", "cut", "add", "bring", "boil", "stir", "mix", "reduce", "simmer", "stir", "cool"]

RESPONSE FORMAT:
Return ONLY a JSON with this exact structure:
{{
  "recipes": [
    {{
      "id": "recipe_id_1",
      "corrected_sequence": ["action1", "action2", "action3"]
    }},
    {{
      "id": "recipe_id_2",
      "corrected_sequence": ["action1", "action2", "action3", "action4"]
    }},
    ...
  ]
}}

IMPORTANT:
- Process ALL {len(recipes_batch)} recipes
- Return ONLY the JSON, no explanations
- Include ALL action verbs (both gestures and non-gestures)
- If no correction needed, return the original sequence
- Ensure logical order of actions
- Do not invent actions not mentioned in the instructions
"""

    for retry in range(max_retries):
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            
            extra_headers = {
                "HTTP-Referer": "recipe variants generator",
                "X-Title": "Stage 1: Main Variant Reevaluation"
            }
            
            completion = client.chat.completions.create(
                extra_headers=extra_headers,
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert culinaire qui corrige les séquences d'actions de cuisine avec précision."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=6000,
                temperature=0.1,
            )
            
            llm_response = completion.choices[0].message.content.strip()
            print(f"Réponse brute (100 premiers caractères): {llm_response[:100]}...")
            result = extract_json_from_response(llm_response)

            if result is None:
                print("Erreur: Impossible de parser la réponse JSON pour l'étape 1")
                return None
            
            # Traitement des résultats
            stage_1_results = {}
            recipes_results = result.get("recipes", [])
            
            for recipe_result in recipes_results:
                recipe_id = recipe_result.get("id")
                corrected_sequence = recipe_result.get("corrected_sequence", [])
                stage_1_results[recipe_id] = corrected_sequence
            
            return stage_1_results
            
        except Exception as e:
            if "429" in str(e):
                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 3 * 60  # (retry+1) * 3 minutes
                    print(f"    Erreur 429 à l'étape 1, attente de {wait_time//60} minutes (tentative {retry+1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"    Erreur 429 persistante après {max_retries} tentatives à l'étape 1")
                    raise Exception("429_max_retries")
            else:
                print(f"Erreur lors de l'étape 1: {str(e)}")
                return None
    
    return None

# ================================ ÉTAPE 2: GÉNÉRATION DES VARIANTES SECONDAIRES ================================

def stage_2_generate_secondary_variants(recipes_batch, stage_1_results, api_key, model_name, max_retries=3):
    """
    ÉTAPE 2: Génère 3 variantes secondaires basées sur les résultats de l'étape 1
    
    Args:
        recipes_batch (list): Liste des recettes originales
        stage_1_results (dict): Résultats de l'étape 1 {recipe_id: corrected_sequence}
        api_key (str): Clé API OpenRouter
        model_name (str): Nom du modèle
        max_retries (int): Nombre maximum de tentatives en cas d'erreur 429
    
    Returns:
        dict: {recipe_id: {"ingredient_variant": [...], "permutation_1": [...], "permutation_2": [...]}}
    """
    
    # Construction du prompt avec les séquences corrigées
    recipes_data = []
    for i, recipe in enumerate(recipes_batch):
        recipe_id = recipe['id']
        corrected_sequence = stage_1_results.get(recipe_id, recipe['actions'])
        actions_str = ", ".join(corrected_sequence)
        
        recipe_info = f"""
RECIPE {i+1}:
ID: {recipe['id']}
TITLE: {recipe['title']}
CORRECTED MAIN SEQUENCE: [{actions_str}]
COMPLETE INSTRUCTIONS: {recipe['instructions']}
INGREDIENTS: {recipe['ingredients']}
"""
        recipes_data.append(recipe_info)
    
    recipes_text = "\n".join(recipes_data)
    
    prompt = f"""
You are a culinary expert specialized in creating cooking sequence variants.

Here are {len(recipes_batch)} recipes with their CORRECTED main sequences from Stage 1:

{recipes_text}

TASK: GENERATE 3 SECONDARY VARIANTS
For EACH recipe, create exactly 3 variants:

1. **INGREDIENT-BASED VARIANT**: Analyze ingredients for pre-processed items and add preparation gestures
2. **PERMUTATION VARIANT 1**: Logically reorder the corrected sequence while respecting cooking constraints  
3. **PERMUTATION VARIANT 2**: Another logical reordering, different from variant 1

DETAILED RULES:

**INGREDIENT-BASED VARIANT:**
- Look for ingredients indicating pre-processing: "diced onions" → add "dice", "sliced tomatoes" → add "slice"
- Pre-processing terms: cubed→cube, diced→dice, chopped→chop, sliced→slice, minced→mince, grated→grate, shredded→shred, crushed→crush, beaten→beat, peeled→peel, cored→core, seeded→seed
- Place ingredient preparation actions AT THE BEGINNING
- Then include all actions from the corrected main sequence
- Example: Main=["mix", "pour"], Ingredients="diced tomatoes, sliced onions" → Variant=["dice", "slice", "mix", "pour"]

**PERMUTATION VARIANTS:**
- Respect cooking logic: preparation → combination → finishing
- Don't mix ingredients before cutting them
- Don't add liquids before solids are ready
- Don't season before main ingredients are combined
- Example: Main=["cut", "season", "mix", "pour"] → Variant1=["cut", "mix", "season", "pour"], Variant2=["season", "cut", "mix", "pour"]

EXAMPLES:

Recipe: Tomato Salad
- Main sequence: ["cut", "add", "mix", "season"]  
- Ingredients: "diced tomatoes, sliced cucumbers, olive oil, salt"
- Ingredient variant: ["dice", "slice", "cut", "add", "mix", "season"]
- Permutation 1: ["cut", "season", "add", "mix"]
- Permutation 2: ["cut", "mix", "add", "season"]

RESPONSE FORMAT:
{{
  "recipes": [
    {{
      "id": "recipe_id_1",
      "variants": {{
        "ingredient_variant": ["action1", "action2", "action3"],
        "permutation_1": ["action1", "action3", "action2"],
        "permutation_2": ["action2", "action1", "action3"]
      }}
    }},
    ...
  ]
}}

IMPORTANT:
- Process ALL {len(recipes_batch)} recipes
- Each recipe MUST have exactly 3 variants
- If no meaningful variant possible, return the corrected main sequence
- Only include PHYSICAL GESTURES
- Ensure all variants are logically coherent
- Return ONLY the JSON
"""

    for retry in range(max_retries):
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            
            extra_headers = {
                "HTTP-Referer": "recipe variants generator",
                "X-Title": "Stage 2: Secondary Variants Generation"
            }
            
            completion = client.chat.completions.create(
                extra_headers=extra_headers,
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert culinaire qui crée des variantes logiques de séquences d'actions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=8000,
                temperature=0.2,
            )
            
            llm_response = completion.choices[0].message.content.strip()
            print(f"Réponse brute (100 premiers caractères): {llm_response[:100]}...")
            result = extract_json_from_response(llm_response)

            if result is None:
                print("Erreur: Impossible de parser la réponse JSON pour l'étape 2")
                return None
            
            # Traitement des résultats
            stage_2_results = {}
            recipes_results = result.get("recipes", [])
            
            for recipe_result in recipes_results:
                recipe_id = recipe_result.get("id")
                variants = recipe_result.get("variants", {})
                stage_2_results[recipe_id] = variants
            
            return stage_2_results
            
        except Exception as e:
            if "429" in str(e):
                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 3 * 60
                    print(f"    Erreur 429 à l'étape 2, attente de {wait_time//60} minutes (tentative {retry+1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"    Erreur 429 persistante après {max_retries} tentatives à l'étape 2")
                    raise Exception("429_max_retries")
            else:
                print(f"Erreur lors de l'étape 2: {str(e)}")
                return None
    
    return None

# ================================ ÉTAPE 3: GÉNÉRATION DE LA VARIANTE TEMPORELLE ================================

def stage_3_generate_temporal_variant(recipes_batch, stage_1_results, api_key, model_name, max_retries=3):
    """
    ÉTAPE 3: Génère une variante temporelle en remplaçant les non-gestes par des tuples (min, max)
    
    Args:
        recipes_batch (list): Liste des recettes originales
        stage_1_results (dict): Résultats de l'étape 1
        api_key (str): Clé API OpenRouter
        model_name (str): Nom du modèle
        max_retries (int): Nombre maximum de tentatives en cas d'erreur 429
    
    Returns:
        dict: {recipe_id: temporal_variant_with_tuples}
    """
    
    # Construction du prompt avec les séquences corrigées et les instructions
    recipes_data = []
    for i, recipe in enumerate(recipes_batch):
        recipe_id = recipe['id']
        corrected_sequence = stage_1_results.get(recipe_id, recipe['actions'])
        actions_str = ", ".join(corrected_sequence)
        
        recipe_info = f"""
RECIPE {i+1}:
ID: {recipe['id']}
TITLE: {recipe['title']}
CORRECTED MAIN SEQUENCE: [{actions_str}]
COMPLETE INSTRUCTIONS: {recipe['instructions']}
"""
        recipes_data.append(recipe_info)
    
    recipes_text = "\n".join(recipes_data)
    
    prompt = f"""
You are a culinary expert specialized in timing estimation for cooking processes.

Here are {len(recipes_batch)} recipes with their corrected sequences:

{recipes_text}

TASK: GENERATE TEMPORAL VARIANTS
For EACH recipe:

1. **ANALYZE THE INSTRUCTIONS** for time-related non-gesture actions mentioned
2. **IDENTIFY NON-GESTURE ACTIONS** that should be represented as time durations
3. **CREATE TEMPORAL VARIANT** by replacing non-gestures with (min, max) time tuples in MINUTES

TIME-RELATED NON-GESTURES TO CONVERT:
- cook, simmer, boil → (cooking time range)
- bake, roast → (baking time range)  
- chill, cool, refrigerate → (cooling time range)
- rest, set → (resting time range)
- marinate → (marinating time range)
- steep → (steeping time range)
- proof, rise → (rising time range)
- freeze → (freezing time range)

PHYSICAL GESTURES TO KEEP AS-IS:
cut, chop, slice, mix, stir, add, pour, season, blend, whip, fold, spread, grate, peel, wash, drain, etc.

TIMING ESTIMATION RULES:
- **Quick processes**: 1-5 minutes (simmer briefly, cool slightly)
- **Medium processes**: 5-15 minutes (cook vegetables, bake cookies)  
- **Long processes**: 15-60 minutes (roast meat, bake bread)
- **Extended processes**: 60+ minutes (marinate, proof dough, freeze)
- Always give realistic ranges, not single values

EXAMPLES:

Recipe: Pasta with sauce
- Instructions mention: "cook pasta for 8-10 minutes, simmer sauce"
- Corrected sequence: ["chop", "cook", "simmer", "drain", "mix"]
- Temporal variant: ["chop", [8, 12], [5, 10], "drain", "mix"]

Recipe: Chocolate chip cookies  
- Instructions mention: "bake for 12 minutes, cool completely"
- Corrected sequence: ["mix", "add", "bake", "cool"]
- Temporal variant: ["mix", "add", [10, 15], [15, 30]]

RESPONSE FORMAT:
{{
  "recipes": [
    {{
      "id": "recipe_id_1", 
      "temporal_variant": ["action1", [5, 10], "action2", [2, 5]]
    }},
    {{
      "id": "recipe_id_2",
      "temporal_variant": ["action1", "action2", [15, 25]]  
    }},
    ...
  ]
}}

CRITICAL FORMATTING RULES:
- Return ONLY valid JSON with NO comments (no /* */ or //)
- NO explanatory text inside the JSON
- NO comments after tuples or actions
- The JSON must be parseable by json.loads() directly
- Do NOT add any markdown formatting except the outer ```json ``` tags

IMPORTANT:
- Process ALL {len(recipes_batch)} recipes
- If no timing info in instructions, estimate reasonable times for common processes
- Tuples must be (min_minutes, max_minutes) as integers
- Keep physical gestures unchanged
- Return ONLY the JSON with absolutely NO comments inside
- Base estimates on the actual instructions when possible
"""

    for retry in range(max_retries):
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            
            extra_headers = {
                "HTTP-Referer": "recipe variants generator",
                "X-Title": "Stage 3: Temporal Variant Generation"
            }
            
            completion = client.chat.completions.create(
                extra_headers=extra_headers,
                model=model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a culinary expert who estimates cooking times precisely. You MUST return only valid JSON without any comments (no /* */ or //) inside the JSON structure."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=6000,
                temperature=0.1,
            )
            
            llm_response = completion.choices[0].message.content.strip()
            print(f"Réponse brute (100 premiers caractères): {llm_response[:100]}...")
            result = extract_json_from_response(llm_response)
            
            if result is None:
                print("Erreur: Impossible de parser la réponse JSON pour l'étape 3")
                return None
            
            # Traitement des résultats
            stage_3_results = {}
            recipes_results = result.get("recipes", [])
            
            for recipe_result in recipes_results:
                recipe_id = recipe_result.get("id")
                temporal_variant = recipe_result.get("temporal_variant", [])
                stage_3_results[recipe_id] = temporal_variant
            
            return stage_3_results
            
        except Exception as e:
            if "429" in str(e):
                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 3 * 60
                    print(f"    Erreur 429 à l'étape 3, attente de {wait_time//60} minutes (tentative {retry+1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    print(f"    Erreur 429 persistante après {max_retries} tentatives à l'étape 3")
                    raise Exception("429_max_retries")
            else:
                print(f"Erreur lors de l'étape 3: {str(e)}")
                return None
    
    return None

# ================================ FONCTION RÉCURSIVE DE TRAITEMENT DES BATCHES ================================

def process_batch_recursive(recipes_batch, api_key, model_name, stage, stage_1_results=None, 
                           failed_recipes=None, max_retries=3, depth=0):
    """
    Traite récursivement un batch en le divisant si nécessaire
    
    Args:
        recipes_batch (list): Liste des recettes du batch
        api_key (str): Clé API
        model_name (str): Nom du modèle
        stage (int): Numéro de l'étape (1, 2 ou 3)
        stage_1_results (dict): Résultats de l'étape 1 (pour stages 2 et 3)
        failed_recipes (set): Ensemble des IDs de recettes échouées
        max_retries (int): Nombre max de tentatives pour erreur 429
        depth (int): Profondeur de récursion (pour logging)
    
    Returns:
        dict: Résultats pour ce batch
    """
    if failed_recipes is None:
        failed_recipes = set()
    
    indent = "  " * depth
    recipe_ids = [r['id'] for r in recipes_batch]
    
    print(f"{indent}Traitement récursif - Stage {stage} - {len(recipes_batch)} recettes - Profondeur {depth}")
    
    # Cas de base: une seule recette qui échoue
    if len(recipes_batch) == 1:
        recipe_id = recipes_batch[0]['id']
        print(f"{indent}Recette unique {recipe_id} - attribution de valeur par défaut 'NA'")
        failed_recipes.add(recipe_id)
        
        if stage == 1:
            return {recipe_id: ["NA"]}
        elif stage == 2:
            return {recipe_id: {
                "ingredient_variant": ["NA"],
                "permutation_1": ["NA"],
                "permutation_2": ["NA"]
            }}
        else:  # stage == 3
            return {recipe_id: ["NA"]}
    
    # Tentative de traitement du batch complet
    try:
        if stage == 1:
            results = stage_1_reevaluate_main_variant(recipes_batch, api_key, model_name, max_retries)
        elif stage == 2:
            results = stage_2_generate_secondary_variants(recipes_batch, stage_1_results, api_key, model_name, max_retries)
        else:  # stage == 3
            results = stage_3_generate_temporal_variant(recipes_batch, stage_1_results, api_key, model_name, max_retries)
        
        # Vérifier si tous les IDs sont présents
        if results and set(results.keys()) == set(recipe_ids):
            #print(f"{indent}✅ Batch traité avec succès - tous les IDs présents")
            return results
        else:
            print(f"{indent}⚠️ Résultats incomplets - division du batch nécessaire")
            raise Exception("incomplete_results")
            
    except Exception as e:
        if "429_max_retries" in str(e):
            print(f"{indent}❌ Erreur 429 persistante - abandon du batch")
            raise
        
        # Division du batch en deux
        mid = len(recipes_batch) // 2
        batch_1 = recipes_batch[:mid]
        batch_2 = recipes_batch[mid:]
        
        print(f"{indent}📦 Division du batch: {len(batch_1)} + {len(batch_2)} recettes")
        
        # Traitement récursif de chaque moitié
        results_1 = process_batch_recursive(batch_1, api_key, model_name, stage, 
                                           stage_1_results, failed_recipes, max_retries, depth+1)
        results_2 = process_batch_recursive(batch_2, api_key, model_name, stage,
                                           stage_1_results, failed_recipes, max_retries, depth+1)
        
        # Fusion des résultats
        combined_results = {**results_1, **results_2}
        return combined_results

# ================================ FONCTION PRINCIPALE DE TRAITEMENT DES BATCHES ================================

def process_batch_3_stages_complete(recipes_batch, api_key, model_name, batch_counter, cohort, 
                                   failed_recipes, max_retries=5):
    """
    Traite un batch complet avec les 3 étapes séquentielles et gestion récursive
    
    Args:
        recipes_batch (list): Liste des recettes du batch
        api_key (str): Clé API
        model_name (str): Nom du modèle
        batch_counter (int): Numéro du batch
        cohort (str): Numéro de la cohorte
        failed_recipes (set): Ensemble des IDs de recettes échouées
        max_retries (int): Nombre max de tentatives pour erreur 429
    
    Returns:
        dict: {
            'variantes_principales': {recipe_id: [...]},
            'variantes_secondaires': {recipe_id: {...}}, 
            'variantes_ternaires': {recipe_id: [...]}
        }
    """
    
    
    # Variables pour stocker les résultats de chaque étape
    variantes_principales = {}
    variantes_secondaires = {}
    variantes_ternaires = {}
    
    # ============ ÉTAPE 1: RÉÉVALUATION ============
    print(f"    🔄 Étape 1: Réévaluation des séquences principales...")
    try:
        variantes_principales = process_batch_recursive(
            recipes_batch, api_key, model_name, stage=1, 
            failed_recipes=failed_recipes, max_retries=max_retries
        )
        print(f"    ✅ Étape 1 réussie ({len(variantes_principales)} recettes)")
    except Exception as e:
        if "429_max_retries" in str(e):
            print(f"    ❌ Échec définitif de l'étape 1 après max_retries")
            raise
        print(f"    ❌ Erreur étape 1: {str(e)}")
        raise
    
    # ============ ÉTAPE 2: VARIANTES SECONDAIRES ============
    print(f"    🔄 Étape 2: Génération des variantes secondaires...")
    try:
        variantes_secondaires = process_batch_recursive(
            recipes_batch, api_key, model_name, stage=2,
            stage_1_results=variantes_principales, 
            failed_recipes=failed_recipes, max_retries=max_retries
        )
        print(f"    ✅ Étape 2 réussie ({len(variantes_secondaires)} recettes)")
    except Exception as e:
        if "429_max_retries" in str(e):
            print(f"    ❌ Échec définitif de l'étape 2 après max_retries")
            raise
        print(f"    ❌ Erreur étape 2: {str(e)}")
        raise
    
    # ============ ÉTAPE 3: VARIANTE TEMPORELLE ============
    print(f"    🔄 Étape 3: Génération des variantes temporelles...")
    try:
        variantes_ternaires = process_batch_recursive(
            recipes_batch, api_key, model_name, stage=3,
            stage_1_results=variantes_principales,
            failed_recipes=failed_recipes, max_retries=max_retries
        )
        print(f"    ✅ Étape 3 réussie ({len(variantes_ternaires)} recettes)")
    except Exception as e:
        if "429_max_retries" in str(e):
            print(f"    ❌ Échec définitif de l'étape 3 après max_retries")
            raise
        print(f"    ❌ Erreur étape 3: {str(e)}")
        raise
    
    # ============ COMPILATION DES RÉSULTATS ============
    batch_results = {
        'variantes_principales': variantes_principales,
        'variantes_secondaires': variantes_secondaires, 
        'variantes_ternaires': variantes_ternaires
    }
    
    print(f"  ✅ Batch {batch_counter} traité complètement avec les 3 étapes")
    return batch_results

# ================================ FONCTIONS DE SAUVEGARDE ================================

def ensure_output_directory():
    """Crée le dossier de sortie s'il n'existe pas"""
    output_dir = "recipes_variants_3stages"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def save_intermediate_results_3stages(results, cohort, failed_recipes, filename_prefix="sauvegarde_intermediaire_3stages"):
    """Sauvegarde les résultats intermédiaires des 3 étapes"""
    output_dir = ensure_output_directory()
    filename = os.path.join(output_dir, f"{filename_prefix}_cohort_{cohort}.json")
    
    save_data = {
        'results': results,
        'failed_recipes': list(failed_recipes)
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)

def load_intermediate_results_3stages(cohort, filename_prefix="sauvegarde_intermediaire_3stages"):
    """Charge les résultats intermédiaires des 3 étapes"""
    output_dir = ensure_output_directory()
    filename = os.path.join(output_dir, f"{filename_prefix}_cohort_{cohort}.json")
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
                results = save_data.get('results', {
                    'variantes_principales': {},
                    'variantes_secondaires': {},
                    'variantes_ternaires': {}
                })
                failed_recipes = set(save_data.get('failed_recipes', []))
                return results, failed_recipes
        except:
            return {
                'variantes_principales': {},
                'variantes_secondaires': {},
                'variantes_ternaires': {}
            }, set()
    return {
        'variantes_principales': {},
        'variantes_secondaires': {},
        'variantes_ternaires': {}
    }, set()

def save_failed_recipes(failed_recipes, cohort):
    """Sauvegarde la liste des recettes échouées"""
    output_dir = ensure_output_directory()
    filename = os.path.join(output_dir, f"failed_recipes_cohort_{cohort}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(list(failed_recipes), f, indent=2, ensure_ascii=False)
    
    print(f"Liste des recettes échouées sauvegardée: {len(failed_recipes)} recettes")
    print(f"Fichier: {filename}")

# ================================ FONCTION PRINCIPALE ================================

def process_recipes_batch_3stages(recipes_df, api_key, model_name, cohort, batch_size=5, 
                                 delay=1, resume_from_temp=False, max_retries=3):
    """
    Traite un lot de recettes avec l'architecture à 3 étapes
    
    Args:
        recipes_df (pandas.DataFrame): DataFrame contenant les recettes
        api_key (str): Clé API pour OpenRouter
        model_name (str): Nom du modèle à utiliser
        cohort (str): Numéro de la cohorte de données
        batch_size (int): Nombre de recettes par batch
        delay (float): Délai en secondes entre chaque batch
        resume_from_temp (bool): Si True, reprend depuis le dernier batch sauvegardé
        max_retries (int): Nombre maximum de tentatives en cas d'erreur 429
    
    Returns:
        dict: Résultats complets des 3 étapes
    """
    
    # Créer le dossier de sortie
    ensure_output_directory()
    
    # Calcul et affichage du nombre total de batches
    total_recipes = len(recipes_df)
    total_batches = (total_recipes + batch_size - 1) // batch_size
    print(f"========================================")
    print(f"DÉMARRAGE DU TRAITEMENT")
    print(f"========================================")
    print(f"Total de recettes: {total_recipes}")
    print(f"Taille des batches: {batch_size}")
    print(f"Nombre total de batches: {total_batches}")
 
    
    # Initialisation
    results = {
        'variantes_principales': {},
        'variantes_secondaires': {},
        'variantes_ternaires': {}
    }
    failed_recipes = set()
    
    batch_counter = 0
    start_index = 0
    
    # Gestion de la reprise
    if resume_from_temp:
        results, failed_recipes = load_intermediate_results_3stages(cohort)
        processed_recipes = len(results['variantes_principales'])
        start_index = processed_recipes
        batch_counter = processed_recipes // batch_size
        print(f"Reprise depuis l'index {start_index}, batch {batch_counter}")
        print(f"Recettes échouées précédemment: {len(failed_recipes)}\n")
    
    # Traitement par batches avec les 3 étapes
    for i in range(start_index, total_recipes, batch_size):
        batch_counter += 1
        end_index = min(i + batch_size, total_recipes)
        current_batch = recipes_df.iloc[i:end_index]
        
       
        print(f"BATCH {batch_counter}/{total_batches}")
        print(f"Recettes {i+1} à {end_index}")
      
        
        # Préparer les données du batch
        recipes_batch = []
        for idx, row in current_batch.iterrows():
            recipe_data = {
                'id': row['id'],
                'title': row['title'],
                'actions': eval(row['actions']) if isinstance(row['actions'], str) else row['actions'],
                'instructions': row['instruction'],
                'ingredients': row['ingredient']
            }
            recipes_batch.append(recipe_data)
        
        # Traiter le batch complet avec les 3 étapes
        try:
            batch_results = process_batch_3_stages_complete(
                recipes_batch, api_key, model_name, batch_counter, cohort, 
                failed_recipes, max_retries
            )
            
            if batch_results:
                # Intégrer les résultats
                results['variantes_principales'].update(batch_results['variantes_principales'])
                results['variantes_secondaires'].update(batch_results['variantes_secondaires']) 
                results['variantes_ternaires'].update(batch_results['variantes_ternaires'])
                
                print(f"\n📊 Progression:")
                print(f"  - Recettes traitées: {len(results['variantes_principales'])}/{total_recipes}")
                print(f"  - Recettes échouées: {len(failed_recipes)}")
                print(f"  - Batches restants: {total_batches - batch_counter}")
            
        except Exception as e:
            print(f"\n❌ ERREUR CRITIQUE pour le batch {batch_counter}: {str(e)}")
            print(f"Sauvegarde des résultats en cours...")
            save_intermediate_results_3stages(results, cohort, failed_recipes)
            print(f"✅ Résultats sauvegardés - Arrêt du programme")
            print(f"Pour reprendre: utilisez resume_from_temp=True")
            return results
        
        # Gestion des pauses
        if batch_counter % 50 == 0:
            print(f"\n⏸️  PAUSE DE 3 MINUTES après {batch_counter} batches...")
            save_intermediate_results_3stages(results, cohort, failed_recipes)
            time.sleep(3 * 60)
        elif batch_counter % 10 == 0:
            print(f"\n⏸️  PAUSE DE 1 MINUTE après {batch_counter} batches...")
            save_intermediate_results_3stages(results, cohort, failed_recipes)
            time.sleep(60)
        
        # Pause normale entre batches
        if delay > 0 and batch_counter < total_batches:
            time.sleep(delay)
    
    # Sauvegarde finale
    print("\n========================================")
    print("TRAITEMENT TERMINÉ - Sauvegarde finale")
    print("========================================")
    
    output_dir = ensure_output_directory()
    final_filename = os.path.join(output_dir, f'sauvegarde_final_3stages_cohort_{cohort}.json')
    
    final_save_data = {
        'results': results,
        'failed_recipes': list(failed_recipes)
    }
    
    with open(final_filename, 'w', encoding='utf-8') as f:
        json.dump(final_save_data, f, indent=2, ensure_ascii=False)
    
    # Sauvegarder la liste des recettes échouées
    save_failed_recipes(failed_recipes, cohort)
    
    return results



def reprocess_failed_recipes(cohort, api_key, model_name, batch_size=5, max_retries=3):
    """
    Retraite les recettes échouées d'une cohorte et met à jour la sauvegarde finale
    
    Args:
        cohort (str): Numéro de la cohorte
        api_key (str): Clé API OpenRouter
        model_name (str): Nom du modèle à utiliser
        batch_size (int): Nombre de recettes par batch
        max_retries (int): Nombre maximum de tentatives en cas d'erreur 429
    
    Returns:
        dict: Résultats mis à jour avec les recettes retraitées
    """
    
    output_dir = ensure_output_directory()
    
    # Charger la liste des recettes échouées
    failed_file = os.path.join(output_dir, f"failed_recipes_cohort_{cohort}.json")
    if not os.path.exists(failed_file):
        print(f"Aucun fichier de recettes échouées trouvé pour la cohorte {cohort}")
        return None
    
    with open(failed_file, 'r', encoding='utf-8') as f:
        failed_recipe_ids = json.load(f)
    
    if not failed_recipe_ids:
        print("Aucune recette échouée à retraiter")
        return None
    
    print(f"========================================")
    print(f"RETRAITEMENT DES RECETTES ÉCHOUÉES")
    print(f"Cohorte: {cohort}")
    print(f"Nombre de recettes à retraiter: {len(failed_recipe_ids)}")
    print(f"Taille des batches: {batch_size}")
    print(f"========================================\n")
    
    # Charger les données originales
    data = data_preparation_to_extract_recipes_variants(cohort)
    
    # Filtrer uniquement les recettes échouées
    failed_recipes_data = data[data['id'].isin(failed_recipe_ids)]
    
    if len(failed_recipes_data) == 0:
        print("Aucune donnée trouvée pour les recettes échouées")
        return None
    
    print(f"Données chargées: {len(failed_recipes_data)} recettes\n")
    
    # Charger les résultats existants
    final_file = os.path.join(output_dir, f'sauvegarde_final_3stages_cohort_{cohort}.json')
    with open(final_file, 'r', encoding='utf-8') as f:
        save_data = json.load(f)
        results = save_data.get('results', save_data)
    
    # Calculer le nombre de batches
    total_recipes = len(failed_recipes_data)
    total_batches = (total_recipes + batch_size - 1) // batch_size
    print(f"Nombre total de batches: {total_batches}\n")
    
    # Traiter par batches
    failed_recipes_set = set()
    batch_counter = 0
    
    for i in range(0, total_recipes, batch_size):
        batch_counter += 1
        end_index = min(i + batch_size, total_recipes)
        current_batch = failed_recipes_data.iloc[i:end_index]
        
        print(f"BATCH {batch_counter}/{total_batches}")
        print(f"Recettes {i+1} à {end_index}")
        
        # Préparer les données du batch
        recipes_batch = []
        for idx, row in current_batch.iterrows():
            recipe_data = {
                'id': row['id'],
                'title': row['title'],
                'actions': eval(row['actions']) if isinstance(row['actions'], str) else row['actions'],
                'instructions': row['instruction'],
                'ingredients': row['ingredient']
            }
            recipes_batch.append(recipe_data)
        
        # Traiter le batch avec les 3 étapes
        try:
            batch_results = process_batch_3_stages_complete(
                recipes_batch, api_key, model_name, 
                batch_counter=batch_counter, cohort=cohort,
                failed_recipes=failed_recipes_set, 
                max_retries=max_retries
            )
            
            if batch_results:
                # Mettre à jour les résultats existants avec les nouvelles valeurs
                results['variantes_principales'].update(batch_results['variantes_principales'])
                results['variantes_secondaires'].update(batch_results['variantes_secondaires'])
                results['variantes_ternaires'].update(batch_results['variantes_ternaires'])
                
                print(f"✅ Batch {batch_counter} traité avec succès\n")
             
            # Gestion des pauses
            if batch_counter % 50 == 0:
                print(f"\n⏸️  PAUSE DE 3 MINUTES après {batch_counter} batches...")
                save_intermediate_results_3stages(results, cohort, failed_recipes)
                time.sleep(3 * 60)
            elif batch_counter % 10 == 0:
                print(f"\n⏸️  PAUSE DE 1 MINUTE après {batch_counter} batches...")
                save_intermediate_results_3stages(results, cohort, failed_recipes)
                time.sleep(30)
            
        except Exception as e:
            print(f"\n❌ ERREUR pour le batch {batch_counter}: {str(e)}")
            print(f"Sauvegarde des résultats partiels...\n")
    
    # Sauvegarder les résultats mis à jour
    updated_save_data = {
        'results': results,
        'failed_recipes': list(failed_recipes_set)
    }
    
    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump(updated_save_data, f, indent=2, ensure_ascii=False)
    
    # Mettre à jour la liste des recettes échouées
    save_failed_recipes(failed_recipes_set, cohort)
    
    print(f"\n========================================")
    print(f"RETRAITEMENT TERMINÉ")
    print(f"========================================")
    print(f"Recettes retraitées avec succès: {len(failed_recipe_ids) - len(failed_recipes_set)}")
    print(f"Recettes toujours en échec: {len(failed_recipes_set)}")
    print(f"Fichier mis à jour: {final_file}")
    
    return results



def remove_duplicates_with_lists(df):
    """
    Supprime les doublons dans un DataFrame contenant des listes dans les colonnes
    """
    df_temp = df.copy()
    
    # Identifier les colonnes contenant des listes
    list_columns = []
    for col in df_temp.columns:
        if df_temp[col].apply(lambda x: isinstance(x, list)).any():
            list_columns.append(col)
            # Convertir les listes en strings
            df_temp[f"{col}_str"] = df_temp[col].astype(str)
    
    # Créer la liste des colonnes pour drop_duplicates
    comparison_columns = [col for col in df_temp.columns if not col.endswith('_str')] + [f"{col}_str" for col in list_columns]
    comparison_columns = [col for col in comparison_columns if col not in list_columns]
    
    # Supprimer les doublons
    df_clean = df_temp.drop_duplicates(subset=comparison_columns)
    
    # Supprimer les colonnes temporaires
    cols_to_drop = [f"{col}_str" for col in list_columns]
    df_clean = df_clean.drop(columns=cols_to_drop)
    
    return df_clean.reset_index(drop=True)





def remove_consecutive_duplicates(lst):


            # Convertir la chaîne en liste Python
    if isinstance(lst, str):
        lst = ast.literal_eval(lst)
    
    # Vérifications de sécurité
    if lst is None:
        return lst
    if not isinstance(lst, list):
        return lst
    if len(lst) == 0:
        return lst
    if len(lst) == 1:
        return lst
    
    # Suppression des doublons consécutifs
    result = [lst[0]]
    for i in range(1, len(lst)):
        if lst[i] != lst[i-1]:
            result.append(lst[i])
    
    return result


def ensure_list_robust(x):
    """
    Version améliorée de ensure_list qui gère tous les cas problématiques
    """
    # Cas 1: Si c'est déjà une liste propre
    if isinstance(x, list):
        # Nettoyer la liste existante
        cleaned_list = []
        for item in x:
            if isinstance(item, np.ndarray):
                # Convertir l'array en liste
                if item.ndim == 0:  # Scalar array
                    cleaned_list.append(item.item())
                elif item.ndim == 1:  # 1D array
                    cleaned_list.extend(item.tolist())
                else:  # Multi-dimensional array
                    # Flatten et convertir
                    cleaned_list.extend(item.flatten().tolist())
            elif isinstance(item, list):
                # Aplatir les listes imbriquées
                cleaned_list.extend(item)
            elif pd.notna(item):
                cleaned_list.append(item)
        return cleaned_list
    
    # Cas 2: Si c'est une string représentant une liste
    if isinstance(x, str):
        try:
            parsed = ast.literal_eval(x)
            # Récursion pour nettoyer le résultat parsé
            return ensure_list_robust(parsed)
        except Exception:
            # Si ce n'est pas une liste valide, retourner la string dans une liste
            return [x] if x and x != "NA" else []
    
    # Cas 3: Si c'est un array NumPy
    if isinstance(x, np.ndarray):
        if x.ndim == 0:  # Scalar array
            return [x.item()]
        elif x.ndim == 1:  # 1D array
            return x.tolist()
        else:  # Multi-dimensional array
            return x.flatten().tolist()
    
    # Cas 4: Valeur unique (non-liste)
    if pd.notna(x):
        return [x]
    
    # Cas 5: NaN ou None
    return []


def convert_actions_column_elements(df):
    """
    Nettoyer complètement la colonne actions
    """
    print("\nNettoyage de la colonne 'actions'...")
    
    # Étape 1: Convertir tous les types en listes propres
    df['actions'] = df['actions'].apply(ensure_list_robust)
    
    # Étape 2: Supprimer les NaN à l'intérieur des listes
    def remove_nans_from_list(lst):
        if isinstance(lst, list):
            # Utiliser une compréhension de liste simple qui évite pd.notna sur des arrays
            cleaned = []
            for item in lst:
                # Vérifier si c'est NaN de manière sûre
                try:
                    if item is not None and not (isinstance(item, float) and np.isnan(item)):
                        cleaned.append(item)
                except (TypeError, ValueError):
                    # Si on ne peut pas vérifier, on garde l'élément
                    cleaned.append(item)
            return cleaned
        return lst
    
    df['actions'] = df['actions'].apply(remove_nans_from_list)
    
    # Étape 3: Convertir tous les éléments en strings si nécessaire
    def stringify_elements(lst):
        if isinstance(lst, list):
            return [str(item) for item in lst]
        return lst
    
    df['actions'] = df['actions'].apply(stringify_elements)
    
    print("✅ Nettoyage terminé!")
    
    return df



def data_preparation_3stages(subset):

    
    # Charger les résultats des 3 étapes
    file_path = f"recipes_variants_3stages/sauvegarde_final_3stages_cohort_{subset}.json"
    with open(file_path, 'r',encoding="utf-8") as f:
        save_data = json.load(f)
        results = save_data.get('results', save_data)
    
    # Charger les données de base et créer un dictionnaire
    recipes = pd.read_csv(DATA_DIR/"recipes.csv", usecols=['id', 'title'])
    recipe_titles = dict(zip(recipes['id'], recipes['title']))
    
    # Pré-allouer les listes avec une estimation de taille
    estimated_size = len(results['variantes_principales']) * 5
    all_data = []
    temporal_data = []
    
    # Définir les configurations de variantes pour éviter la répétition de code
    variante_configs = [
        ('variantes_principales', None, 'principal', 'variante_principale'),
        ('variantes_secondaires', 'ingredient_variant', 'secondaire', 'variante_ingredients'),
        ('variantes_secondaires', 'permutation_1', 'secondaire', 'variante_permutation'),
        ('variantes_secondaires', 'permutation_2', 'secondaire', 'variante_permutation'),
    ]
    
    # Traitement de chaque recette
    for recipe_id in results['variantes_principales'].keys():
        recipe_title = recipe_titles.get(recipe_id, f"Recipe_{recipe_id}")
        
        # Traiter les variantes principales et secondaires
        for result_key, sub_key, type_val, type_2_val in variante_configs:
            if sub_key is None:
                variante = results[result_key].get(recipe_id, [])
            else:
                variante = results[result_key].get(recipe_id, {}).get(sub_key, [])
            
            if variante and variante != ["NA"]:
                all_data.append({
                    'id': recipe_id,
                    'title': recipe_title,
                    'actions': variante,
                    'type': type_val,
                    'type_2': type_2_val
                })
        
        # Variante ternaire (temporelle)
        variante_ternaire = results['variantes_ternaires'].get(recipe_id, [])
        if variante_ternaire and variante_ternaire != ["NA"]:
            temporal_data.append({
                'id': recipe_id,
                'title': recipe_title,
                'actions': variante_ternaire,
                'type': 'principal'
            })
    
    # Créer les DataFrames une seule fois
    final_df = pd.DataFrame(all_data)
    temporal_df = pd.DataFrame(temporal_data)

    return final_df, temporal_df


"""
SCRIPT OPTIMISÉ POUR NETTOYAGE DES ACTIONS
===========================================
Méthode : MAPPING avec pré-calcul (la plus rapide)
Temps estimé : 2-10 secondes pour 2.6M lignes (au lieu de 22-44 heures!)
"""

import re
import pandas as pd
from rapidfuzz import fuzz, process
import time


def normalize_surface(text):
    """Normalisation de base"""
    text = str(text).lower().strip()
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text


class ActionCleaner:
    """Cleaner optimisé avec cache"""
    
    def __init__(self, actions_to_remove, normalization_dict, similarity_threshold=90):
        self.threshold = similarity_threshold
        
        # Sets pour matching exact (ultra rapide)
        self.removal_exact = {normalize_surface(a) for a in actions_to_remove}
        self.norm_exact = {
            normalize_surface(k): normalize_surface(v)
            for k, v in normalization_dict.items()
        }
        
        # Listes pour fuzzy matching
        self.removal_list = list(self.removal_exact)
        self.norm_keys = list(self.norm_exact.keys())
        
        # Cache
        self._norm_cache = {}
        self._remove_cache = {}
    
    def normalize_with_dict(self, action_norm):
        """Normalisation avec cache"""
        if action_norm in self._norm_cache:
            return self._norm_cache[action_norm]
        
        # Exact match
        if action_norm in self.norm_exact:
            result = self.norm_exact[action_norm]
            self._norm_cache[action_norm] = result
            return result
        
        # Fuzzy match si nécessaire
        if self.norm_keys:
            result = process.extractOne(
                action_norm,
                self.norm_keys,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self.threshold
            )
            if result is not None:
                match, score, _ = result
                result_val = self.norm_exact[match]
                self._norm_cache[action_norm] = result_val
                return result_val
        
        self._norm_cache[action_norm] = action_norm
        return action_norm
    
    def should_remove(self, action_norm):
        """Vérification de suppression avec cache"""
        if action_norm in self._remove_cache:
            return self._remove_cache[action_norm]
        
        # Exact match
        if action_norm in self.removal_exact:
            self._remove_cache[action_norm] = True
            return True
        
        # Fuzzy match si nécessaire
        if self.removal_list:
            result = process.extractOne(
                action_norm,
                self.removal_list,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self.threshold
            )
            if result is not None:
                match, score, _ = result
                self._remove_cache[action_norm] = True
                return True
        
        self._remove_cache[action_norm] = False
        return False


def clean_dataframe_optimized(data, actions_to_remove, normalization_dict, 
                               similarity_threshold=90, verbose=True):
    """
    Fonction principale : nettoie le dataframe avec la méthode la plus rapide
    
    Paramètres:
    -----------
    data : DataFrame
        Ton dataframe avec une colonne 'actions'
    actions_to_remove : list
        Liste des actions à supprimer
    normalization_dict : dict
        Dictionnaire de normalisation {variante: forme_normalisée}
    similarity_threshold : int (85-95)
        Seuil de similarité fuzzy. 90 est recommandé.
    verbose : bool
        Afficher les messages de progression
    
    Retourne:
    ---------
    DataFrame avec une nouvelle colonne 'actions_cleaned'
    """
    
    if verbose:
        print("🚀 Début du nettoyage optimisé...")
        print(f"   Dataset: {len(data):,} lignes")
        print(f"   Actions à supprimer: {len(actions_to_remove)}")
        print(f"   Règles de normalisation: {len(normalization_dict)}")
        print(f"   Seuil de similarité: {similarity_threshold}")
    
    start_total = time.time()
    
    # Créer le cleaner
    cleaner = ActionCleaner(actions_to_remove, normalization_dict, similarity_threshold)
    
    # Étape 1: Extraire les actions uniques
    if verbose:
        print("\n📋 Étape 1/3: Extraction des actions uniques...")
    
    all_actions = set()
    for actions_list in data['actions']:
        if isinstance(actions_list, str):
            if actions_list.startswith('['):
                actions_list = eval(actions_list)
            else:
                actions_list = [actions_list]
        all_actions.update(actions_list)
    
    if verbose:
        print(f"   ✓ {len(all_actions):,} actions uniques trouvées")
    
    # Étape 2: Nettoyer les actions uniques (une seule fois!)
    if verbose:
        print("\n🧹 Étape 2/3: Nettoyage des actions uniques...")
    
    action_mapping = {}
    for action in all_actions:
        action_norm = normalize_surface(action)
        action_norm = cleaner.normalize_with_dict(action_norm)
        
        if not cleaner.should_remove(action_norm):
            action_mapping[action] = action_norm
    
    if verbose:
        removed = len(all_actions) - len(action_mapping)
        print(f"   ✓ {len(action_mapping):,} actions conservées")
        print(f"   ✓ {removed:,} actions supprimées ({removed/len(all_actions)*100:.1f}%)")
    
    # Étape 3: Appliquer le mapping (ultra rapide!)
    if verbose:
        print("\n⚡ Étape 3/3: Application du mapping...")
    
    def apply_mapping(actions_list):
        if isinstance(actions_list, str):
            if actions_list.startswith('['):
                actions_list = eval(actions_list)
            else:
                actions_list = [actions_list]
        return [action_mapping[a] for a in actions_list if a in action_mapping]
    
    data_copy = data.copy()
    data_copy['actions_cleaned'] = data_copy['actions'].apply(apply_mapping)
    
    elapsed = time.time() - start_total
    
    if verbose:
        print(f"\n✅ Terminé en {elapsed:.2f} secondes!")
        print(f"   Vitesse: {len(data)/elapsed:,.0f} lignes/seconde")
        
        # Statistiques
        avg_before = data['actions'].apply(len).mean()
        avg_after = data_copy['actions_cleaned'].apply(len).mean()
        print(f"\n📊 Statistiques:")
        print(f"   Actions moyennes AVANT: {avg_before:.2f}")
        print(f"   Actions moyennes APRÈS: {avg_after:.2f}")
        print(f"   Réduction: {(1 - avg_after/avg_before)*100:.1f}%")
    data_copy['actions'] = data_copy['actions_cleaned']
    data_copy = data_copy.drop(columns=['actions_cleaned'])
    return data_copy


def data_cleaning_before_test(data, match_threshold=95):
    """
    Nettoie et prétraite les données finaux 
    
    Parameters:
    -----------
    pd.DataFrame :dataset final 
       
    
    Returns:
    --------
    tuple of (pd.DataFrame, pd.DataFrame)
        final_df : DataFrame nettoyé avec gestes uniquement
        data_with_gesture : DataFrame nettoyé avec tous les verbes
    """

    final_df =  data.copy()
    if len(final_df) == 0:
        print(f"⚠️  DataFrame vide pour la cohorte {subset}")
        return pd.DataFrame(), pd.DataFrame()
    
    # Importer actions_to_remove depuis le fichier texte
    with open('actions_to_remove_final.txt', 'r', encoding='utf-8') as f:
        actions_to_remove = [line.strip() for line in f if line.strip()]

    # Importer normalization_dict depuis le fichier JSON
    with open('normalization_dict_final.json', 'r', encoding='utf-8') as f:
        normalization_dict = json.load(f)
    
    try:



        # 1. convertir la colonne actions en lists
        print("→ Nettoyage de la colonne actions...")
        final_df = convert_actions_column_elements(final_df)
        print(f"  ✓ Nettoyage terminé: {len(final_df):,} lignes")
        
        
        # 2. netoyage et Normalisation des verbes 
        print("→ Netoyage et Normalisation des verbes...")
        final_df = clean_dataframe_optimized(
        data= final_df,
        actions_to_remove=actions_to_remove,
        normalization_dict=normalization_dict,
        similarity_threshold= match_threshold, 
        verbose=True
    )
        # 3. Supprimer les doublons de listes d'actions identiques pour une même recette
        print("→ Suppression des doublons par ID...")
        
        # Pour final_df
        final_df['actions_tuple'] = final_df['actions'].apply(
            lambda x: tuple(x) if isinstance(x, (list, np.ndarray)) else x
        )
        before_dedup = len(final_df)
        final_df = final_df.drop_duplicates(subset=['id', 'actions_tuple'], keep='first')
        final_df = final_df.drop(columns=['actions_tuple'])
        print(f"  ✓ final_df: {before_dedup - len(final_df):,} doublons supprimés ({len(final_df):,} restantes)")
        
        print(f"  ✓ Netoyage et Normalisation terminés")
        
        final_df.to_csv(DATA_DIR/'final_dataset_cleaned_and_normalized.csv', index=False)
       
        
        return final_df
    
    except Exception as e:
        print(f"\n❌ ERREUR lors du traitement de la cohorte : {e}")
        import traceback
        traceback.print_exc()
        
        # Retourner des DataFrames vides en cas d'erreur
        return pd.DataFrame()
    



def data_cleaning_after_test(data):
    """
    Nettoie et prétraite les données d'une final en eliminant les non geste pour creer le dataset final de avec geste uniquement 
    
    Parameters:
    -----------
    pd.DataFrame :dataset final 
       
    
    Returns:
    --------
    tuple of (pd.DataFrame, pd.DataFrame)
        final_df : DataFrame nettoyé avec gestes uniquement
        
    """


    final_df =  data.copy()
    if len(final_df) == 0:
        print(f"⚠️  DataFrame vide pour la cohorte {subset}")
        return pd.DataFrame(), pd.DataFrame()
    

   
 
    try:



        # 1. Nettoyer la colonne actions
        print("→ Nettoyage de la colonne actions...")
        final_df = convert_actions_column_elements(final_df)
        print(f"  ✓ Nettoyage terminé: {len(final_df):,} lignes")
        
        
    
        
 
        # 2. Filtrer pour ne garder que les gestes (sur final_df uniquement)
        print("→ Filtrage des gestes...")
        final_df['actions'] = final_df['actions'].apply(filter_actions)
        print(f"  ✓ Filtrage terminé")
        
        # 3. Supprimer les doublons consécutifs 
        print("→ Suppression des doublons consécutifs...")
        final_df['actions'] = final_df['actions'].apply(
            lambda x: remove_consecutive_duplicates(x) if isinstance(x, (list, np.ndarray)) else x
        )
       
        print(f"  ✓ Doublons consécutifs supprimés")
        
        # 4. Supprimer les doublons de listes d'actions identiques pour une même recette
        print("→ Suppression des doublons par ID...")
        
        # Pour final_df
        final_df['actions_tuple'] = final_df['actions'].apply(
            lambda x: tuple(x) if isinstance(x, (list, np.ndarray)) else x
        )
        before_dedup = len(final_df)
        final_df = final_df.drop_duplicates(subset=['id', 'actions_tuple'], keep='first')
        final_df = final_df.drop(columns=['actions_tuple'])
        print(f"  ✓ final_df: {before_dedup - len(final_df):,} doublons supprimés ({len(final_df):,} restantes)")
        
        

        # 5. Supprimer les lignes avec des listes d'actions vides
        print("→ Suppression des lignes avec actions vides...")

        before_empty = len(final_df)
        final_df = final_df[final_df['actions'].map(lambda x: len(x) > 0 if isinstance(x, (list, np.ndarray)) else False)]
        print(f"  ✓ final_df: {before_empty - len(final_df):,} lignes vides supprimées")

             
                
        # 6. Trier par ID puis par type
        print("→ Tri des données...")
        if 'type' in final_df.columns:
            final_df = final_df.sort_values(['id', 'type']).reset_index(drop=True)
            
        else:
            final_df = final_df.sort_values('id').reset_index(drop=True)
            
        print(f"  ✓ Tri terminé")
        

        print(f"final_df (gestes uniquement): {len(final_df):,} lignes")
       
        # S'assurer que ce sont bien des DataFrames
        assert isinstance(final_df, pd.DataFrame), "final_df n'est pas un DataFrame!"
       

        final_df.to_csv(DATA_DIR/'final_dataset_cleaned_gestures_only.csv', index=False)
       
        
        return final_df
        
    except Exception as e:
        print(f"\n❌ ERREUR lors du traitement de la cohorte : {e}")
        import traceback
        traceback.print_exc()
        
        # Retourner des DataFrames vides en cas d'erreur
        return pd.DataFrame()



def process_files_smart(cohort_min=None, cohort_max=None, num_processes=None, batch_size=None):
    """
    Solution intelligente qui s'adapte à votre machine
    
    Parameters:
    -----------
    cohort_min : int, optional
        Numéro minimum de cohorte à traiter (inclus)
    cohort_max : int, optional
        Numéro maximum de cohorte à traiter (inclus)
    num_processes : int, optional
        Nombre de processus parallèles (par défaut: CPU/2)
    batch_size : int, optional
        Nombre de fichiers par lot (par défaut: num_processes * 2)
    """
    import os
    from multiprocessing import Pool
    import time
    
    # Configuration automatique
    num_cpus = os.cpu_count()
    
    if num_processes is None:
        # Garde 25-50% des CPUs libres
        num_processes = max(2, num_cpus // 2)
    
    if batch_size is None:
        # Batch size = 2x le nombre de processus
        batch_size = num_processes * 2
    
    # Trouver tous les fichiers de cohortes
    all_files = [f for f in os.listdir("recipes_variants_3stages/") 
                 if f.startswith("sauvegarde_final_3stages_cohort_")]
    
    # Extraire les numéros de cohortes
    subset_list = []
    for f in all_files:
        try:
            cohort_num = int(f.split('_')[-1].split('.')[0])
            
            # Filtrer selon cohort_min et cohort_max
            if cohort_min is not None and cohort_num < cohort_min:
                continue
            if cohort_max is not None and cohort_num > cohort_max:
                continue
            
            subset_list.append(cohort_num)
        except ValueError:
            # Ignorer les fichiers avec des noms non conformes
            continue
    
    # Trier les cohortes pour un traitement ordonné
    subset_list.sort()
    
    # Afficher la configuration
    print(f"{'='*60}")
    print(f"CONFIGURATION DU TRAITEMENT")
    print(f"{'='*60}")
    print(f"CPUs disponibles: {num_cpus}")
    print(f"Processus utilisés: {num_processes}")
    print(f"Taille des lots: {batch_size} fichiers")
    print(f"Cohortes à traiter: {len(subset_list)}")
    if cohort_min is not None or cohort_max is not None:
        range_str = f"[{cohort_min if cohort_min is not None else 'début'} - {cohort_max if cohort_max is not None else 'fin'}]"
        print(f"Intervalle: {range_str}")
    print(f"Liste des cohortes: {subset_list[:10]}{'...' if len(subset_list) > 10 else ''}")
    print(f"{'='*60}\n")
    
    all_final_dfs = []
    all_temporal_dfs = []
    
    # Traiter par lots
    total_batches = (len(subset_list) - 1) // batch_size + 1
    
    for i in range(0, len(subset_list), batch_size):
        batch = subset_list[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        print(f"\n{'='*60}")
        print(f"LOT {batch_num}/{total_batches}")
        print(f"{'='*60}")
        print(f"Cohortes traitées dans ce lot: {batch}")
        print(f"Nombre de fichiers: {len(batch)}")
        print(f"{'-'*60}")
        
        start_time = time.time()
        
        with Pool(processes=num_processes) as pool:
            results = pool.map(data_preparation_3stages, batch)
        
        elapsed = time.time() - start_time
        print(f"\n✓ Lot {batch_num} terminé!")
        print(f"  Temps écoulé: {elapsed:.2f}s ({elapsed/len(batch):.2f}s par fichier)")
        
        all_final_dfs.extend([r[0] for r in results])
        all_temporal_dfs.extend([r[1] for r in results])
        
        # Afficher les statistiques du lot
        total_rows = sum(len(r[0]) for r in results)
        total_temporal = sum(len(r[1]) for r in results)
        print(f"  Lignes ajoutées: {total_rows:,} (final) + {total_temporal:,} (temporal)")
        
        # Estimation du temps restant
        if batch_num < total_batches:
            remaining_files = len(subset_list) - (i + batch_size)
            estimated_time = (elapsed / len(batch)) * remaining_files
            print(f"\n⏱  Temps estimé restant: {estimated_time/60:.1f} minutes")
            print(f"  Progression: {((i + batch_size) / len(subset_list) * 100):.1f}%")
            print("  Pause de 3 secondes...")
            time.sleep(3)
    
    # Combiner tous les résultats
    print(f"\n{'='*60}")
    print("FINALISATION")
    print(f"{'='*60}")
    print("Combination des résultats...")
    
    combined_final = pd.concat(all_final_dfs, ignore_index=True)
    combined_temporal = pd.concat(all_temporal_dfs, ignore_index=True)
    
    print(f"✓ Traitement terminé!")
    print(f"  Total final: {len(combined_final):,} lignes")
    print(f"  Total temporal: {len(combined_temporal):,} lignes")
    print(f"  Cohortes traitées: {len(subset_list)}")
    print(f"{'='*60}\n")

    combined_final.to_csv(DATA_DIR/'combined_variants_results_dataset.csv', index=False)
    combined_temporal.to_csv(DATA_DIR/'combined_variants_results_dataset_temporal_variant.csv', index=False)
    
    
    
    return combined_final, combined_temporal



import pandas as pd

def extraire_actions_depuis_fichiers(chemin_pattern, num_min, num_max, respect_casse=False):
    """
    Charge des dataframes depuis des fichiers et extrait les actions uniques.
    
    Args:
        chemin_pattern: Pattern du chemin (ex: "data/recettes_{}.csv" où {} sera remplacé par le numéro)
        num_min: Numéro minimum du dataframe (ex: 1)
        num_max: Numéro maximum du dataframe (ex: 100)
        respect_casse: Si True, 'Couper' et 'couper' sont différents. Si False, tout en minuscules.
    
    Returns:
        Liste triée d'actions uniques
    """
    actions_uniques = set()
    fichiers_non_trouves = []
    
    for i in range(num_min, num_max + 1):
        try:
            chemin = chemin_pattern.format(i)
            df = pd.read_csv(chemin)
            
            if 'verb' in df.columns:
                actions = df['verb'].dropna().astype(str)
                
                if not respect_casse:
                    actions = actions.str.lower()
                
                actions_uniques.update(actions)
            else:
                print(f"⚠️ Colonne 'verb' non trouvée dans {chemin}")
                
        except FileNotFoundError:
            fichiers_non_trouves.append(chemin)
            continue
        except Exception as e:
            print(f"❌ Erreur lors de la lecture de {chemin}: {str(e)}")
            continue
    
    if fichiers_non_trouves:
        print(f"\n⚠️ {len(fichiers_non_trouves)} fichier(s) non trouvé(s)")
    
    print(f"✓ {num_max - num_min + 1 - len(fichiers_non_trouves)} fichiers traités avec succès")
    
    return sorted(list(actions_uniques))




def rechercher_recettes_par_action(dataframe, action, respect_casse=False):
    """
    Vérifie si une action existe dans au moins une recette du dataframe.
    S'arrête dès la première occurrence trouvée.
    """

    def action_dans_liste(liste_actions, action_recherchee, respect_casse):
        """Vérifie si l'action est présente dans la liste d'actions."""

        # ----- 1) Gérer NA sans provoquer ValueError -----
        if liste_actions is None:
            return False
        if isinstance(liste_actions, float) and pd.isna(liste_actions):
            return False

        # ----- 2) Si c'est une chaîne représentant une liste -----
        if isinstance(liste_actions, str):
            try:
                liste_actions = ast.literal_eval(liste_actions)
            except:
                return False

        # ----- 3) Si c'est un numpy array -----
        if isinstance(liste_actions, np.ndarray):
            liste_actions = liste_actions.tolist()

        # ----- 4) Vérifier que c'est bien une liste -----
        if not isinstance(liste_actions, list):
            return False

        # ----- 5) Gestion de la casse -----
        if not respect_casse:
            action_recherchee = action_recherchee.lower()
            liste_actions = [
                a.lower() for a in liste_actions
                if isinstance(a, str)
            ]

        # ----- 6) Vérification -----
        return action_recherchee in liste_actions

    # ----- 7) Parcourir le dataframe -----
    for idx, row in dataframe.iterrows():
        if action_dans_liste(row['actions'], action, respect_casse):
            return True

    return False



def analyze_failed_and_na_recipes(cohort_min=None, cohort_max=None):
    """
    Analyse les recettes échouées en croisant les données originales avec les NA produits
    
    Parameters:
    -----------
    cohort_min : int, optional
        Numéro minimum de cohorte à analyser
    cohort_max : int, optional
        Numéro maximum de cohorte à analyser
    
    Returns:
    --------
    pd.DataFrame
        DataFrame avec les recettes échouées, leurs verbes originaux, instructions et statut NA
    """
    import os
    import json
    import pandas as pd
    
    # Trouver tous les fichiers de cohortes
    all_files = [f for f in os.listdir("recipes_variants_3stages/") 
                 if f.startswith("sauvegarde_final_3stages_cohort_")]
    
    # Identifier les cohortes avec failed_recipes
    cohorts_with_failures = []
    failed_recipes_by_cohort = {}
    
    for f in all_files:
        try:
            cohort_num = int(f.split('_')[-1].split('.')[0])
            
            # Filtrer selon cohort_min et cohort_max
            if cohort_min is not None and cohort_num < cohort_min:
                continue
            if cohort_max is not None and cohort_num > cohort_max:
                continue
            
            # Vérifier si cette cohorte a des failed_recipes
            json_file = f"recipes_variants_3stages/{f}"
            with open(json_file, 'r') as file:
                data = json.load(file)
                if 'failed_recipes' in data and len(data['failed_recipes']) > 0:
                    cohorts_with_failures.append(cohort_num)
                    failed_recipes_by_cohort[cohort_num] = data['failed_recipes']
        except Exception as e:
            print(f"⚠️  Erreur lors de l'analyse de {f}: {e}")
            continue
    
    print(f"{'='*60}")
    print(f"ANALYSE DES RECETTES ÉCHOUÉES")
    print(f"{'='*60}")
    print(f"Cohortes avec échecs: {len(cohorts_with_failures)}")
    print(f"Cohortes: {cohorts_with_failures[:10]}{'...' if len(cohorts_with_failures) > 10 else ''}")
    print(f"{'='*60}\n")
    
    if not cohorts_with_failures:
        print("Aucune cohorte avec échecs trouvée.")
        return pd.DataFrame()
    
    # Collecter les données des Instructions_segments
    all_data = []
    
    for cohort_num in cohorts_with_failures:
        try:
            segment_file = f"Instructions_segments_treated/Instructions_segment_{cohort_num}.csv"
            if not os.path.exists(segment_file):
                print(f"⚠️  Fichier non trouvé: {segment_file}")
                continue
            
            print(f"Chargement: {segment_file}")
            df_segment = pd.read_csv(segment_file)
            df_segment['cohort'] = cohort_num
            all_data.append(df_segment)
            
        except Exception as e:
            print(f"⚠️  Erreur pour cohorte {cohort_num}: {e}")
    
    if not all_data:
        print("Aucune donnée collectée.")
        return pd.DataFrame()
    
    # Combiner tous les segments
    data = pd.concat(all_data, ignore_index=True)
    print(f"\n✓ Total de lignes collectées: {len(data):,}")
    data =  data.dropna()
    # Grouper les verbes par recette
    print("→ Groupement des verbes par recette...")
    data_grouped = data.groupby(['id'])["verb"].agg(list).reset_index()
    print(f"✓ Recettes uniques: {len(data_grouped):,}")
    
    # Charger les instructions complètes
    print("→ Chargement des instructions...")
    try:
        instructions_df = pd.read_csv("recipe_instructions.csv", usecols=['id',  'instruction'])
        # # Renommer si nécessaire
        # if 'instructions' in instructions_df.columns:
        #     instructions_df = instructions_df.rename(columns={'instructions': 'instruction'})
        
        # Joindre avec les verbes
        data_with_instructions = pd.merge(
            data_grouped,
            instructions_df[['id', 'instruction']],
            on=['id'],
            how='left'
        )
        print(f"✓ Instructions jointes: {len(data_with_instructions):,} lignes")
    except Exception as e:
        print(f"⚠️  Erreur lors du chargement des instructions: {e}")
        data_with_instructions = data_grouped
    
    # Extraire les recettes avec NA (variantes principales uniquement)
    print(f"\n{'='*60}")
    print("EXTRACTION DES VARIANTES NA")
    print(f"{'='*60}\n")
    
    df_na = extract_na_from_all_cohorts(cohort_min=cohort_min, cohort_max=cohort_max)
    
    if len(df_na) > 0:
        # Filtrer uniquement les variantes principales
        df_na_principal = df_na[df_na['type'] == 'principal'].copy()
        print(f"Variantes principales avec NA: {len(df_na_principal)}")
        
        # Merger avec les données collectées
        final_df = pd.merge(
            data_with_instructions,
            df_na_principal[['id', 'title','actions', 'source_file']],  # 'actions' pas vraiment besoin car rempli de [NA]
            on=['id'],
            how='inner',
            suffixes=('_original', '_na')
        )
        
        print(f"\n{'='*60}")
        print(f"RÉSULTAT FINAL")
        print(f"{'='*60}")
        print(f"Total de lignes: {len(final_df):,}")
        print(f"Recettes uniques: {final_df['id'].nunique()}")
        print(f"Recettes avec verbes originaux: {final_df['verb'].notna().sum()}")
        print(f"Recettes avec NA: {final_df['actions'].notna().sum()}")
        print(f"Recettes dans les deux: {((final_df['verb'].notna()) & (final_df['actions'].notna())).sum()}")
        print(f"{'='*60}\n")
        
        return final_df
    else:
        print("Aucune variante NA trouvée.")
        return data_with_instructions
    

def process_recipes_retry_pipeline(recipes_df, api_key, model_name, cohort, batch_size=5, 
                                   delay=1, max_retries=3):
    """
    Traite les recettes récalcitrantes en utilisant leurs verbes originaux comme variante principale
    et génère uniquement les variantes secondaires et ternaires
    
    Args:
        recipes_df (pandas.DataFrame): DataFrame contenant les recettes avec colonnes:
                                       ['id', 'title', 'actions', 'instruction', 'ingredient']
        api_key (str): Clé API pour OpenRouter
        model_name (str): Nom du modèle à utiliser
        cohort (str): Identifiant de la cohorte
        batch_size (int): Nombre de recettes par batch
        delay (float): Délai en secondes entre chaque batch
        max_retries (int): Nombre maximum de tentatives en cas d'erreur 429
    
    Returns:
        dict: Résultats des 3 types de variantes
    """
    
    # Créer le dossier de sortie
    ensure_output_directory()
    
    # Calcul et affichage du nombre total de batches
    total_recipes = len(recipes_df)
    total_batches = (total_recipes + batch_size - 1) // batch_size
    print(f"========================================")
    print(f"DÉMARRAGE DU TRAITEMENT RETRY")
    print(f"========================================")
    print(f"Total de recettes: {total_recipes}")
    print(f"Taille des batches: {batch_size}")
    print(f"Nombre total de batches: {total_batches}")
    print(f"⚠️  Mode: Utilisation des verbes originaux comme variante principale")
    print()
    
    # Initialisation
    results = {
        'variantes_principales': {},
        'variantes_secondaires': {},
        'variantes_ternaires': {}
    }
    failed_recipes = set()
    
    batch_counter = 0
    
    # Traitement par batches
    for i in range(0, total_recipes, batch_size):
        batch_counter += 1
        end_index = min(i + batch_size, total_recipes)
        current_batch = recipes_df.iloc[i:end_index]
        
        print(f"BATCH {batch_counter}/{total_batches}")
        print(f"Recettes {i+1} à {end_index}")
        
        # Préparer les données du batch
        recipes_batch = []
        for idx, row in current_batch.iterrows():
            # Convertir actions en liste si c'est une string
            actions = row['actions']
            if isinstance(actions, str):
                try:
                    actions = eval(actions)
                except:
                    actions = []
            
            recipe_data = {
                'id': row['id'],
                'title': row['title'],
                'actions': actions,
                'instructions': row['instruction'],
                'ingredients': row['ingredient']
            }
            recipes_batch.append(recipe_data)
        
        # ============ UTILISER LES VERBES ORIGINAUX COMME VARIANTE PRINCIPALE ============
        print(f"    📋 Utilisation des séquences originales comme variantes principales...")
        variantes_principales = {}
        for recipe in recipes_batch:
            variantes_principales[recipe['id']] = recipe['actions']
        
        results['variantes_principales'].update(variantes_principales)
        print(f"    ✅ {len(variantes_principales)} variantes principales enregistrées")
        
        # ============ ÉTAPE 2: VARIANTES SECONDAIRES ============
        print(f"    🔄 Étape 2: Génération des variantes secondaires...")
        try:
            variantes_secondaires = process_batch_recursive(
                recipes_batch, api_key, model_name, stage=2,
                stage_1_results=variantes_principales,
                failed_recipes=failed_recipes, 
                max_retries=max_retries
            )
            
            if variantes_secondaires:
                results['variantes_secondaires'].update(variantes_secondaires)
                print(f"    ✅ Étape 2 réussie ({len(variantes_secondaires)} recettes)")
            else:
                print(f"    ⚠️  Étape 2: Aucun résultat")
                for recipe in recipes_batch:
                    failed_recipes.add(recipe['id'])
                    
        except Exception as e:
            print(f"    ❌ Erreur étape 2: {str(e)}")
            for recipe in recipes_batch:
                failed_recipes.add(recipe['id'])
        
        # ============ ÉTAPE 3: VARIANTE TEMPORELLE ============
        print(f"    🔄 Étape 3: Génération des variantes temporelles...")
        try:
            variantes_ternaires = process_batch_recursive(
                recipes_batch, api_key, model_name, stage=3,
                stage_1_results=variantes_principales,
                failed_recipes=failed_recipes, 
                max_retries=max_retries
            )
            
            if variantes_ternaires:
                results['variantes_ternaires'].update(variantes_ternaires)
                print(f"    ✅ Étape 3 réussie ({len(variantes_ternaires)} recettes)")
            else:
                print(f"    ⚠️  Étape 3: Aucun résultat")
                for recipe in recipes_batch:
                    failed_recipes.add(recipe['id'])
                    
        except Exception as e:
            print(f"    ❌ Erreur étape 3: {str(e)}")
            for recipe in recipes_batch:
                failed_recipes.add(recipe['id'])
        
        print(f"  ✅ Batch {batch_counter} traité")
        print(f"\n📊 Progression:")
        print(f"  - Recettes traitées: {len(results['variantes_principales'])}/{total_recipes}")
        print(f"  - Recettes échouées: {len(failed_recipes)}")
        print(f"  - Batches restants: {total_batches - batch_counter}\n")
        
        # Gestion des pauses
        if batch_counter % 50 == 0:
            print(f"⏸️  PAUSE DE 3 MINUTES après {batch_counter} batches...")
            save_intermediate_results_3stages(results, cohort, failed_recipes, 
                                             filename_prefix="retry_intermediaire")
            time.sleep(3 * 60)
        elif batch_counter % 10 == 0:
            print(f"⏸️  PAUSE DE 1 MINUTE après {batch_counter} batches...")
            save_intermediate_results_3stages(results, cohort, failed_recipes,
                                             filename_prefix="retry_intermediaire")
            time.sleep(60)
        
        # Pause normale entre batches
        if delay > 0 and batch_counter < total_batches:
            time.sleep(delay)
    
    # Sauvegarde finale
    print("\n========================================")
    print("TRAITEMENT RETRY TERMINÉ - Sauvegarde finale")
    print("========================================")
    
    ''' output_dir = ensure_output_directory()
    final_filename = os.path.join(output_dir, f'retry_final_results_cohort_{cohort}.json')
    
    final_save_data = {
        'results': results,
        'failed_recipes': list(failed_recipes)
    }
    
    with open(final_filename, 'w', encoding='utf-8') as f:
        json.dump(final_save_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Fichier sauvegardé: {final_filename}")'''

    print(f"📊 Statistiques finales:")
    print(f"  - Variantes principales: {len(results['variantes_principales'])}")
    print(f"  - Variantes secondaires: {len(results['variantes_secondaires'])}")
    print(f"  - Variantes ternaires: {len(results['variantes_ternaires'])}")
    print(f"  - Recettes échouées: {len(failed_recipes)}")
    
    return results



def retry_pipeline_for_na_recipes(cohort_min=None, cohort_max=None, api_key=None, model_name=None, 
                                   batch_size=5, max_retries=3, output_suffix="retry"):
    """
    Pipeline de retraitement pour les recettes avec NA détectées
    
    Ce pipeline:
    1. Extrait les recettes avec NA et failed_recipes
    2. Joint avec les instructions et ingrédients complets
    3. Utilise les verbes originaux comme variante principale
    4. Génère les variantes secondaires et ternaires via LLM
    5. Sauvegarde les résultats dans un nouveau JSON
    
    Parameters:
    -----------
    cohort_min : int, optional
        Numéro minimum de cohorte à analyser
    cohort_max : int, optional
        Numéro maximum de cohorte à analyser
    api_key : str
        Clé API OpenRouter
    model_name : str
        Nom du modèle à utiliser (ex: "anthropic/claude-3.5-sonnet")
    batch_size : int
        Nombre de recettes par batch
    max_retries : int
        Nombre maximum de tentatives en cas d'erreur 429
    output_suffix : str
        Suffixe pour les fichiers de sortie
    
    Returns:
    --------
    dict : Résultats des variantes générées
    """
    
    import os
    import json
    import pandas as pd
    import time
    
    if not api_key or not model_name:
        raise ValueError("api_key et model_name sont requis")
    
    print(f"{'='*80}")
    print(f"PIPELINE DE RETRAITEMENT DES RECETTES RÉCALCITRANTES")
    print(f"{'='*80}\n")
    
    # ========== ÉTAPE 1: EXTRACTION DES DONNÉES ==========
    print("ÉTAPE 1: Extraction des recettes problématiques...")
    print("-" * 80)
    
    # Analyser les recettes échouées
    df_failed = analyze_failed_and_na_recipes(cohort_min=cohort_min, cohort_max=cohort_max)
    
    if df_failed.empty:
        print("Aucune recette à retraiter.")
        return None
    
    print(f"\n✅ {len(df_failed)} recettes identifiées pour retraitement")
    print(f"   Recettes uniques: {df_failed['id'].nunique()}")
    
    # ========== ÉTAPE 2: PRÉPARATION DES DONNÉES ==========
    print(f"\nÉTAPE 2: Préparation des données complètes...")
    print("-" * 80)
    
    # Charger les instructions et ingrédients
    try:
        # Grouper les instructions par recette si besoin
        if 'instruction' not in df_failed.columns:
            print("Chargement des instructions ...")
            recipes_full = pd.read_csv("recipe_instructions.csv")
            recipes_full["instruction"] = recipes_full["instruction"].fillna("").astype(str)
            df_instructions = recipes_full.groupby(['id'])["instruction"].agg(" ".join).reset_index() # [id, instruction]
            df_failed = pd.merge(
                df_failed,
                df_instructions[['id', 'instruction']],
                on='id',
                how='inner'
            )
            #df_failed = df_failed.rename(columns={'instructions': 'instruction'})
        
        # Charger et joindre les ingrédients
        print("Chargement et agrégation des ingrédients...")
        ingredients = pd.read_csv("recipe_ingredients.csv")
        ingredients["ingredient"] = ingredients["ingredient"].fillna("").astype(str)
        df_ingredients = ingredients.groupby(['id'])["ingredient"].agg(" ".join).reset_index()
        
        df_failed = pd.merge(df_failed, df_ingredients, on='id', how='inner')
        
        # S'assurer que la colonne 'ingredient' existe
        #if 'ingredient' not in df_failed.columns:
        #    df_failed['ingredient'] = ""
        
        print(f"✅ Données préparées: {len(df_failed)} lignes")
        
    except Exception as e:
        print(f"⚠️  Erreur lors de la préparation des données: {e}")
        print("Continuation avec les données disponibles...")
    
    df_failed = df_failed.drop(columns=["actions"])
    # Renommer 'verb' en 'actions' si nécessaire pour compatibilité
    if 'verb' in df_failed.columns and 'actions' not in df_failed.columns:
        df_failed['actions'] = df_failed['verb']
    
    # Vérifier que toutes les colonnes nécessaires sont présentes
    required_cols = ['id', 'title', 'actions', 'instruction', 'ingredient']
    missing_cols = [col for col in required_cols if col not in df_failed.columns]
    if missing_cols:
        print(f"⚠️  Colonnes manquantes: {missing_cols}")
        return None
    
    # Garder uniquement les colonnes nécessaires et dédupliquer par ID
    df_to_process = df_failed[required_cols].drop_duplicates(subset=['id']).reset_index(drop=True)
    
    print(f"✅ Recettes uniques à traiter: {len(df_to_process)}")
    
    # ========== ÉTAPE 3: TRAITEMENT VIA LLM ==========
    print(f"\nÉTAPE 3: Génération des variantes via LLM...")
    print("-" * 80)
    print(f"Batch size: {batch_size}")
    print(f"Nombre total de batches: {(len(df_to_process) + batch_size - 1) // batch_size}")
    print()
    
    # Utiliser la fonction existante de traitement
    results = process_recipes_batch_3stages(            #process_recipes_retry_pipeline
        recipes_df=df_to_process,
        api_key=api_key,
        model_name=model_name,
        cohort=f"{cohort_min}_{cohort_max}_{output_suffix}",
        batch_size=batch_size,
        delay=1,
        max_retries=max_retries
    )
    
    # ========== ÉTAPE 4: SAUVEGARDE DES RÉSULTATS ==========
    print(f"\nÉTAPE 4: Sauvegarde des résultats...")
    print("-" * 80)
    
    output_dir = "recipes_variants_3stages"
    final_filename = os.path.join(
        output_dir, 
        f'retry_na_results_cohorts_{cohort_min}_to_{cohort_max}_{output_suffix}.json'
    )
    
    final_save_data = {
        'results': results,
        'metadata': {
            'cohort_min': cohort_min,
            'cohort_max': cohort_max,
            'total_recipes_processed': len(df_to_process),
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'model_used': model_name
        }
    }
    
    with open(final_filename, 'w', encoding='utf-8') as f:
        json.dump(final_save_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Résultats sauvegardés dans: {final_filename}")
    
    # Statistiques finales
    print(f"\n{'='*80}")
    print(f"TRAITEMENT TERMINÉ")
    print(f"{'='*80}")
    print(f"Recettes traitées: {len(results['variantes_principales'])}")
    print(f"Variantes principales générées: {len(results['variantes_principales'])}")
    print(f"Variantes secondaires générées: {len(results['variantes_secondaires'])}")
    print(f"Variantes ternaires générées: {len(results['variantes_ternaires'])}")
    print(f"{'='*80}\n")
    
    return results



def extract_na_recipes_from_json(json_file_path):
    """
    Extrait directement les recettes avec NA depuis le fichier JSON
    avant qu'elles ne soient filtrées par data_preparation_3stages
    
    Parameters:
    -----------
    json_file_path : str
        Chemin vers le fichier JSON (ex: "recipes_variants_3stages/sauvegarde_final_3stages_cohort_97.json")
    
    Returns:
    --------
    pd.DataFrame
        DataFrame contenant les recettes avec NA
    """
    import json
    import pandas as pd
    
    # Charger le JSON
    with open(json_file_path, 'r') as f:
        save_data = json.load(f)
        results = save_data.get('results', save_data)
    
    # Charger les titres des recettes
    try:
        recipes = pd.read_csv("recipes.csv", usecols=['id', 'title'])
        recipe_titles = dict(zip(recipes['id'], recipes['title']))
    except:
        recipe_titles = {}
    
    na_recipes = []
    
    # Définir les configurations de variantes
    variante_configs = [
        ('variantes_principales', None, 'principal', 'variante_principale'),
        ('variantes_secondaires', 'ingredient_variant', 'secondaire', 'variante_ingredients'),
        ('variantes_secondaires', 'permutation_1', 'secondaire', 'variante_permutation'),
        ('variantes_secondaires', 'permutation_2', 'secondaire', 'variante_permutation'),
        ('variantes_ternaires', None, 'ternaire', 'variante_temporelle'),
    ]
    
    # Parcourir toutes les recettes
    for recipe_id in results.get('variantes_principales', {}).keys():
        recipe_title = recipe_titles.get(recipe_id, f"Recipe_{recipe_id}")
        
        # Vérifier chaque type de variante
        for result_key, sub_key, type_val, type_2_val in variante_configs:
            if result_key not in results:
                continue
                
            if sub_key is None:
                variante = results[result_key].get(recipe_id, [])
            else:
                variante = results[result_key].get(recipe_id, {}).get(sub_key, [])
            
            # Si la variante contient NA (exactement ["NA"] ou contient "NA")
            if variante == ["NA"] or (isinstance(variante, list) and "NA" in variante):
                na_recipes.append({
                    'id': recipe_id,
                    'title': recipe_title,
                    'actions': variante,
                    'type': type_val,
                    'type_2': type_2_val,
                    'source_file': json_file_path
                })
    
    df_na = pd.DataFrame(na_recipes)
    
    print(f"{'='*60}")
    print(f"EXTRACTION DES RECETTES AVEC NA")
    print(f"{'='*60}")
    print(f"Fichier analysé: {json_file_path}")
    print(f"Recettes avec NA trouvées: {len(df_na)}")
    if len(df_na) > 0:
        print(f"\nExemples d'IDs: {df_na['id'].unique()[:5].tolist()}")
    print(f"{'='*60}\n")
    
    return df_na
def extract_na_from_all_cohorts(cohort_min=None, cohort_max=None):
    """
    Extrait les recettes avec NA de toutes les cohortes resultantes de la generation des variantes.
    
    Parameters:
    -----------
    cohort_min : int, optional
        Numéro minimum de cohorte à analyser
    cohort_max : int, optional
        Numéro maximum de cohorte à analyser
    
    Returns:
    --------
    pd.DataFrame
        DataFrame combiné de toutes les recettes avec NA
    """
    import os
    import pandas as pd
    
    # Trouver tous les fichiers de cohortes
    all_files = [f for f in os.listdir("recipes_variants_3stages/") 
                 if f.startswith("sauvegarde_final_3stages_cohort_")]
    
    subset_list = []
    for f in all_files:
        try:
            cohort_num = int(f.split('_')[-1].split('.')[0])
            if cohort_min is not None and cohort_num < cohort_min:
                continue
            if cohort_max is not None and cohort_num > cohort_max:
                continue
            subset_list.append(cohort_num)
        except ValueError:
            continue
    
    subset_list.sort()
    
    print(f"{'='*60}")
    print(f"EXTRACTION NA DE TOUTES LES COHORTES")
    print(f"{'='*60}")
    print(f"Nombre de cohortes à analyser: {len(subset_list)}")
    print(f"Cohortes: {subset_list[:10]}{'...' if len(subset_list) > 10 else ''}")
    print(f"{'='*60}\n")
    
    all_na_dfs = []
    
    for cohort_num in subset_list:
        json_file = f"recipes_variants_3stages/sauvegarde_final_3stages_cohort_{cohort_num}.json"
        try:
            df_na = extract_na_recipes_from_json(json_file)
            if len(df_na) > 0:
                all_na_dfs.append(df_na)
        except Exception as e:
            print(f"⚠️  Erreur pour cohorte {cohort_num}: {e}")
    
    if all_na_dfs:
        combined_na = pd.concat(all_na_dfs, ignore_index=True)
        print(f"\n{'='*60}")
        print(f"RÉSULTAT FINAL")
        print(f"{'='*60}")
        print(f"Total de recettes avec NA: {len(combined_na)}")
        print(f"Nombre d'IDs uniques: {combined_na['id'].nunique()}")
        print(f"{'='*60}\n")
        return combined_na
    else:
        print("Aucune recette avec NA trouvée.")
        return pd.DataFrame()
