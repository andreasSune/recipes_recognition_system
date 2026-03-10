"""
MODULE : pipeline.py
====================
Pipeline principal pour construire tous les graphes de recettes depuis un DataFrame.

Auteur: Laboratoire Liara, UQAC
Date: 2026-01-26
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional, Dict, List
import time
from tqdm import tqdm

from graph_builder import RecipeGraphBuilder
from db_manager import GraphDatabase

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RecipeGraphPipeline:
    """
    Pipeline pour construire les graphes de toutes les recettes.
    
    Workflow :
    1. Charger le DataFrame
    2. Grouper par recipe_id
    3. Pour chaque recette (par batch) :
       - Extraire les variantes
       - Construire le graphe
       - Sauvegarder dans SQLite
    4. Générer rapport
    
    Attributs:
        df (pd.DataFrame): DataFrame des recettes
        db_path (str): Chemin vers la base de données
        batch_size (int): Taille des batchs
        stats (dict): Statistiques de traitement
    """
    
    def __init__(
        self,
        dataframe: pd.DataFrame,
        db_path: str = "recipe_graphs.db",
        batch_size: int = 10000
    ):
        """
        Initialise le pipeline.
        
        Args:
            dataframe: DataFrame avec colonnes ['id', 'title', 'actions', 'type_2']
            db_path: Chemin vers la base de données SQLite
            batch_size: Nombre de recettes à traiter par batch
        """
        self.df = dataframe
        self.db_path = db_path
        self.batch_size = batch_size
        
        # Statistiques
        self.stats = {
            'total_recipes': 0,
            'successful': 0,
            'failed': 0,
            'total_time': 0,
            'errors': []
        }
        
        # Validation du DataFrame
        self._validate_dataframe()
    
    def _validate_dataframe(self) -> None:
        """Valide la structure du DataFrame."""
        required_columns = ['id', 'actions', 'type_2']
        missing = [col for col in required_columns if col not in self.df.columns]
        
        if missing:
            raise ValueError(f"Colonnes manquantes dans le DataFrame: {missing}")
        
        # Vérifier que actions est bien une liste
        sample = self.df['actions'].iloc[0]
        if not isinstance(sample, list):
            raise ValueError(
                f"La colonne 'actions' doit contenir des listes Python. "
                f"Type trouvé: {type(sample)}"
            )
        
        logger.info(f"✓ DataFrame validé : {len(self.df)} lignes")
    
    def run(self, limit: Optional[int] = None) -> Dict:
        """
        Exécute le pipeline complet.
        
        Args:
            limit: Limiter au N premières recettes (None = toutes)
            
        Returns:
            Dictionnaire de statistiques
        """
        start_time = time.time()
        
        logger.info("=" * 70)
        logger.info("DÉMARRAGE DU PIPELINE DE CONSTRUCTION DE GRAPHES")
        logger.info("=" * 70)
        
        # Grouper par recipe_id
        logger.info("\n Étape 1/3 : Groupement des recettes...")
        grouped = self.df.groupby('id')
        recipe_groups = list(grouped)
        
        # Limiter si demandé
        if limit:
            recipe_groups = recipe_groups[:limit]
            logger.info(f"  ⚠️  Limite appliquée : {limit} recettes")
        
        self.stats['total_recipes'] = len(recipe_groups)
        logger.info(f"  ✓ {self.stats['total_recipes']} recettes uniques trouvées")
        
        # Créer la base de données
        logger.info("\n  Étape 2/3 : Initialisation de la base de données...")
        db = GraphDatabase(self.db_path)
        logger.info(f"  ✓ Base de données prête : {self.db_path}")
        
        # Traiter les recettes
        logger.info("\n Étape 3/3 : Construction des graphes...")
        self._process_recipes(recipe_groups, db)
        
        # Fermer la DB
        db.close()
        
        # Finaliser les stats
        self.stats['total_time'] = time.time() - start_time
        
        # Rapport final
        self._print_report()
        
        return self.stats
    
    def _process_recipes(self, recipe_groups: List, db: GraphDatabase) -> None:
        """
        Traite toutes les recettes par batch.
        
        Args:
            recipe_groups: Liste de (recipe_id, group_df)
            db: Instance de GraphDatabase
        """
        num_batches = (len(recipe_groups) + self.batch_size - 1) // self.batch_size
        
        logger.info(f"  Traitement par batch de {self.batch_size} recettes")
        logger.info(f"  Nombre de batchs : {num_batches}")
        
        # Barre de progression
        with tqdm(total=len(recipe_groups), desc="Construction graphes") as pbar:
            
            for batch_idx in range(num_batches):
                start_idx = batch_idx * self.batch_size
                end_idx = min((batch_idx + 1) * self.batch_size, len(recipe_groups))
                batch = recipe_groups[start_idx:end_idx]
                
                # Traiter le batch
                for recipe_id, group_df in batch:
                    try:
                        self._process_single_recipe(recipe_id, group_df, db)
                        self.stats['successful'] += 1
                    except Exception as e:
                        self.stats['failed'] += 1
                        error_msg = f"Recette {recipe_id}: {str(e)}"
                        self.stats['errors'].append(error_msg)
                        logger.error(f"  ✗ {error_msg}")
                    
                    pbar.update(1)
    
    def _process_single_recipe(
        self,
        recipe_id: str,
        group_df: pd.DataFrame,
        db: GraphDatabase
    ) -> None:
        """
        Traite une seule recette.
        
        Args:
            recipe_id: Identifiant de la recette
            group_df: DataFrame groupé pour cette recette
            db: Instance de GraphDatabase
        """
        # Extraire titre
        title = group_df['title'].iloc[0] if 'title' in group_df.columns else ""
        
        # Créer le builder
        builder = RecipeGraphBuilder(recipe_id, title)
        
        # Ajouter chaque variante
        for idx, row in group_df.iterrows():
            actions = row['actions']
            variant_type = row.get('type_2', 'unknown')
            
            if isinstance(actions, list) and len(actions) > 0:
                builder.add_variant(actions, variant_type)
        
        # Construire le graphe
        graph = builder.build()
        metadata = builder.get_metadata()
        
        # Sauvegarder
        db.save_graph(recipe_id, graph, metadata)
    
    def _print_report(self) -> None:
        """Affiche le rapport final."""
        logger.info("\n" + "=" * 70)
        logger.info("RAPPORT FINAL")
        logger.info("=" * 70)
        
        logger.info(f"  Total recettes          : {self.stats['total_recipes']}")
        logger.info(f"  ✓ Succès                : {self.stats['successful']}")
        logger.info(f"  ✗ Échecs                : {self.stats['failed']}")
        logger.info(f"    Temps total           : {self.stats['total_time']:.2f}s")
        
        if self.stats['successful'] > 0:
            avg_time = self.stats['total_time'] / self.stats['successful']
            logger.info(f"   Temps moyen/recette  : {avg_time:.3f}s")
        
        if self.stats['failed'] > 0:
            logger.info(f"\n  ⚠️  {self.stats['failed']} erreurs rencontrées :")
            for i, error in enumerate(self.stats['errors'][:10], 1):
                logger.info(f"    {i}. {error}")
            if len(self.stats['errors']) > 10:
                logger.info(f"    ... et {len(self.stats['errors']) - 10} autres")
        
        logger.info("=" * 70)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def build_graphs_from_csv(
    csv_path: str,
    db_path: str = "recipe_graphs.db",
    batch_size: int = 10000,
    limit: Optional[int] = None
) -> Dict:
    """
    Construit les graphes depuis un fichier CSV.
    
    Args:
        csv_path: Chemin vers le fichier CSV
        db_path: Chemin vers la base de données
        batch_size: Taille des batchs
        limit: Limiter au N premières recettes
        
    Returns:
        Statistiques de traitement
    """
    logger.info(f"📂 Chargement du CSV : {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Convertir la colonne actions si nécessaire
    if df['actions'].dtype == object and isinstance(df['actions'].iloc[0], str):
        import ast
        logger.info("  ⚙️  Conversion de la colonne 'actions' (str → list)")
        df['actions'] = df['actions'].apply(ast.literal_eval)
    
    pipeline = RecipeGraphPipeline(df, db_path, batch_size)
    return pipeline.run(limit=limit)


def build_graphs_from_dataframe(
    df: pd.DataFrame,
    db_path: str = "recipe_graphs.db",
    batch_size: int = 10000,
    limit: Optional[int] = None
) -> Dict:
    """
    Construit les graphes depuis un DataFrame pandas.
    
    Args:
        df: DataFrame avec colonnes ['id', 'title', 'actions', 'type_2']
        db_path: Chemin vers la base de données
        batch_size: Taille des batchs
        limit: Limiter au N premières recettes
        
    Returns:
        Statistiques de traitement
    """
    pipeline = RecipeGraphPipeline(df, db_path, batch_size)
    return pipeline.run(limit=limit)


