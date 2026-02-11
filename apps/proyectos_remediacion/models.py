# apps/proyectos_remediacion/models.py

from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Sum
from apps.core.models import BaseModel
from apps.proyectos_remediacion.utils.date_utils import agregar_dias_laborables, calcular_dias_laborables_entre_fechas
from apps.respuestas.models import CalculoNivel
from apps.empresas.models import Empresa
from apps.usuarios.models import Usuario
from apps.encuestas.models import Pregunta
from datetime import date, timedelta
import uuid


class ProyectoCierreBrecha(BaseModel):
    """
    Proyecto de cierre de brecha derivado de análisis GAP
    
    Soporta DOS modos de presupuesto:
    1. GLOBAL: Monto único para todo el proyecto
    2. POR_ITEMS: Desglose en ítems/tareas con presupuesto individual
    """
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 1: INFORMACIÓN BÁSICA
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
        verbose_name='Nombre del Proyecto'
    )
    
    descripcion = models.TextField(
        max_length=1000,
        verbose_name='Descripción del Proyecto'
    )
    
    # ═══ VÍNCULO CON EL GAP ═══
    calculo_nivel = models.ForeignKey(
        'respuestas.CalculoNivel',
        on_delete=models.PROTECT,
        related_name='proyectos_remediacion',
        verbose_name='Brecha GAP Asociada'
    )
    
    # ═══ EMPRESA ═══
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='proyectos_remediacion',
        verbose_name='Empresa'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 2: CLASIFICACIÓN Y PRIORIDAD
    # ═══════════════════════════════════════════════════════════
    
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
    
    PRIORIDADES = [
        ('critica', 'Crítica'),
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    ]
    prioridad = models.CharField(
        max_length=20,
        choices=PRIORIDADES,
        verbose_name='Prioridad',
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
    # SECCIÓN 3: FECHAS
    # ═══════════════════════════════════════════════════════════
    
    fecha_inicio = models.DateField(
        verbose_name='Fecha de Inicio'
    )
    
    fecha_fin_estimada = models.DateField(
        verbose_name='Fecha de Fin Estimada'
    )
    
    fecha_fin_real = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Fin Real'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 4: RESPONSABLES (SIMPLIFICADO)
    # ═══════════════════════════════════════════════════════════
    
    dueno_proyecto = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='proyectos_propietario',
        verbose_name='Dueño del Proyecto',
        help_text='Responsable general del proyecto'
    )
    
    responsable_implementacion = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='proyectos_responsable',
        verbose_name='Responsable de Implementación',
        help_text='Quien ejecuta las tareas'
    )
    
    validador_interno = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proyectos_validador',
        verbose_name='Validador Interno',
        help_text='Quien aprueba el proyecto'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 5: PRESUPUESTO ⭐ NUEVO SISTEMA
    # ═══════════════════════════════════════════════════════════
    
    MODOS_PRESUPUESTO = [
        ('global', 'Presupuesto Global'),
        ('por_items', 'Presupuesto por Ítems'),
    ]
    modo_presupuesto = models.CharField(
        max_length=20,
        choices=MODOS_PRESUPUESTO,
        default='global',
        verbose_name='Modo de Presupuesto',
        help_text='Global: monto único. Por ítems: suma de ítems individuales'
    )
    
    MONEDAS = [
        ('USD', 'USD - Dólar Estadounidense'),
        ('EUR', 'EUR - Euro'),
        ('PEN', 'PEN - Sol Peruano'),
        ('COP', 'COP - Peso Colombiano'),
        ('MXN', 'MXN - Peso Mexicano'),
    ]
    moneda = models.CharField(
        max_length=3,
        choices=MONEDAS,
        default='USD',
        verbose_name='Moneda'
    )
    
    # ═══ PRESUPUESTO GLOBAL (solo si modo_presupuesto='global') ═══
    presupuesto_global = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto Global',
        help_text='Solo aplica si modo_presupuesto = "global"',
        validators=[MinValueValidator(0)]
    )
    
    presupuesto_global_gastado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto Global Gastado',
        validators=[MinValueValidator(0)]
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 6: PLANIFICACIÓN (SIMPLIFICADO)
    # ═══════════════════════════════════════════════════════════
    
    alcance_proyecto = models.TextField(
        verbose_name='Alcance del Proyecto',
        help_text='Qué se incluye y qué no'
    )
    
    objetivos_especificos = models.TextField(
        verbose_name='Objetivos Específicos',
        help_text='Lista de objetivos medibles'
    )
    
    criterios_aceptacion = models.TextField(
        verbose_name='Criterios de Aceptación',
        help_text='Condiciones para dar por cerrado el proyecto'
    )
    
    riesgos_proyecto = models.TextField(
        blank=True,
        verbose_name='Riesgos Identificados',
        help_text='Riesgos que podrían afectar el proyecto'
    )
    
    # ═══ RELACIÓN CON PREGUNTAS ═══
    preguntas_abordadas = models.ManyToManyField(
        'encuestas.Pregunta',
        related_name='proyectos_remediacion',
        blank=True,
        verbose_name='Preguntas Abordadas'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SECCIÓN 7: CIERRE
    # ═══════════════════════════════════════════════════════════
    
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
        verbose_name='Lecciones Aprendidas'
    )
    
    # ═══════════════════════════════════════════════════════════
    # AUDITORÍA
    # ═══════════════════════════════════════════════════════════
    
    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        related_name='proyectos_remediacion_creados',
        verbose_name='Creado Por'
    )
    
    version = models.IntegerField(
        default=1,
        verbose_name='Versión del Proyecto'
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
        Genera código único: REM-{YEAR}-{NUMERO}
        Ejemplo: REM-2025-001
        """
        from django.utils import timezone
        
        year = timezone.now().year
        ultimo = ProyectoCierreBrecha.objects.filter(
            codigo_proyecto__startswith=f'REM-{year}-'
        ).order_by('-codigo_proyecto').first()
        
        if ultimo:
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
        """Días desde el inicio"""
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
    def esta_vencido(self):
        """Indica si el proyecto está vencido"""
        from django.utils import timezone
        if self.estado not in ['cerrado', 'cancelado']:
            return self.fecha_fin_estimada < timezone.now().date()
        return False
    
    @property
    def porcentaje_tiempo_transcurrido(self):
        """Porcentaje del tiempo transcurrido respecto a la duración total"""
        if self.duracion_estimada_dias > 0:
            porcentaje = (self.dias_transcurridos / self.duracion_estimada_dias) * 100
            return min(round(porcentaje, 2), 100)  # Máximo 100%
        return 0
    # ═══════════════════════════════════════════════════════════
    # PROPIEDADES DE PRESUPUESTO (MODO INTELIGENTE)
    # ═══════════════════════════════════════════════════════════
    
    @property
    def presupuesto_total_planificado(self):
        """
        Presupuesto total según el modo:
        - GLOBAL: retorna presupuesto_global
        - POR_ITEMS: suma de presupuestos de ítems
        """
        if self.modo_presupuesto == 'global':
            return self.presupuesto_global
        else:
            # Suma de ítems
            total = self.items.aggregate(
                total=Sum('presupuesto_planificado')
            )['total']
            return total or 0
    
    @property
    def presupuesto_total_ejecutado(self):
        """
        Presupuesto ejecutado según el modo:
        - GLOBAL: retorna presupuesto_global_gastado
        - POR_ITEMS: suma de presupuestos ejecutados de ítems
        """
        if self.modo_presupuesto == 'global':
            return self.presupuesto_global_gastado
        else:
            # Suma de ítems ejecutados
            total = self.items.aggregate(
                total=Sum('presupuesto_ejecutado')
            )['total']
            return total or 0
    
    @property
    def presupuesto_disponible(self):
        """Presupuesto restante"""
        return self.presupuesto_total_planificado - self.presupuesto_total_ejecutado
    
    @property
    def porcentaje_presupuesto_gastado(self):
        """Porcentaje del presupuesto consumido"""
        total = self.presupuesto_total_planificado
        if total > 0:
            return round((self.presupuesto_total_ejecutado / total) * 100, 2)
        return 0
    
    @property
    def total_items(self):
        """Cantidad total de ítems"""
        if self.modo_presupuesto == 'por_items':
            return self.items.count()
        return 0
    
    @property
    def items_completados(self):
        """Cantidad de ítems completados"""
        if self.modo_presupuesto == 'por_items':
            return self.items.filter(estado='completado').count()
        return 0
    
    @property
    def porcentaje_avance_items(self):
        """Porcentaje de avance basado en ítems completados"""
        if self.modo_presupuesto == 'por_items' and self.total_items > 0:
            return round((self.items_completados / self.total_items) * 100, 2)
        return 0
    
    # ═══════════════════════════════════════════════════════════
    # PROPIEDADES DEL GAP
    # ═══════════════════════════════════════════════════════════
    
    @property
    def gap_original(self):
        """GAP original que dio origen al proyecto"""
        if self.calculo_nivel:
            return float(self.calculo_nivel.gap)
        return 0
    
    @property
    def dimension_nombre(self):
        """Nombre de la dimensión asociada"""
        if self.calculo_nivel and self.calculo_nivel.dimension:
            return self.calculo_nivel.dimension.nombre
        return "N/A"


# ═══════════════════════════════════════════════════════════════
# MODELO NUEVO: ItemProyecto (Para Presupuesto por Ítems)
# ═══════════════════════════════════════════════════════════════

class ItemProyecto(BaseModel):
    """
    Ítem/Tarea individual dentro de un proyecto (Modo: por_items)
    
    Permite desglosar el proyecto en tareas con:
    - Presupuesto individual
    - Proveedor opcional
    - Responsable
    - Cronograma (inicio, duración, fin)
    - Dependencias entre ítems
    """
    
    # ═══════════════════════════════════════════════════════════
    # RELACIÓN CON PROYECTO
    # ═══════════════════════════════════════════════════════════
    
    proyecto = models.ForeignKey(
        ProyectoCierreBrecha,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Proyecto'
    )
    
    numero_item = models.IntegerField(
        verbose_name='Número de Ítem',
        help_text='Orden secuencial (1, 2, 3...)'
    )
    
    # ═══════════════════════════════════════════════════════════
    # INFORMACIÓN DEL ÍTEM
    # ═══════════════════════════════════════════════════════════
    
    nombre_item = models.CharField(
        max_length=200,
        verbose_name='Nombre del Ítem',
        help_text='Ej: Adquisición de Licencia de Antivirus'
    )
    
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    # ═══════════════════════════════════════════════════════════
    # PROVEEDOR (OPCIONAL)
    # ═══════════════════════════════════════════════════════════
    
    requiere_proveedor = models.BooleanField(
        default=False,
        verbose_name='¿Requiere Proveedor?'
    )
    
    proveedor = models.ForeignKey(
        'proveedores.Proveedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items_proyecto',
        verbose_name='Proveedor',
        help_text='Solo si requiere_proveedor=True'
    )
    
    nombre_responsable_proveedor = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Responsable del Proveedor',
        help_text='Ej: Responsable de Compras, Gerente Comercial'
    )
    
    # ═══════════════════════════════════════════════════════════
    # RESPONSABLE INTERNO
    # ═══════════════════════════════════════════════════════════
    
    responsable_ejecucion = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='items_responsable',
        verbose_name='Responsable de Ejecución',
        help_text='Quien ejecuta este ítem (Obligatorio)'
    )
    
    # ═══════════════════════════════════════════════════════════
    # PRESUPUESTO
    # ═══════════════════════════════════════════════════════════
    
    presupuesto_planificado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto Planificado',
        validators=[MinValueValidator(0)]
    )
    
    presupuesto_ejecutado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto Ejecutado',
        validators=[MinValueValidator(0)]
    )
    
    # ═══════════════════════════════════════════════════════════
    # CRONOGRAMA
    # ═══════════════════════════════════════════════════════════
    
    fecha_inicio = models.DateField(
        verbose_name='Fecha de Inicio'
    )
    
    duracion_dias = models.IntegerField(
        verbose_name='Duración en Días',
        validators=[MinValueValidator(1)],
        help_text='Días que tomará este ítem'
    )
    
    fecha_fin = models.DateField(
        verbose_name='Fecha de Fin (Calculada)',
        help_text='Se calcula: fecha_inicio + duracion_dias'
    )
    
    # ═══════════════════════════════════════════════════════════
    # DEPENDENCIAS
    # ═══════════════════════════════════════════════════════════
    
    tiene_dependencia = models.BooleanField(
        default=False,
        verbose_name='¿Tiene Dependencia?',
        help_text='Si depende de otro ítem para iniciar'
    )
    
    item_dependencia = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items_dependientes',
        verbose_name='Ítem del que Depende',
        help_text='Solo si tiene_dependencia=True'
    )
    
    # ═══════════════════════════════════════════════════════════
    # SEGUIMIENTO
    # ═══════════════════════════════════════════════════════════
    
    ESTADOS_ITEM = [
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En Proceso'),
        ('completado', 'Completado'),
        ('bloqueado', 'Bloqueado por Dependencia'),
    ]
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_ITEM,
        default='pendiente',
        verbose_name='Estado del Ítem'
    )
    
    porcentaje_avance = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Avance (%)'
    )
    
    fecha_completado = models.DateField(
    null=True,
    blank=True,
    verbose_name='Fecha de Completado',
    help_text='Fecha en que el ítem fue marcado como completado'
    )
    observaciones = models.TextField(
    blank=True,
    verbose_name='Observaciones'
    )
    
    class Meta:
        db_table = 'items_proyecto'
        verbose_name = 'Ítem de Proyecto'
        verbose_name_plural = 'Ítems de Proyecto'
        ordering = ['proyecto', 'numero_item']
        unique_together = [['proyecto', 'numero_item']]
        indexes = [
            models.Index(fields=['proyecto', 'estado']),
            models.Index(fields=['responsable_ejecucion']),
        ]
    
    def __str__(self):
        return f"{self.numero_item}. {self.nombre_item}"
    
    def save(self, *args, **kwargs):
        """Calcular fecha_fin automáticamente"""
        if self.fecha_inicio and self.duracion_dias:
            self.fecha_fin = self.fecha_inicio + timedelta(days=self.duracion_dias)
        super().save(*args, **kwargs)
    
    # ═══════════════════════════════════════════════════════════
    # PROPIEDADES CALCULADAS
    # ═══════════════════════════════════════════════════════════
    
    @property
    def diferencia_presupuesto(self):
        """Diferencia entre ejecutado y planificado"""
        return self.presupuesto_ejecutado - self.presupuesto_planificado
    
    @property
    def puede_iniciar(self):
        """Validar si puede iniciar (dependencias completadas)"""
        if not self.tiene_dependencia:
            return True
        
        if self.item_dependencia:
            return self.item_dependencia.estado == 'completado'
        
        return False
    
    @property
    def dias_restantes(self):
        """Días restantes para completar el ítem"""
        from django.utils import timezone
        if self.fecha_fin:
            delta = self.fecha_fin - timezone.now().date()
            return delta.days
        return 0
    
    @property
    def esta_vencido(self):
        """Indica si el ítem está vencido"""
        from django.utils import timezone
        if self.estado not in ['completado']:
            return self.fecha_fin < timezone.now().date()
        return False
    
    @property
    def fecha_fin_estimada(self) -> date:
        """
        Calcula la fecha de fin estimada basándose en días laborables.
        Excluye sábados y domingos.
        """
        if not self.fecha_inicio or not self.duracion_dias:
            return self.fecha_inicio
        
        return agregar_dias_laborables(self.fecha_inicio, self.duracion_dias)
    
    @property
    def fecha_fin_real(self) -> date:
        """
        Fecha de finalización real del ítem (cuando se completó).
        Si aún no está completado, retorna None.
        """
        if self.estado == 'completado' and self.fecha_completado:
            return self.fecha_completado
        return None
    
    @property
    def dias_laborables_transcurridos(self) -> int:
        """
        Días laborables transcurridos desde el inicio.
        """
        if not self.fecha_inicio:
            return 0
        
        hoy = date.today()
        
        # Si ya se completó, usar fecha de completado
        if self.fecha_completado:
            fecha_fin = self.fecha_completado
        else:
            fecha_fin = hoy
        
        return calcular_dias_laborables_entre_fechas(self.fecha_inicio, fecha_fin)
    
    @property
    def dias_laborables_restantes(self) -> int:
        """
        Días laborables restantes hasta la fecha fin estimada.
        """
        if not self.fecha_inicio or not self.duracion_dias:
            return 0
        
        hoy = date.today()
        fecha_fin = self.fecha_fin_estimada
        
        if hoy >= fecha_fin:
            return 0
        
        return calcular_dias_laborables_entre_fechas(hoy, fecha_fin)
    
    @property
    def esta_retrasado(self) -> bool:
        """
        Verifica si el ítem está retrasado (pasó la fecha estimada y no está completado).
        """
        if self.estado == 'completado':
            return False
        
        if not self.fecha_inicio or not self.duracion_dias:
            return False
        
        return date.today() > self.fecha_fin_estimada
    
    # ═══════════════════════════════════════════════════════════════
    # ELASTICIDAD DE PRESUPUESTO (10%)
    # ═══════════════════════════════════════════════════════════════
    
    @property
    def presupuesto_elasticidad(self) -> Decimal:
        """
        Margen de elasticidad del presupuesto (10% del presupuesto planificado).
        """
        return self.presupuesto_planificado * Decimal('0.10')
    
    @property
    def presupuesto_limite(self) -> Decimal:
        """
        Límite máximo de presupuesto permitido (presupuesto + elasticidad).
        """
        return self.presupuesto_planificado + self.presupuesto_elasticidad
    
    @property
    def porcentaje_presupuesto_usado(self) -> float:
        """
        Porcentaje del presupuesto planificado que se ha utilizado.
        """
        if self.presupuesto_planificado <= 0:
            return 0.0
        
        return float((self.presupuesto_ejecutado / self.presupuesto_planificado) * 100)
    
    @property
    def esta_en_elasticidad(self) -> bool:
        """
        Verifica si el gasto está dentro del margen de elasticidad (100-110%).
        """
        return (
            self.presupuesto_ejecutado > self.presupuesto_planificado and
            self.presupuesto_ejecutado <= self.presupuesto_limite
        )
    
    @property
    def excede_presupuesto_limite(self) -> bool:
        """
        Verifica si el gasto ejecutado excede el límite permitido (>110%).
        """
        return self.presupuesto_ejecutado > self.presupuesto_limite
    
    @property
    def monto_excedido(self) -> Decimal:
        """
        Monto que excede el límite de presupuesto.
        Retorna 0 si no excede.
        """
        if self.excede_presupuesto_limite:
            return self.presupuesto_ejecutado - self.presupuesto_limite
        return Decimal('0.00')
    
    @property
    def estado_presupuesto(self) -> str:
        """
        Estado del presupuesto del ítem:
        - 'ok': Dentro del presupuesto planificado (< 100%)
        - 'elasticidad': En margen de elasticidad (100-110%)
        - 'excedido': Excede el límite (> 110%)
        """
        if self.excede_presupuesto_limite:
            return 'excedido'
        elif self.esta_en_elasticidad:
            return 'elasticidad'
        else:
            return 'ok'
    
    def __str__(self):
        return f"#{self.numero_item} - {self.nombre_item} ({self.proyecto.codigo_proyecto})"
    
    class Meta:
        verbose_name = 'Ítem de Proyecto'
        verbose_name_plural = 'Ítems de Proyecto'
        ordering = ['proyecto', 'numero_item']
        constraints = [
            models.UniqueConstraint(
                fields=['proyecto', 'numero_item'],
                name='unique_numero_item_por_proyecto'
            )
        ]
        

class AprobacionGAP(BaseModel):
    """
    Modelo para gestionar el workflow de aprobación de cierre de GAP.
    
    Cuando un proyecto de remediación se completa, el responsable solicita
    la aprobación. El validador (dueño de evaluación o validador interno)
    puede aprobar o rechazar el cierre del GAP.
    """
    
    ESTADOS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    
    # ═══ RELACIONES ═══
    proyecto = models.ForeignKey(
        ProyectoCierreBrecha,
        on_delete=models.CASCADE,
        related_name='aprobaciones',
        verbose_name='Proyecto'
    )
    
    solicitado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='aprobaciones_solicitadas',
        verbose_name='Solicitado por'
    )
    
    validador = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='aprobaciones_asignadas',
        verbose_name='Validador',
        help_text='Usuario que debe aprobar o rechazar'
    )
    
    # ═══ DATOS DE LA SOLICITUD ═══
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de solicitud'
    )
    
    comentarios_solicitud = models.TextField(
        blank=True,
        verbose_name='Comentarios de la solicitud',
        help_text='Comentarios del responsable al solicitar la aprobación'
    )
    
    # ═══ DATOS DE LA REVISIÓN ═══
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_CHOICES,
        default='pendiente',
        verbose_name='Estado'
    )
    
    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de revisión'
    )
    
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
        help_text='Observaciones del validador (requerido si rechaza)'
    )
    
    # ═══ EVIDENCIAS ═══
    documentos_adjuntos = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Documentos adjuntos',
        help_text='Lista de URLs de documentos de evidencia'
    )
    
    # ═══ MÉTRICAS AL MOMENTO DE LA SOLICITUD ═══
    items_completados = models.IntegerField(
        default=0,
        verbose_name='Ítems completados'
    )
    
    items_totales = models.IntegerField(
        default=0,
        verbose_name='Ítems totales'
    )
    
    presupuesto_ejecutado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto ejecutado'
    )
    
    presupuesto_planificado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Presupuesto planificado'
    )
    
    gap_original = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='GAP original'
    )
    
    # ═══ PROPIEDADES CALCULADAS ═══
    
    @property
    def esta_pendiente(self) -> bool:
        """Verifica si la aprobación está pendiente"""
        return self.estado == 'pendiente'
    
    @property
    def fue_aprobado(self) -> bool:
        """Verifica si fue aprobado"""
        return self.estado == 'aprobado'
    
    @property
    def fue_rechazado(self) -> bool:
        """Verifica si fue rechazado"""
        return self.estado == 'rechazado'
    
    @property
    def dias_pendiente(self) -> int:
        """Días que lleva pendiente de revisión"""
        if self.estado != 'pendiente':
            return 0
        
        from datetime import datetime
        from django.utils import timezone
        
        ahora = timezone.now()
        delta = ahora - self.fecha_solicitud
        return delta.days
    
    @property
    def porcentaje_completitud(self) -> float:
        """Porcentaje de ítems completados"""
        if self.items_totales == 0:
            return 0.0
        return (self.items_completados / self.items_totales) * 100
    
    @property
    def porcentaje_presupuesto_usado(self) -> float:
        """Porcentaje del presupuesto utilizado"""
        if self.presupuesto_planificado == 0:
            return 0.0
        return float((self.presupuesto_ejecutado / self.presupuesto_planificado) * 100)
    
    def __str__(self):
        return f"Aprobación {self.proyecto.codigo_proyecto} - {self.get_estado_display()}"
    
    class Meta:
        verbose_name = 'Aprobación de GAP'
        verbose_name_plural = 'Aprobaciones de GAP'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado', 'fecha_solicitud']),
            models.Index(fields=['validador', 'estado']),
        ]