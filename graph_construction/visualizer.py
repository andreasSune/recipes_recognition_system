"""
MODULE : visualizer.py
======================
Visualisation des graphes de recettes avec matplotlib et plotly.

Auteur: Laboratoire Liara, UQAC
Date: 2026-01-26
"""

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Optional, Dict, List, Tuple
import numpy as np
from pathlib import Path
import logging

# Import conditionnel de plotly
try:
    import plotly.graph_objects as go
    from plotly.graph_objects import Figure as PlotlyFigure
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    PlotlyFigure = type(None)  # Type dummy pour éviter erreurs
    logging.warning("Plotly non installé. Visualisation interactive désactivée.")

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecipeGraphVisualizer:
    """
    Visualisateur de graphes de recettes.
    
    Supporte deux modes :
    - Matplotlib (statique) : PNG, SVG
    - Plotly (interactif) : HTML
    
    Attributs:
        graph (nx.DiGraph): Graphe à visualiser
        recipe_id (str): Identifiant de la recette
        metadata (dict): Métadonnées du graphe
    """
    
    # Palette de couleurs
    COLORS = {
        'start': '#2ecc71',        # Vert pour START
        'action': '#3498db',       # Bleu pour actions normales
        'high_freq': '#e74c3c',    # Rouge pour actions très fréquentes
        'edge': '#95a5a6',         # Gris pour arêtes normales
        'edge_strong': '#2c3e50',  # Noir pour arêtes fortes
    }
    
    def __init__(self, graph: nx.DiGraph, recipe_id: str = "", metadata: Optional[Dict] = None):
        """
        Initialise le visualisateur.
        
        Args:
            graph: Graphe NetworkX à visualiser
            recipe_id: Identifiant de la recette
            metadata: Métadonnées optionnelles
        """
        self.graph = graph
        self.recipe_id = recipe_id
        self.metadata = metadata or {}
        
        if graph.number_of_nodes() == 0:
            raise ValueError("Le graphe est vide, impossible de visualiser")
    
    def visualize_matplotlib(
        self,
        figsize: Tuple[int, int] = (16, 12),
        layout: str = 'spring',
        show_weights: bool = True,
        node_size_scale: float = 500,
        save_path: Optional[str] = None,
        show: bool = True
    ) -> plt.Figure:
        """
        Visualise le graphe avec matplotlib (statique).
        
        Args:
            figsize: Taille de la figure (largeur, hauteur)
            layout: Type de layout ('spring', 'kamada_kawai', 'circular', 'hierarchical')
            show_weights: Afficher les poids sur les arêtes
            node_size_scale: Facteur d'échelle pour la taille des nœuds
            save_path: Chemin pour sauvegarder l'image (None = pas de sauvegarde)
            show: Afficher la figure
            
        Returns:
            Figure matplotlib
        """
        # Créer la figure
        fig, ax = plt.subplots(figsize=figsize)
        
        # Calculer le layout
        pos = self._get_layout(layout)
        
        # Préparer les propriétés des nœuds
        node_colors = []
        node_sizes = []
        
        for node in self.graph.nodes():
            attrs = self.graph.nodes[node]
            
            # Couleur
            if attrs.get('is_virtual', False):
                node_colors.append(self.COLORS['start'])
            elif attrs.get('occurrence_count', 0) > 5:
                node_colors.append(self.COLORS['high_freq'])
            else:
                node_colors.append(self.COLORS['action'])
            
            # Taille (proportionnelle à occurrence_count)
            count = attrs.get('occurrence_count', 1)
            if attrs.get('is_virtual', False):
                node_sizes.append(node_size_scale * 2)  # START plus grand
            else:
                node_sizes.append(node_size_scale * (1 + count * 0.3))
        
        # Dessiner les nœuds
        nx.draw_networkx_nodes(
            self.graph,
            pos,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.9,
            ax=ax
        )
        
        # Dessiner les labels des nœuds
        labels = {node: node for node in self.graph.nodes()}
        nx.draw_networkx_labels(
            self.graph,
            pos,
            labels,
            font_size=10,
            font_weight='bold',
            ax=ax
        )
        
        # Préparer les propriétés des arêtes
        edge_widths = []
        edge_colors = []
        
        for u, v in self.graph.edges():
            weight = self.graph[u][v].get('weight', 1)
            edge_widths.append(0.5 + weight * 0.5)
            
            if weight > 3:
                edge_colors.append(self.COLORS['edge_strong'])
            else:
                edge_colors.append(self.COLORS['edge'])
        
        # Dessiner les arêtes
        nx.draw_networkx_edges(
            self.graph,
            pos,
            width=edge_widths,
            edge_color=edge_colors,
            alpha=0.6,
            arrows=True,
            arrowsize=20,
            arrowstyle='->',
            connectionstyle='arc3,rad=0.1',
            ax=ax
        )
        
        # Afficher les poids sur les arêtes si demandé
        if show_weights:
            edge_labels = {
                (u, v): f"{self.graph[u][v]['weight']}"
                for u, v in self.graph.edges()
            }
            nx.draw_networkx_edge_labels(
                self.graph,
                pos,
                edge_labels,
                font_size=8,
                font_color='red',
                ax=ax
            )
        
        # Titre et informations
        title = f"Graphe de recette : {self.recipe_id}"
        if self.metadata.get('title'):
            title += f"\n{self.metadata['title']}"
        
        info = (
            f"Nœuds: {self.graph.number_of_nodes()} | "
            f"Arêtes: {self.graph.number_of_edges()} | "
            f"Variantes: {self.metadata.get('num_variants', '?')} | "
            f"Cycles: {'Oui' if self.metadata.get('has_cycles', False) else 'Non'}"
        )
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.text(
            0.5, -0.05, info,
            transform=ax.transAxes,
            ha='center',
            fontsize=10,
            style='italic'
        )
        
        # Légende
        legend_elements = [
            mpatches.Patch(color=self.COLORS['start'], label='Nœud START'),
            mpatches.Patch(color=self.COLORS['action'], label='Action normale'),
            mpatches.Patch(color=self.COLORS['high_freq'], label='Action fréquente (>5)'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        ax.axis('off')
        plt.tight_layout()
        
        # Sauvegarder si demandé
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"✓ Figure sauvegardée : {save_path}")
        
        # Afficher si demandé
        if show:
            plt.show()
        
        return fig
    
    def visualize_plotly(
        self,
        layout: str = 'spring',
        save_path: Optional[str] = None,
        show: bool = True
    ):
        """
        Visualise le graphe avec plotly (interactif).
        
        Args:
            layout: Type de layout ('spring', 'kamada_kawai', 'circular')
            save_path: Chemin pour sauvegarder en HTML (None = pas de sauvegarde)
            show: Afficher la figure dans le navigateur
            
        Returns:
            Figure plotly ou None si plotly non installé
        """
        if not HAS_PLOTLY:
            logger.error("✗ Plotly non installé. Installez avec: pip install plotly")
            return None
        
        # Calculer le layout
        pos = self._get_layout(layout)
        
        # Préparer les données des arêtes
        edge_x = []
        edge_y = []
        edge_traces = []
        
        for edge in self.graph.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            
            weight = self.graph[edge[0]][edge[1]].get('weight', 1)
            
            edge_trace = go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(
                    width=0.5 + weight * 0.5,
                    color=self.COLORS['edge_strong'] if weight > 3 else self.COLORS['edge']
                ),
                hoverinfo='text',
                text=f"{edge[0]} → {edge[1]}<br>Poids: {weight}",
                showlegend=False
            )
            edge_traces.append(edge_trace)
        
        # Préparer les données des nœuds
        node_x = []
        node_y = []
        node_colors = []
        node_sizes = []
        node_text = []
        node_hover = []
        
        for node in self.graph.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            attrs = self.graph.nodes[node]
            count = attrs.get('occurrence_count', 1)
            
            # Couleur
            if attrs.get('is_virtual', False):
                node_colors.append(self.COLORS['start'])
                node_sizes.append(30)
            elif count > 5:
                node_colors.append(self.COLORS['high_freq'])
                node_sizes.append(15 + count * 2)
            else:
                node_colors.append(self.COLORS['action'])
                node_sizes.append(15 + count * 2)
            
            # Texte
            node_text.append(node)
            
            # Hover info
            hover_info = f"<b>{node}</b><br>"
            hover_info += f"Occurrences: {count}<br>"
            hover_info += f"Degré entrant: {self.graph.in_degree(node)}<br>"
            hover_info += f"Degré sortant: {self.graph.out_degree(node)}"
            node_hover.append(hover_info)
        
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=2, color='white')
            ),
            text=node_text,
            textposition="top center",
            textfont=dict(size=10, color='black'),
            hoverinfo='text',
            hovertext=node_hover,
            showlegend=False
        )
        
        # Créer la figure
        fig = go.Figure(data=edge_traces + [node_trace])
        
        # Mise en page
        title = f"Graphe de recette : {self.recipe_id}"
        if self.metadata.get('title'):
            title += f"<br><sub>{self.metadata['title']}</sub>"
        
        fig.update_layout(
            title=dict(text=title, x=0.5, xanchor='center'),
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=80),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='white',
            width=1200,
            height=800
        )
        
        # Annotations pour les statistiques
        info_text = (
            f"Nœuds: {self.graph.number_of_nodes()} | "
            f"Arêtes: {self.graph.number_of_edges()} | "
            f"Variantes: {self.metadata.get('num_variants', '?')} | "
            f"Cycles: {'Oui' if self.metadata.get('has_cycles', False) else 'Non'}"
        )
        
        fig.add_annotation(
            text=info_text,
            xref="paper", yref="paper",
            x=0.5, y=-0.05,
            showarrow=False,
            font=dict(size=12, color="gray")
        )
        
        # Sauvegarder si demandé
        if save_path:
            fig.write_html(save_path)
            logger.info(f"✓ Figure interactive sauvegardée : {save_path}")
        
        # Afficher si demandé
        if show:
            fig.show()
        
        return fig
    
    def _get_layout(self, layout_type: str) -> Dict:
        """
        Calcule le layout des nœuds.
        
        Args:
            layout_type: Type de layout
            
        Returns:
            Dictionnaire {node: (x, y)}
        """
        if layout_type == 'spring':
            return nx.spring_layout(self.graph, seed=42, k=1, iterations=50)
        elif layout_type == 'kamada_kawai':
            return nx.kamada_kawai_layout(self.graph)
        elif layout_type == 'circular':
            return nx.circular_layout(self.graph)
        elif layout_type == 'hierarchical':
            return self._hierarchical_layout()
        else:
            logger.warning(f"Layout '{layout_type}' inconnu, utilisation de 'spring'")
            return nx.spring_layout(self.graph, seed=42)
    
    def _hierarchical_layout(self) -> Dict:
        """
        Crée un layout hiérarchique depuis START.
        
        Returns:
            Dictionnaire {node: (x, y)}
        """
        pos = {}
        
        # Calculer les niveaux depuis START
        if 'START' not in self.graph:
            return nx.spring_layout(self.graph, seed=42)
        
        # BFS depuis START pour déterminer les niveaux
        levels = {node: -1 for node in self.graph.nodes()}
        levels['START'] = 0
        
        queue = ['START']
        visited = {'START'}
        
        while queue:
            current = queue.pop(0)
            current_level = levels[current]
            
            for neighbor in self.graph.successors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    levels[neighbor] = current_level + 1
                    queue.append(neighbor)
        
        # Organiser les nœuds par niveau
        nodes_by_level = {}
        for node, level in levels.items():
            if level == -1:
                level = max(levels.values()) + 1  # Nœuds non accessibles à la fin
            if level not in nodes_by_level:
                nodes_by_level[level] = []
            nodes_by_level[level].append(node)
        
        # Positionner les nœuds
        max_level = max(nodes_by_level.keys())
        
        for level, nodes in nodes_by_level.items():
            y = 1.0 - (level / max_level)  # De haut en bas
            num_nodes = len(nodes)
            
            for i, node in enumerate(nodes):
                if num_nodes == 1:
                    x = 0.5
                else:
                    x = i / (num_nodes - 1)
                pos[node] = (x, y)
        
        return pos
    
    def compare_with(
        self,
        other_graph: nx.DiGraph,
        other_id: str = "",
        save_path: Optional[str] = None,
        show: bool = True
    ) -> plt.Figure:
        """
        Compare ce graphe avec un autre (matplotlib).
        
        Args:
            other_graph: Autre graphe à comparer
            other_id: Identifiant de l'autre recette
            save_path: Chemin pour sauvegarder
            show: Afficher la figure
            
        Returns:
            Figure matplotlib
        """
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        
        # Graphe 1
        ax1 = axes[0]
        pos1 = nx.spring_layout(self.graph, seed=42)
        nx.draw(
            self.graph,
            pos1,
            ax=ax1,
            with_labels=True,
            node_color=self.COLORS['action'],
            node_size=500,
            font_size=10,
            arrows=True
        )
        ax1.set_title(f"Recette 1: {self.recipe_id}\n({self.graph.number_of_nodes()} nœuds, {self.graph.number_of_edges()} arêtes)")
        ax1.axis('off')
        
        # Graphe 2
        ax2 = axes[1]
        pos2 = nx.spring_layout(other_graph, seed=42)
        nx.draw(
            other_graph,
            pos2,
            ax=ax2,
            with_labels=True,
            node_color=self.COLORS['high_freq'],
            node_size=500,
            font_size=10,
            arrows=True
        )
        ax2.set_title(f"Recette 2: {other_id}\n({other_graph.number_of_nodes()} nœuds, {other_graph.number_of_edges()} arêtes)")
        ax2.axis('off')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"✓ Comparaison sauvegardée : {save_path}")
        
        if show:
            plt.show()
        
        return fig


def visualize_graph(
    recipe_id: str,
    graph: Optional[nx.DiGraph] = None,
    db_path: Optional[str] = None,
    backend: str = 'matplotlib',
    **kwargs
):
    """
    Fonction utilitaire pour visualiser rapidement un graphe.
    
    Args:
        recipe_id: Identifiant de la recette
        graph: Graphe NetworkX (si None, charge depuis db_path)
        db_path: Chemin vers la base de données (si graph est None)
        backend: 'matplotlib' ou 'plotly'
        **kwargs: Arguments additionnels pour la visualisation
        
    Returns:
        Figure matplotlib ou plotly
    """
    # Charger le graphe si nécessaire
    if graph is None:
        if db_path is None:
            raise ValueError("graph ou db_path doit être fourni")
        
        from db_manager import GraphDatabase
        
        with GraphDatabase(db_path) as db:
            graph = db.load_graph(recipe_id)
            metadata = db.load_metadata(recipe_id)
        
        if graph is None:
            raise ValueError(f"Recette {recipe_id} non trouvée dans {db_path}")
    else:
        metadata = {}
    
    # Créer le visualisateur
    visualizer = RecipeGraphVisualizer(graph, recipe_id, metadata)
    
    # Visualiser selon le backend
    if backend == 'matplotlib':
        return visualizer.visualize_matplotlib(**kwargs)
    elif backend == 'plotly':
        return visualizer.visualize_plotly(**kwargs)
    else:
        raise ValueError(f"Backend inconnu: {backend}")


