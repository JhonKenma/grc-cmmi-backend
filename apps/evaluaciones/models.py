# apps/evaluaciones/models.py
"""
MODELOS PARA SISTEMA DE EVALUACIONES INTELIGENTES
Versión corregida - Sin límites en campos de texto largos
"""

from django.db import models
from django.contrib.auth import get_user_model
from apps.empresas.models import Empresa

User = get_user_model()


# ============================================================================
# MODELOS BASE: FRAMEWORKS Y PREGUNTAS
# ============================================================================

class Framework(models.Model):
    """
    Framework de evaluación
    Ejemplo: ISO 27001 - SGSI, ISO 27701, DAMA DMBOK, etc.
    """
    
    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código',
        help_text='Código único (ISO27001, ISO27701, DAMADMBOK)'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre',
        help_text='Ejemplo: ISO 27001 - SGSI'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    version = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Versión'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Actualización'
    )
    
    class Meta:
        db_table = 'frameworks'
        verbose_name = 'Framework'
        verbose_name_plural = 'Frameworks'
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class PreguntaEvaluacion(models.Model):
    """
    Pregunta de evaluación - Mapeo directo de las filas del Excel
    
    Estructura del Excel:
    - Correlativo: Número único de pregunta
    - Framework Base: ISO 27001, ISO 27701, etc.
    - Código Control: A.5.1, 5.1, DG-01, etc.
    - Sección General: Categoría del control
    - Nombre del Control: Título del control
    - Tags: Etiquetas para búsqueda
    - Frameworks Referenciales: CAMPO CLAVE (relaciones)
    - Objetivo: Qué se evalúa
    - Pregunta: Pregunta exhaustiva
    - Evidencias: 5 evidencias en filas siguientes
    - Nivel Madurez: 1-5
    """
    
    NIVEL_MADUREZ_CHOICES = [
        (1, 'Nivel 1 - Inicial'),
        (2, 'Nivel 2 - Gestionado'),
        (3, 'Nivel 3 - Definido'),
        (4, 'Nivel 4 - Gestionado Cuantitativamente'),
        (5, 'Nivel 5 - Optimizado'),
    ]
    
    # Columna A: Correlativo
    correlativo = models.IntegerField(
        verbose_name='Correlativo',
        help_text='Número único de pregunta en el Excel'
    )
    
    # Columna B: Framework Base
    framework = models.ForeignKey(
        Framework,
        on_delete=models.CASCADE,
        related_name='preguntas',
        verbose_name='Framework Base'
    )
    
    # ⭐ NUEVO: Nombre completo del framework base (del Excel)
    framework_base_nombre = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Framework Base Nombre',
        help_text='Ejemplo: ISO 27001 - SGSI, ISO 42001:2023 AIMS'
    )
    
    # Columna C: Código Control / Referencia
    # ✅ CORREGIDO: Aumentado de 50 a 100
    codigo_control = models.CharField(
        max_length=100,
        verbose_name='Código Control',
        help_text='Ejemplo: A.5.1, 5.1, DG-01'
    )
    
    # Columna D: Sección General o Tema del Control
    seccion_general = models.CharField(
        max_length=500,
        verbose_name='Sección General',
        help_text='Categoría o tema del control'
    )
    
    # Columna E: Nombre del Control
    # ✅ CORREGIDO: De CharField(500) a TextField
    nombre_control = models.TextField(
        verbose_name='Nombre del Control'
    )
    
    # Columna F: Etiquetas Contextuales Unificadas (Tags)
    # ✅ CORREGIDO: De CharField(500) a TextField
    tags = models.TextField(
        blank=True,
        verbose_name='Tags',
        help_text='Etiquetas separadas por comas'
    )
    
    # Columna G: Frameworks y Controles Referenciales
    # ESTE ES EL CAMPO MÁS IMPORTANTE
    frameworks_referenciales = models.TextField(
        blank=True,
        verbose_name='Frameworks y Controles Referenciales',
        help_text='Ejemplo: ISO 27001:2022:5.1, COBIT 2019:APO01.01'
    )
    
    # Columna H: Objetivo de Evaluación Basado en Etiquetas
    objetivo_evaluacion = models.TextField(
        verbose_name='Objetivo de Evaluación',
        help_text='Qué se busca verificar con esta pregunta'
    )
    
    # Columna I: Pregunta de evaluación bien exhaustiva
    pregunta = models.TextField(
        verbose_name='Pregunta de Evaluación',
        help_text='Pregunta detallada y exhaustiva'
    )
    
    # Columna K: Nivel de Madurez de la Pregunta
    nivel_madurez = models.IntegerField(
        choices=NIVEL_MADUREZ_CHOICES,
        verbose_name='Nivel de Madurez'
    )
    
    # Campos adicionales de control
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Actualización'
    )
    
    class Meta:
        db_table = 'preguntas_evaluacion'
        verbose_name = 'Pregunta de Evaluación'
        verbose_name_plural = 'Preguntas de Evaluación'
        unique_together = ['framework', 'correlativo']
        ordering = ['framework', 'correlativo']
        indexes = [
            models.Index(fields=['framework', 'correlativo']),
            models.Index(fields=['codigo_control']),
            models.Index(fields=['nivel_madurez']),
        ]
    
    def __str__(self):
        return f"#{self.correlativo} - {self.framework.codigo} {self.codigo_control}"


class EvidenciaRequerida(models.Model):
    """
    Evidencias requeridas para cada pregunta
    
    Columna J: Mínimo 5 Evidencias Tipo Aceptadas para Evaluación
    
    En el Excel, las 5 evidencias están en las siguientes 5 filas
    después de la pregunta principal.
    """
    
    pregunta = models.ForeignKey(
        PreguntaEvaluacion,
        on_delete=models.CASCADE,
        related_name='evidencias_requeridas',
        verbose_name='Pregunta'
    )
    
    # Columna J: Texto de la evidencia
    # ✅ CORREGIDO: De CharField(500) a TextField
    descripcion = models.TextField(
        verbose_name='Descripción de la Evidencia',
        help_text='Ejemplo: 1. Documento formal de políticas...'
    )
    
    # Orden de la evidencia (1-5)
    orden = models.IntegerField(
        verbose_name='Orden',
        help_text='Número de evidencia (1-5)'
    )
    
    class Meta:
        db_table = 'evidencias_requeridas'
        verbose_name = 'Evidencia Requerida'
        verbose_name_plural = 'Evidencias Requeridas'
        ordering = ['pregunta', 'orden']
        unique_together = ['pregunta', 'orden']
    
    def __str__(self):
        return f"Pregunta {self.pregunta.correlativo} - Evidencia {self.orden}"


class RelacionFramework(models.Model):
    """
    MODELO CLAVE: Relaciones entre frameworks
    
    Parsea el campo "Frameworks y Controles Referenciales" y crea
    relaciones estructuradas entre preguntas de diferentes frameworks.
    
    Ejemplo del campo original:
    "ISO 27001:2022:5.1, COBIT 2019:APO01.01, TOGAF:Business Principles"
    
    Se convierte en 3 registros:
    1. pregunta_origen=ISO27701 5.1 → framework_destino=ISO27001
    2. pregunta_origen=ISO27701 5.1 → framework_destino=COBIT2019
    3. pregunta_origen=ISO27701 5.1 → framework_destino=TOGAF
    """
    
    pregunta_origen = models.ForeignKey(
        PreguntaEvaluacion,
        on_delete=models.CASCADE,
        related_name='relaciones_frameworks',
        verbose_name='Pregunta Origen',
        help_text='Pregunta que referencia a otros frameworks'
    )
    
    # Framework al que se hace referencia (parseado)
    framework_destino = models.ForeignKey(
        Framework,
        on_delete=models.CASCADE,
        related_name='referencias_desde_otros',
        verbose_name='Framework Destino',
        help_text='Framework referenciado'
    )
    
    # Texto original completo de la referencia
    # ✅ CORREGIDO: Aumentado de 300 a 1000
    referencia_textual = models.CharField(
        max_length=1000,
        verbose_name='Referencia Textual',
        help_text='Ejemplo: ISO 27001:2022:5.1 o COBIT 2019:APO01.01'
    )
    
    # Componentes parseados de la referencia
    # ✅ CORREGIDO: Aumentado de 100 a 200
    codigo_control_referenciado = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Código Control Referenciado',
        help_text='Ejemplo: 5.1, APO01.01, Business Principles'
    )
    
    porcentaje_cobertura = models.IntegerField(
        default=100,
        verbose_name='Porcentaje de Cobertura',
        help_text='Qué tanto esta pregunta cubre la referencia (0-100)'
    )
    
    class Meta:
        db_table = 'relaciones_frameworks'
        verbose_name = 'Relación entre Frameworks'
        verbose_name_plural = 'Relaciones entre Frameworks'
        unique_together = ['pregunta_origen', 'referencia_textual']
        indexes = [
            models.Index(fields=['pregunta_origen']),
            models.Index(fields=['framework_destino']),
        ]
    
    def __str__(self):
        return f"{self.pregunta_origen.framework.codigo} → {self.framework_destino.codigo}: {self.referencia_textual}"

class EmpresaFramework(models.Model):
    """
    Asignación de un Framework a una Empresa.
    El SuperAdmin decide qué frameworks tiene disponibles cada empresa.
    Un mismo framework puede asignarse a múltiples empresas (no exclusivo).
    """

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='frameworks_asignados',
        verbose_name='Empresa'
    )
    framework = models.ForeignKey(
        Framework,
        on_delete=models.CASCADE,
        related_name='empresas_asignadas',
        verbose_name='Framework'
    )
    asignado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='frameworks_asignados_por_mi',
        verbose_name='Asignado por'
    )
    fecha_asignacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Asignación'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    notas = models.TextField(
        blank=True,
        verbose_name='Notas'
    )

    class Meta:
        db_table = 'empresa_frameworks'
        verbose_name = 'Framework Asignado a Empresa'
        verbose_name_plural = 'Frameworks Asignados a Empresas'
        unique_together = ['empresa', 'framework']
        ordering = ['empresa', 'framework']
        indexes = [
            models.Index(fields=['empresa', 'activo']),
            models.Index(fields=['framework']),
        ]

    def __str__(self):
        return f"{self.empresa.nombre} → {self.framework.codigo}"
# ============================================================================
# MODELOS DE EVALUACIÓN
# ============================================================================

class Evaluacion(models.Model):
    """
    Evaluación creada por el Admin de una Empresa.

    - El Admin usa los frameworks que el SuperAdmin le asignó a su empresa.
    - Define un nivel deseado (meta que quiere alcanzar: 1-5).
    - Puede usar todas las preguntas de los frameworks o seleccionar.
    - Puede combinar múltiples frameworks.
    """

    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),      # Creada, lista para usar
        ('configurando', 'Configurando'),   # Seleccionando preguntas manualmente
        ('en_proceso', 'En Proceso'),       # Usuarios respondiendo
        ('completada', 'Completada'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    NIVEL_DESEADO_CHOICES = [
        (1, 'Nivel 1 - Inicial'),
        (2, 'Nivel 2 - Gestionado'),
        (3, 'Nivel 3 - Definido'),
        (4, 'Nivel 4 - Cuantitativamente Gestionado'),
        (5, 'Nivel 5 - Optimizado'),
    ]

    # ⭐ EMPRESA: obligatorio, la evaluación pertenece a una empresa
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='evaluaciones_inteligentes',
        verbose_name='Empresa',
        help_text='Empresa dueña de esta evaluación'
    )

    frameworks = models.ManyToManyField(
        Framework,
        related_name='evaluaciones',
        verbose_name='Frameworks',
        help_text='Frameworks incluidos (deben estar asignados a la empresa)'
    )

    nombre = models.CharField(
        max_length=300,
        verbose_name='Nombre de la Evaluación'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )

    # ⭐ NIVEL DESEADO: meta que quiere alcanzar la empresa
    nivel_deseado = models.IntegerField(
        choices=NIVEL_DESEADO_CHOICES,
        default=3,
        verbose_name='Nivel Deseado',
        help_text='Nivel de madurez que la empresa quiere alcanzar con esta evaluación'
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='disponible',
        verbose_name='Estado'
    )

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='evaluaciones_inteligentes_creadas',
        verbose_name='Creado por'
    )

    usar_todas_preguntas = models.BooleanField(
        default=True,
        verbose_name='Usar Todas las Preguntas',
        help_text='True = todas las preguntas de los frameworks. False = selección manual.'
    )

    usar_respuestas_compartidas = models.BooleanField(
        default=True,
        verbose_name='Usar Respuestas Compartidas',
        help_text='Si es True, las respuestas se propagan automáticamente entre preguntas relacionadas'
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Actualización'
    )

    class Meta:
        db_table = 'evaluaciones'
        verbose_name = 'Evaluación'
        verbose_name_plural = 'Evaluaciones'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"

    def get_preguntas_a_responder(self):
        """Retorna las preguntas que deben responderse en esta evaluación"""
        if self.usar_todas_preguntas:
            return PreguntaEvaluacion.objects.filter(
                framework__in=self.frameworks.all(),
                activo=True
            ).select_related('framework')
        else:
            return PreguntaEvaluacion.objects.filter(
                en_evaluaciones__evaluacion=self,
                activo=True
            ).order_by('en_evaluaciones__orden').select_related('framework')

    @property
    def total_preguntas(self):
        return self.get_preguntas_a_responder().count()

    @property
    def puede_asignar(self):
        if self.usar_todas_preguntas:
            return True
        return self.total_preguntas > 0

    def save(self, *args, **kwargs):
        # Al crear: si selección manual → estado configurando
        if not self.pk and not self.usar_todas_preguntas:
            self.estado = 'configurando'
        super().save(*args, **kwargs)




class EvaluacionPregunta(models.Model):
    """
    Preguntas seleccionadas manualmente para una evaluación
    
    Solo se usa cuando Evaluacion.usar_todas_preguntas = False
    
    Permite:
    - Seleccionar preguntas específicas de diferentes frameworks
    - Establecer orden personalizado de preguntas
    - Crear evaluaciones "a medida"
    
    Ejemplo:
    - Evaluación con 50 preguntas de ISO 27001 + 30 de DAMA DMBOK
    - Solo preguntas de nivel 4 y 5
    - Ordenadas por sección
    """
    
    evaluacion = models.ForeignKey(
        Evaluacion,
        on_delete=models.CASCADE,
        related_name='preguntas_seleccionadas',
        verbose_name='Evaluación'
    )
    
    pregunta = models.ForeignKey(
        PreguntaEvaluacion,
        on_delete=models.CASCADE,
        related_name='en_evaluaciones',
        verbose_name='Pregunta'
    )
    
    orden = models.IntegerField(
        verbose_name='Orden',
        help_text='Orden de la pregunta en esta evaluación (1, 2, 3...)'
    )
    
    fecha_agregada = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha Agregada'
    )
    
    class Meta:
        db_table = 'evaluacion_preguntas'
        verbose_name = 'Pregunta en Evaluación'
        verbose_name_plural = 'Preguntas en Evaluaciones'
        unique_together = ['evaluacion', 'pregunta']
        ordering = ['evaluacion', 'orden']
        indexes = [
            models.Index(fields=['evaluacion', 'orden']),
        ]
    
    def __str__(self):
        return f"{self.evaluacion.nombre} - Pregunta {self.orden}: {self.pregunta.codigo_control}"


class RespuestaEvaluacion(models.Model):
    """
    Respuesta del usuario a una pregunta de evaluación
    """
    
    RESPUESTA_CHOICES = [
        ('cumple', 'Cumple Totalmente'),
        ('cumple_parcial', 'Cumple Parcialmente'),
        ('no_cumple', 'No Cumple'),
        ('no_aplica', 'No Aplica'),
        ('en_progreso', 'En Progreso'),
    ]
    
    evaluacion = models.ForeignKey(
        Evaluacion,
        on_delete=models.CASCADE,
        related_name='respuestas',
        verbose_name='Evaluación'
    )
    pregunta = models.ForeignKey(
        PreguntaEvaluacion,
        on_delete=models.CASCADE,
        related_name='respuestas',
        verbose_name='Pregunta'
    )
    
    respuesta = models.CharField(
        max_length=20,
        choices=RESPUESTA_CHOICES,
        verbose_name='Respuesta'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    
    es_respuesta_original = models.BooleanField(
        default=True,
        verbose_name='Es Respuesta Original'
    )
    heredada_de = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='respuestas_heredadas',
        verbose_name='Heredada De'
    )
    
    fecha_respuesta = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Respuesta'
    )
    respondido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='respuestas_evaluaciones_dadas',
        verbose_name='Respondido Por'
    )
    
    class Meta:
        db_table = 'respuestas_evaluacion'
        verbose_name = 'Respuesta de Evaluación'
        verbose_name_plural = 'Respuestas de Evaluación'
        unique_together = ['evaluacion', 'pregunta']
        ordering = ['-fecha_respuesta']
    
    def __str__(self):
        return f"{self.evaluacion.nombre} - Pregunta {self.pregunta.correlativo}"


class NotaEvidencia(models.Model):
    """
    Notas/Sugerencias del usuario sobre las evidencias
    (NO archivos, solo texto según indicación del jefe)
    """
    
    respuesta = models.ForeignKey(
        RespuestaEvaluacion,
        on_delete=models.CASCADE,
        related_name='notas_evidencias',
        verbose_name='Respuesta'
    )
    evidencia_requerida = models.ForeignKey(
        EvidenciaRequerida,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='notas_usuario',
        verbose_name='Evidencia Requerida'
    )
    
    nota = models.TextField(
        verbose_name='Nota/Sugerencia',
        help_text='Descripción de cómo se cumple con esta evidencia'
    )
    referencia_documento = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Referencia a Documento',
        help_text='Ej: POL-SEG-001, PROC-GRC-002'
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de Actualización'
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notas_evidencias_creadas',
        verbose_name='Creado Por'
    )
    
    class Meta:
        db_table = 'notas_evidencias'
        verbose_name = 'Nota de Evidencia'
        verbose_name_plural = 'Notas de Evidencias'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Nota - Pregunta {self.respuesta.pregunta.correlativo}"


class ComentarioEvaluacion(models.Model):
    """
    Comentarios colaborativos sobre evaluaciones
    """
    
    evaluacion = models.ForeignKey(
        Evaluacion,
        on_delete=models.CASCADE,
        related_name='comentarios',
        verbose_name='Evaluación'
    )
    respuesta = models.ForeignKey(
        RespuestaEvaluacion,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='comentarios',
        verbose_name='Respuesta'
    )
    
    comentario = models.TextField(
        verbose_name='Comentario'
    )
    es_interno = models.BooleanField(
        default=False,
        verbose_name='Es Interno'
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='comentarios_evaluaciones_creados',
        verbose_name='Creado Por'
    )
    
    class Meta:
        db_table = 'comentarios_evaluacion'
        verbose_name = 'Comentario de Evaluación'
        verbose_name_plural = 'Comentarios de Evaluación'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Comentario en {self.evaluacion.nombre}"