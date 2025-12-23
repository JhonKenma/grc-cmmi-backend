# apps/usuarios/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Usuario
from apps.empresas.serializers import EmpresaSerializer

class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer completo de usuario"""
    empresa_info = EmpresaSerializer(source='empresa', read_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    nombre_completo = serializers.ReadOnlyField()
    total_asignaciones = serializers.ReadOnlyField()
    asignaciones_pendientes = serializers.ReadOnlyField()
    
    class Meta:
        model = Usuario
        fields = [
            'id', 'username', 'email', 'password', 'first_name', 'last_name',
            'empresa', 'empresa_info', 'rol', 'telefono', 'cargo', 'departamento',
            'avatar', 'activo', 'is_active', 'nombre_completo',
            'total_asignaciones', 'asignaciones_pendientes',
            'fecha_creacion', 'fecha_actualizacion'
        ]
        read_only_fields = ['fecha_creacion', 'fecha_actualizacion', 'username']
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }
    
    def validate_email(self, value):
        """Validar que el email sea único"""
        if self.instance:
            if Usuario.objects.exclude(id=self.instance.id).filter(email=value).exists():
                raise serializers.ValidationError("Ya existe un usuario con este email")
        else:
            if Usuario.objects.filter(email=value).exists():
                raise serializers.ValidationError("Ya existe un usuario con este email")
        return value.lower()
    
    def validate_rol(self, value):
        """Validar asignación de roles según permisos"""
        user = self.context['request'].user
        
        # SuperAdmin puede asignar cualquier rol
        if user.rol == 'superadmin':
            return value
        
        # Administrador NO puede crear superadmins
        if user.rol == 'administrador' and value == 'superadmin':
            raise serializers.ValidationError(
                "No tienes permiso para crear super administradores"
            )
        
        return value
    
    def validate_empresa(self, value):
        """Validar asignación de empresa según permisos"""
        user = self.context['request'].user
        rol = self.initial_data.get('rol', 'usuario')
        
        # SuperAdmin creando superadmin no necesita empresa
        if user.rol == 'superadmin' and rol == 'superadmin':
            return None
        
        # SuperAdmin puede asignar cualquier empresa para otros roles
        if user.rol == 'superadmin':
            if not value and rol != 'superadmin':
                raise serializers.ValidationError(
                    "Debes asignar una empresa para este rol"
                )
            return value
        
        # Administrador solo puede asignar su propia empresa
        if user.rol == 'administrador':
            if value != user.empresa:
                raise serializers.ValidationError(
                    "Solo puedes crear usuarios de tu propia empresa"
                )
            return value
        
        return value
    
    def validate(self, attrs):
        """Validaciones generales"""
        rol = attrs.get('rol', 'usuario')
        empresa = attrs.get('empresa')
        
        # SuperAdmin no debe tener empresa
        if rol == 'superadmin' and empresa:
            raise serializers.ValidationError({
                'empresa': 'Super administradores no deben tener empresa asignada'
            })
        
        # Otros roles deben tener empresa
        if rol != 'superadmin' and not empresa:
            raise serializers.ValidationError({
                'empresa': 'Este rol requiere una empresa asignada'
            })
        
        return attrs
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        
        # Generar username automático desde email
        if 'username' not in validated_data or not validated_data.get('username'):
            validated_data['username'] = validated_data['email'].split('@')[0]
        
        usuario = Usuario(**validated_data)
        
        if password:
            usuario.set_password(password)
        else:
            # Generar password temporal
            temp_password = Usuario.objects.make_random_password(length=12)
            usuario.set_password(temp_password)
        
        usuario.save()
        return usuario
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        # No permitir cambiar rol de/a superadmin si no eres superadmin
        user = self.context['request'].user
        if 'rol' in validated_data:
            nuevo_rol = validated_data['rol']
            rol_actual = instance.rol
            
            if user.rol != 'superadmin':
                if nuevo_rol == 'superadmin' or rol_actual == 'superadmin':
                    raise serializers.ValidationError({
                        'rol': 'No tienes permiso para cambiar este rol'
                    })
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance

class UsuarioListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listados"""
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    nombre_completo = serializers.ReadOnlyField()
    
    class Meta:
        model = Usuario
        fields = [
            'id', 'email', 'nombre_completo',
            'empresa_nombre', 'rol', 'cargo', 'activo'
        ]

class UsuarioCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear usuarios"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = Usuario
        fields = [
            'email', 'password', 'first_name', 'last_name',
            'empresa', 'rol', 'cargo', 'departamento', 'telefono'
        ]
    
    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este email")
        return value.lower()
    
    def validate_rol(self, value):
        user = self.context['request'].user
        if user.rol != 'superadmin' and value == 'superadmin':
            raise serializers.ValidationError(
                "No tienes permiso para crear super administradores"
            )
        return value
    
    def validate_empresa(self, value):
        user = self.context['request'].user
        rol = self.initial_data.get('rol', 'usuario')
        
        # SuperAdmin puede asignar cualquier empresa
        if user.rol == 'superadmin':
            if not value and rol != 'superadmin':
                raise serializers.ValidationError("Debes asignar una empresa")
            return value
        
        # Administrador solo su empresa
        if user.rol == 'administrador' and value != user.empresa:
            raise serializers.ValidationError(
                "Solo puedes crear usuarios de tu propia empresa"
            )
        
        return value
    
    def validate(self, attrs):
        rol = attrs.get('rol')
        empresa = attrs.get('empresa')
        
        if rol == 'superadmin' and empresa:
            raise serializers.ValidationError({
                'empresa': 'Super administradores no deben tener empresa'
            })
        
        if rol != 'superadmin' and not empresa:
            raise serializers.ValidationError({
                'empresa': 'Este rol requiere una empresa'
            })
        
        return attrs
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        validated_data['username'] = validated_data['email'].split('@')[0]
        
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario

class CambiarPasswordSerializer(serializers.Serializer):
    """Serializer para cambio de contraseña"""
    password_actual = serializers.CharField(required=True, write_only=True)
    password_nuevo = serializers.CharField(required=True, validators=[validate_password], write_only=True)
    password_confirmacion = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['password_nuevo'] != attrs['password_confirmacion']:
            raise serializers.ValidationError({
                "password_confirmacion": "Las contraseñas no coinciden"
            })
        return attrs
    
    def validate_password_actual(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Contraseña actual incorrecta")
        return value