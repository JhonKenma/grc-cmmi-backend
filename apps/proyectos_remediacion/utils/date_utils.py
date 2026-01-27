from datetime import date, timedelta
from typing import List


def agregar_dias_laborables(fecha_inicio, dias_laborables):
    fecha_actual = fecha_inicio
    dias_agregados = 0
    while dias_agregados < dias_laborables:
        fecha_actual += timedelta(days=1)
        if fecha_actual.weekday() < 5:
            dias_agregados += 1
    return fecha_actual


def calcular_dias_laborables_entre_fechas(fecha_inicio, fecha_fin):
    if fecha_fin < fecha_inicio:
        return 0
    dias_laborables = 0
    fecha_actual = fecha_inicio
    while fecha_actual <= fecha_fin:
        if fecha_actual.weekday() < 5:
            dias_laborables += 1
        fecha_actual += timedelta(days=1)
    return dias_laborables


def es_dia_laborable(fecha):
    return fecha.weekday() < 5
