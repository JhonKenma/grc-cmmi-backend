# apps/encuestas/admin.py
from django.contrib import admin
from .models import (
    Encuesta, Dimension, Pregunta, 
    NivelReferencia, ConfigNivelDeseado
)

class NivelReferenciaInline(admin.TabularInline):
    model = NivelReferencia
    extra = 5
    max_num = 5
    min_num = 5
    fields = ['numero', 'descripcion', 'recomendaciones', 'activo']

@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'titulo', 'dimension', 'peso', 'obligatoria', 'orden', 'activo']
    list_filter = ['dimension__encuesta', 'dimension', 'obligatoria', 'activo']
    search_fields = ['codigo', 'titulo', 'texto']
    inlines = [NivelReferenciaInline]
    ordering = ['dimension', 'orden']

class PreguntaInline(admin.TabularInline):
    model = Pregunta
    extra = 0
    fields = ['codigo', 'titulo', 'peso', 'orden', 'activo']
    show_change_link = True

@admin.register(Dimension)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'encuesta', 'orden', 'total_preguntas', 'activo']
    list_filter = ['encuesta', 'activo']
    search_fields = ['codigo', 'nombre']
    inlines = [PreguntaInline]
    ordering = ['encuesta', 'orden']

class DimensionInline(admin.TabularInline):
    model = Dimension
    extra = 0
    fields = ['codigo', 'nombre', 'orden', 'activo']
    show_change_link = True

@admin.register(Encuesta)
class EncuestaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'version', 'total_dimensiones', 'total_preguntas', 'es_plantilla', 'activo', 'fecha_creacion']
    list_filter = ['es_plantilla', 'activo', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    inlines = [DimensionInline]
    readonly_fields = ['total_dimensiones', 'total_preguntas', 'fecha_creacion', 'fecha_actualizacion']

@admin.register(ConfigNivelDeseado)
class ConfigNivelDeseadoAdmin(admin.ModelAdmin):
    list_display = ['dimension', 'empresa', 'nivel_deseado', 'configurado_por', 'fecha_creacion']
    list_filter = ['empresa', 'nivel_deseado', 'fecha_creacion']
    search_fields = ['dimension__nombre', 'empresa__nombre']
    readonly_fields = ['configurado_por', 'fecha_creacion', 'fecha_actualizacion']