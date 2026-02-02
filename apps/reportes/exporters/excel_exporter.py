# apps/reportes/exporters/excel_exporter.py

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from .base import BaseExporter


class ExcelExporter(BaseExporter):
    """
    Exportador de reportes a formato Excel (.xlsx)
    """
    
    def get_content_type(self):
        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    def get_file_extension(self):
        return 'xlsx'
    
    def generate(self):
        """Genera el archivo Excel completo"""
        wb = Workbook()
        
        # Estilos reutilizables
        self.header_fill = PatternFill(start_color="1F4788", end_color="1F4788", fill_type="solid")
        self.header_font = Font(color="FFFFFF", bold=True, size=12)
        self.title_font = Font(bold=True, size=14)
        self.center_align = Alignment(horizontal="center", vertical="center")
        
        # Generar hojas
        self._crear_hoja_resumen(wb)
        self._crear_hoja_dimensiones(wb)
        self._crear_hoja_usuarios(wb)
        self._crear_hoja_clasificaciones(wb)
        
        # Guardar en buffer
        wb.save(self.buffer)
    
    def _crear_hoja_resumen(self, wb):
        """Hoja 1: Resumen General"""
        ws = wb.active
        ws.title = "Resumen General"
        
        # Título
        ws['A1'] = "REPORTE DE EVALUACIÓN CMMI"
        ws['A1'].font = self.title_font
        ws.merge_cells('A1:B1')
        
        # Información básica
        ws['A2'] = f"Evaluación: {self.evaluacion.encuesta.nombre}"
        ws['A3'] = f"Empresa: {self.evaluacion.empresa.nombre}"
        ws['A4'] = f"Fecha: {self.evaluacion.fecha_asignacion.strftime('%d/%m/%Y')}"
        
        # Métricas
        ws['A6'] = "Métrica"
        ws['B6'] = "Valor"
        ws['A6'].fill = self.header_fill
        ws['B6'].fill = self.header_fill
        ws['A6'].font = self.header_font
        ws['B6'].font = self.header_font
        
        stats = self.get_estadisticas_generales()
        
        metricas = [
            ("Nivel Deseado Promedio", stats['nivel_deseado_avg']),
            ("Nivel Actual Promedio", stats['nivel_actual_avg']),
            ("GAP Promedio", stats['gap_avg']),
            ("% Cumplimiento Promedio", stats['cumplimiento_avg']),
            ("Total Dimensiones", stats['total_dimensiones']),
            ("Total Usuarios", stats['total_usuarios']),
        ]
        
        for i, (metrica, valor) in enumerate(metricas, start=7):
            ws[f'A{i}'] = metrica
            ws[f'B{i}'] = valor
        
        # Ajustar anchos
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 15
    
    def _crear_hoja_dimensiones(self, wb):
        """Hoja 2: Dimensiones"""
        ws = wb.create_sheet("Dimensiones")
        
        headers = ["Código", "Dimensión", "Nivel Deseado", "Nivel Actual", "GAP", "% Cumplimiento", "Usuarios"]
        ws.append(headers)
        
        # Aplicar estilo a headers
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.center_align
        
        # Datos
        dimensiones_data = self.get_dimensiones_data()
        
        for dim_data in dimensiones_data:
            ws.append([
                dim_data['dimension'].codigo,
                dim_data['dimension'].nombre,
                dim_data['nivel_deseado'],
                dim_data['nivel_actual_avg'],
                dim_data['gap_avg'],
                dim_data['cumplimiento_avg'],
                dim_data['total_usuarios'],
            ])
        
        # Ajustar anchos
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 35
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 18
        ws.column_dimensions['G'].width = 12
    
    def _crear_hoja_usuarios(self, wb):
        """Hoja 3: Usuarios"""
        ws = wb.create_sheet("Usuarios")
        
        headers = ["Usuario", "Email", "Cargo", "Nivel Actual", "GAP", "% Cumplimiento", "Dimensiones"]
        ws.append(headers)
        
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.center_align
        
        # Datos
        usuarios_data = self.get_usuarios_data()
        
        for user_data in usuarios_data:
            usuario = user_data['usuario']
            ws.append([
                usuario.nombre_completo,
                usuario.email,
                usuario.cargo or 'N/A',
                user_data['nivel_actual_avg'],
                user_data['gap_avg'],
                user_data['cumplimiento_avg'],
                user_data['total_dimensiones'],
            ])
        
        # Ajustar anchos
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 18
        ws.column_dimensions['G'].width = 15
    
    def _crear_hoja_clasificaciones(self, wb):
        """Hoja 4: Clasificación GAP"""
        ws = wb.create_sheet("Clasificación GAP")
        
        headers = ["Clasificación", "Cantidad", "Porcentaje"]
        ws.append(headers)
        
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.center_align
        
        # Datos
        clasificaciones = self.get_clasificaciones_gap()
        
        clasificaciones_labels = {
            'critico': 'Crítico',
            'alto': 'Alto',
            'medio': 'Medio',
            'bajo': 'Bajo',
            'cumplido': 'Cumplido',
            'superado': 'Superado',
        }
        
        for key, label in clasificaciones_labels.items():
            ws.append([
                label,
                clasificaciones[key],
                f"{clasificaciones[f'{key}_porcentaje']}%"
            ])
        
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 15