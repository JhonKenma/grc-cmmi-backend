# apps/reportes/exporters/pdf_exporter.py

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, 
    Paragraph, Spacer, PageBreak, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT, TA_LEFT
from datetime import datetime
from .base import BaseExporter
from .charts import ChartGenerator
import os
from django.conf import settings


class PDFExporter(BaseExporter):
    """Exportador de reportes a formato PDF profesional"""
    
    def get_content_type(self):
        return 'application/pdf'
    
    def get_file_extension(self):
        return 'pdf'
    
    def generate(self):
        """Genera el PDF completo"""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=1.5*cm,
            bottomMargin=2*cm,
        )
        
        self._setup_styles()
        
        story = []
        story.extend(self._crear_portada())
        story.append(PageBreak())
        story.extend(self._crear_resumen_ejecutivo())
        story.extend(self._crear_analisis_grafico())
        story.append(PageBreak())
        story.extend(self._crear_clasificaciones_detalladas())
        story.extend(self._crear_resultados_dimensiones())
        story.append(PageBreak())
        story.extend(self._crear_resultados_usuarios())
        story.extend(self._crear_recomendaciones())
        story.extend(self._crear_footer_shieldgrid())
        
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
    
    def _add_page_number(self, canvas, doc):
        """Agrega número de página"""
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - 2*cm, 1*cm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()
    
    def _setup_styles(self):
        """Configura estilos del documento"""
        styles = getSampleStyleSheet()
        
        # Logo style (ShieldGrid) - Sin salto de línea
        self.logo_style = ParagraphStyle(
            'LogoStyle',
            fontSize=20,
            textColor=colors.HexColor('#1F4788'),
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            spaceAfter=5,
        )
        
        self.title_style = ParagraphStyle(
            'CustomTitle',
            fontSize=20,
            textColor=colors.HexColor('#1F4788'),
            spaceAfter=8,
            spaceBefore=8,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=24,
        )
        
        self.subtitle_style = ParagraphStyle(
            'Subtitle',
            fontSize=12,
            textColor=colors.HexColor('#666666'),
            spaceAfter=5,
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique',
        )
        
        self.heading1_style = ParagraphStyle(
            'H1',
            fontSize=14,
            textColor=colors.HexColor('#1F4788'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='Helvetica-Bold',
            backColor=colors.HexColor('#E8EAF6'),
            leftIndent=10,
            rightIndent=10,
            borderPadding=8,
        )
        
        self.heading2_style = ParagraphStyle(
            'H2',
            fontSize=12,
            textColor=colors.HexColor('#1F4788'),
            spaceAfter=6,
            spaceBefore=8,
            fontName='Helvetica-Bold',
        )
        
        self.normal_style = ParagraphStyle(
            'Normal',
            fontSize=9,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leading=12,
        )
        
        self.caption_style = ParagraphStyle(
            'Caption',
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique',
            spaceAfter=8,
        )
        
        self.footer_style = ParagraphStyle(
            'Footer',
            fontSize=10,
            textColor=colors.HexColor('#1F4788'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        )
        
        self.info_label_style = ParagraphStyle(
            'InfoLabel',
            fontSize=10,
            textColor=colors.HexColor('#1F4788'),
            fontName='Helvetica-Bold',
            spaceAfter=3,
        )
        
        self.info_value_style = ParagraphStyle(
            'InfoValue',
            fontSize=10,
            textColor=colors.HexColor('#424242'),
            fontName='Helvetica',
            spaceAfter=8,
        )
    
    def _crear_portada(self):
        """Crea carátula profesional sin tablas"""
        elements = []
        
        # Logo ShieldGrid en esquina superior izquierda (sin salto de línea)
        elements.append(Paragraph("🛡️<b> ShieldGrid</b>", self.logo_style))
        elements.append(Spacer(1, 2.5*cm))
        
        # Título principal - CORREGIDO sin salto de línea
        elements.append(Paragraph("REPORTE DE EVALUACIÓN", self.title_style))
        elements.append(Paragraph("CAPABILITY MATURITY MODEL INTEGRATION", self.title_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Subtítulo con nombre de la encuesta
        elements.append(Paragraph(self.evaluacion.encuesta.nombre, self.subtitle_style))
        elements.append(Spacer(1, 2*cm))
        
        # Información de la empresa - SIN TABLAS
        empresa = self.evaluacion.empresa
        
        elements.append(Paragraph("INFORMACIÓN DE LA EMPRESA", self.info_label_style))
        elements.append(Paragraph(f"<b>Empresa:</b> {empresa.nombre}", self.info_value_style))
        elements.append(Paragraph(f"<b>RUC:</b> {getattr(empresa, 'ruc', 'N/A') or 'N/A'}", self.info_value_style))
        if hasattr(empresa, 'sector') and empresa.sector:
            elements.append(Paragraph(f"<b>Sector:</b> {empresa.sector}", self.info_value_style))
        
        elements.append(Spacer(1, 1*cm))
        
        # Información de la evaluación - SIN TABLAS
        elements.append(Paragraph("INFORMACIÓN DE LA EVALUACIÓN", self.info_label_style))
        elements.append(Paragraph(
            f"<b>Fecha de Asignación:</b> {self.evaluacion.fecha_asignacion.strftime('%d de %B de %Y')}", 
            self.info_value_style
        ))
        elements.append(Paragraph(
            f"<b>Fecha Límite:</b> {self.evaluacion.fecha_limite.strftime('%d de %B de %Y')}", 
            self.info_value_style
        ))
        elements.append(Paragraph(
            f"<b>Estado:</b> {self.evaluacion.get_estado_display()}", 
            self.info_value_style
        ))
        elements.append(Paragraph(
            f"<b>Avance:</b> {self.evaluacion.porcentaje_avance:.1f}%", 
            self.info_value_style
        ))
        
        elements.append(Spacer(1, 1*cm))
        
        # Responsables - SIN TABLAS
        elements.append(Paragraph("EQUIPO RESPONSABLE", self.info_label_style))
        
        if self.evaluacion.administrador:
            admin = self.evaluacion.administrador
            elements.append(Paragraph(
                f"<b>Administrador Responsable:</b> {admin.nombre_completo}", 
                self.info_value_style
            ))
            if admin.cargo:
                elements.append(Paragraph(f"<b>Cargo:</b> {admin.cargo}", self.info_value_style))
            if admin.email:
                elements.append(Paragraph(f"<b>Email:</b> {admin.email}", self.info_value_style))
        
        if self.evaluacion.asignado_por:
            elements.append(Paragraph(
                f"<b>Asignado por:</b> {self.evaluacion.asignado_por.nombre_completo}", 
                self.info_value_style
            ))
        
        elements.append(Spacer(1, 1*cm))
        
        # Información del documento
        elements.append(Paragraph("INFORMACIÓN DEL DOCUMENTO", self.info_label_style))
        elements.append(Paragraph(
            f"<b>Fecha de Generación:</b> {datetime.now().strftime('%d de %B de %Y a las %H:%M')}", 
            self.info_value_style
        ))
        elements.append(Paragraph("<b>Versión:</b> 1.0", self.info_value_style))
        
        elements.append(Spacer(1, 1.5*cm))
        
        # Nota de confidencialidad
        conf_text = (
            "<b>CONFIDENCIAL:</b> Este documento contiene información confidencial destinada "
            f"únicamente para {empresa.nombre}. Cualquier divulgación no autorizada está prohibida."
        )
        elements.append(Paragraph(conf_text, self.caption_style))
        
        return elements
    
    def _crear_resumen_ejecutivo(self):
        """Resumen ejecutivo con toda la información"""
        elements = []
        
        elements.append(Paragraph("1. RESUMEN EJECUTIVO", self.heading1_style))
        elements.append(Spacer(1, 0.3*cm))
        
        stats = self.get_estadisticas_generales()
        
        # Introducción
        intro = (
            f"Este reporte presenta los resultados de la evaluación CMMI realizada para "
            f"<b>{self.evaluacion.empresa.nombre}</b> utilizando el modelo "
            f"<b>{self.evaluacion.encuesta.nombre}</b>. La evaluación contó con la participación de "
            f"<b>{stats['total_usuarios']} usuarios</b> evaluando <b>{stats['total_dimensiones']} dimensiones</b> "
            f"del modelo CMMI."
        )
        elements.append(Paragraph(intro, self.normal_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Métricas principales en tabla
        metricas = [
            ['MÉTRICA CLAVE', 'VALOR', 'INTERPRETACIÓN'],
            [
                'GAP Promedio',
                f"{stats['gap_avg']:.2f}",
                self._interpretar_gap(stats['gap_avg'])
            ],
            [
                '% Cumplimiento',
                f"{stats['cumplimiento_avg']:.1f}%",
                self._interpretar_cumplimiento(stats['cumplimiento_avg'])
            ],
            [
                'Nivel Actual Promedio',
                f"{stats['nivel_actual_avg']:.2f}",
                f"Sobre {stats['nivel_deseado_avg']:.2f} deseado"
            ],
            [
                'Total Evaluaciones',
                f"{stats['total_dimensiones']} dimensiones",
                f"{stats['total_usuarios']} usuarios participantes"
            ],
        ]
        
        metricas_table = Table(metricas, colWidths=[4*cm, 3.5*cm, 9.5*cm])
        metricas_table.setStyle(self._get_table_style())
        elements.append(metricas_table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _crear_analisis_grafico(self):
        """Sección con gráficas mejoradas"""
        elements = []
        
        elements.append(Paragraph("2. ANÁLISIS GRÁFICO", self.heading1_style))
        elements.append(Spacer(1, 0.3*cm))
        
        dimensiones_data = self.get_dimensiones_data()
        clasificaciones = self.get_clasificaciones_gap()
        usuarios_data = self.get_usuarios_data()
        
        # ⭐ GRÁFICA 1: Barras GAP (MEJORADA)
        try:
            elements.append(Paragraph("2.1 Análisis de Brechas por Dimensión", self.heading2_style))
            elements.append(Spacer(1, 0.2*cm))
            
            grafica_barras = ChartGenerator.grafica_barras_gap(dimensiones_data, width=17, height=10)
            elements.append(grafica_barras)
            elements.append(Paragraph(
                "<i>Figura 1: Brechas (GAP) identificadas por cada dimensión evaluada del modelo CMMI</i>", 
                self.caption_style
            ))
        except Exception as e:
            print(f"⚠️ Error en gráfica barras: {e}")
            import traceback
            traceback.print_exc()
        
        elements.append(Spacer(1, 0.8*cm))
        
        # ⭐ GRÁFICA 2 y 3: Donut + Radar lado a lado
        try:
            elements.append(Paragraph("2.2 Distribuciones y Comparación de Niveles", self.heading2_style))
            elements.append(Spacer(1, 0.2*cm))
            
            # Gráfica donut
            grafica_donut = ChartGenerator.grafica_donut_distribucion(clasificaciones, width=11, height=10)
            
            # Gráfica radar si hay suficientes dimensiones
            if len(dimensiones_data) >= 3:
                grafica_radar = ChartGenerator.grafica_radar_dimensiones(dimensiones_data, width=13, height=13)
                
                # Lado a lado
                graficas_dobles = Table([[grafica_donut, grafica_radar]], colWidths=[8.5*cm, 8.5*cm])
                graficas_dobles.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                elements.append(graficas_dobles)
                
                # Pies
                pies = Table([[
                    Paragraph("<i>Figura 2a: Distribución de clasificaciones por criticidad</i>", self.caption_style),
                    Paragraph("<i>Figura 2b: Comparación nivel actual vs deseado</i>", self.caption_style)
                ]], colWidths=[8.5*cm, 8.5*cm])
                elements.append(pies)
            else:
                tabla_centrada = Table([[grafica_donut]], colWidths=[17*cm])
                tabla_centrada.setStyle(TableStyle([('ALIGN', (0, 0), (0, 0), 'CENTER')]))
                elements.append(tabla_centrada)
                elements.append(Paragraph(
                    "<i>Figura 2: Distribución de clasificaciones GAP</i>", 
                    self.caption_style
                ))
                
        except Exception as e:
            print(f"⚠️ Error en gráficas donut/radar: {e}")
            import traceback
            traceback.print_exc()
        
        elements.append(Spacer(1, 0.8*cm))
        
        # ⭐ GRÁFICA 4: Líneas de cumplimiento
        try:
            elements.append(Paragraph("2.3 Evolución del Cumplimiento por Dimensión", self.heading2_style))
            elements.append(Spacer(1, 0.2*cm))
            
            grafica_lineas = ChartGenerator.grafica_lineas_cumplimiento(dimensiones_data, width=17, height=9)
            elements.append(grafica_lineas)
            elements.append(Paragraph(
                "<i>Figura 3: Porcentaje de cumplimiento alcanzado en cada dimensión evaluada</i>", 
                self.caption_style
            ))
        except Exception as e:
            print(f"⚠️ Error en gráfica líneas: {e}")
            import traceback
            traceback.print_exc()
        
        elements.append(Spacer(1, 0.8*cm))
        
        # ⭐ GRÁFICA 5: Barras horizontales de usuarios (solo si hay datos)
        try:
            if len(usuarios_data) > 0:
                elements.append(Paragraph("2.4 Usuarios con Mayor Brecha", self.heading2_style))
                elements.append(Spacer(1, 0.2*cm))
                
                grafica_usuarios = ChartGenerator.grafica_barras_horizontales_usuarios(
                    usuarios_data, width=17, height=10
                )
                elements.append(grafica_usuarios)
                elements.append(Paragraph(
                    "<i>Figura 4: Top 10 usuarios con mayor GAP promedio identificado</i>", 
                    self.caption_style
                ))
        except Exception as e:
            print(f"⚠️ Error en gráfica usuarios: {e}")
            import traceback
            traceback.print_exc()
        
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _crear_clasificaciones_detalladas(self):
        """Clasificaciones con más detalle"""
        elements = []
        
        elements.append(Paragraph("3. CLASIFICACIÓN DE BRECHAS (GAPs)", self.heading1_style))
        elements.append(Spacer(1, 0.3*cm))
        
        intro = (
            "Las brechas identificadas se han clasificado en seis categorías según su nivel de criticidad, "
            "permitiendo priorizar las acciones de mejora de acuerdo al impacto y urgencia de cada una."
        )
        elements.append(Paragraph(intro, self.normal_style))
        elements.append(Spacer(1, 0.4*cm))
        
        clasificaciones = self.get_clasificaciones_gap()
        
        # Tabla con más detalle
        clasif_data = [['CLASIFICACIÓN', 'CRITERIO', 'CANTIDAD', '%', 'PRIORIDAD']]
        
        clasif_info = [
            ('Crítico', 'GAP ≥ 2.5', 'critico', 'INMEDIATA'),
            ('Alto', '2.0 ≤ GAP < 2.5', 'alto', 'ALTA'),
            ('Medio', '1.0 ≤ GAP < 2.0', 'medio', 'MEDIA'),
            ('Bajo', '0 < GAP < 1.0', 'bajo', 'BAJA'),
            ('Cumplido', 'GAP = 0', 'cumplido', 'MANTENIMIENTO'),
            ('Superado', 'GAP < 0', 'superado', 'REPLICAR'),
        ]
        
        for label, criterio, key, prioridad in clasif_info:
            clasif_data.append([
                label,
                criterio,
                str(clasificaciones[key]),
                f"{clasificaciones[f'{key}_porcentaje']:.1f}%",
                prioridad
            ])
        
        clasif_table = Table(clasif_data, colWidths=[3*cm, 3.5*cm, 2.5*cm, 2.5*cm, 5.5*cm])
        clasif_table.setStyle(self._get_table_style())
        elements.append(clasif_table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _crear_resultados_dimensiones(self):
        """Resultados detallados por dimensión"""
        elements = []
        
        elements.append(Paragraph("4. RESULTADOS POR DIMENSIÓN", self.heading1_style))
        elements.append(Spacer(1, 0.3*cm))
        
        dimensiones_data = self.get_dimensiones_data()
        
        # Tabla resumen de todas las dimensiones
        dim_table_data = [['CÓDIGO', 'DIMENSIÓN', 'DESEADO', 'ACTUAL', 'GAP', '% CUMPL.', 'USUARIOS']]
        
        for dim_data in dimensiones_data:
            dim = dim_data['dimension']
            dim_table_data.append([
                dim.codigo,
                dim.nombre[:35] + '...' if len(dim.nombre) > 35 else dim.nombre,
                f"{dim_data['nivel_deseado']:.1f}",
                f"{dim_data['nivel_actual_avg']:.1f}",
                f"{dim_data['gap_avg']:.1f}",
                f"{dim_data['cumplimiento_avg']:.0f}%",
                str(dim_data['total_usuarios']),
            ])
        
        dim_table = Table(dim_table_data, colWidths=[2*cm, 6*cm, 2*cm, 2*cm, 1.5*cm, 2*cm, 1.5*cm])
        dim_table.setStyle(self._get_table_style())
        elements.append(dim_table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _crear_resultados_usuarios(self):
        """Resultados por usuario participante"""
        elements = []
        
        elements.append(Paragraph("5. RESULTADOS POR USUARIO", self.heading1_style))
        elements.append(Spacer(1, 0.3*cm))
        
        usuarios_data = self.get_usuarios_data()
        
        intro = (
            f"Se contó con la participación de <b>{len(usuarios_data)} usuarios</b> en la evaluación. "
            "A continuación se presenta el desempeño individual de cada participante."
        )
        elements.append(Paragraph(intro, self.normal_style))
        elements.append(Spacer(1, 0.4*cm))
        
        # Tabla de usuarios
        usuarios_table_data = [['USUARIO', 'CARGO', 'NIVEL ACTUAL', 'GAP', '% CUMPL.', 'DIMS.']]
        
        for user_data in usuarios_data:
            usuario = user_data['usuario']
            usuarios_table_data.append([
                usuario.nombre_completo[:30],
                (usuario.cargo or 'N/A')[:20],
                f"{user_data['nivel_actual_avg']:.2f}",
                f"{user_data['gap_avg']:.2f}",
                f"{user_data['cumplimiento_avg']:.1f}%",
                str(user_data['total_dimensiones']),
            ])
        
        usuarios_table = Table(usuarios_table_data, colWidths=[5*cm, 4*cm, 2.5*cm, 2*cm, 2.5*cm, 1*cm])
        usuarios_table.setStyle(self._get_table_style())
        elements.append(usuarios_table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _crear_recomendaciones(self):
        """Recomendaciones basadas en los resultados"""
        elements = []
        
        elements.append(Paragraph("6. RECOMENDACIONES", self.heading1_style))
        elements.append(Spacer(1, 0.3*cm))
        
        stats = self.get_estadisticas_generales()
        dimensiones_data = self.get_dimensiones_data()
        
        intro = (
            "Con base en los resultados obtenidos y el análisis realizado, se presentan las siguientes "
            "recomendaciones prioritarias para mejorar el nivel de madurez de los procesos organizacionales."
        )
        elements.append(Paragraph(intro, self.normal_style))
        elements.append(Spacer(1, 0.4*cm))
        
        recomendaciones = self._generar_recomendaciones(stats, dimensiones_data)
        
        for idx, recom in enumerate(recomendaciones, 1):
            elements.append(Paragraph(f"<b>{idx}.</b> {recom}", self.normal_style))
            elements.append(Spacer(1, 0.3*cm))
        
        elements.append(Spacer(1, 0.5*cm))
        
        # Conclusión
        conclusion = self._generar_conclusion(stats)
        elements.append(Paragraph("<b>Conclusión General:</b>", self.heading2_style))
        elements.append(Paragraph(conclusion, self.normal_style))
        
        return elements
    
    def _crear_footer_shieldgrid(self):
        """Footer con Powered by ShieldGrid"""
        elements = []
        
        elements.append(Spacer(1, 2*cm))
        
        # Línea separadora
        line_table = Table([['']], colWidths=[17*cm])
        line_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#1F4788')),
        ]))
        elements.append(line_table)
        elements.append(Spacer(1, 0.4*cm))
        
        # Powered by ShieldGrid
        footer_text = "🛡️ <b>Powered by ShieldGrid</b>"
        elements.append(Paragraph(footer_text, self.footer_style))
        
        return elements
    
    # Métodos auxiliares
    
    def _get_table_style(self):
        """Estilo estándar para tablas"""
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ])
    
    def _interpretar_gap(self, gap):
        if gap >= 2.5: return "⚠️ Crítico - Acción inmediata requerida"
        if gap >= 2.0: return "⚠️ Alto - Requiere atención prioritaria"
        if gap >= 1.0: return "⚡ Medio - Plan de mejora necesario"
        if gap > 0: return "✓ Bajo - Mejoras incrementales"
        return "✓✓ Objetivos cumplidos"
    
    def _interpretar_cumplimiento(self, pct):
        if pct >= 90: return "✓✓ Excelente desempeño"
        if pct >= 75: return "✓ Buen desempeño"
        if pct >= 60: return "⚡ Desempeño aceptable"
        return "⚠️ Requiere atención urgente"
    
    def _generar_recomendaciones(self, stats, dimensiones_data):
        recomendaciones = []
        
        if stats['gap_avg'] >= 2.0:
            recomendaciones.append(
                "Desarrollar un plan de mejora integral con asignación de recursos dedicados y "
                "seguimiento ejecutivo para cerrar las brechas identificadas."
            )
        else:
            recomendaciones.append(
                "Implementar un programa de mejora continua con revisiones trimestrales de progreso."
            )
        
        if stats['cumplimiento_avg'] < 70:
            recomendaciones.append(
                "Establecer un programa de capacitación intensiva en estándares CMMI y mejores "
                "prácticas de la industria para todo el equipo."
            )
        
        dims_criticas = [d for d in dimensiones_data if d['gap_avg'] >= 2.0]
        if dims_criticas:
            codigos = ", ".join([d['dimension'].codigo for d in dims_criticas[:3]])
            recomendaciones.append(
                f"Priorizar la atención de las dimensiones: {codigos}, desarrollando planes de "
                "acción específicos para cada una en un plazo de 30-60 días."
            )
        
        recomendaciones.append(
            "Documentar y estandarizar los procesos existentes, estableciendo métricas de "
            "seguimiento y procedimientos de control de calidad."
        )
        
        recomendaciones.append(
            "Promover una cultura organizacional orientada a la calidad y la mejora continua, "
            "con reconocimientos a los equipos que implementen mejoras exitosas."
        )
        
        return recomendaciones
    
    def _generar_conclusion(self, stats):
        if stats['gap_avg'] >= 2.0:
            return (
                f"La evaluación revela un GAP promedio de {stats['gap_avg']:.2f}, indicando "
                "oportunidades significativas de mejora en los procesos organizacionales. "
                "Con el compromiso adecuado de recursos y liderazgo, es posible alcanzar el "
                "nivel de madurez deseado en un plazo de 12-18 meses. La implementación "
                "sistemática de las recomendaciones presentadas será fundamental para el éxito "
                "de esta iniciativa de mejora."
            )
        elif stats['gap_avg'] >= 1.0:
            return (
                f"Con un GAP promedio de {stats['gap_avg']:.2f}, la organización muestra un "
                "nivel de madurez moderado. Se recomienda enfocarse en las áreas específicas "
                "identificadas como críticas, mientras se mantienen las fortalezas actuales. "
                "Un plan de mejora estructurado permitirá cerrar las brechas en 6-12 meses."
            )
        else:
            return (
                f"El GAP bajo ({stats['gap_avg']:.2f}) demuestra un buen nivel de madurez "
                "en los procesos organizacionales. Se recomienda continuar con mejoras "
                "incrementales y mantener las buenas prácticas establecidas, enfocándose en "
                "la optimización y la innovación continua."
            )