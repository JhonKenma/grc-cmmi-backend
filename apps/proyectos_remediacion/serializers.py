# apps/proyectos_remediacion/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import date

from .models import ProyectoCierreBrecha
from apps.respuestas.models import CalculoNivel
from apps.empresas.models import Empresa
from apps.usuarios.models import Usuario
from apps.encuestas.models import Pregunta, Dimension
from apps.empresas.serializers import EmpresaSerializer
from apps.usuarios.serializers import UsuarioListSerializer


# ═══════════════════════════════════════════════════════════════
# SERIALIZERS DE LECTURA (Para mostrar datos completos)
# ═══════════════════════════════════════════════════════════════

class ProyectoCierreBrechaListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para LISTADO de proyectos
    Incluye solo campos esenciales para vistas de lista
    """
    
    # Información de la empresa
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    
    # Información del GAP
    dimension_nombre = serializers.CharField(source='calculo_nivel.dimension.nombre', read_only=True)
    gap_original = serializers.DecimalField(source='calculo_nivel.gap', max_digits=3, decimal_places=1, read_only=True)
    
    # Responsables
    dueno_nombre = serializers.CharField(source='dueno_proyecto.nombre_completo', read_only=True)
    responsable_nombre = serializers.CharField(source='responsable_implementacion.nombre_completo', read_only=True)
    
    # Estados display
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)
    
    # Campos calculados
    dias_restantes = serializers.ReadOnlyField()
    dias_transcurridos = serializers.ReadOnlyField()
    esta_vencido = serializers.ReadOnlyField()
    porcentaje_presupuesto_gastado = serializers.ReadOnlyField()
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = [
            'id',
            'codigo_proyecto',
            'nombre_proyecto',
            'empresa',
            'empresa_nombre',
            'dimension_nombre',
            'gap_original',
            'estado',
            'estado_display',
            'prioridad',
            'prioridad_display',
            'categoria',
            'categoria_display',
            'dueno_nombre',
            'responsable_nombre',
            'fecha_inicio',
            'fecha_fin_estimada',
            'dias_restantes',
            'dias_transcurridos',
            'esta_vencido',
            'presupuesto_asignado',
            'presupuesto_gastado',
            'porcentaje_presupuesto_gastado',
            'moneda',
            'fecha_creacion',
        ]


class ProyectoCierreBrechaDetailSerializer(serializers.ModelSerializer):
    """
    Serializer COMPLETO para DETALLE de un proyecto
    Incluye TODOS los campos y relaciones
    """
    
    # ═══ INFORMACIÓN DE RELACIONES ═══
    empresa_info = EmpresaSerializer(source='empresa', read_only=True)
    
    # GAP original
    calculo_nivel_info = serializers.SerializerMethodField()
    
    # Responsables
    dueno_proyecto_info = UsuarioListSerializer(source='dueno_proyecto', read_only=True)
    responsable_implementacion_info = UsuarioListSerializer(source='responsable_implementacion', read_only=True)
    equipo_implementacion_info = UsuarioListSerializer(source='equipo_implementacion', many=True, read_only=True)
    validador_interno_info = UsuarioListSerializer(source='validador_interno', read_only=True)
    auditor_verificacion_info = UsuarioListSerializer(source='auditor_verificacion', read_only=True)
    responsable_validacion_info = UsuarioListSerializer(source='responsable_validacion', read_only=True)
    creado_por_info = UsuarioListSerializer(source='creado_por', read_only=True)
    
    # Preguntas abordadas
    preguntas_abordadas_info = serializers.SerializerMethodField()
    
    # Estados display
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)
    normativa_display = serializers.CharField(source='get_normativa_display', read_only=True)
    tipo_brecha_display = serializers.CharField(source='get_tipo_brecha_display', read_only=True)
    estrategia_cierre_display = serializers.CharField(source='get_estrategia_cierre_display', read_only=True)
    frecuencia_reporte_display = serializers.CharField(source='get_frecuencia_reporte_display', read_only=True)
    canal_comunicacion_display = serializers.CharField(source='get_canal_comunicacion_display', read_only=True)
    metodo_verificacion_display = serializers.CharField(source='get_metodo_verificacion_display', read_only=True)
    resultado_final_display = serializers.CharField(source='get_resultado_final_display', read_only=True)
    moneda_display = serializers.CharField(source='get_moneda_display', read_only=True)
    
    # Campos calculados
    dias_restantes = serializers.ReadOnlyField()
    dias_transcurridos = serializers.ReadOnlyField()
    duracion_estimada_dias = serializers.ReadOnlyField()
    porcentaje_tiempo_transcurrido = serializers.ReadOnlyField()
    presupuesto_disponible = serializers.ReadOnlyField()
    porcentaje_presupuesto_gastado = serializers.ReadOnlyField()
    esta_vencido = serializers.ReadOnlyField()
    gap_original = serializers.ReadOnlyField()
    dimension_nombre = serializers.ReadOnlyField()
    nivel_deseado_original = serializers.ReadOnlyField()
    nivel_actual_original = serializers.ReadOnlyField()
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = '__all__'
    
    def get_calculo_nivel_info(self, obj):
        """Información del GAP original"""
        if obj.calculo_nivel:
            return {
                'id': str(obj.calculo_nivel.id),
                'dimension': obj.calculo_nivel.dimension.nombre,
                'dimension_codigo': obj.calculo_nivel.dimension.codigo,
                'nivel_deseado': float(obj.calculo_nivel.nivel_deseado),
                'nivel_actual': float(obj.calculo_nivel.nivel_actual),
                'gap': float(obj.calculo_nivel.gap),
                'clasificacion_gap': obj.calculo_nivel.clasificacion_gap,
                'clasificacion_gap_display': obj.calculo_nivel.get_clasificacion_gap_display(),
                'porcentaje_cumplimiento': float(obj.calculo_nivel.porcentaje_cumplimiento),
                'calculado_at': obj.calculo_nivel.calculado_at,
            }
        return None
    
    def get_preguntas_abordadas_info(self, obj):
        """Información de las preguntas que aborda este proyecto"""
        preguntas = obj.preguntas_abordadas.filter(activo=True)
        return [
            {
                'id': str(p.id),
                'codigo': p.codigo,
                'titulo': p.titulo,
                'texto': p.texto,
                'dimension': p.dimension.nombre,
            }
            for p in preguntas
        ]


# ═══════════════════════════════════════════════════════════════
# SERIALIZERS DE ESCRITURA (Para crear/actualizar proyectos)
# ═══════════════════════════════════════════════════════════════

class ProyectoCierreBrechaCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para CREAR un nuevo proyecto de remediación
    
    Validaciones:
    - Solo Admin o SuperAdmin pueden crear
    - El GAP debe existir y pertenecer a la empresa
    - Fechas deben ser coherentes
    - Responsables deben pertenecer a la empresa
    - Presupuesto debe ser positivo
    """
    
    # ⭐ CAMPO ESPECIAL: Permitir seleccionar preguntas específicas (opcional)
    preguntas_abordadas_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text='IDs de preguntas específicas que aborda este proyecto (opcional)'
    )
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = [
            # Sección 1: Básico
            'nombre_proyecto',
            'descripcion',
            'calculo_nivel',
            'fecha_inicio',
            'fecha_fin_estimada',
            'prioridad',
            'categoria',
            
            # Sección 2: Brecha
            'normativa',
            'control_no_conforme',
            'tipo_brecha',
            'nivel_criticidad_original',
            'impacto_riesgo',
            'evidencia_no_conformidad',
            'fecha_identificacion_gap',
            
            # Sección 3: Planificación
            'estrategia_cierre',
            'alcance_proyecto',
            'objetivos_especificos',
            'criterios_aceptacion',
            'supuestos',
            'restricciones',
            'riesgos_proyecto',
            'preguntas_abordadas_ids',  # ⭐ Campo especial
            
            # Sección 4: Responsables
            'dueno_proyecto',
            'responsable_implementacion',
            'equipo_implementacion',
            'validador_interno',
            'auditor_verificacion',
            
            # Sección 5: Recursos
            'presupuesto_asignado',
            'moneda',
            'recursos_humanos_asignados',
            'recursos_tecnicos',
            
            # Sección 6: Seguimiento
            'frecuencia_reporte',
            'metricas_desempeno',
            'umbrales_alerta',
            'canal_comunicacion',
            
            # Sección 7: Validación
            'criterios_validacion',
            'metodo_verificacion',
            'responsable_validacion',
        ]
    
    def validate_calculo_nivel(self, value):
        """Validar que el GAP exista y esté activo"""
        if not value.activo:
            raise serializers.ValidationError(
                'El GAP seleccionado no está activo'
            )
        return value
    
    def validate_fecha_inicio(self, value):
        """Validar que la fecha de inicio no sea muy antigua"""
        from datetime import timedelta
        
        # Permitir hasta 30 días en el pasado
        fecha_minima = date.today() - timedelta(days=30)
        if value < fecha_minima:
            raise serializers.ValidationError(
                f'La fecha de inicio no puede ser anterior a {fecha_minima}'
            )
        return value
    
    def validate_presupuesto_asignado(self, value):
        """Validar que el presupuesto sea positivo"""
        if value < 0:
            raise serializers.ValidationError(
                'El presupuesto debe ser mayor o igual a 0'
            )
        return value
    
    def validate_recursos_humanos_asignados(self, value):
        """Validar que las horas sean positivas"""
        if value < 0:
            raise serializers.ValidationError(
                'Los recursos humanos deben ser mayor o igual a 0'
            )
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas"""
        
        # ═══ 1. VALIDAR FECHAS ═══
        fecha_inicio = attrs.get('fecha_inicio')
        fecha_fin = attrs.get('fecha_fin_estimada')
        
        if fecha_fin <= fecha_inicio:
            raise serializers.ValidationError({
                'fecha_fin_estimada': 'La fecha de fin debe ser posterior a la fecha de inicio'
            })
        
        # Validar que el proyecto no sea muy largo (máx 2 años)
        from datetime import timedelta
        duracion = (fecha_fin - fecha_inicio).days
        if duracion > 730:  # 2 años
            raise serializers.ValidationError({
                'fecha_fin_estimada': 'El proyecto no puede durar más de 2 años'
            })
        
        # ═══ 2. VALIDAR PERMISOS DEL USUARIO ═══
        user = self.context['request'].user
        calculo_nivel = attrs.get('calculo_nivel')
        
        # Solo Admin o SuperAdmin pueden crear proyectos
        if user.rol not in ['administrador', 'superadmin']:
            raise serializers.ValidationError(
                'Solo administradores pueden crear proyectos de remediación'
            )
        
        # Admin solo puede crear para su empresa
        if user.rol == 'administrador':
            if calculo_nivel.empresa != user.empresa:
                raise serializers.ValidationError({
                    'calculo_nivel': 'Solo puedes crear proyectos para GAPs de tu empresa'
                })
        
        # ═══ 3. VALIDAR RESPONSABLES ═══
        empresa = calculo_nivel.empresa
        
        # Dueno del proyecto
        dueno = attrs.get('dueno_proyecto')
        if dueno.empresa != empresa:
            raise serializers.ValidationError({
                'dueno_proyecto': f'El dueño debe pertenecer a {empresa.nombre}'
            })
        
        # Responsable de implementación
        responsable = attrs.get('responsable_implementacion')
        if responsable.empresa != empresa:
            raise serializers.ValidationError({
                'responsable_implementacion': f'El responsable debe pertenecer a {empresa.nombre}'
            })
        
        # Equipo de implementación
        equipo = attrs.get('equipo_implementacion', [])
        for miembro in equipo:
            if miembro.empresa != empresa:
                raise serializers.ValidationError({
                    'equipo_implementacion': f'{miembro.nombre_completo} no pertenece a {empresa.nombre}'
                })
        
        # Validador interno
        validador = attrs.get('validador_interno')
        if validador and validador.empresa != empresa:
            raise serializers.ValidationError({
                'validador_interno': f'El validador debe pertenecer a {empresa.nombre}'
            })
        
        # Auditor
        auditor = attrs.get('auditor_verificacion')
        if auditor and auditor.empresa != empresa:
            raise serializers.ValidationError({
                'auditor_verificacion': f'El auditor debe pertenecer a {empresa.nombre}'
            })
        
        # Responsable de validación
        resp_validacion = attrs.get('responsable_validacion')
        if resp_validacion and resp_validacion.empresa != empresa:
            raise serializers.ValidationError({
                'responsable_validacion': f'El responsable de validación debe pertenecer a {empresa.nombre}'
            })
        
        # ═══ 4. VALIDAR PREGUNTAS ABORDADAS (SI SE PROPORCIONAN) ═══
        preguntas_ids = attrs.pop('preguntas_abordadas_ids', [])
        if preguntas_ids:
            # Validar que las preguntas pertenezcan a la dimensión del GAP
            dimension = calculo_nivel.dimension
            preguntas = Pregunta.objects.filter(id__in=preguntas_ids, activo=True)
            
            if preguntas.count() != len(preguntas_ids):
                raise serializers.ValidationError({
                    'preguntas_abordadas_ids': 'Una o más preguntas no existen o están inactivas'
                })
            
            for pregunta in preguntas:
                if pregunta.dimension != dimension:
                    raise serializers.ValidationError({
                        'preguntas_abordadas_ids': f'La pregunta {pregunta.codigo} no pertenece a la dimensión {dimension.nombre}'
                    })
            
            # Guardar preguntas validadas para usarlas en create()
            attrs['_preguntas_validadas'] = preguntas
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Crear proyecto con todos los datos"""
        
        # ═══ 1. EXTRAER DATOS ESPECIALES ═══
        equipo = validated_data.pop('equipo_implementacion', [])
        preguntas_validadas = validated_data.pop('_preguntas_validadas', [])
        
        # ═══ 2. ASIGNAR EMPRESA Y USUARIO CREADOR ═══
        calculo_nivel = validated_data['calculo_nivel']
        validated_data['empresa'] = calculo_nivel.empresa
        validated_data['creado_por'] = self.context['request'].user
        
        # ═══ 3. ASIGNAR ESTADO INICIAL ═══
        validated_data['estado'] = 'planificado'
        
        # ═══ 4. PRE-LLENAR DATOS DE LA BRECHA SI NO SE PROPORCIONARON ═══
        # Si no se llenó la fecha de identificación, usar la del GAP
        if not validated_data.get('fecha_identificacion_gap'):
            validated_data['fecha_identificacion_gap'] = calculo_nivel.calculado_at.date()
        
        # ═══ 5. CREAR EL PROYECTO ═══
        proyecto = ProyectoCierreBrecha.objects.create(**validated_data)
        
        # ═══ 6. ASIGNAR EQUIPO (ManyToMany) ═══
        if equipo:
            proyecto.equipo_implementacion.set(equipo)
        
        # ═══ 7. ASIGNAR PREGUNTAS ABORDADAS ═══
        if preguntas_validadas:
            proyecto.preguntas_abordadas.set(preguntas_validadas)
        
        # ═══ 8. ENVIAR NOTIFICACIONES ═══
        # TODO: Implementar servicio de notificaciones
        # NotificacionProyectoService.notificar_proyecto_creado(proyecto)
        
        return proyecto


class ProyectoCierreBrechaUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para ACTUALIZAR un proyecto existente
    
    Restricciones:
    - NO se puede cambiar el GAP asociado
    - NO se puede cambiar la empresa
    - Solo ciertos campos según el estado
    """
    
    # ⭐ Campo especial para preguntas
    preguntas_abordadas_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text='IDs de preguntas específicas'
    )
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = [
            # Básico (algunos no editables)
            'nombre_proyecto',
            'descripcion',
            'fecha_fin_estimada',
            'prioridad',
            'categoria',
            'estado',
            
            # Brecha (solo algunos editables)
            'control_no_conforme',
            'impacto_riesgo',
            
            # Planificación
            'estrategia_cierre',
            'alcance_proyecto',
            'objetivos_especificos',
            'criterios_aceptacion',
            'supuestos',
            'restricciones',
            'riesgos_proyecto',
            'preguntas_abordadas_ids',
            
            # Responsables
            'dueno_proyecto',
            'responsable_implementacion',
            'equipo_implementacion',
            'validador_interno',
            'auditor_verificacion',
            
            # Recursos
            'presupuesto_asignado',
            'presupuesto_gastado',
            'recursos_humanos_asignados',
            'recursos_tecnicos',
            
            # Seguimiento
            'frecuencia_reporte',
            'metricas_desempeno',
            'umbrales_alerta',
            'canal_comunicacion',
            
            # Validación
            'criterios_validacion',
            'metodo_verificacion',
            'responsable_validacion',
            
            # Cierre
            'lecciones_aprendidas',
            'acciones_mejora_continua',
            'recomendaciones_futuros_gap',
        ]
    
    def validate_estado(self, value):
        """Validar transiciones de estado permitidas"""
        if self.instance:
            estado_actual = self.instance.estado
            
            # Definir transiciones válidas
            transiciones_validas = {
                'planificado': ['en_ejecucion', 'cancelado'],
                'en_ejecucion': ['en_validacion', 'suspendido', 'cancelado'],
                'en_validacion': ['cerrado', 'en_ejecucion'],
                'suspendido': ['en_ejecucion', 'cancelado'],
                'cerrado': [],  # No se puede cambiar de cerrado
                'cancelado': [],  # No se puede cambiar de cancelado
            }
            
            if value != estado_actual:
                if value not in transiciones_validas.get(estado_actual, []):
                    raise serializers.ValidationError(
                        f'No se puede cambiar de "{estado_actual}" a "{value}"'
                    )
        
        return value
    
    def validate_presupuesto_gastado(self, value):
        """Validar que no se gaste más del presupuesto"""
        if self.instance:
            if value > self.instance.presupuesto_asignado:
                raise serializers.ValidationError(
                    f'El gasto no puede superar el presupuesto asignado ({self.instance.presupuesto_asignado})'
                )
        return value
    
    def validate(self, attrs):
        """Validaciones cruzadas"""
        
        user = self.context['request'].user
        
        # ═══ 1. VALIDAR PERMISOS ═══
        # Solo Admin de la empresa o SuperAdmin pueden editar
        if user.rol == 'administrador':
            if self.instance.empresa != user.empresa:
                raise serializers.ValidationError(
                    'Solo puedes editar proyectos de tu empresa'
                )
        elif user.rol not in ['superadmin']:
            raise serializers.ValidationError(
                'No tienes permisos para editar proyectos'
            )
        
        # ═══ 2. VALIDAR FECHAS ═══
        fecha_fin = attrs.get('fecha_fin_estimada')
        if fecha_fin:
            if fecha_fin <= self.instance.fecha_inicio:
                raise serializers.ValidationError({
                    'fecha_fin_estimada': 'La fecha de fin debe ser posterior a la fecha de inicio'
                })
        
        # ═══ 3. VALIDAR RESPONSABLES (SI SE CAMBIAN) ═══
        empresa = self.instance.empresa
        
        dueno = attrs.get('dueno_proyecto')
        if dueno and dueno.empresa != empresa:
            raise serializers.ValidationError({
                'dueno_proyecto': f'El dueño debe pertenecer a {empresa.nombre}'
            })
        
        responsable = attrs.get('responsable_implementacion')
        if responsable and responsable.empresa != empresa:
            raise serializers.ValidationError({
                'responsable_implementacion': f'El responsable debe pertenecer a {empresa.nombre}'
            })
        
        # ═══ 4. VALIDAR PREGUNTAS ═══
        preguntas_ids = attrs.pop('preguntas_abordadas_ids', None)
        if preguntas_ids is not None:
            dimension = self.instance.calculo_nivel.dimension
            preguntas = Pregunta.objects.filter(id__in=preguntas_ids, activo=True)
            
            for pregunta in preguntas:
                if pregunta.dimension != dimension:
                    raise serializers.ValidationError({
                        'preguntas_abordadas_ids': f'La pregunta {pregunta.codigo} no pertenece a la dimensión {dimension.nombre}'
                    })
            
            attrs['_preguntas_validadas'] = preguntas
        
        return attrs
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Actualizar proyecto"""
        
        # ═══ 1. EXTRAER DATOS ESPECIALES ═══
        equipo = validated_data.pop('equipo_implementacion', None)
        preguntas_validadas = validated_data.pop('_preguntas_validadas', None)
        
        # ═══ 2. ACTUALIZAR CAMPOS NORMALES ═══
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # ═══ 3. INCREMENTAR VERSIÓN ═══
        instance.version += 1
        
        # ═══ 4. GUARDAR ═══
        instance.save()
        
        # ═══ 5. ACTUALIZAR EQUIPO SI SE PROPORCIONÓ ═══
        if equipo is not None:
            instance.equipo_implementacion.set(equipo)
        
        # ═══ 6. ACTUALIZAR PREGUNTAS SI SE PROPORCIONARON ═══
        if preguntas_validadas is not None:
            instance.preguntas_abordadas.set(preguntas_validadas)
        
        # ═══ 7. ENVIAR NOTIFICACIONES ═══
        # TODO: Implementar
        # NotificacionProyectoService.notificar_proyecto_actualizado(instance)
        
        return instance


# ═══════════════════════════════════════════════════════════════
# SERIALIZERS ESPECIALES
# ═══════════════════════════════════════════════════════════════

class ProyectoSimpleSerializer(serializers.ModelSerializer):
    """Serializer ultra-simple para referencias rápidas"""
    
    class Meta:
        model = ProyectoCierreBrecha
        fields = ['id', 'codigo_proyecto', 'nombre_proyecto', 'estado']