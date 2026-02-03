# apps/reportes/exporters/charts.py

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
import numpy as np


class ChartGenerator:
    """Generador de gráficas para reportes PDF"""
    
    COLORS = {
        'primary': '#1F4788',
        'success': '#10B981',
        'warning': '#F59E0B',
        'danger': '#EF4444',
        'info': '#3B82F6',
        'gray': '#6B7280',
    }
    
    GAP_COLORS = {
        'critico': '#DC2626',
        'alto': '#F59E0B',
        'medio': '#FBBF24',
        'bajo': '#A3E635',
        'cumplido': '#10B981',
        'superado': '#059669',
    }
    
    @staticmethod
    def _setup_plot_style():
        """Configura el estilo general de las gráficas"""
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.size'] = 10
        plt.rcParams['axes.labelsize'] = 11
        plt.rcParams['axes.titlesize'] = 13
        plt.rcParams['axes.titleweight'] = 'bold'
        plt.rcParams['xtick.labelsize'] = 9
        plt.rcParams['ytick.labelsize'] = 9
        plt.rcParams['legend.fontsize'] = 9
        plt.rcParams['figure.titlesize'] = 14
    
    @staticmethod
    def grafica_barras_gap(dimensiones_data, width=16, height=10):
        """
        Gráfica de barras MEJORADA - Proporciones correctas
        """
        ChartGenerator._setup_plot_style()
        
        labels = [d['dimension'].codigo for d in dimensiones_data]
        # ⭐ CORREGIDO: Convertir Decimal a float
        gaps = [float(d['gap_avg']) for d in dimensiones_data]
        
        # Colores según el GAP
        colors = []
        for gap in gaps:
            if gap >= 2.5:
                colors.append(ChartGenerator.GAP_COLORS['critico'])
            elif gap >= 2.0:
                colors.append(ChartGenerator.GAP_COLORS['alto'])
            elif gap >= 1.0:
                colors.append(ChartGenerator.GAP_COLORS['medio'])
            elif gap > 0:
                colors.append(ChartGenerator.GAP_COLORS['bajo'])
            else:
                colors.append(ChartGenerator.GAP_COLORS['cumplido'])
        
        # ⭐ MEJORADO: Figura con proporciones adecuadas
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54), dpi=100)
        
        # Crear barras con ancho adecuado
        x_pos = np.arange(len(labels))
        bars = ax.bar(x_pos, gaps, color=colors, edgecolor='white', 
                    linewidth=2, width=0.7, alpha=0.9)
        
        # Valores sobre las barras
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., h + 0.1,
                    f'{h:.2f}',
                    ha='center', va='bottom',
                    fontsize=9, fontweight='bold')
        
        # Configurar ejes con límites adecuados
        ax.set_xlabel('Dimensiones CMMI', fontweight='bold', fontsize=11)
        ax.set_ylabel('Nivel de Brecha (GAP)', fontweight='bold', fontsize=11)
        ax.set_title('Análisis de Brechas por Dimensión', 
                    fontweight='bold', fontsize=13, pad=15)
        
        # ⭐ CORREGIDO: Asegurar que max_gap sea float
        max_gap = float(max(gaps)) if gaps else 3.0
        ax.set_ylim(0, max_gap + 0.5)
        
        # Grid suave
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.7)
        ax.set_axisbelow(True)
        
        # Etiquetas en X
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, rotation=0 if len(labels) <= 5 else 45, 
                        ha='right' if len(labels) > 5 else 'center')
        
        # Leyenda de colores
        legend_elements = [
            mpatches.Patch(color=ChartGenerator.GAP_COLORS['critico'], label='Crítico (≥2.5)'),
            mpatches.Patch(color=ChartGenerator.GAP_COLORS['alto'], label='Alto (2.0-2.5)'),
            mpatches.Patch(color=ChartGenerator.GAP_COLORS['medio'], label='Medio (1.0-2.0)'),
            mpatches.Patch(color=ChartGenerator.GAP_COLORS['bajo'], label='Bajo (<1.0)'),
            mpatches.Patch(color=ChartGenerator.GAP_COLORS['cumplido'], label='Cumplido'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=8, framealpha=0.9)
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_barras_horizontales_usuarios(usuarios_data, width=16, height=10):
        """
        ⭐ NUEVA: Gráfica de barras horizontales para usuarios
        """
        ChartGenerator._setup_plot_style()
        
        # Tomar top 10 usuarios
        usuarios_sorted = sorted(usuarios_data, key=lambda x: x['gap_avg'], reverse=True)[:10]
        
        nombres = [u['usuario'].nombre_completo[:20] for u in usuarios_sorted]
        gaps = [u['gap_avg'] for u in usuarios_sorted]
        
        # Colores
        colors = []
        for gap in gaps:
            if gap >= 2.0:
                colors.append(ChartGenerator.GAP_COLORS['alto'])
            elif gap >= 1.0:
                colors.append(ChartGenerator.GAP_COLORS['medio'])
            else:
                colors.append(ChartGenerator.GAP_COLORS['bajo'])
        
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54))
        
        y_pos = np.arange(len(nombres))
        bars = ax.barh(y_pos, gaps, color=colors, edgecolor='white', 
                       linewidth=1.5, alpha=0.85)
        
        # Valores al final de las barras
        for i, bar in enumerate(bars):
            w = bar.get_width()
            ax.text(w + 0.05, bar.get_y() + bar.get_height()/2.,
                    f'{w:.2f}',
                    ha='left', va='center',
                    fontsize=9, fontweight='bold')
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(nombres, fontsize=9)
        ax.set_xlabel('GAP Promedio', fontweight='bold', fontsize=11)
        ax.set_title('Top 10 Usuarios con Mayor Brecha', 
                     fontweight='bold', fontsize=13, pad=15)
        
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_lineas_cumplimiento(dimensiones_data, width=16, height=9):
        """
        ⭐ NUEVA: Gráfica de líneas para % cumplimiento por dimensión
        """
        ChartGenerator._setup_plot_style()
        
        # Ordenar por código de dimensión
        dims_sorted = sorted(dimensiones_data, key=lambda x: x['dimension'].codigo)
        
        labels = [d['dimension'].codigo for d in dims_sorted]
        cumplimiento = [d['cumplimiento_avg'] for d in dims_sorted]
        
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54))
        
        # Línea principal
        ax.plot(labels, cumplimiento, marker='o', linewidth=2.5, 
                markersize=8, color='#1F4788', label='% Cumplimiento')
        
        # Línea de referencia al 100%
        ax.axhline(y=100, color='#10B981', linestyle='--', 
                   linewidth=1.5, alpha=0.7, label='Meta 100%')
        
        # Línea de referencia al 75%
        ax.axhline(y=75, color='#F59E0B', linestyle='--', 
                   linewidth=1.5, alpha=0.7, label='Umbral Aceptable 75%')
        
        # Valores sobre los puntos
        for i, (label, val) in enumerate(zip(labels, cumplimiento)):
            ax.text(i, val + 3, f'{val:.1f}%',
                    ha='center', va='bottom',
                    fontsize=8, fontweight='bold')
        
        ax.set_xlabel('Dimensiones', fontweight='bold', fontsize=11)
        ax.set_ylabel('Porcentaje de Cumplimiento (%)', fontweight='bold', fontsize=11)
        ax.set_title('Nivel de Cumplimiento por Dimensión', 
                     fontweight='bold', fontsize=13, pad=15)
        
        ax.set_ylim(0, 110)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        ax.legend(loc='lower right', fontsize=9)
        
        if len(labels) > 5:
            plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_donut_distribucion(clasificaciones, width=12, height=11):
        """
        ⭐ NUEVA: Gráfica de donut (pastel con hueco) para clasificaciones
        """
        ChartGenerator._setup_plot_style()
        
        labels_map = {
            'critico': 'Crítico',
            'alto': 'Alto',
            'medio': 'Medio',
            'bajo': 'Bajo',
            'cumplido': 'Cumplido',
            'superado': 'Superado',
        }
        
        data = []
        labels = []
        colors = []
        
        for key in ['critico', 'alto', 'medio', 'bajo', 'cumplido', 'superado']:
            count = clasificaciones.get(key, 0)
            if count > 0:
                data.append(count)
                labels.append(labels_map[key])
                colors.append(ChartGenerator.GAP_COLORS[key])
        
        if not data:
            data = [1]
            labels = ['Sin datos']
            colors = ['#E5E7EB']
        
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54))
        
        # Crear donut (wedgeprops crea el hueco central)
        wedges, texts, autotexts = ax.pie(
            data,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            pctdistance=0.85,
            explode=[0.05] * len(data),
            wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2),
            textprops={'fontsize': 10, 'weight': 'bold'}
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(9)
            autotext.set_weight('bold')
        
        # Texto en el centro
        total = sum(data)
        ax.text(0, 0, f'{total}\nEvaluaciones', 
                ha='center', va='center',
                fontsize=14, fontweight='bold',
                color='#1F4788')
        
        ax.set_title('Distribución de Clasificaciones', 
                     fontweight='bold', fontsize=13, pad=20)
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_pastel_clasificacion(clasificaciones, width=12, height=10):
        """Gráfica de pastel para clasificaciones GAP"""
        ChartGenerator._setup_plot_style()
        
        labels_map = {
            'critico': 'Crítico',
            'alto': 'Alto',
            'medio': 'Medio',
            'bajo': 'Bajo',
            'cumplido': 'Cumplido',
            'superado': 'Superado',
        }
        
        data = []
        labels = []
        colors = []
        
        for key in ['critico', 'alto', 'medio', 'bajo', 'cumplido', 'superado']:
            count = clasificaciones.get(key, 0)
            if count > 0:
                data.append(count)
                labels.append(labels_map[key])
                colors.append(ChartGenerator.GAP_COLORS[key])
        
        if not data:
            data = [1]
            labels = ['Sin datos']
            colors = ['#E5E7EB']
        
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54))
        
        wedges, texts, autotexts = ax.pie(
            data,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            pctdistance=0.85,
            explode=[0.05] * len(data),
            shadow=True,
            textprops={'fontsize': 10, 'weight': 'bold'}
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(9)
            autotext.set_weight('bold')
        
        ax.set_title('Distribución de Clasificaciones', 
                     fontweight='bold', fontsize=13, pad=20)
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_pastel_respuestas(distribucion, width=12, height=10):
        """Gráfica de pastel para distribución de respuestas"""
        ChartGenerator._setup_plot_style()
        
        data = [
            distribucion.get('si_cumple', 0),
            distribucion.get('cumple_parcial', 0),
            distribucion.get('no_cumple', 0),
            distribucion.get('no_aplica', 0),
        ]
        
        labels = ['Sí Cumple', 'Cumple Parcial', 'No Cumple', 'No Aplica']
        colors = ['#10B981', '#FBBF24', '#EF4444', '#9CA3AF']
        
        data_filtered = []
        labels_filtered = []
        colors_filtered = []
        
        for i, val in enumerate(data):
            if val > 0:
                data_filtered.append(val)
                labels_filtered.append(labels[i])
                colors_filtered.append(colors[i])
        
        if not data_filtered:
            data_filtered = [1]
            labels_filtered = ['Sin respuestas']
            colors_filtered = ['#E5E7EB']
        
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54))
        
        wedges, texts, autotexts = ax.pie(
            data_filtered,
            labels=labels_filtered,
            colors=colors_filtered,
            autopct='%1.1f%%',
            startangle=90,
            pctdistance=0.85,
            explode=[0.05] * len(data_filtered),
            shadow=True,
            textprops={'fontsize': 10, 'weight': 'bold'}
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(9)
            autotext.set_weight('bold')
        
        ax.set_title('Distribución de Respuestas', 
                     fontweight='bold', fontsize=13, pad=20)
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_radar_dimensiones(dimensiones_data, width=13, height=13):
        """Gráfica radar para comparación de dimensiones"""
        ChartGenerator._setup_plot_style()
        
        labels = [d['dimension'].codigo for d in dimensiones_data]
        nivel_actual = [d['nivel_actual_avg'] for d in dimensiones_data]
        nivel_deseado = [d['nivel_deseado'] for d in dimensiones_data]
        
        num_vars = len(labels)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        
        nivel_actual += nivel_actual[:1]
        nivel_deseado += nivel_deseado[:1]
        angles += angles[:1]
        
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54), 
                              subplot_kw=dict(projection='polar'))
        
        # Nivel deseado
        ax.plot(angles, nivel_deseado, 'o-', linewidth=2.5, 
                label='Nivel Deseado', color='#3B82F6', markersize=6)
        ax.fill(angles, nivel_deseado, alpha=0.15, color='#3B82F6')
        
        # Nivel actual
        ax.plot(angles, nivel_actual, 'o-', linewidth=2.5, 
                label='Nivel Actual', color='#10B981', markersize=6)
        ax.fill(angles, nivel_actual, alpha=0.25, color='#10B981')
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=10)
        
        ax.set_ylim(0, 5)
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.set_yticklabels(['1', '2', '3', '4', '5'], fontsize=9)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        ax.set_title('Comparación de Niveles de Madurez', 
                     fontweight='bold', fontsize=13, pad=20, y=1.08)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)