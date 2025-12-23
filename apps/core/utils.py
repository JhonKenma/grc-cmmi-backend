# apps/core/utils.py
from django.utils import timezone
from datetime import datetime, timedelta

def calcular_dias_restantes(fecha_limite):
    """
    Calcula días restantes hasta una fecha límite
    """
    if not fecha_limite:
        return None
    
    hoy = timezone.now().date()
    if isinstance(fecha_limite, datetime):
        fecha_limite = fecha_limite.date()
    
    dias = (fecha_limite - hoy).days
    return dias

def esta_vencido(fecha_limite):
    """
    Verifica si una fecha ya venció
    """
    if not fecha_limite:
        return False
    
    hoy = timezone.now().date()
    if isinstance(fecha_limite, datetime):
        fecha_limite = fecha_limite.date()
    
    return fecha_limite < hoy

def calcular_porcentaje(valor, total):
    """
    Calcula porcentaje de forma segura
    """
    if not total or total == 0:
        return 0
    
    return round((valor / total) * 100, 2)