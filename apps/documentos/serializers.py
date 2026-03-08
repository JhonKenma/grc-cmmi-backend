import os
from rest_framework import serializers
from django.utils.text import slugify
from django.conf import settings

# Importación de modelos
from .models import Documento, Proceso, Norma, TipoDocumento

# Se asume que este servicio existe y conecta con S3/Supabase/Local
from apps.core.services.storage_service import StorageService 

# =============================================================================
# 1. SERIALIZERS DE APOYO (CATÁLOGOS)
# =============================================================================

class TipoDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoDocumento
        fields = ['id', 'nombre', 'abreviatura', 'nivel_jerarquico', 'requiere_word_y_pdf']

class ProcesoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proceso
        fields = ['id', 'nombre', 'sigla']

class NormaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Norma
        fields = ['id', 'nombre', 'descripcion']

# =============================================================================
# 2. SERIALIZER MAESTRO DE DOCUMENTOS
# =============================================================================

class DocumentoSerializer(serializers.ModelSerializer):
    # --- 1. Campos de Lectura (Flattening / Aplanados) ---
    nombre_tipo = serializers.CharField(source='tipo.nombre', read_only=True)
    abreviatura_tipo = serializers.CharField(source='tipo.abreviatura', read_only=True)
    nivel_jerarquico = serializers.IntegerField(source='tipo.nivel_jerarquico', read_only=True)
    
    nombre_proceso = serializers.CharField(source='proceso.nombre', read_only=True, default="---")
    sigla_proceso = serializers.CharField(source='proceso.sigla', read_only=True, default="GEN")
    nombre_norma = serializers.CharField(source='norma.nombre', read_only=True, default="---")
    
    # --- 2. URLs y Metadatos de Archivos ---
    url_pdf = serializers.SerializerMethodField()
    url_editable = serializers.SerializerMethodField()
    
    nombre_archivo_pdf = serializers.SerializerMethodField()
    nombre_archivo_editable = serializers.SerializerMethodField()
    
    tiene_pdf = serializers.SerializerMethodField()
    tiene_editable = serializers.SerializerMethodField()

    # --- 3. Campos de Escritura (Uploads) ---
    fichero_pdf = serializers.FileField(write_only=True, required=False)
    fichero_editable = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Documento
        fields = [
            'id', 
            'tipo', 'nombre_tipo', 'abreviatura_tipo', 'nivel_jerarquico',
            'proceso', 'nombre_proceso', 'sigla_proceso',
            'norma', 'nombre_norma',
            'codigo', 'titulo', 'version', 
            'objetivo', 'alcance', 
            'nivel_confidencialidad', 'frecuencia_revision', 'periodo_retencion',
            'elaborado_por', 'revisado_por', 'aprobado_por',
            # Campos de archivo internos (BD)
            'archivo_pdf', 'archivo_editable',    
            # Campos calculados para el Front
            'url_pdf', 'url_editable',            
            'nombre_archivo_pdf', 'nombre_archivo_editable', 
            'tiene_pdf', 'tiene_editable',        
            # Campos de subida (Inputs)
            'fichero_pdf', 'fichero_editable',    
            # Metadatos automáticos
            'estado', 'fecha_emision', 'fecha_proxima_revision', 'fecha_creacion'
        ]
        read_only_fields = ['archivo_pdf', 'archivo_editable', 'fecha_creacion', 'id']

    # --- VALIDACIONES ---

    def validate_codigo(self, value):
        """Valida que el código sea único al crear, excluyendo el actual al editar"""
        qs = Documento.objects.filter(codigo=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un documento con este código.")
        return value

    def validate_fichero_pdf(self, value):
        """Asegura que el archivo principal sea PDF"""
        if value:
            ext = os.path.splitext(value.name)[1].lower()
            if ext != '.pdf':
                raise serializers.ValidationError("El archivo principal debe ser formato PDF.")
        return value

    # --- MÉTODOS DE VISUALIZACIÓN (GETTERS) ---

    def get_url_pdf(self, obj):
        if not obj.archivo_pdf:
            return None
        try:
            url = StorageService().get_file_url(str(obj.archivo_pdf))
            # Si la URL es una cadena vacía (error), retornamos None
            return url if url else None
        except Exception as e:
            # Opcional: loguear el error para depuración
            print(f"Error generando URL para PDF {obj.archivo_pdf}: {e}")
            return None

    def get_url_editable(self, obj):
        if not obj.archivo_editable:
            return None
        try:
            url = StorageService().get_file_url(str(obj.archivo_editable))
            return url if url else None
        except Exception as e:
            print(f"Error generando URL para editable {obj.archivo_editable}: {e}")
            return None

    def get_nombre_archivo_pdf(self, obj):
        """Devuelve solo el nombre visual del archivo"""
        if obj.archivo_pdf:
            return os.path.basename(str(obj.archivo_pdf))
        return None

    def get_nombre_archivo_editable(self, obj):
        if obj.archivo_editable:
            return os.path.basename(str(obj.archivo_editable))
        return None

    def get_tiene_pdf(self, obj):
        return bool(obj.archivo_pdf)

    def get_tiene_editable(self, obj):
        return bool(obj.archivo_editable)

    # --- LÓGICA INTERNA DE RUTAS Y SUBIDA ---

    def _generar_ruta_guardado(self, instance, archivo, es_editable=False):
        """Genera una estructura de carpetas limpia y organizada"""
        codigo_clean = slugify(instance.codigo).upper() if instance.codigo else "PENDIENTE"
        version_str = f"v{instance.version}"
        
        if instance.proceso:
            proceso_folder = slugify(instance.proceso.sigla)
        else:
            proceso_folder = 'general'

        folder_path = f"documentos/{proceso_folder}/{codigo_clean}/{version_str}"
        
        if es_editable:
            folder_path += "/editables"
        
        nombre_clean = slugify(os.path.splitext(archivo.name)[0])
        ext = os.path.splitext(archivo.name)[1].lower()
        full_name = f"{nombre_clean}{ext}"

        return f"{folder_path}/{full_name}"

    def _subir_archivo_storage(self, instance, archivo, es_editable=False):
        """Sube el archivo físico al Storage y retorna la ruta relativa para la BD"""
        try:
            storage = StorageService()
            full_path = self._generar_ruta_guardado(instance, archivo, es_editable)
            
            resultado = storage.upload_file(archivo, full_path)
            
            if resultado and resultado.get('success'):
                return resultado.get('path')
            else:
                print(f"Error Storage: {resultado.get('error') if resultado else 'Desconocido'}")
                return None
                
        except Exception as e:
            print(f"Excepción crítica subiendo archivo: {str(e)}")
            return None

    # --- MÉTODOS CREATE Y UPDATE ---

    def create(self, validated_data):
        fichero_pdf = validated_data.pop('fichero_pdf', None)
        fichero_editable = validated_data.pop('fichero_editable', None)
        
        instance = super().create(validated_data)
        
        update_needed = False
        
        if fichero_pdf:
            path_pdf = self._subir_archivo_storage(instance, fichero_pdf, es_editable=False)
            if path_pdf:
                instance.archivo_pdf = path_pdf
                update_needed = True
                
        if fichero_editable:
            path_editable = self._subir_archivo_storage(instance, fichero_editable, es_editable=True)
            if path_editable:
                instance.archivo_editable = path_editable
                update_needed = True
        
        if update_needed:
            instance.save()
            
        return instance

    def update(self, instance, validated_data):
        fichero_pdf = validated_data.pop('fichero_pdf', None)
        fichero_editable = validated_data.pop('fichero_editable', None)
        
        instance = super().update(instance, validated_data)
        
        update_needed = False

        if fichero_pdf:
            path_pdf = self._subir_archivo_storage(instance, fichero_pdf, es_editable=False)
            if path_pdf:
                instance.archivo_pdf = path_pdf
                update_needed = True

        if fichero_editable:
            path_editable = self._subir_archivo_storage(instance, fichero_editable, es_editable=True)
            if path_editable:
                instance.archivo_editable = path_editable
                update_needed = True

        if update_needed:
            instance.save()
            
        return instance