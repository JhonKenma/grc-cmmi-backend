# apps/reportes/exporters/pdf_exporter.py

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, 
    Paragraph, Spacer, PageBreak, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
from .base import BaseExporter
from .charts import ChartGenerator  # ⭐ IMPORT NUEVO
import os
from django.conf import settings


class PDFExporter(BaseExporter):
    """
    Exportador de reportes a formato PDF con gráficas
    """
    
    def get_content_type(self):
        return 'application/pdf'
    
    def get_file_extension(self):
        return 'pdf'
    
    def generate(self):
        """Genera el archivo PDF completo con gráficas"""
        # Crear documento
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        # Configurar estilos
        self._setup_styles()
        
        # Construir contenido
        story = []
        story.extend(self._crear_portada())
        story.append(PageBreak())
        story.extend(self._crear_resumen_ejecutivo())
        story.extend(self._crear_clasificacion_gaps())
        story.append(PageBreak())
        story.extend(self._crear_graficas_analisis())  # ⭐ NUEVO: Gráficas
        story.append(PageBreak())
        story.extend(self._crear_resultados_dimensiones())
        
        # Generar PDF
        doc.build(story)
    
    def _setup_styles(self):
        """Configura los estilos del documento"""
        styles = getSampleStyleSheet()
        
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1F4788'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1F4788'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
        )
    
    def _crear_portada(self):
        """Crea la portada del reporte con logo"""
        elements = []
        
        # ⭐ LOGO EN ESQUINA SUPERIOR DERECHA
        try:
            logo_path = os.path.join(
                settings.BASE_DIR,
                'apps', 'reportes', 'assets', 'logo.jpeg'
            )
            
            if os.path.exists(logo_path):
                logo = RLImage(logo_path, width=3*cm, height=3*cm)
                
                # Tabla invisible para posicionar logo a la derecha
                logo_table = Table([[Spacer(1, 1), logo]], colWidths=[14*cm, 4*cm])
                logo_table.setStyle(TableStyle([
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                elements.append(logo_table)
                elements.append(Spacer(1, 1*cm))
            else:
                print(f"⚠️ Logo no encontrado en: {logo_path}")
                elements.append(Spacer(1, 3*cm))
        except Exception as e:
            print(f"⚠️ Error al cargar logo: {e}")
            elements.append(Spacer(1, 3*cm))
        
        # Título principal
        elements.append(Paragraph("REPORTE DE EVALUACIÓN CMMI", self.title_style))
        elements.append(Spacer(1, 1*cm))
        
        # Información de la evaluación
        info_data = [
            ['Evaluación:', self.evaluacion.encuesta.nombre],
            ['Empresa:', self.evaluacion.empresa.nombre],
            ['RUC:', self.evaluacion.empresa.ruc or 'N/A'],
            ['Fecha de Asignación:', self.evaluacion.fecha_asignacion.strftime('%d/%m/%Y')],
            ['Fecha Límite:', self.evaluacion.fecha_limite.strftime('%d/%m/%Y') if self.evaluacion.fecha_limite else 'N/A'],
            ['Estado:', self.evaluacion.get_estado_display()],
            ['Generado:', datetime.now().strftime('%d/%m/%Y %H:%M')],
        ]
        
        info_table = Table(info_data, colWidths=[5*cm, 10*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8EAF6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(info_table)
        
        return elements
    
    def _crear_resumen_ejecutivo(self):
        """Crea la sección de resumen ejecutivo"""
        elements = []
        
        elements.append(Paragraph("1. RESUMEN EJECUTIVO", self.heading_style))
        
        stats = self.get_estadisticas_generales()
        
        resumen_data = [
            ['Métrica', 'Valor'],
            ['Total Dimensiones Evaluadas', str(stats['total_dimensiones'])],
            ['Total Usuarios Participantes', str(stats['total_usuarios'])],
            ['Nivel Deseado Promedio', f"{stats['nivel_deseado_avg']:.2f}"],
            ['Nivel Actual Promedio', f"{stats['nivel_actual_avg']:.2f}"],
            ['GAP Promedio', f"{stats['gap_avg']:.2f}"],
            ['% Cumplimiento Promedio', f"{stats['cumplimiento_avg']:.1f}%"],
        ]
        
        resumen_table = Table(resumen_data, colWidths=[10*cm, 5*cm])
        resumen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ]))
        
        elements.append(resumen_table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _crear_clasificacion_gaps(self):
        """Crea la sección de clasificación de GAPs"""
        elements = []
        
        elements.append(Paragraph("2. CLASIFICACIÓN DE GAPs", self.heading_style))
        
        clasificaciones = self.get_clasificaciones_gap()
        
        clasificacion_data = [['Clasificación', 'Cantidad', 'Porcentaje']]
        
        clasificaciones_labels = {
            'critico': 'Crítico',
            'alto': 'Alto',
            'medio': 'Medio',
            'bajo': 'Bajo',
            'cumplido': 'Cumplido',
            'superado': 'Superado',
        }
        
        for key, label in clasificaciones_labels.items():
            clasificacion_data.append([
                label,
                str(clasificaciones[key]),
                f"{clasificaciones[f'{key}_porcentaje']:.1f}%"
            ])
        
        clasificacion_table = Table(clasificacion_data, colWidths=[8*cm, 4*cm, 3*cm])
        clasificacion_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ]))
        
        elements.append(clasificacion_table)
        elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _crear_graficas_analisis(self):
        """⭐ NUEVO: Crea sección con gráficas de análisis"""
        elements = []
        
        elements.append(Paragraph("3. ANÁLISIS GRÁFICO", self.heading_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Obtener datos
        dimensiones_data = self.get_dimensiones_data()
        clasificaciones = self.get_clasificaciones_gap()
        
        # ⭐ Gráfica de barras GAP
        try:
            elements.append(Paragraph(
                "<b>3.1 Brechas por Dimensión</b>",
                self.normal_style
            ))
            elements.append(Spacer(1, 0.3*cm))
            
            grafica_barras = ChartGenerator.grafica_barras_gap(dimensiones_data, width=16, height=9)
            elements.append(grafica_barras)
            elements.append(Spacer(1, 1*cm))
        except Exception as e:
            print(f"⚠️ Error al generar gráfica de barras: {e}")
            import traceback
            traceback.print_exc()
        
        # ⭐ Gráfica de pastel clasificaciones
        try:
            elements.append(Paragraph(
                "<b>3.2 Distribución de Clasificaciones GAP</b>",
                self.normal_style
            ))
            elements.append(Spacer(1, 0.3*cm))
            
            grafica_pastel = ChartGenerator.grafica_pastel_clasificacion(clasificaciones, width=13, height=11)
            elements.append(grafica_pastel)
            elements.append(Spacer(1, 1*cm))
        except Exception as e:
            print(f"⚠️ Error al generar gráfica de pastel clasificaciones: {e}")
            import traceback
            traceback.print_exc()
        
        # ⭐ Gráfica radar (opcional)
        try:
            if len(dimensiones_data) >= 3:  # Solo si hay suficientes dimensiones
                elements.append(Paragraph(
                    "<b>3.3 Comparación: Nivel Actual vs Deseado</b>",
                    self.normal_style
                ))
                elements.append(Spacer(1, 0.3*cm))
                
                grafica_radar = ChartGenerator.grafica_radar_dimensiones(dimensiones_data, width=14, height=14)
                elements.append(grafica_radar)
        except Exception as e:
            print(f"⚠️ Error al generar gráfica radar: {e}")
            import traceback
            traceback.print_exc()
        
        return elements
    
    def _crear_resultados_dimensiones(self):
        """Crea la sección de resultados por dimensión"""
        elements = []
        
        elements.append(Paragraph("4. RESULTADOS DETALLADOS POR DIMENSIÓN", self.heading_style))
        
        dimensiones_data = self.get_dimensiones_data()
        
        for dim_data in dimensiones_data:
            dimension = dim_data['dimension']
            
            elements.append(Paragraph(
                f"<b>{dimension.codigo}</b> - {dimension.nombre}",
                self.normal_style
            ))
            
            dim_table_data = [
                ['Métrica', 'Valor'],
                ['Nivel Deseado', f"{dim_data['nivel_deseado']:.2f}"],
                ['Nivel Actual Promedio', f"{dim_data['nivel_actual_avg']:.2f}"],
                ['GAP Promedio', f"{dim_data['gap_avg']:.2f}"],
                ['% Cumplimiento', f"{dim_data['cumplimiento_avg']:.1f}%"],
                ['Usuarios Evaluados', str(dim_data['total_usuarios'])],
            ]
            
            dim_table = Table(dim_table_data, colWidths=[10*cm, 5*cm])
            dim_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E3F2FD')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FAFAFA')]),
            ]))
            
            elements.append(dim_table)
            elements.append(Spacer(1, 0.5*cm))
        
        return elements