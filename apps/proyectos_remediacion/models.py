# apps/proyectos_remediacion/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from apps.respuestas.models import CalculoNivel
from apps.empresas.models import Empresa
from apps.usuarios.models import Usuario
from apps.encuestas.models import Dimension, Pregunta
import uuid


class ProyectoCierreBrecha(BaseModel):
    """
    Proyecto completo de cierre de brecha derivado de análisis GAP
    
    Este modelo representa un proyecto formal de remediación que:
    - Se deriva de un GAP identificado (CalculoNivel)
    - Tiene un plan completo de ejecución
    - Incluye recursos, responsables, fechas, presupuesto
    - Tiene ciclo de vida: planificado → en_ejecucion → validacion → cerrado
    
    Ejemplo:
        Dimensión "Seguridad de Red" tiene GAP = 2.67 (Crítico)
        → Se crea ProyectoCierreBrecha para cerrar esa brecha
        → Se asignan responsables, tareas, presupuesto
        → Se ejecuta y valida
        → GAP se reduce a 0
    """
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 1: INFORMACIÓN BÁSICA DEL PROYECTO
    # ═══════════════════════════════════════════════════════════
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        verbose_name='ID del Proyecto'
    )
    
    codigo_proyecto = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código del Proyecto',
        help_text='Código único autogenerado (ej: REM-2025-001)',
        db_index=True
    )
    
    nombre_proyecto = models.CharField(
        max_length=200,
        verbose_name='Nombre del Proyecto de Remediación',
        help_text='Nombre descriptivo del proyecto'
    )
    
    descripcion = models.TextField(
        max_length=1000,
        verbose_name='Descripción del Proyecto',
        help_text='Descripción detallada del alcance y objetivos'
    )
    
    # ═══ VÍNCULO CON EL GAP ORIGINAL ═══
    calculo_nivel = models.ForeignKey(
        'respuestas.CalculoNivel',
        on_delete=models.PROTECT,
        related_name='proyectos_remediacion',
        verbose_name='Brecha GAP Asociada',
        help_text='CalculoNivel que originó este proyecto'
    )
    
    # ═══ FECHAS ═══
    fecha_inicio = models.DateField(
        verbose_name='Fecha de Inicio del Proyecto'
    )
    
    fecha_fin_estimada = models.DateField(
        verbose_name='Fecha de Finalización Estimada'
    )
    
    fecha_fin_real = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Finalización Real'
    )
    
    # ═══ ESTADOS ═══
    ESTADOS_PROYECTO = [
        ('planificado', 'Planificado'),
        ('en_ejecucion', 'En Ejecución'),
        ('en_validacion', 'En Validación'),
        ('cerrado', 'Cerrado'),
        ('suspendido', 'Suspendido'),
        ('cancelado', 'Cancelado'),
    ]
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_PROYECTO,
        default='planificado',
        verbose_name='Estado del Proyecto'
    )
    
    # ═══ CLASIFICACIÓN ═══
    PRIORIDADES = [
        ('critica', 'Crítica'),
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    ]
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDADES,
        verbose_name='Prioridad del Proyecto',
        help_text='Derivada de la criticidad del GAP'
    )
    
    CATEGORIAS = [
        ('tecnico', 'Técnico'),
        ('documental', 'Documental'),
        ('procesal', 'Procesal'),
        ('organizacional', 'Organizacional'),
        ('capacitacion', 'Capacitación'),
    ]
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIAS,
        verbose_name='Categoría de Proyecto'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 2: DATOS DE LA BRECHA ORIGINAL (DEL ANÁLISIS GAP)
    # ═══════════════════════════════════════════════════════════
    
    NORMATIVAS = [
        ('iso_27001', 'ISO 27001'),
        ('iso_9001', 'ISO 9001'),
        ('nist_csf', 'NIST CSF'),
        ('gdpr', 'GDPR'),
        ('pci_dss', 'PCI-DSS'),
        ('sox', 'SOX'),
        ('hipaa', 'HIPAA'),
        ('cmmi', 'CMMI'),
        ('otro', 'Otro'),
    ]
    normativa = models.CharField(
        max_length=20,
        choices=NORMATIVAS,
        verbose_name='Normativa/Estándar',
        help_text='Marco normativo de cumplimiento'
    )
    
    control_no_conforme = models.CharField(
        max_length=200,
        verbose_name='Control/Requisito No Conforme',
        help_text='Código y descripción del control que no cumple'
    )
    
    TIPOS_BRECHA = [
        ('ausencia_total', 'Ausencia Total'),
        ('parcial', 'Parcial'),
        ('no_efectiva', 'No Efectiva'),
        ('no_documentada', 'No Documentada'),
    ]
    tipo_brecha = models.CharField(
        max_length=20,
        choices=TIPOS_BRECHA,
        verbose_name='Tipo de Brecha',
        help_text='Clasificación de la no conformidad'
    )
    
    nivel_criticidad_original = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Nivel de Criticidad Original (1-5)',
        help_text='Criticidad identificada en el análisis GAP'
    )
    
    impacto_riesgo = models.TextField(
        verbose_name='Impacto Estimado del Riesgo',
        help_text='Descripción del impacto si no se remedia'
    )
    
    evidencia_no_conformidad = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Evidencia de No Conformidad Original',
        help_text='Ruta o URL de la evidencia del GAP'
    )
    
    fecha_identificacion_gap = models.DateField(
        verbose_name='Fecha de Identificación (GAP)',
        help_text='Fecha en que se identificó la brecha'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 3: PLANIFICACIÓN Y ESTRATEGIA
    # ═══════════════════════════════════════════════════════════
    
    ESTRATEGIAS = [
        ('implementacion_nueva', 'Implementación Nueva'),
        ('fortalecimiento', 'Fortalecimiento'),
        ('optimizacion', 'Optimización'),
        ('documentacion', 'Documentación'),
    ]
    estrategia_cierre = models.CharField(
        max_length=30,
        choices=ESTRATEGIAS,
        verbose_name='Estrategia de Cierre Seleccionada',
        help_text='Enfoque para cerrar la brecha'
    )
    
    alcance_proyecto = models.TextField(
        verbose_name='Alcance del Proyecto',
        help_text='Qué se incluye y qué no en el proyecto'
    )
    
    objetivos_especificos = models.TextField(
        verbose_name='Objetivos de Cierre Específicos',
        help_text='Lista de objetivos medibles y verificables'
    )
    
    criterios_aceptacion = models.TextField(
        verbose_name='Criterios de Aceptación',
        help_text='Condiciones que deben cumplirse para dar por cerrado el proyecto'
    )
    
    supuestos = models.TextField(
        blank=True,
        verbose_name='Supuestos del Proyecto',
        help_text='Condiciones que se asumen como verdaderas'
    )
    
    restricciones = models.TextField(
        blank=True,
        verbose_name='Restricciones Identificadas',
        help_text='Limitaciones del proyecto (tiempo, presupuesto, recursos)'
    )
    
    riesgos_proyecto = models.TextField(
        blank=True,
        verbose_name='Riesgos del Proyecto de Cierre',
        help_text='Riesgos identificados que podrían afectar el proyecto'
    )
    
    # ═══ RELACIÓN CON PREGUNTAS ═══
    # Permite vincular el proyecto con preguntas específicas que se están remediando
    preguntas_abordadas = models.ManyToManyField(
        'encuestas.Pregunta',
        related_name='proyectos_remediacion',
        blank=True,
        verbose_name='Preguntas Abordadas',
        help_text='Preguntas específicas del GAP que este proyecto remedia'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 4: RECURSOS Y RESPONSABILIDADES (Matriz RACI)
    # ═══════════════════════════════════════════════════════════
    
    dueno_proyecto = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='proyectos_propietario',
        verbose_name='Dueño del Proyecto (Project Owner)',
        help_text='Responsable general del éxito del proyecto'
    )
    
    responsable_implementacion = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='proyectos_responsable',
        verbose_name='Responsable de Implementación',
        help_text='Quien ejecuta las tareas técnicas (R en RACI)'
    )
    
    equipo_implementacion = models.ManyToManyField(
        Usuario,
        related_name='proyectos_equipo',
        blank=True,
        verbose_name='Equipo de Implementación',
        help_text='Miembros del equipo que ejecutarán tareas'
    )
    
    validador_interno = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proyectos_validador',
        verbose_name='Validador/Aprobador Interno',
        help_text='Quien aprueba los entregables (A en RACI)'
    )
    
    auditor_verificacion = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proyectos_auditor',
        verbose_name='Auditor de Verificación',
        help_text='Quien valida el cierre formal del proyecto'
    )
    
    # ═══ PRESUPUESTO ═══
    presupuesto_asignado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto Asignado',
        validators=[MinValueValidator(0)]
    )
    
    MONEDAS = [
        ('USD', 'USD - Dólar Estadounidense'),
        ('EUR', 'EUR - Euro'),
        ('GBP', 'GBP - Libra Esterlina'),
        ('PEN', 'PEN - Sol Peruano'),
        ('COP', 'COP - Peso Colombiano'),
        ('MXN', 'MXN - Peso Mexicano'),
        ('CLP', 'CLP - Peso Chileno'),
        ('ARS', 'ARS - Peso Argentino'),
    ]
    moneda = models.CharField(
        max_length=3,
        choices=MONEDAS,
        default='USD',
        verbose_name='Moneda del Presupuesto'
    )
    
    presupuesto_gastado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto Gastado',
        validators=[MinValueValidator(0)]
    )
    
    recursos_humanos_asignados = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Recursos Humanos Asignados (Horas)',
        help_text='Horas-persona estimadas',
        validators=[MinValueValidator(0)]
    )
    
    recursos_tecnicos = models.TextField(
        blank=True,
        verbose_name='Recursos Técnicos Requeridos',
        help_text='Hardware, software, herramientas necesarias'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 5: SEGUIMIENTO Y MONITOREO
    # ═══════════════════════════════════════════════════════════
    
    FRECUENCIAS_REPORTE = [
        ('diaria', 'Diaria'),
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
    ]
    frecuencia_reporte = models.CharField(
        max_length=20,
        choices=FRECUENCIAS_REPORTE,
        default='semanal',
        verbose_name='Frecuencia de Reporte',
        help_text='Periodicidad de reportes de avance'
    )
    
    metricas_desempeno = models.TextField(
        blank=True,
        verbose_name='Métricas de Desempeño del Proyecto',
        help_text='KPIs para medir el desempeño'
    )
    
    umbrales_alerta = models.TextField(
        blank=True,
        verbose_name='Umbrales de Alerta',
        help_text='Ejemplo: Retraso >10% genera alerta amarilla'
    )
    
    CANALES_COMUNICACION = [
        ('email', 'Email'),
        ('teams', 'Microsoft Teams'),
        ('slack', 'Slack'),
        ('whatsapp', 'WhatsApp'),
        ('otro', 'Otro'),
    ]
    canal_comunicacion = models.CharField(
        max_length=20,
        choices=CANALES_COMUNICACION,
        default='email',
        verbose_name='Canal de Comunicación Principal'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 6: EVIDENCIA Y VALIDACIÓN
    # ═══════════════════════════════════════════════════════════
    
    criterios_validacion = models.TextField(
        verbose_name='Criterios de Validación Específicos',
        help_text='Criterios que debe cumplir para ser validado'
    )
    
    METODOS_VERIFICACION = [
        ('muestreo', 'Muestreo'),
        ('prueba_completa', 'Prueba Completa'),
        ('observacion', 'Observación'),
        ('revision_documental', 'Revisión Documental'),
        ('entrevista', 'Entrevista'),
        ('inspeccion', 'Inspección Física'),
    ]
    metodo_verificacion = models.CharField(
        max_length=30,
        choices=METODOS_VERIFICACION,
        verbose_name='Método de Verificación',
        help_text='Cómo se verificará el cumplimiento'
    )
    
    responsable_validacion = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proyectos_validacion',
        verbose_name='Responsable de Validación',
        help_text='Quien valida que se cumplieron los criterios'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 7: CIERRE DEL PROYECTO
    # ═══════════════════════════════════════════════════════════
    
    fecha_cierre_tecnico = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Cierre Técnico',
        help_text='Cuando se completó la implementación técnica'
    )
    
    fecha_cierre_formal = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Cierre Formal',
        help_text='Cuando se validó formalmente el cierre'
    )
    
    RESULTADOS_FINALES = [
        ('exitoso', 'Exitoso'),
        ('parcialmente_exitoso', 'Parcialmente Exitoso'),
        ('no_exitoso', 'No Exitoso'),
        ('cancelado', 'Cancelado'),
    ]
    resultado_final = models.CharField(
        max_length=30,
        choices=RESULTADOS_FINALES,
        blank=True,
        verbose_name='Resultado Final'
    )
    
    lecciones_aprendidas = models.TextField(
        blank=True,
        verbose_name='Lecciones Aprendidas',
        help_text='Qué funcionó bien y qué se puede mejorar'
    )
    
    acciones_mejora_continua = models.TextField(
        blank=True,
        verbose_name='Acciones de Mejora Continua Derivadas',
        help_text='Mejoras identificadas para futuros proyectos'
    )
    
    recomendaciones_futuros_gap = models.TextField(
        blank=True,
        verbose_name='Recomendaciones para Futuros Análisis GAP',
        help_text='Feedback para mejorar próximos análisis GAP'
    )
    
    # ═══════════════════════════════════════════════════════════
    # EMPRESA Y AUDITORÍA
    # ═══════════════════════════════════════════════════════════
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='proyectos_remediacion',
        verbose_name='Empresa'
    )
    
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        related_name='proyectos_remediacion_creados',
        verbose_name='Creado Por'
    )
    
    version = models.IntegerField(
        default=1,
        verbose_name='Versión del Proyecto',
        help_text='Se incrementa con cada modificación mayor'
    )
    
    class Meta:
        db_table = 'proyectos_cierre_brecha'
        verbose_name = 'Proyecto de Cierre de Brecha'
        verbose_name_plural = 'Proyectos de Cierre de Brecha'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['empresa', 'estado']),
            models.Index(fields=['codigo_proyecto']),
            models.Index(fields=['prioridad']),
            models.Index(fields=['calculo_nivel']),
            models.Index(fields=['fecha_inicio']),
            models.Index(fields=['fecha_fin_estimada']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['codigo_proyecto'],
                name='unique_codigo_proyecto'
            ),
        ]
    
    def __str__(self):
        return f"{self.codigo_proyecto} - {self.nombre_proyecto}"
    
    def save(self, *args, **kwargs):
        """Generar código automático si no existe"""
        if not self.codigo_proyecto:
            self.codigo_proyecto = self.generar_codigo_proyecto()
        super().save(*args, **kwargs)
    
    def generar_codigo_proyecto(self):
        """
        Genera código único del proyecto
        Formato: REM-{YEAR}-{NUMERO_SECUENCIAL}
        Ejemplo: REM-2025-001
        """
        from django.utils import timezone
        
        year = timezone.now().year
        # Obtener último código del año
        ultimo = ProyectoCierreBrecha.objects.filter(
            codigo_proyecto__startswith=f'REM-{year}-'
        ).order_by('-codigo_proyecto').first()
        
        if ultimo:
            # Extraer número y sumar 1
            try:
                numero = int(ultimo.codigo_proyecto.split('-')[-1]) + 1
            except (ValueError, IndexError):
                numero = 1
        else:
            numero = 1
        
        return f'REM-{year}-{numero:03d}'
    
    # ═══════════════════════════════════════════════════════════
    # PROPIEDADES CALCULADAS
    # ═══════════════════════════════════════════════════════════
    
    @property
    def dias_transcurridos(self):
        """Días desde el inicio del proyecto"""
        from django.utils import timezone
        if self.fecha_inicio:
            delta = timezone.now().date() - self.fecha_inicio
            return delta.days
        return 0
    
    @property
    def dias_restantes(self):
        """Días hasta la fecha estimada de fin"""
        from django.utils import timezone
        if self.fecha_fin_estimada:
            delta = self.fecha_fin_estimada - timezone.now().date()
            return delta.days
        return 0
    
    @property
    def duracion_estimada_dias(self):
        """Duración estimada total en días"""
        if self.fecha_inicio and self.fecha_fin_estimada:
            delta = self.fecha_fin_estimada - self.fecha_inicio
            return delta.days
        return 0
    
    @property
    def porcentaje_tiempo_transcurrido(self):
        """Porcentaje del tiempo que ha transcurrido"""
        if self.duracion_estimada_dias > 0:
            return round((self.dias_transcurridos / self.duracion_estimada_dias) * 100, 2)
        return 0
    
    @property
    def presupuesto_disponible(self):
        """Presupuesto restante"""
        return self.presupuesto_asignado - self.presupuesto_gastado
    
    @property
    def porcentaje_presupuesto_gastado(self):
        """Porcentaje del presupuesto consumido"""
        if self.presupuesto_asignado > 0:
            return round((self.presupuesto_gastado / self.presupuesto_asignado) * 100, 2)
        return 0
    
    @property
    def esta_vencido(self):
        """Indica si el proyecto está vencido"""
        from django.utils import timezone
        if self.estado not in ['cerrado', 'cancelado']:
            return self.fecha_fin_estimada < timezone.now().date()
        return False
    
    @property
    def gap_original(self):
        """Obtiene el GAP original que dio origen al proyecto"""
        if self.calculo_nivel:
            return float(self.calculo_nivel.gap)
        return 0
    
    @property
    def dimension_nombre(self):
        """Nombre de la dimensión asociada"""
        if self.calculo_nivel and self.calculo_nivel.dimension:
            return self.calculo_nivel.dimension.nombre
        return "N/A"
    
    @property
    def nivel_deseado_original(self):
        """Nivel deseado del GAP original"""
        if self.calculo_nivel:
            return float(self.calculo_nivel.nivel_deseado)
        return 0
    
    @property
    def nivel_actual_original(self):
        """Nivel actual del GAP original"""
        if self.calculo_nivel:
            return float(self.calculo_nivel.nivel_actual)
        return 0