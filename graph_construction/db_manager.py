"""
MODULE : db_manager.py
======================
Gestion de la base de données SQLite pour stocker et récupérer les graphes de recettes.

Auteur: Laboratoire Liara, UQAC
Date: 2026-01-26
"""

import sqlite3
import json
import networkx as nx
from typing import Optional, List, Dict, Tuple
from pathlib import Path
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphDatabase:
    """
    Gestionnaire de base de données SQLite pour les graphes de recettes.
    
    Structure de la base de données :
    - Table nodes : Stocke les nœuds de chaque graphe
    - Table edges : Stocke les arêtes de chaque graphe
    - Table metadata : Stocke les métadonnées de chaque recette
    
    Attributs:
        db_path (Path): Chemin vers le fichier de base de données
        conn (sqlite3.Connection): Connexion à la base de données
    """
    
    def __init__(self, db_path: str = "recipe_graphs.db"):
        """
        Initialise la connexion à la base de données.
        
        Args:
            db_path: Chemin vers le fichier de base de données SQLite
        """
        self.db_path = Path(db_path)
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self) -> None:
        """Établit la connexion à la base de données."""
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
            logger.info(f"✓ Connexion établie à {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"✗ Erreur de connexion à la base de données : {e}")
            raise
    
    def _create_tables(self) -> None:
        """Crée les tables si elles n'existent pas."""
        cursor = self.conn.cursor()
        
        # Table nodes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                recipe_id TEXT NOT NULL,
                action TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL,
                is_virtual INTEGER NOT NULL,
                PRIMARY KEY (recipe_id, action)
            )
        """)
        
        # Index sur recipe_id pour nodes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_recipe 
            ON nodes(recipe_id)
        """)
        
        # Table edges
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                recipe_id TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                weight INTEGER NOT NULL,
                PRIMARY KEY (recipe_id, source, target)
            )
        """)
        
        # Index sur recipe_id pour edges
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_edges_recipe 
            ON edges(recipe_id)
        """)
        
        # Table metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                recipe_id TEXT PRIMARY KEY,
                title TEXT,
                num_nodes INTEGER,
                num_edges INTEGER,
                num_variants INTEGER,
                has_cycles INTEGER,
                entry_points TEXT
            )
        """)
        
        self.conn.commit()
        logger.info("✓ Tables créées/vérifiées")
    
    def save_graph(self, recipe_id: str, graph: nx.DiGraph, metadata: Dict) -> None:
        """
        Sauvegarde un graphe dans la base de données.
        
        Args:
            recipe_id: Identifiant unique de la recette
            graph: Graphe NetworkX à sauvegarder
            metadata: Métadonnées du graphe
            
        Raises:
            ValueError: Si le graphe ou les métadonnées sont invalides
            sqlite3.Error: En cas d'erreur de base de données
        """
        if not recipe_id:
            raise ValueError("recipe_id ne peut pas être vide")
        
        if graph is None or graph.number_of_nodes() == 0:
            raise ValueError(f"Graphe vide pour recipe_id {recipe_id}")
        
        cursor = self.conn.cursor()
        
        try:
            # Supprimer les anciennes données si elles existent
            self.delete_graph(recipe_id)
            
            # Sauvegarder les nœuds
            nodes_data = []
            for node, attrs in graph.nodes(data=True):
                nodes_data.append((
                    recipe_id,
                    attrs.get('action', node),
                    attrs.get('occurrence_count', 0),
                    1 if attrs.get('is_virtual', False) else 0
                ))
            
            cursor.executemany("""
                INSERT INTO nodes (recipe_id, action, occurrence_count, is_virtual)
                VALUES (?, ?, ?, ?)
            """, nodes_data)
            
            # Sauvegarder les arêtes
            edges_data = []
            for source, target, attrs in graph.edges(data=True):
                edges_data.append((
                    recipe_id,
                    source,
                    target,
                    attrs.get('weight', 1)
                ))
            
            cursor.executemany("""
                INSERT INTO edges (recipe_id, source, target, weight)
                VALUES (?, ?, ?, ?)
            """, edges_data)
            
            # Sauvegarder les métadonnées
            entry_points_json = json.dumps(metadata.get('entry_points', []))
            
            cursor.execute("""
                INSERT INTO metadata (
                    recipe_id, title, num_nodes, num_edges, 
                    num_variants, has_cycles, entry_points
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                recipe_id,
                metadata.get('title', ''),
                metadata.get('num_nodes', 0),
                metadata.get('num_edges', 0),
                metadata.get('num_variants', 0),
                1 if metadata.get('has_cycles', False) else 0,
                entry_points_json
            ))
            
            self.conn.commit()
            logger.info(f"✓ Graphe sauvegardé : {recipe_id} ({graph.number_of_nodes()} nœuds, {graph.number_of_edges()} arêtes)")
            
        except sqlite3.Error as e:
            self.conn.rollback()
            logger.error(f"✗ Erreur lors de la sauvegarde de {recipe_id} : {e}")
            raise
    
    def load_graph(self, recipe_id: str) -> Optional[nx.DiGraph]:
        """
        Charge un graphe depuis la base de données.
        
        Args:
            recipe_id: Identifiant de la recette à charger
            
        Returns:
            Graphe NetworkX ou None si non trouvé
        """
        cursor = self.conn.cursor()
        
        # Vérifier si la recette existe
        cursor.execute("""
            SELECT COUNT(*) FROM metadata WHERE recipe_id = ?
        """, (recipe_id,))
        
        if cursor.fetchone()[0] == 0:
            logger.warning(f"✗ Recette {recipe_id} non trouvée")
            return None
        
        # Créer le graphe
        graph = nx.DiGraph()
        
        # Charger les nœuds
        cursor.execute("""
            SELECT action, occurrence_count, is_virtual
            FROM nodes
            WHERE recipe_id = ?
        """, (recipe_id,))
        
        for row in cursor.fetchall():
            graph.add_node(
                row['action'],
                action=row['action'],
                occurrence_count=row['occurrence_count'],
                is_virtual=bool(row['is_virtual'])
            )
        
        # Charger les arêtes
        cursor.execute("""
            SELECT source, target, weight
            FROM edges
            WHERE recipe_id = ?
        """, (recipe_id,))
        
        for row in cursor.fetchall():
            graph.add_edge(
                row['source'],
                row['target'],
                weight=row['weight']
            )
        
        logger.info(f"✓ Graphe chargé : {recipe_id} ({graph.number_of_nodes()} nœuds, {graph.number_of_edges()} arêtes)")
        return graph
    
    def load_metadata(self, recipe_id: str) -> Optional[Dict]:
        """
        Charge les métadonnées d'une recette.
        
        Args:
            recipe_id: Identifiant de la recette
            
        Returns:
            Dictionnaire de métadonnées ou None si non trouvé
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM metadata WHERE recipe_id = ?
        """, (recipe_id,))
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        metadata = {
            'recipe_id': row['recipe_id'],
            'title': row['title'],
            'num_nodes': row['num_nodes'],
            'num_edges': row['num_edges'],
            'num_variants': row['num_variants'],
            'has_cycles': bool(row['has_cycles']),
            'entry_points': json.loads(row['entry_points'])
        }
        
        return metadata
    
    def delete_graph(self, recipe_id: str) -> bool:
        """
        Supprime un graphe de la base de données.
        
        Args:
            recipe_id: Identifiant de la recette à supprimer
            
        Returns:
            True si supprimé, False si non trouvé
        """
        cursor = self.conn.cursor()
        
        # Vérifier si existe
        cursor.execute("""
            SELECT COUNT(*) FROM metadata WHERE recipe_id = ?
        """, (recipe_id,))
        
        if cursor.fetchone()[0] == 0:
            return False
        
        # Supprimer des trois tables
        cursor.execute("DELETE FROM nodes WHERE recipe_id = ?", (recipe_id,))
        cursor.execute("DELETE FROM edges WHERE recipe_id = ?", (recipe_id,))
        cursor.execute("DELETE FROM metadata WHERE recipe_id = ?", (recipe_id,))
        
        self.conn.commit()
        logger.info(f"✓ Graphe supprimé : {recipe_id}")
        return True
    
    def list_all_recipes(self) -> List[str]:
        """
        Liste tous les recipe_id dans la base de données.
        
        Returns:
            Liste des identifiants de recettes
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT recipe_id FROM metadata ORDER BY recipe_id")
        return [row['recipe_id'] for row in cursor.fetchall()]
    
    def count_recipes(self) -> int:
        """
        Compte le nombre total de recettes.
        
        Returns:
            Nombre de recettes
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM metadata")
        return cursor.fetchone()[0]
    
    def get_statistics(self) -> Dict:
        """
        Calcule des statistiques globales sur la base de données.
        
        Returns:
            Dictionnaire de statistiques
        """
        cursor = self.conn.cursor()
        
        # Nombre total de recettes
        cursor.execute("SELECT COUNT(*) FROM metadata")
        total_recipes = cursor.fetchone()[0]
        
        # Statistiques sur les nœuds
        cursor.execute("""
            SELECT 
                COUNT(*) as total_nodes,
                AVG(num_nodes) as avg_nodes_per_recipe,
                MIN(num_nodes) as min_nodes,
                MAX(num_nodes) as max_nodes
            FROM metadata
        """)
        node_stats = cursor.fetchone()
        
        # Statistiques sur les arêtes
        cursor.execute("""
            SELECT 
                AVG(num_edges) as avg_edges_per_recipe,
                MIN(num_edges) as min_edges,
                MAX(num_edges) as max_edges
            FROM metadata
        """)
        edge_stats = cursor.fetchone()
        
        # Statistiques sur les variantes
        cursor.execute("""
            SELECT 
                AVG(num_variants) as avg_variants_per_recipe,
                MIN(num_variants) as min_variants,
                MAX(num_variants) as max_variants
            FROM metadata
        """)
        variant_stats = cursor.fetchone()
        
        # Nombre de recettes avec cycles
        cursor.execute("SELECT COUNT(*) FROM metadata WHERE has_cycles = 1")
        recipes_with_cycles = cursor.fetchone()[0]
        
        stats = {
            'total_recipes': total_recipes,
            'avg_nodes_per_recipe': float(node_stats['avg_nodes_per_recipe']) if node_stats['avg_nodes_per_recipe'] else 0,
            'min_nodes': node_stats['min_nodes'],
            'max_nodes': node_stats['max_nodes'],
            'avg_edges_per_recipe': float(edge_stats['avg_edges_per_recipe']) if edge_stats['avg_edges_per_recipe'] else 0,
            'min_edges': edge_stats['min_edges'],
            'max_edges': edge_stats['max_edges'],
            'avg_variants_per_recipe': float(variant_stats['avg_variants_per_recipe']) if variant_stats['avg_variants_per_recipe'] else 0,
            'min_variants': variant_stats['min_variants'],
            'max_variants': variant_stats['max_variants'],
            'recipes_with_cycles': recipes_with_cycles,
            'recipes_with_cycles_percent': (recipes_with_cycles / total_recipes * 100) if total_recipes > 0 else 0,
        }
        
        return stats
    
    def search_by_action(self, action: str) -> List[str]:
        """
        Recherche les recettes contenant une action spécifique.
        
        Args:
            action: Nom de l'action à rechercher
            
        Returns:
            Liste des recipe_id contenant cette action
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT recipe_id 
            FROM nodes 
            WHERE action = ? AND is_virtual = 0
            ORDER BY recipe_id
        """, (action,))
        
        return [row['recipe_id'] for row in cursor.fetchall()]
    
    def search_by_transition(self, source: str, target: str) -> List[str]:
        """
        Recherche les recettes contenant une transition spécifique.
        
        Args:
            source: Action source
            target: Action cible
            
        Returns:
            Liste des recipe_id contenant cette transition
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT recipe_id 
            FROM edges 
            WHERE source = ? AND target = ?
            ORDER BY recipe_id
        """, (source, target))
        
        return [row['recipe_id'] for row in cursor.fetchall()]
    
    def close(self) -> None:
        """Ferme la connexion à la base de données."""
        if self.conn:
            self.conn.close()
            logger.info("✓ Connexion fermée")
    
    def __enter__(self):
        """Support du context manager (with statement)."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme la connexion lors de la sortie du context."""
        self.close()
    
    def __repr__(self) -> str:
        """Représentation textuelle du gestionnaire."""
        count = self.count_recipes()
        return f"GraphDatabase(db_path='{self.db_path}', recipes={count})"


