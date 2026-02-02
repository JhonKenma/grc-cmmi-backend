# apps/reportes/exporters/charts.py (CREAR ARCHIVO NUEVO)

import matplotlib
matplotlib.use('Agg')  # ⭐ IMPORTANTE: Backend sin GUI

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage


class ChartGenerator:
    """Generador de gráficas para reportes PDF"""
    
    # Colores corporativos
    COLORS = {
        'primary': '#1F4788',
        'success': '#10B981',
        'warning': '#F59E0B',
        'danger': '#EF4444',
        'info': '#3B82F6',
        'gray': '#6B7280',
    }
    
    # Colores para clasificaciones GAP
    GAP_COLORS = {
        'critico': '#DC2626',    # Rojo oscuro
        'alto': '#F59E0B',       # Naranja
        'medio': '#FBBF24',      # Amarillo
        'bajo': '#A3E635',       # Verde claro
        'cumplido': '#10B981',   # Verde
        'superado': '#059669',   # Verde oscuro
    }
    
    @staticmethod
    def _setup_plot_style():
        """Configura el estilo general de las gráficas"""
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.size'] = 9
        plt.rcParams['axes.labelsize'] = 10
        plt.rcParams['axes.titlesize'] = 12
        plt.rcParams['axes.titleweight'] = 'bold'
        plt.rcParams['xtick.labelsize'] = 8
        plt.rcParams['ytick.labelsize'] = 8
        plt.rcParams['legend.fontsize'] = 8
        plt.rcParams['figure.titlesize'] = 14
    
    @staticmethod
    def grafica_barras_gap(dimensiones_data, width=15, height=8):
        """
        Genera gráfica de barras para GAP por dimensión
        
        Args:
            dimensiones_data: Lista de diccionarios con datos de dimensiones
            width: Ancho en cm
            height: Alto en cm
            
        Returns:
            RLImage para usar en ReportLab
        """
        ChartGenerator._setup_plot_style()
        
        # Preparar datos
        labels = [d['dimension'].codigo for d in dimensiones_data]
        gaps = [d['gap_avg'] for d in dimensiones_data]
        
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
        
        # Crear gráfica
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54))  # cm a pulgadas
        
        bars = ax.bar(labels, gaps, color=colors, edgecolor='white', linewidth=1.5)
        
        # Agregar valores sobre las barras
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}',
                ha='center', va='bottom',
                fontsize=8, fontweight='bold'
            )
        
        # Configurar ejes
        ax.set_xlabel('Dimensiones', fontweight='bold')
        ax.set_ylabel('Brecha (GAP)', fontweight='bold')
        ax.set_title('Análisis de Brechas por Dimensión', fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        # Rotar etiquetas si son muchas
        if len(labels) > 5:
            plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Convertir a imagen para ReportLab
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_pastel_clasificacion(clasificaciones, width=12, height=10):
        """
        Genera gráfica de pastel para clasificaciones GAP
        
        Args:
            clasificaciones: Dict con conteos de clasificaciones
            width: Ancho en cm
            height: Alto en cm
            
        Returns:
            RLImage para usar en ReportLab
        """
        ChartGenerator._setup_plot_style()
        
        # Preparar datos
        labels_map = {
            'critico': 'Crítico',
            'alto': 'Alto',
            'medio': 'Medio',
            'bajo': 'Bajo',
            'cumplido': 'Cumplido',
            'superado': 'Superado',
        }
        
        # Filtrar solo los que tienen valores > 0
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
        
        # Crear gráfica
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54))
        
        # Crear pastel con efecto 3D suave
        wedges, texts, autotexts = ax.pie(
            data,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            pctdistance=0.85,
            explode=[0.05] * len(data),  # Separar ligeramente las secciones
            shadow=True,
            textprops={'fontsize': 9, 'weight': 'bold'}
        )
        
        # Mejorar legibilidad de porcentajes
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(8)
            autotext.set_weight('bold')
        
        ax.set_title('Distribución de Clasificaciones GAP', fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        # Convertir a imagen
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_pastel_respuestas(distribucion, width=12, height=10):
        """
        Genera gráfica de pastel para distribución de respuestas
        
        Args:
            distribucion: Dict con distribución de respuestas
            width: Ancho en cm
            height: Alto en cm
            
        Returns:
            RLImage para usar en ReportLab
        """
        ChartGenerator._setup_plot_style()
        
        # Preparar datos
        data = [
            distribucion.get('si_cumple', 0),
            distribucion.get('cumple_parcial', 0),
            distribucion.get('no_cumple', 0),
            distribucion.get('no_aplica', 0),
        ]
        
        labels = ['Sí Cumple', 'Cumple Parcial', 'No Cumple', 'No Aplica']
        colors = ['#10B981', '#FBBF24', '#EF4444', '#9CA3AF']
        
        # Filtrar ceros
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
        
        # Crear gráfica
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
            textprops={'fontsize': 9, 'weight': 'bold'}
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(8)
            autotext.set_weight('bold')
        
        ax.set_title('Distribución de Respuestas', fontweight='bold', pad=20)
        
        plt.tight_layout()
        
        # Convertir a imagen
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)
    
    @staticmethod
    def grafica_radar_dimensiones(dimensiones_data, width=14, height=14):
        """
        Genera gráfica radar para comparación de dimensiones
        
        Args:
            dimensiones_data: Lista de diccionarios con datos de dimensiones
            width: Ancho en cm
            height: Alto en cm
            
        Returns:
            RLImage para usar en ReportLab
        """
        import numpy as np
        
        ChartGenerator._setup_plot_style()
        
        # Preparar datos
        labels = [d['dimension'].codigo for d in dimensiones_data]
        nivel_actual = [d['nivel_actual_avg'] for d in dimensiones_data]
        nivel_deseado = [d['nivel_deseado'] for d in dimensiones_data]
        
        # Número de variables
        num_vars = len(labels)
        
        # Ángulos para cada eje
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        
        # Cerrar el círculo
        nivel_actual += nivel_actual[:1]
        nivel_deseado += nivel_deseado[:1]
        angles += angles[:1]
        
        # Crear gráfica
        fig, ax = plt.subplots(figsize=(width/2.54, height/2.54), subplot_kw=dict(projection='polar'))
        
        # Plotear nivel deseado
        ax.plot(angles, nivel_deseado, 'o-', linewidth=2, label='Nivel Deseado', color='#3B82F6')
        ax.fill(angles, nivel_deseado, alpha=0.15, color='#3B82F6')
        
        # Plotear nivel actual
        ax.plot(angles, nivel_actual, 'o-', linewidth=2, label='Nivel Actual', color='#10B981')
        ax.fill(angles, nivel_actual, alpha=0.25, color='#10B981')
        
        # Configurar etiquetas
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=9)
        
        # Configurar escala radial
        ax.set_ylim(0, 5)
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.set_yticklabels(['1', '2', '3', '4', '5'], fontsize=8)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        # Título y leyenda
        ax.set_title('Comparación: Nivel Actual vs Deseado', fontweight='bold', pad=20, y=1.08)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=9)
        
        plt.tight_layout()
        
        # Convertir a imagen
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return RLImage(buffer, width=width*cm, height=height*cm)