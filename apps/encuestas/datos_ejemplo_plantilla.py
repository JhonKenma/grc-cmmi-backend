# apps/encuestas/datos_ejemplo_plantilla.py

"""
Datos de ejemplo para la plantilla Excel de encuestas
Cada pregunta debe tener exactamente 5 niveles (1-5)
"""

DATOS_EJEMPLO_PLANTILLA = [
    # ========================================
    # PREGUNTA 1: Planificación Estratégica
    # ========================================
    
    # Nivel 1
    [
        '1',  # seccion_codigo
        'Gestión Estratégica',  # seccion_nombre
        'GES1.1',  # pregunta_codigo
        'Planificación Estratégica',  # pregunta_titulo
        '¿La organización cuenta con un plan estratégico formal documentado y comunicado?',  # pregunta_texto
        1,  # nivel_numero
        'No existe plan estratégico. Las decisiones son reactivas y no hay visión a largo plazo.',  # nivel_descripcion
        'Formar comité estratégico. Realizar diagnóstico FODA. Definir misión, visión y objetivos estratégicos.',  # nivel_recomendaciones
        4,  # nivel_deseado (solo en nivel 1)
        1.5  # peso (solo en nivel 1)
    ],
    
    # Nivel 2
    [
        '1',
        'Gestión Estratégica',
        'GES1.1',
        'Planificación Estratégica',
        '¿La organización cuenta con un plan estratégico formal documentado y comunicado?',
        2,
        'Existe plan estratégico informal o desactualizado. Comunicación limitada a nivel gerencial.',
        'Documentar plan estratégico. Establecer objetivos SMART. Comunicar a toda la organización.',
        '',  # nivel_deseado vacío
        ''   # peso vacío
    ],
    
    # Nivel 3
    [
        '1',
        'Gestión Estratégica',
        'GES1.1',
        'Planificación Estratégica',
        '¿La organización cuenta con un plan estratégico formal documentado y comunicado?',
        3,
        'Plan estratégico documentado y comunicado. Seguimiento anual con indicadores básicos.',
        'Implementar BSC (Balanced Scorecard). Establecer seguimiento trimestral de KPIs.',
        '',
        ''
    ],
    
    # Nivel 4
    [
        '1',
        'Gestión Estratégica',
        'GES1.1',
        'Planificación Estratégica',
        '¿La organización cuenta con un plan estratégico formal documentado y comunicado?',
        4,
        'Plan estratégico con seguimiento trimestral, ajustes basados en resultados y cultura de mejora continua.',
        'Implementar dashboard ejecutivo. Establecer proceso de revisión estratégica formal.',
        '',
        ''
    ],
    
    # Nivel 5
    [
        '1',
        'Gestión Estratégica',
        'GES1.1',
        'Planificación Estratégica',
        '¿La organización cuenta con un plan estratégico formal documentado y comunicado?',
        5,
        'Gestión estratégica madura con análisis predictivo, escenarios y agilidad para adaptarse al mercado.',
        'Benchmark con líderes de industria. Implementar war rooms estratégicos y análisis de tendencias.',
        '',
        ''
    ],
    
    # ========================================
    # PREGUNTA 2: Documentación de Procesos
    # ========================================
    
    # Nivel 1
    [
        '2',
        'Gestión de Procesos',
        'PRO2.1',
        'Documentación de Procesos',
        '¿Los procesos clave de la organización están documentados, estandarizados y optimizados?',
        1,
        'Procesos no documentados. Trabajo basado en conocimiento tácito y experiencia individual.',
        'Identificar procesos clave. Realizar mapeo de procesos críticos con metodología BPMN.',
        3,
        1.2
    ],
    
    # Nivel 2
    [
        '2',
        'Gestión de Procesos',
        'PRO2.1',
        'Documentación de Procesos',
        '¿Los procesos clave de la organización están documentados, estandarizados y optimizados?',
        2,
        'Algunos procesos documentados de forma básica. Falta estandarización y actualización.',
        'Crear repositorio de procesos. Estandarizar nomenclatura y formato de documentación.',
        '',
        ''
    ],
    
    # Nivel 3
    [
        '2',
        'Gestión de Procesos',
        'PRO2.1',
        'Documentación de Procesos',
        '¿Los procesos clave de la organización están documentados, estandarizados y optimizados?',
        3,
        'Procesos documentados y estandarizados. Seguimiento de indicadores de desempeño.',
        'Implementar sistema BPM. Establecer dueños de proceso y SLAs.',
        '',
        ''
    ],
    
    # Nivel 4
    [
        '2',
        'Gestión de Procesos',
        'PRO2.1',
        'Documentación de Procesos',
        '¿Los procesos clave de la organización están documentados, estandarizados y optimizados?',
        4,
        'Procesos optimizados con mejora continua. Automatización de actividades repetitivas.',
        'Implementar RPA (Robotic Process Automation). Establecer programa de mejora continua.',
        '',
        ''
    ],
    
    # Nivel 5
    [
        '2',
        'Gestión de Procesos',
        'PRO2.1',
        'Documentación de Procesos',
        '¿Los procesos clave de la organización están documentados, estandarizados y optimizados?',
        5,
        'Procesos end-to-end optimizados con IA, automatización inteligente y adaptación en tiempo real.',
        'Implementar process mining e inteligencia artificial predictiva para optimización continua.',
        '',
        ''
    ],
    
    # ========================================
    # PREGUNTA 3: Gestión de Riesgos
    # ========================================
    
    # Nivel 1
    [
        '3',
        'Gestión de Riesgos',
        'RIE3.1',
        'Identificación y Gestión de Riesgos',
        '¿La organización tiene implementado un sistema de gestión de riesgos?',
        1,
        'No hay identificación formal de riesgos. La gestión es reactiva ante problemas.',
        'Realizar matriz de riesgos inicial. Identificar top 10 riesgos críticos del negocio.',
        5,
        1.3
    ],
    
    # Nivel 2
    [
        '3',
        'Gestión de Riesgos',
        'RIE3.1',
        'Identificación y Gestión de Riesgos',
        '¿La organización tiene implementado un sistema de gestión de riesgos?',
        2,
        'Identificación básica de riesgos en áreas clave. Sin metodología estandarizada.',
        'Adoptar marco de referencia (ISO 31000, COSO ERM). Capacitar en gestión de riesgos.',
        '',
        ''
    ],
    
    # Nivel 3
    [
        '3',
        'Gestión de Riesgos',
        'RIE3.1',
        'Identificación y Gestión de Riesgos',
        '¿La organización tiene implementado un sistema de gestión de riesgos?',
        3,
        'Sistema formal de gestión de riesgos con metodología definida y actualización periódica.',
        'Implementar herramienta GRC. Establecer comité de riesgos y reportes ejecutivos.',
        '',
        ''
    ],
    
    # Nivel 4
    [
        '3',
        'Gestión de Riesgos',
        'RIE3.1',
        'Identificación y Gestión de Riesgos',
        '¿La organización tiene implementado un sistema de gestión de riesgos?',
        4,
        'Gestión integrada de riesgos con monitoreo continuo y planes de mitigación activos.',
        'Implementar risk appetite framework. Establecer indicadores de riesgo (KRIs).',
        '',
        ''
    ],
    
    # Nivel 5
    [
        '3',
        'Gestión de Riesgos',
        'RIE3.1',
        'Identificación y Gestión de Riesgos',
        '¿La organización tiene implementado un sistema de gestión de riesgos?',
        5,
        'Gestión de riesgos madura con análisis predictivo, simulaciones y cultura de risk awareness.',
        'Implementar análisis de escenarios con IA. Establecer stress testing periódico.',
        '',
        ''
    ],
]

# Nota explicativa para incluir en la plantilla
NOTA_EXPLICATIVA = (
    "Los datos anteriores son EJEMPLOS para que veas la estructura. "
    "Elimina estas filas y agrega tus propios datos. "
    "IMPORTANTE: Cada pregunta debe tener exactamente 5 niveles (del 1 al 5). "
    "Solo completa 'nivel_deseado' y 'peso' en la primera fila de cada pregunta (nivel 1)."
)