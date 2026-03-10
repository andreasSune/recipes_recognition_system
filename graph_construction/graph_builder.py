"""
MODULE : graph_builder.py
=========================
Construction de graphes orientés pondérés à partir de variantes de recettes.


Date: 2026-01-26
"""

import networkx as nx
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import re
import ast
import time
from pathlib import Path
from functools import lru_cache
from typing import List, Dict, Set, Union, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein


# Import conditionnel de pandas (optionnel)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
"""
PIPELINE  DE NETTOYAGE DES VERBES CULINAIRES
=====================================================
Combine normalisation + filtrage des non-gestes avec RapidFuzz
Temps estimé : quelques secondes pour des millions de lignes

"""

# =============================================================================
# DICTIONNAIRE DE NORMALISATION COMPLET
# =============================================================================

MAPPING_VERBES = {
    # =========================================================================
    # 1. VARIANTES ORTHOGRAPHIQUES (UK/US, accents, typos)
    # =========================================================================
    'mould': 'mold',
    'colour': 'color',
    'flavour': 'flavor',
    'pulverise': 'pulverize',
    'marbleise': 'marbleize',
    'texturise': 'texturize',
    'tenderise': 'tenderize',
    'caramelise': 'caramelize',
    'crystallise': 'crystallize',
    'spiralise': 'spiralize',
    'liquidise': 'liquidize',
    'brûlée': 'brulee',
    'flambé': 'flambe',
    'sauté': 'saute',
    'purée': 'puree',
    'julienned': 'julienne',
    'wisk': 'whisk',
    'whizz': 'whiz',
    'garish': 'garnish',
    'rins': 'rinse',
   
    'season': 'add',
    # =========================================================================
    # 2. SYNONYMES D'ÉCRASEMENT
    # =========================================================================
    'smash': 'mash',
    'smoosh': 'mash',
    'moosh': 'mash',
    'smush': 'mash',
    'mush': 'mash',
    
    # =========================================================================
    # 3. SYNONYMES DE MÉLANGE
    # =========================================================================
    'amalgamate': 'combine',
    'admixture': 'mix',
    'meld': 'blend',
    'mingle': 'mix',
    'incorporate': 'mix',
    'reincorporate': 'mix',
    'recombine': 'combine',
    'reblend': 'blend',
    'premix': 'mix',
    'remash': 'mash',
    
    # =========================================================================
    # 4. SYNONYMES DE DÉCOUPE
    # =========================================================================
    'hacken': 'cut',
    'crosscut': 'cut',
    'trisect': 'cut',
    'cleave': 'cut',
    'sever': 'cut',
    'prechop': 'cut',
    'chop' : 'cut',
    # =========================================================================
    # 5. SYNONYMES DE PLACEMENT
    # =========================================================================
    'plonk': 'place',
    'plop': 'place',
    'plunk': 'place',
    'position': 'place',
    'reposition': 'place',
    'situate': 'place',
    
    # =========================================================================
    # 6. SYNONYMES DE VERSEMENT
    # =========================================================================
    'dribble': 'drizzle',
    'trickle': 'drizzle',
    'stream': 'pour',
    'decant': 'pour',
    
    # =========================================================================
    # 7. SYNONYMES DE SAUPOUDRAGE
    # =========================================================================
    'scatter': 'sprinkle',
    'strew': 'sprinkle',
    'shower': 'sprinkle',
    'dot': 'sprinkle',
    'fleck': 'sprinkle',
    
    # =========================================================================
    # 8. SYNONYMES D'ÉTALEMENT
    # =========================================================================
    'smear': 'spread',
    'slather': 'spread',
    'schmear': 'spread',
    
    # =========================================================================
    # 9. SYNONYMES DE NETTOYAGE
    # =========================================================================
    'cleanse': 'clean',
    'scrub': 'clean',
    'scour': 'clean',
    
    # =========================================================================
    # 10. SYNONYMES D'ENROBAGE
    # =========================================================================
    'enrobe': 'coat',
    'encrust': 'coat',
    'recoat': 'coat',
    'dredge': 'coat',
    
    # =========================================================================
    # 11. SYNONYMES DE RETRAIT
    # =========================================================================
    'discard': 'remove',
    'dispose': 'remove',
    'eliminate': 'remove',
    'extract': 'remove',
    
    # =========================================================================
    # 12. PRÉPARATION DES INGRÉDIENTS
    # =========================================================================
    'debone': 'bone',
    'deseed': 'seed',
    'de-seed': 'seed',
    'pare': 'peel',
    'skin': 'peel',
    'shuck': 'shell',
    'unshell': 'shell',
    
    # =========================================================================
    # 13. FILTRAGE/SÉPARATION
    # =========================================================================
    'sieve': 'sift',
    'strain': 'drain',
    
    # =========================================================================
    # 14. FORME/MODELAGE
    # =========================================================================
    'reshape': 'shape',
    'reform': 'form',
    'remold': 'mold',
    
    # =========================================================================
    # 15. OUVERTURE/FERMETURE
    # =========================================================================
    'uncover': 'open',
    'unwrap': 'open',
    'unfurl': 'open',
    'unfoil': 'open',
    'unseal': 'open',
    'reseal': 'seal',
    'close': 'seal',
    
    # =========================================================================
    # 16. RETOURNEMENT/ROTATION
    # =========================================================================
    'invert': 'turn',
    'rotate': 'turn',
    'revolve': 'turn',
    
    # =========================================================================
    # 17. PLIAGE/ENROULEMENT
    # =========================================================================
    'enfold': 'fold',
    'crease': 'fold',
    'coil': 'roll',
    'curl': 'roll',
    'spiral': 'roll',
    'twirl': 'roll',
    
    # =========================================================================
    # 18. PERFORATION
    # =========================================================================
    'poke': 'pierce',
    'prick': 'pierce',
    'puncture': 'pierce',
    'perforate': 'pierce',
    'stab': 'pierce',
    
    # =========================================================================
    # 19. TAPOTEMENT
    # =========================================================================
    'dab': 'pat',
    'tap': 'pat',
    'blot': 'pat',
    
    # =========================================================================
    # 20. ASSEMBLAGE
    # =========================================================================
    'build': 'assemble',
    'construct': 'assemble',
    'reassemble': 'assemble',
    
    # =========================================================================
    # 21. ATTACHEMENT
    # =========================================================================
    'fasten': 'tie',
    'secure': 'tie',
    'truss': 'tie',
    'bind': 'tie',
    'attach': 'tie',
    
    # =========================================================================
    # 22. GARNITURE/DÉCORATION
    # =========================================================================
    'adorn': 'garnish',
    'ornament': 'garnish',
    'decorate': 'garnish',
    
    # =========================================================================
    # 23. PRÉFIXES RE-
    # =========================================================================
    'readjust': 'adjust',
    'rearrange': 'arrange',
    'rebottle': 'bottle',
    'redraw': 'draw',
    'refill': 'fill',
    'reglaze': 'glaze',
    'rehydrate': 'hydrate',
    'reprocess': 'process',
    'reseason': 'season',
    'rewrap': 'wrap',
    'rework': 'work',
    'rewhisk': 'whisk',
    
    # =========================================================================
    # 24. PRÉFIXES PRE-
    # =========================================================================
    'premeasure': 'measure',
    'preseason': 'season',
    'presoak': 'soak',
    'prewarm': 'warm',
    
    # =========================================================================
    # 25. PRÉFIXES UN-
    # =========================================================================
    'uncurl': 'straighten',
    'untwist': 'straighten',
    'unwind': 'straighten',
    'unroll': 'open',
    'unmold': 'remove',
    'unskewer': 'remove',
    'unspit': 'remove',
    'unstack': 'separate',
    'unstuff': 'remove',
    'unthread': 'remove',
    'untie': 'open',
    'untruss': 'open',
    
    # =========================================================================
    # 26. VERBES COMPOSÉS
    # =========================================================================
    'tip out': 'pour',
    'wedge slice': 'slice',
    'egg wash': 'brush',
    'vacuum seal': 'seal',
    
    # =========================================================================
    # 27. FORMES CONJUGUÉES
    # =========================================================================
    'tipping': 'tip',
    'wrapper': 'wrap',
    'pieces': 'piece',
    'cooks': 'cook',
    'mixing': 'mix',
    'mixed': 'mix',
    'chopping': 'chop',
    'chopped': 'chop',
    'slicing': 'slice',
    'sliced': 'slice',
    'dicing': 'dice',
    'diced': 'dice',
    'stirring': 'stir',
    'stirred': 'stir',
    'beating': 'beat',
    'beaten': 'beat',
    'whisking': 'whisk',
    'whisked': 'whisk',
    'pouring': 'pour',
    'poured': 'pour',
    'folding': 'fold',
    'folded': 'fold',
    'kneading': 'knead',
    'kneaded': 'knead',
    'grating': 'grate',
    'grated': 'grate',
    'peeling': 'peel',
    'peeled': 'peel',
    'mincing': 'mince',
    'minced': 'mince',
    'crushing': 'crush',
    'crushed': 'crush',
    'mashing': 'mash',
    'mashed': 'mash',
    'spreading': 'spread',
    'spreaded': 'spread',
    'rolling': 'roll',
    'rolled': 'roll',
    'wrapping': 'wrap',
    'wrapped': 'wrap',
    'coating': 'coat',
    'coated': 'coat',
    'seasoning': 'season',
    'seasoned': 'season',
    'garnishing': 'garnish',
    'garnished': 'garnish',
    'draining': 'drain',
    'drained': 'drain',
    'straining': 'strain',
    'strained': 'strain',
    'sifting': 'sift',
    'sifted': 'sift',
    'crumbling': 'crumble',
    'crumbled': 'crumble',
    'flaking': 'flake',
    'flaked': 'flake',
    'shelling': 'shell',
    'shelled': 'shell',
    'piping': 'pipe',
    'piped': 'pipe',
    'tossing': 'toss',
    'tossed': 'toss',
    'shaking': 'shake',
    'shaked': 'shake',
    'sandwiching': 'sandwich',
    'sandwiched': 'sandwich',
    'processing': 'process',
    'processed': 'process',
    
    # =========================================================================
    # 28. ÉCLABOUSSURES
    # =========================================================================
    'splat': 'splash',
    'splatter': 'splash',
    'splodge': 'splash',
    'sploosh': 'splash',
    'splotch': 'splash',
    'spritz': 'spray',
    'squirt': 'spray',
    
    # =========================================================================
    # 29. PRESSER
    # =========================================================================
    'squish': 'squeeze',
    'squash': 'squeeze',
    
    # =========================================================================
    # 30. TECHNIQUES RARES
    # =========================================================================
    'chiffonade': 'slice',
    'concasse': 'chop',
    'tournee': 'cut',
    'quenelle': 'shape',
    'spatchcock': 'butterfly',
    'supreme': 'segment',
    
    # =========================================================================
    # 31. TREMPAGE/IMMERSION
    # =========================================================================
    'submerge': 'soak',
    'immerse': 'soak',
    'dunk': 'dip',
    'douse': 'soak',
    'drench': 'soak',
    'drown': 'soak',
    
    # =========================================================================
    # 32. VARIANTES REDONDANTES
    # =========================================================================
    'baggie': 'bag',
    'dollop': 'spoon',
    'ladle': 'spoon',
    'brÃ»lÃ©e': 'brulee',
    'purÃ©e': 'puree',
    
    # Découpe
    'chisel': 'cut',
    'shear': 'cut',
    'slash': 'cut',
    'slit': 'cut',
    'sliver': 'slice',
    'shave': 'slice',
    'gash': 'cut',
    'nick': 'cut',
    'nip': 'cut',
    'clip': 'cut',
    
    # Perforation
    'cavity': 'pierce',
    'pip': 'seed',
    
    # Placement
    'nestle': 'place',
    'nest': 'place',
    'cradle': 'place',
    'seat': 'place',
    'mount': 'place',
    'center': 'place',
    'lean': 'place',
    
    # Pressage
    'compress': 'press',
    
    # Tapotement
    'buff': 'pat',
    'nudge': 'pat',
    
    # Assemblage
    'bundle': 'tie',
    'package': 'wrap',
    
    # Enrobage
    'blanket': 'coat',
    'dust': 'sprinkle',  # ou 'coat'
    'film': 'coat',
    'nap': 'coat',
    
    # Mélange
    'marry': 'combine',
    'muddle': 'mix',
    'swizzle': 'stir',
    'swirl': 'stir',
    'agitate': 'stir',
    
    # Saupoudrage
    'rain': 'sprinkle',
    
    # Techniques françaises
    'brunoise': 'dice',
    
    # Verbes composés
    'air dry': 'dry',
    'flash freeze': 'freeze',
    'flash fry': 'fry',
    'hard boil': 'boil',
    'level off': 'level',
    'punch down': 'punch',
    'slow cook': 'cook',
    'slow roast': 'roast',
    'spit roast': 'roast',
    'turn off': 'turn',
    'throw away': 'discard',
    'take off': 'remove',
    
    # Préfixes
    'overmix': 'mix',
    'declump': 'separate',
    'degrease': 'remove',
    'degas': 'remove',
    'devein': 'remove',
    'devil': 'season',
    'disjoint': 'cut',
    'eviscerate': 'gut',
    'unglaze': 'clean',
    'ungrease': 'clean',
}


# =============================================================================
# VERBES NON-GESTUELS (à filtrer)
# =============================================================================

NON_GESTURE_VERBS = {
    # Cuissons passives
    'bake', 'roast', 'boil', 'simmer', 'steam', 'broil', 'grill', 'fry',
    'deep fry', 'shallow fry', 'pan fry', 'stir fry', 'air fry',
    'poach', 'braise', 'stew', 'barbecue', 'smoke', 'toast', 'char',
    'sear', 'brown', 'caramelize', 'blacken', 'scorch', 'singe', 'burn',
    'flambe', 'torch', 'griddle', 'blanch', 'parboil', 'parbake',
    'slow cook', 'pressure cook', 'microwave', 'nuke',
    
    # Transformations thermiques passives
    'heat', 'warm', 'reheat', 'preheat', 'cool', 'chill', 'freeze',
    'refrigerate', 'thaw', 'defrost', 'melt', 'soften',
    
    # Processus chimiques/biologiques
    'ferment', 'proof', 'rise', 'leaven', 'activate', 'culture',
    'marinate', 'macerate', 'pickle', 'cure', 'age', 'ripen',
    'caramelize', 'crystallize', 'coagulate', 'curdle', 'congeal',
    'thicken', 'reduce', 'concentrate', 'emulsify', 'dissolve',
    
    # États/résultats passifs
    'rest', 'set', 'settle', 'steep', 'infuse', 'soak',
    'crisp', 'harden', 'firm', 'stiffen', 'soften', 'wilt',
    
    # Appareils qui travaillent seuls
    'blend', 'blenderize', 'blitz', 'grind', 'mill', 'process', 'puree',
    'cream', 'whip', 'churn', 'froth', 'foam',
    
    # Mots non-verbes à supprimer
    'bok', 'cheeses', 'chestnuts', 'chorizo', 'choy', 'ciabatta',
    'cucumber', 'curry', 'plum', 'tons', 'tortillas', 'won',
    'medium high', 'periodically', 'room', 'freezer', 'graham',
    'marzipan', 'frisee', 'fringe', 'degrees', 'minutes', 'seconds',
     # Cuissons
    'parcook', 'coddle', 'droast', 'scald', 'parch',
    
    # Processus chimiques/biologiques
    'autolyse', 'activate', 'inoculate', 'pasteurize', 'sterilize',
    'carbonate', 'acidulate', 'gel', 'solidify', 'leach',
    
    # États passifs
    'bubble', 'shimmer', 'sizzle', 'roil', 'ooze', 'seep',
    'swell', 'shrink', 'burst',
    
    'adhere', 'bathe', 'blanket', 'blast', 'blaze', 'blind bake', 'blow', 'brûlée',
    'candy', 'cook', 'cooks', 'crackle', 'crunch', 'darken', 'deepen', 'dehydrate',
    'dry', 'fire', 'flash', 'frappe', 'freshen', 'frizzle', 'frost', 'glaze', 'hard boil',
    'mull', 'overbake', 'overmix', 'reboil', 'reconstitute', 'refreeze', 'refry', 'ripple', 'undercook',
    # Appareils
    'pulverise', 'churn freeze', 'percolate', 'perk',
}


# =============================================================================
# CLASSE PRINCIPALE : VerbCleaner
# =============================================================================

@dataclass
class CleaningStats:
    """Statistiques de nettoyage"""
    total_input: int = 0
    unique_verbs_found: int = 0
    verbs_normalized: int = 0
    verbs_removed: int = 0
    verbs_kept: int = 0
    fuzzy_matches: int = 0
    processing_time: float = 0.0
    
    def __str__(self):
        return f"""
╔══════════════════════════════════════════════════════╗
║           STATISTIQUES DE NETTOYAGE                  ║
╠══════════════════════════════════════════════════════╣
║  Lignes traitées:        {self.total_input:>15,}        ║
║  Verbes uniques trouvés: {self.unique_verbs_found:>15,}        ║
║  Verbes normalisés:      {self.verbs_normalized:>15,}        ║
║  Verbes supprimés:       {self.verbs_removed:>15,}        ║
║  Verbes conservés:       {self.verbs_kept:>15,}        ║
║  Matches fuzzy:          {self.fuzzy_matches:>15,}        ║
║  Temps de traitement:    {self.processing_time:>12.2f} sec   ║
╚══════════════════════════════════════════════════════╝
"""


class VerbCleaner:
    """
    Nettoyeur de verbes culinaires ultra-optimisé.
    
    Combine:
    - Normalisation (variantes → forme canonique)
    - Filtrage (suppression des verbes non-gestuels)
    - Matching flou avec RapidFuzz
    - Cache pour performance maximale
    """
    
    def __init__(
        self,
        normalization_dict: Optional[Dict[str, str]] = None,
        non_gesture_verbs: Optional[Set[str]] = None,
        similarity_threshold: int = 85,
        use_fuzzy: bool = True,
        verbose: bool = True
    ):
        """
        Initialise le cleaner.
        
        Args:
            normalization_dict: Dictionnaire de normalisation (variante → canonique)
            non_gesture_verbs: Set des verbes non-gestuels à filtrer (None = utiliser défaut)
            similarity_threshold: Seuil de similarité pour fuzzy matching (0-100)
            use_fuzzy: Activer le matching flou
            verbose: Afficher les messages de progression
        """
        self.threshold = similarity_threshold
        self.use_fuzzy = use_fuzzy
        self.verbose = verbose
        
        # CORRECTION ICI: Utiliser is None pour distinguer None de set()
        norm_dict = normalization_dict if normalization_dict is not None else MAPPING_VERBES
        remove_set = non_gesture_verbs if non_gesture_verbs is not None else NON_GESTURE_VERBS
        
        # Pré-normaliser les dictionnaires (tout en minuscules, sans tirets)
        self.norm_exact = {
            self._normalize_surface(k): self._normalize_surface(v)
            for k, v in norm_dict.items()
        }
        self.removal_exact = {
            self._normalize_surface(v) for v in remove_set
        }
        
        # Listes pour fuzzy matching
        self.norm_keys = list(self.norm_exact.keys())
        self.removal_list = list(self.removal_exact)
        
        # Caches pour éviter les recalculs
        self._norm_cache: Dict[str, str] = {}
        self._remove_cache: Dict[str, bool] = {}
        self._final_cache: Dict[str, Optional[str]] = {}
        
        # Statistiques
        self.stats = CleaningStats()
        
        if self.verbose:
            print(f"✓ VerbCleaner initialisé:")
            print(f"  - {len(self.norm_exact)} règles de normalisation")
            print(f"  - {len(self.removal_exact)} verbes non-gestuels")
            print(f"  - Seuil fuzzy: {self.threshold}%")
            print(f"  - Fuzzy matching: {'activé' if self.use_fuzzy else 'désactivé'}")
            print(f"  - Mode: {'normalisation seule' if len(self.removal_exact) == 0 else 'normalisation + filtrage'}")
    
    @staticmethod
    def _normalize_surface(text: str) -> str:
        """Normalisation de surface (minuscules, espaces, tirets)"""
        text = str(text).lower().strip()
        text = text.replace("-", " ")
        text = re.sub(r"\s+", " ", text)
        return text
    
    def _normalize_with_dict(self, verb: str) -> str:
        """Normalise un verbe avec le dictionnaire (+ fuzzy si activé)"""
        if verb in self._norm_cache:
            return self._norm_cache[verb]
        
        # 1. Match exact
        if verb in self.norm_exact:
            result = self.norm_exact[verb]
            self._norm_cache[verb] = result
            self.stats.verbs_normalized += 1
            return result
        
        # 2. Fuzzy match si activé
        if self.use_fuzzy and self.norm_keys:
            match_result = process.extractOne(
                verb,
                self.norm_keys,
                scorer=fuzz.ratio,
                score_cutoff=self.threshold
            )
            if match_result is not None:
                matched_key, score, _ = match_result
                result = self.norm_exact[matched_key]
                self._norm_cache[verb] = result
                self.stats.verbs_normalized += 1
                self.stats.fuzzy_matches += 1
                return result
        
        # 3. Pas de match → garder tel quel
        self._norm_cache[verb] = verb
        return verb
    
    def _should_remove(self, verb: str) -> bool:
        """Vérifie si un verbe doit être supprimé (non-gestuel)"""
        # Si pas de verbes à supprimer, ne rien supprimer
        if not self.removal_exact:
            return False
        
        if verb in self._remove_cache:
            return self._remove_cache[verb]
        
        # 1. Match exact
        if verb in self.removal_exact:
            self._remove_cache[verb] = True
            return True
        
        # 2. Fuzzy match si activé
        if self.use_fuzzy and self.removal_list:
            match_result = process.extractOne(
                verb,
                self.removal_list,
                scorer=fuzz.ratio,
                score_cutoff=self.threshold
            )
            if match_result is not None:
                self._remove_cache[verb] = True
                self.stats.fuzzy_matches += 1
                return True
        
        # 3. Pas de match → garder
        self._remove_cache[verb] = False
        return False
    
    def clean_verb(self, verb: str) -> Optional[str]:
        """
        Nettoie un seul verbe: normalise puis filtre.
        
        Returns:
            Verbe normalisé ou None si à supprimer
        """
        # Check cache final
        if verb in self._final_cache:
            return self._final_cache[verb]
        
        # Normalisation de surface
        verb_norm = self._normalize_surface(verb)
        
        # Normalisation avec dictionnaire
        verb_norm = self._normalize_with_dict(verb_norm)
        
        # Filtrage
        if self._should_remove(verb_norm):
            self._final_cache[verb] = None
            self.stats.verbs_removed += 1
            return None
        
        self._final_cache[verb] = verb_norm
        self.stats.verbs_kept += 1
        return verb_norm
    
    def clean_list(self, verbs: Union[str, List[str]]) -> List[str]:
        """
        Nettoie une liste de verbes.
        
        Args:
            verbs: Liste de verbes (str format liste ou List[str])
            
        Returns:
            Liste de verbes nettoyés (normalisés + filtrés)
        """
        # Conversion si chaîne
        if isinstance(verbs, str):
            try:
                verbs = ast.literal_eval(verbs)
            except (ValueError, SyntaxError):
                verbs = [verbs]
        
        if not isinstance(verbs, list):
            return []
        
        # Nettoyage
        cleaned = []
        for verb in verbs:
            result = self.clean_verb(verb)
            if result is not None:
                cleaned.append(result)
        
        return cleaned
    
    def clean_dataframe(
        self, 
        df, 
        input_col: str = 'actions',
        output_col: str = 'actions_cleaned'
    ):
        """
        Nettoie une colonne de DataFrame (optimisé).
        
        Args:
            df: DataFrame pandas
            input_col: Nom de la colonne d'entrée
            output_col: Nom de la colonne de sortie
            
        Returns:
            DataFrame avec nouvelle colonne nettoyée
        """
        if not HAS_PANDAS:
            raise ImportError("pandas requis pour cette fonction")
        
        start_time = time.time()
        self.stats = CleaningStats()  # Reset stats
        self.stats.total_input = len(df)
        
        if self.verbose:
            print(f"\n🚀 Nettoyage du DataFrame...")
            print(f"   {len(df):,} lignes à traiter")
        
        # Étape 1: Extraire tous les verbes uniques
        if self.verbose:
            print("\n📋 Étape 1/3: Extraction des verbes uniques...")
        
        all_verbs = set()
        for actions_list in df[input_col]:
            if isinstance(actions_list, str):
                try:
                    actions_list = ast.literal_eval(actions_list)
                except:
                    actions_list = [actions_list]
            if isinstance(actions_list, list):
                all_verbs.update(actions_list)
        
        self.stats.unique_verbs_found = len(all_verbs)
        if self.verbose:
            print(f"   ✓ {len(all_verbs):,} verbes uniques trouvés")
        
        # Étape 2: Pré-calculer le mapping pour tous les verbes uniques
        if self.verbose:
            print("\n🧹 Étape 2/3: Pré-calcul du mapping...")
        
        verb_mapping = {}
        for verb in all_verbs:
            result = self.clean_verb(verb)
            if result is not None:
                verb_mapping[verb] = result
        
        if self.verbose:
            print(f"   ✓ {len(verb_mapping):,} verbes conservés")
            print(f"   ✓ {len(all_verbs) - len(verb_mapping):,} verbes supprimés")
        
        # Étape 3: Appliquer le mapping (ultra-rapide!)
        if self.verbose:
            print("\n⚡ Étape 3/3: Application du mapping...")
        
        def apply_mapping(actions_list):
            if isinstance(actions_list, str):
                try:
                    actions_list = ast.literal_eval(actions_list)
                except:
                    actions_list = [actions_list]
            if not isinstance(actions_list, list):
                return []
            return [verb_mapping[v] for v in actions_list if v in verb_mapping]
        
        df_result = df.copy()
        df_result[output_col] = df[input_col].apply(apply_mapping)
        
        # Finaliser stats
        self.stats.processing_time = time.time() - start_time
        
        if self.verbose:
            print(self.stats)
            
            # Stats supplémentaires
            avg_before = df[input_col].apply(
                lambda x: len(ast.literal_eval(x) if isinstance(x, str) else x) 
                if x else 0
            ).mean()
            avg_after = df_result[output_col].apply(len).mean()
            
            print(f"📊 Réduction moyenne: {avg_before:.2f} → {avg_after:.2f} actions/recette")
            if avg_before > 0:
                print(f"   ({(1 - avg_after/avg_before)*100:.1f}% de réduction)")
        
        return df_result
    
    def clear_cache(self):
        """Vide tous les caches"""
        self._norm_cache.clear()
        self._remove_cache.clear()
        self._final_cache.clear()
        if self.verbose:
            print("✓ Caches vidés")
    
    def get_cache_stats(self) -> Dict:
        """Retourne les statistiques des caches"""
        return {
            'norm_cache_size': len(self._norm_cache),
            'remove_cache_size': len(self._remove_cache),
            'final_cache_size': len(self._final_cache),
        }



# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def load_verbs_from_file(filepath: str) -> Set[str]:
    """Charge une liste de verbes depuis un fichier texte"""
    verbs = set()
    path = Path(filepath)
    
    if not path.exists():
        raise FileNotFoundError(f"Fichier non trouvé: {filepath}")
    
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                verbs.add(line.lower())
    
    return verbs


def create_cleaner_from_files(
    normalization_file: Optional[str] = None,
    non_gesture_file: Optional[str] = None,
    **kwargs
) -> VerbCleaner:
    """
    Crée un VerbCleaner à partir de fichiers externes.
    
    Args:
        normalization_file: Chemin vers fichier de normalisation (format: variante,canonique)
        non_gesture_file: Chemin vers fichier des verbes non-gestuels
        **kwargs: Arguments supplémentaires pour VerbCleaner
    """
    norm_dict = None
    non_gesture = None
    
    if normalization_file:
        norm_dict = {}
        with open(normalization_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        norm_dict[parts[0].strip()] = parts[1].strip()
    
    if non_gesture_file:
        non_gesture = load_verbs_from_file(non_gesture_file)
    
    return VerbCleaner(
        normalization_dict=norm_dict,
        non_gesture_verbs=non_gesture,
        **kwargs
    )




class RecipeGraphBuilder:
    """
    Constructeur de graphes de recettes à partir de variantes.
    
    Principe :
    - 1 graphe par recette
    - Fusion de toutes les variantes (principale, ingrédients, permutations)
    - Graphe orienté avec nœud START virtuel
    - Poids des arêtes = nombre total d'occurrences de la transition
    
    Attributs:
        recipe_id (str): Identifiant unique de la recette
        title (str): Nom de la recette
        graph (nx.DiGraph): Graphe NetworkX construit
        metadata (dict): Métadonnées du graphe
    """
    
    def __init__(self, recipe_id: str, title: str = ""):
        """
        Initialise le builder pour une recette.
        
        Args:
            recipe_id: Identifiant unique de la recette
            title: Nom de la recette (optionnel)
        """
        self.recipe_id = recipe_id
        self.title = title
        self.graph = nx.DiGraph()
        self.metadata = {
            'recipe_id': recipe_id,
            'title': title,
            'num_variants': 0,
            'num_nodes': 0,
            'num_edges': 0,
            'has_cycles': False,
            'entry_points': [],
        }
        
        # Compteurs pour optimisation
        self._node_occurrences = defaultdict(int)
        self._edge_weights = defaultdict(int)
        
    def add_variant(self, actions: List[str], variant_type: str = "unknown") -> None:
        """
        Ajoute une variante au graphe.
        
        Args:
            actions: Liste des actions de la variante
            variant_type: Type de variante (principale, ingrédients, permutation)
        
        Raises:
            ValueError: Si la liste d'actions est vide
        """
        if not actions or len(actions) == 0:
            raise ValueError(f"Liste d'actions vide pour variante {variant_type}")
        
        self.metadata['num_variants'] += 1
        
        # Phase 1 : Compter les occurrences de nœuds
        for action in actions:
            self._node_occurrences[action] += 1
        
        # Phase 2 : Compter les transitions (arêtes)
        # START → première action
        first_action = actions[0]
        self._edge_weights[('START', first_action)] += 1
        
        # Transitions consécutives
        for i in range(len(actions) - 1):
            source = actions[i]
            target = actions[i + 1]
            self._edge_weights[(source, target)] += 1
    
    def build(self) -> nx.DiGraph:
        """
        Construit le graphe final à partir des variantes ajoutées.
        
        Returns:
            Le graphe NetworkX construit
            
        Raises:
            ValueError: Si aucune variante n'a été ajoutée
        """
        if self.metadata['num_variants'] == 0:
            raise ValueError(f"Aucune variante ajoutée pour la recette {self.recipe_id}")
        
        # Étape 1 : Ajouter le nœud START
        self.graph.add_node(
            'START',
            action='START',
            occurrence_count=0,
            is_virtual=True
        )
        
        # Étape 2 : Ajouter tous les nœuds d'actions
        for action, count in self._node_occurrences.items():
            self.graph.add_node(
                action,
                action=action,
                occurrence_count=count,
                is_virtual=False
            )
        
        # Étape 3 : Ajouter toutes les arêtes avec leurs poids
        for (source, target), weight in self._edge_weights.items():
            self.graph.add_edge(
                source,
                target,
                weight=weight
            )
        
        # Étape 4 : Calculer les métadonnées
        self._compute_metadata()
        
        # Étape 5 : Validation
        self._validate()
        
        return self.graph
    
    def _compute_metadata(self) -> None:
        """Calcule les métadonnées du graphe construit."""
        self.metadata['num_nodes'] = self.graph.number_of_nodes()
        self.metadata['num_edges'] = self.graph.number_of_edges()
        
        # Points d'entrée (successeurs de START)
        if 'START' in self.graph:
            self.metadata['entry_points'] = list(self.graph.successors('START'))
        
        # Détection de cycles
        try:
            # NetworkX lève une exception si le graphe a des cycles
            list(nx.find_cycle(self.graph, orientation='original'))
            self.metadata['has_cycles'] = True
        except nx.NetworkXNoCycle:
            self.metadata['has_cycles'] = False
    
    def _validate(self) -> None:
        """
        Valide la structure du graphe construit.
        
        Raises:
            ValueError: Si le graphe est invalide
        """
        # Vérification 1 : Au moins 1 nœud (hors START)
        if self.graph.number_of_nodes() <= 1:
            raise ValueError(f"Graphe vide pour recette {self.recipe_id}")
        
        # Vérification 2 : START existe
        if 'START' not in self.graph:
            raise ValueError(f"Nœud START manquant pour recette {self.recipe_id}")
        
        # Vérification 3 : Au moins 1 arête depuis START
        if self.graph.out_degree('START') == 0:
            raise ValueError(f"Aucune arête sortante de START pour recette {self.recipe_id}")
        
        # Vérification 4 : Pas de nœuds isolés (sauf potentiellement en fin)
        isolated = list(nx.isolates(self.graph))
        if isolated:
            raise ValueError(f"Nœuds isolés détectés pour recette {self.recipe_id}: {isolated}")
        
        # Vérification 5 : Tous les nœuds (sauf START) sont accessibles depuis START
        reachable = set(nx.descendants(self.graph, 'START'))
        reachable.add('START')
        all_nodes = set(self.graph.nodes())
        unreachable = all_nodes - reachable
        
        if unreachable:
            raise ValueError(
                f"Nœuds non accessibles depuis START pour recette {self.recipe_id}: {unreachable}"
            )
    
    def get_graph(self) -> nx.DiGraph:
        """
        Retourne le graphe construit.
        
        Returns:
            Le graphe NetworkX
            
        Raises:
            RuntimeError: Si build() n'a pas encore été appelé
        """
        if self.graph.number_of_nodes() == 0:
            raise RuntimeError("Le graphe n'a pas encore été construit. Appelez build() d'abord.")
        return self.graph
    
    def get_metadata(self) -> Dict:
        """
        Retourne les métadonnées du graphe.
        
        Returns:
            Dictionnaire des métadonnées
        """
        return self.metadata.copy()
    
    def get_statistics(self) -> Dict:
        """
        Calcule des statistiques détaillées sur le graphe.
        
        Returns:
            Dictionnaire de statistiques
        """
        if self.graph.number_of_nodes() == 0:
            return {}
        
        stats = {
            'recipe_id': self.recipe_id,
            'title': self.title,
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'num_variants': self.metadata['num_variants'],
            'density': nx.density(self.graph),
            'has_cycles': self.metadata['has_cycles'],
            'entry_points': self.metadata['entry_points'],
            'num_entry_points': len(self.metadata['entry_points']),
        }
        
        # Calculer le degré moyen
        degrees = [d for n, d in self.graph.degree()]
        stats['avg_degree'] = sum(degrees) / len(degrees) if degrees else 0
        
        # Identifier les nœuds terminaux (sans successeurs)
        terminal_nodes = [n for n in self.graph.nodes() if self.graph.out_degree(n) == 0]
        stats['terminal_nodes'] = terminal_nodes
        stats['num_terminal_nodes'] = len(terminal_nodes)
        
        # Calculer la longueur moyenne des chemins depuis START
        try:
            path_lengths = []
            for node in self.graph.nodes():
                if node != 'START' and nx.has_path(self.graph, 'START', node):
                    length = nx.shortest_path_length(self.graph, 'START', node)
                    path_lengths.append(length)
            
            if path_lengths:
                stats['avg_path_length_from_start'] = sum(path_lengths) / len(path_lengths)
                stats['max_path_length_from_start'] = max(path_lengths)
                stats['min_path_length_from_start'] = min(path_lengths)
        except:
            stats['avg_path_length_from_start'] = None
        
        return stats
    
    def __repr__(self) -> str:
        """Représentation textuelle du builder."""
        return (
            f"RecipeGraphBuilder(recipe_id='{self.recipe_id}', "
            f"nodes={self.graph.number_of_nodes()}, "
            f"edges={self.graph.number_of_edges()}, "
            f"variants={self.metadata['num_variants']})"
        )


def build_graph_from_dataframe_group(group_df) -> Tuple[str, nx.DiGraph, Dict]:
    """
    Construit un graphe à partir d'un groupe DataFrame (même recipe_id).
    
    Fonction utilitaire pour faciliter l'utilisation avec pandas groupby.
    
    Args:
        group_df: DataFrame groupé par recipe_id
        
    Returns:
        Tuple (recipe_id, graph, metadata)
        
    Raises:
        ValueError: Si le groupe est invalide
    """
    if len(group_df) == 0:
        raise ValueError("Groupe DataFrame vide")
    
    # Extraire les informations
    recipe_id = group_df['id'].iloc[0]
    title = group_df['title'].iloc[0] if 'title' in group_df.columns else ""
    
    # Créer le builder
    builder = RecipeGraphBuilder(recipe_id, title)
    
    # Ajouter chaque variante
    for idx, row in group_df.iterrows():
        actions = row['actions']
        variant_type = row.get('type_2', 'unknown')
        
        # Valider que actions est une liste
        if not isinstance(actions, list):
            raise ValueError(
                f"La colonne 'actions' doit être une liste Python. "
                f"Type trouvé : {type(actions)} pour recette {recipe_id}"
            )
        
        if len(actions) > 0:
            builder.add_variant(actions, variant_type)
    
    # Construire le graphe
    graph = builder.build()
    metadata = builder.get_metadata()
    
    return recipe_id, graph, metadata



