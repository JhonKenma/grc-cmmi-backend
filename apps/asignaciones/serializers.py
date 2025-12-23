# apps/asignaciones/serializers.py
from rest_framework import serializers
from .models import Asignacion
from apps.encuestas.models import Encuesta, Dimension
from apps.usuarios.models import Usuario
from apps.empresas.models import Empresa
from apps.encuestas.serializers import DimensionListSerializer, EncuestaListSerializer
from apps.empresas.serializers import EmpresaSerializer
from apps.usuarios.serializers import UsuarioListSerializer
from apps.encuestas.models import ConfigNivelDeseado
from django.utils import timezone
from datetime import date, timedelta


# =============================================================================
# SERIALIZERS PRINCIPALES
# =============================================================================

class AsignacionSerializer(serializers.ModelSerializer):
    """Serializer completo de asignaciones con información relacionada"""
    encuesta_info = EncuestaListSerializer(source='encuesta', read_only=True)
    dimension_info = DimensionListSerializer(source='dimension', read_only=True)
    usuario_asignado_info = UsuarioListSerializer(source='usuario_asignado', read_only=True)
    empresa_info = EmpresaSerializer(source='empresa', read_only=True)
    asignado_por_nombre = serializers.CharField(
        source='asignado_por.nombre_completo',
        read_only=True
    )
    
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    dias_restantes = serializers.ReadOnlyField()
    esta_vencido = serializers.ReadOnlyField()
    
    # ⭐ CAMPOS DE REVISIÓN (NUEVOS)
    requiere_revision = serializers.BooleanField(read_only=True)
    fecha_envio_revision = serializers.DateTimeField(read_only=True)
    revisado_por_nombre = serializers.CharField(
        source='revisado_por.nombre_completo',
        read_only=True
    )
    fecha_revision = serializers.DateTimeField(read_only=True)
    comentarios_revision = serializers.CharField(read_only=True)
    
    # Campos para nivel deseado (se usa en creación)
    nivel_deseado = serializers.IntegerField(
        write_only=True,
        required=False,
        min_value=1,
        max_value=5,
        help_text='Nivel deseado para esta dimensión (1-5)'
    )
    motivo_nivel = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text='Motivo por el cual se estableció este nivel deseado'
    )
    
    class Meta:
        model = Asignacion
        fields = [
            'id', 'encuesta', 'encuesta_info', 'dimension', 'dimension_info',
            'usuario_asignado', 'usuario_asignado_info', 'empresa', 'empresa_info',
            'asignado_por', 'asignado_por_nombre',
            'fecha_asignacion', 'fecha_limite', 'fecha_completado',
            'estado', 'estado_display', 'dias_restantes', 'esta_vencido',
            'total_preguntas', 'preguntas_respondidas', 'porcentaje_avance',
            'observaciones', 'activo',
            'nivel_deseado', 'motivo_nivel',
            # ⭐ CAMPOS DE REVISIÓN
            'requiere_revision', 'fecha_envio_revision', 
            'revisado_por', 'revisado_por_nombre',
            'fecha_revision', 'comentarios_revision',
            'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = [
            'id', 'asignado_por', 'fecha_asignacion', 'fecha_completado',
            'estado', 'total_preguntas', 'preguntas_respondidas', 'porcentaje_avance',
            'fecha_creacion', 'fecha_actualizacion'
        ]
    
    def validate_fecha_limite(self, value):
        """Validar que la fecha límite sea futura"""
        if value < date.today():
            raise serializers.ValidationError(
                'La fecha límite debe ser mayor o igual a la fecha actual'
            )
        return value
    
    def validate_nivel_deseado(self, value):
        """Validar nivel deseado"""
        if value and (value < 1 or value > 5):
            raise serializers.ValidationError(
                'El nivel deseado debe estar entre 1 y 5'
            )
        return value
    
    def validate(self, attrs):
        """Validaciones generales"""
        user = self.context['request'].user
        
        # Extraer datos
        dimension = attrs.get('dimension')
        usuario_asignado = attrs.get('usuario_asignado')
        empresa = attrs.get('empresa')
        
        # Solo SuperAdmin puede asignar a cualquier empresa
        if user.rol == 'superadmin':
            if not empresa:
                raise serializers.ValidationError({
                    'empresa': 'Debes especificar una empresa'
                })
        else:
            # Administrador solo puede asignar en su propia empresa
            if user.rol != 'administrador':
                raise serializers.ValidationError(
                    'Solo SuperAdmin y Administradores pueden crear asignaciones'
                )
            
            if not user.empresa:
                raise serializers.ValidationError(
                    'Tu usuario no tiene empresa asignada'
                )
            
            # Forzar la empresa del administrador
            attrs['empresa'] = user.empresa
            empresa = user.empresa
        
        # Validar que el usuario asignado pertenezca a la empresa
        if usuario_asignado.empresa != empresa:
            raise serializers.ValidationError({
                'usuario_asignado': 'El usuario debe pertenecer a la empresa seleccionada'
            })
        
        # Validar que la dimensión pertenezca a la encuesta
        if dimension and dimension.encuesta_id != attrs.get('encuesta').id:
            raise serializers.ValidationError({
                'dimension': 'La dimensión no pertenece a la encuesta seleccionada'
            })
        
        # Validar que no exista ya una asignación activa para esta combinación
        if not self.instance:  # Solo en creación
            existe = Asignacion.objects.filter(
                dimension=dimension,
                usuario_asignado=usuario_asignado,
                empresa=empresa,
                activo=True
            ).exists()
            
            if existe:
                raise serializers.ValidationError(
                    'Ya existe una asignación activa para esta dimensión, usuario y empresa'
                )
        
        return attrs
    
    def create(self, validated_data):
        """Crear asignación y configurar nivel deseado"""
        # Extraer campos de nivel deseado
        nivel_deseado = validated_data.pop('nivel_deseado', None)
        motivo_nivel = validated_data.pop('motivo_nivel', '')
        
        # Asignar usuario que crea
        validated_data['asignado_por'] = self.context['request'].user
        
        # Crear asignación
        asignacion = Asignacion.objects.create(**validated_data)
        
        # Crear o actualizar configuración de nivel deseado si se proporcionó
        if nivel_deseado:
            ConfigNivelDeseado.objects.update_or_create(
                dimension=asignacion.dimension,
                empresa=asignacion.empresa,
                defaults={
                    'nivel_deseado': nivel_deseado,
                    'configurado_por': self.context['request'].user,
                    'motivo_cambio': motivo_nivel,
                    'activo': True
                }
            )
        
        # Enviar notificación de asignación creada
        from apps.notificaciones.services import NotificacionAsignacionService
        NotificacionAsignacionService.notificar_asignacion_creada(asignacion)
        
        return asignacion
    
    def update(self, instance, validated_data):
        """Actualizar asignación"""
        # Remover campos de nivel deseado si vienen (no se permiten en update)
        validated_data.pop('nivel_deseado', None)
        validated_data.pop('motivo_nivel', None)
        
        # No permitir cambiar campos críticos
        validated_data.pop('encuesta', None)
        validated_data.pop('dimension', None)
        validated_data.pop('usuario_asignado', None)
        validated_data.pop('empresa', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class AsignacionListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de asignaciones"""
    encuesta_nombre = serializers.CharField(source='encuesta.nombre', read_only=True)
    dimension_nombre = serializers.CharField(source='dimension.nombre', read_only=True)
    usuario_asignado_nombre = serializers.CharField(
        source='usuario_asignado.nombre_completo',
        read_only=True
    )
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    dias_restantes = serializers.ReadOnlyField()
    
    class Meta:
        model = Asignacion
        fields = [
            'id', 'encuesta_nombre', 'dimension_nombre',
            'usuario_asignado_nombre', 'empresa_nombre',
            'fecha_limite', 'estado', 'estado_display',
            'porcentaje_avance', 'dias_restantes', 'fecha_creacion',
            'requiere_revision'  # ⭐ AGREGADO
        ]


# =============================================================================
# SERIALIZERS PARA ASIGNACIÓN
# =============================================================================

class AsignacionEvaluacionCompletaSerializer(serializers.Serializer):
    """
    Serializer para asignar EVALUACIÓN COMPLETA a un Administrador
    Solo SuperAdmin puede usar esto
    """
    encuesta_id = serializers.UUIDField(required=True, help_text='ID de la encuesta a asignar')
    administrador_id = serializers.IntegerField(required=True, help_text='ID del administrador de empresa')
    fecha_limite = serializers.DateField(required=True, help_text='Fecha límite de completación')
    observaciones = serializers.CharField(required=False, allow_blank=True, help_text='Observaciones opcionales')
    
    def validate_encuesta_id(self, value):
        """Validar que la encuesta exista y esté activa"""
        try:
            encuesta = Encuesta.objects.get(id=value, activo=True)
            if encuesta.total_dimensiones == 0:
                raise serializers.ValidationError('La encuesta no tiene dimensiones configuradas')
            return value
        except Encuesta.DoesNotExist:
            raise serializers.ValidationError('Encuesta no encontrada o inactiva')
    
    def validate_administrador_id(self, value):
        """Validar que sea un administrador con empresa"""
        try:
            usuario = Usuario.objects.get(id=value, activo=True)
            if usuario.rol != 'administrador':
                raise serializers.ValidationError('El usuario debe ser un administrador de empresa')
            if not usuario.empresa:
                raise serializers.ValidationError('El administrador debe tener una empresa asignada')
            return value
        except Usuario.DoesNotExist:
            raise serializers.ValidationError('Usuario no encontrado o inactivo')
    
    def validate_fecha_limite(self, value):
        """Validar que la fecha límite sea futura"""
        if value < timezone.now().date():
            raise serializers.ValidationError('La fecha límite debe ser futura')
        
        if value > timezone.now().date() + timedelta(days=365):
            raise serializers.ValidationError('La fecha límite no puede ser mayor a 1 año')
        
        return value
    
    def validate(self, attrs):
        """Validación cruzada"""
        encuesta = Encuesta.objects.get(id=attrs['encuesta_id'])
        usuario = Usuario.objects.get(id=attrs['administrador_id'])
        
        # Verificar que no exista ya una asignación de esta encuesta para este usuario
        if Asignacion.objects.filter(
            encuesta=encuesta,
            usuario_asignado=usuario,
            empresa=usuario.empresa,
            dimension__isnull=True,  # ⭐ Asegurar que sea evaluación completa
            activo=True
        ).exists():
            raise serializers.ValidationError({
                'encuesta_id': f'El administrador {usuario.nombre_completo} ya tiene asignada esta evaluación'
            })
        
        return attrs


class AsignacionDimensionSerializer(serializers.Serializer):
    """
    Serializer para asignar una o varias dimensiones a un usuario
    """
    encuesta_id = serializers.UUIDField(required=True, help_text='ID de la encuesta')
    dimension_ids = serializers.ListField(  # ⭐ CAMBIO: Ahora es una lista
        child=serializers.UUIDField(),
        required=True,
        help_text='Lista de IDs de dimensiones a asignar'
    )
    usuario_id = serializers.IntegerField(required=True, help_text='ID del usuario a asignar')
    fecha_limite = serializers.DateField(required=True, help_text='Fecha límite')
    observaciones = serializers.CharField(required=False, allow_blank=True, help_text='Observaciones')
    requiere_revision = serializers.BooleanField(
        required=False,
        default=False,
        help_text='¿Requiere revisión del administrador?'
    )
    
    def validate_encuesta_id(self, value):
        """Validar encuesta"""
        try:
            Encuesta.objects.get(id=value, activo=True)
            return value
        except Encuesta.DoesNotExist:
            raise serializers.ValidationError('Encuesta no encontrada')
    
    def validate_dimension_ids(self, value):
        """Validar dimensiones"""
        if not value:
            raise serializers.ValidationError('Debes seleccionar al menos una dimensión')
        
        # Verificar que todas las dimensiones existan y estén activas
        dimensiones = Dimension.objects.filter(id__in=value, activo=True)
        if dimensiones.count() != len(value):
            raise serializers.ValidationError('Una o más dimensiones no existen o están inactivas')
        
        # Verificar que todas tengan preguntas
        for dimension in dimensiones:
            if dimension.total_preguntas == 0:
                raise serializers.ValidationError(
                    f'La dimensión "{dimension.nombre}" no tiene preguntas configuradas'
                )
        
        return value
    
    def validate_usuario_id(self, value):
        """Validar usuario"""
        try:
            usuario = Usuario.objects.get(id=value, activo=True)
            if usuario.rol == 'superadmin':
                raise serializers.ValidationError('No se puede asignar a super administradores')
            if not usuario.empresa:
                raise serializers.ValidationError('El usuario debe pertenecer a una empresa')
            return value
        except Usuario.DoesNotExist:
            raise serializers.ValidationError('Usuario no encontrado')
    
    def validate_fecha_limite(self, value):
        """Validar fecha límite"""
        if value < timezone.now().date():
            raise serializers.ValidationError('La fecha límite debe ser futura')
        if value > timezone.now().date() + timedelta(days=365):
            raise serializers.ValidationError('La fecha límite no puede ser mayor a 1 año')
        return value
    
def validate(self, attrs):
    """Validación cruzada"""
    user = self.context['request'].user
    dimension_ids = attrs.get('dimension_ids')
    encuesta = Encuesta.objects.get(id=attrs['encuesta_id'])
    usuario = Usuario.objects.get(id=attrs['usuario_id'])
    
    # Validar que todas las dimensiones pertenezcan a la encuesta
    dimensiones = Dimension.objects.filter(id__in=dimension_ids)
    for dimension in dimensiones:
        if dimension.encuesta != encuesta:
            raise serializers.ValidationError({
                'dimension_ids': f'La dimensión "{dimension.nombre}" no pertenece a esta encuesta'
            })
    
    # Validar permisos según rol
    if user.rol == 'administrador':
        if usuario.empresa != user.empresa:
            raise serializers.ValidationError({
                'usuario_id': 'Solo puedes asignar a usuarios de tu propia empresa'
            })
        
        if not Asignacion.objects.filter(
            encuesta=encuesta,
            usuario_asignado=user,
            empresa=user.empresa,
            dimension__isnull=True,
            activo=True
        ).exists():
            raise serializers.ValidationError({
                'encuesta_id': 'No tienes asignada esta evaluación, no puedes delegar dimensiones'
            })
    
    # ⭐ CAMBIO CLAVE: Verificar que las dimensiones NO estén asignadas a NADIE en la empresa
    for dimension_id in dimension_ids:
        # Buscar si existe asignación activa de esta dimensión en la empresa
        asignacion_existente = Asignacion.objects.filter(
            dimension_id=dimension_id,
            empresa=usuario.empresa,  # ⭐ Cualquier usuario de la empresa
            activo=True
        ).select_related('usuario_asignado').first()
        
        if asignacion_existente:
            dimension = Dimension.objects.get(id=dimension_id)
            raise serializers.ValidationError({
                'dimension_ids': f'La dimensión "{dimension.nombre}" ya está asignada a {asignacion_existente.usuario_asignado.nombre_completo}'
            })
    
    return attrs


class AsignacionCreateSerializer(serializers.ModelSerializer):
    """Serializer específico para crear asignaciones (más simple)"""
    nivel_deseado = serializers.IntegerField(
        required=True,
        min_value=1,
        max_value=5,
        help_text='Nivel deseado para esta dimensión (1-5)'
    )
    motivo_nivel = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Motivo del nivel deseado'
    )
    requiere_revision = serializers.BooleanField(
        required=False,
        default=False,
        help_text='¿Requiere revisión del administrador?'
    )  # ⭐ CAMPO DE REVISIÓN
    
    class Meta:
        model = Asignacion
        fields = [
            'encuesta', 'dimension', 'usuario_asignado', 'empresa',
            'fecha_limite', 'observaciones', 'nivel_deseado', 'motivo_nivel',
            'requiere_revision'  # ⭐ INCLUIDO
        ]
    
    def validate_fecha_limite(self, value):
        if value < date.today():
            raise serializers.ValidationError(
                'La fecha límite debe ser mayor o igual a la fecha actual'
            )
        return value
    
    def validate(self, attrs):
        user = self.context['request'].user
        dimension = attrs.get('dimension')
        usuario_asignado = attrs.get('usuario_asignado')
        empresa = attrs.get('empresa')
        
        # Validaciones de permisos
        if user.rol == 'superadmin':
            if not empresa:
                raise serializers.ValidationError({
                    'empresa': 'Debes especificar una empresa'
                })
        elif user.rol == 'administrador':
            if not user.empresa:
                raise serializers.ValidationError('Tu usuario no tiene empresa asignada')
            attrs['empresa'] = user.empresa
            empresa = user.empresa
        else:
            raise serializers.ValidationError(
                'Solo SuperAdmin y Administradores pueden crear asignaciones'
            )
        
        # Validar pertenencia
        if usuario_asignado.empresa != empresa:
            raise serializers.ValidationError({
                'usuario_asignado': 'El usuario debe pertenecer a la empresa seleccionada'
            })
        
        if dimension and dimension.encuesta_id != attrs.get('encuesta').id:
            raise serializers.ValidationError({
                'dimension': 'La dimensión no pertenece a la encuesta seleccionada'
            })
        
        # Validar duplicado
        existe = Asignacion.objects.filter(
            dimension=dimension,
            usuario_asignado=usuario_asignado,
            empresa=empresa,
            activo=True
        ).exists()
        
        if existe:
            raise serializers.ValidationError(
                'Ya existe una asignación activa para esta dimensión, usuario y empresa'
            )
        
        return attrs
    
    def create(self, validated_data):
        nivel_deseado = validated_data.pop('nivel_deseado')
        motivo_nivel = validated_data.pop('motivo_nivel', '')
        
        validated_data['asignado_por'] = self.context['request'].user
        
        asignacion = Asignacion.objects.create(**validated_data)
        
        # Configurar nivel deseado
        if asignacion.dimension:  # Solo si es asignación de dimensión
            ConfigNivelDeseado.objects.update_or_create(
                dimension=asignacion.dimension,
                empresa=asignacion.empresa,
                defaults={
                    'nivel_deseado': nivel_deseado,
                    'configurado_por': self.context['request'].user,
                    'motivo_cambio': motivo_nivel,
                    'activo': True
                }
            )
        
        # Notificar
        from apps.notificaciones.services import NotificacionAsignacionService
        NotificacionAsignacionService.notificar_asignacion_creada(asignacion)
        
        return asignacion


# =============================================================================
# SERIALIZERS PARA ACCIONES
# =============================================================================

class ReasignarSerializer(serializers.Serializer):
    """Serializer para reasignar una asignación a otro usuario"""
    nuevo_usuario_id = serializers.IntegerField(required=True)
    nueva_fecha_limite = serializers.DateField(required=False)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate_nuevo_usuario_id(self, value):
        try:
            usuario = Usuario.objects.get(id=value, activo=True)
            if usuario.rol == 'superadmin':
                raise serializers.ValidationError('No se puede asignar a super administradores')
            return value
        except Usuario.DoesNotExist:
            raise serializers.ValidationError('Usuario no encontrado')
    
    def validate_nueva_fecha_limite(self, value):
        if value and value < timezone.now().date():
            raise serializers.ValidationError('La fecha límite debe ser futura')
        return value


class ActualizarProgresoSerializer(serializers.Serializer):
    """Serializer para actualizar manualmente el progreso"""
    preguntas_respondidas = serializers.IntegerField(min_value=0, required=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)


# ⭐ NUEVO SERIALIZER PARA REVISAR ASIGNACIONES
class RevisarAsignacionSerializer(serializers.Serializer):
    """Serializer para aprobar o rechazar una asignación"""
    accion = serializers.ChoiceField(
        choices=['aprobar', 'rechazar'],
        required=True,
        help_text='Acción a realizar: aprobar o rechazar'
    )
    comentarios = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text='Comentarios de la revisión'
    )
    
    def validate_comentarios(self, value):
        """Si rechaza, comentarios son obligatorios"""
        accion = self.initial_data.get('accion')
        if accion == 'rechazar' and not value:
            raise serializers.ValidationError(
                'Los comentarios son obligatorios al rechazar una asignación'
            )
        return value