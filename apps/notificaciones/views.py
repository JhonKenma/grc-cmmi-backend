# apps/notificaciones/views.py
from datetime import timedelta, timezone
from venv import logger
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Q

from apps.usuarios.models import Usuario
from .models import Notificacion, PlantillaNotificacion
from .serializers import (
    EnviarNotificacionSerializer,
    NotificacionSerializer,
    NotificacionDetalleSerializer,  # ⭐ NUEVO
    NotificacionListSerializer,
    MarcarLeidaSerializer,
    PlantillaNotificacionSerializer
)
from .services import NotificacionService
from apps.core.mixins import ResponseMixin
from apps.core.permissions import EsAdminOSuperAdmin, EsSuperAdmin
from datetime import timedelta
from django.utils import timezone

class NotificacionViewSet(ResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para gestión de notificaciones del usuario
    
    ENDPOINTS:
    - GET    /api/notificaciones/                → Listar mis notificaciones
    - GET    /api/notificaciones/{id}/           → 🆕 Detalle COMPLETO de notificación
    - GET    /api/notificaciones/no_leidas/      → Obtener no leídas
    - GET    /api/notificaciones/contador/       → Contador de no leídas
    - POST   /api/notificaciones/{id}/marcar_leida/ → Marcar como leída
    - POST   /api/notificaciones/marcar_todas_leidas/ → Marcar todas como leídas
    - GET    /api/notificaciones/por_tipo/       → Filtrar por tipo
    - POST   /api/notificaciones/test_email/     → 🧪 Probar envío de emails
    
    PERMISOS:
    - Usuario autenticado: Solo puede ver sus propias notificaciones
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Usa serializer detallado para retrieve (GET /id/)"""
        # 🛡️ PROTECCIÓN: Si es anónimo, retornar el más básico para evitar circulares en documentación
        if not self.request.user or self.request.user.is_anonymous:
            return NotificacionListSerializer

        if self.action == 'retrieve':
            return NotificacionDetalleSerializer
        elif self.action == 'list':
            return NotificacionListSerializer
        elif self.action in ['marcar_leida', 'marcar_todas_leidas']:
            return MarcarLeidaSerializer
        return NotificacionSerializer
    
    def get_queryset(self):
        """Usuario solo ve sus propias notificaciones"""
        user = self.request.user
        
        # 🛡️ PROTECCIÓN: Vital para Render y Swagger
        if not user or user.is_anonymous:
            return Notificacion.objects.none()
            
        return Notificacion.objects.filter(
            usuario=user,
            activo=True
        ).select_related('usuario').order_by('-fecha_creacion')
    
    def retrieve(self, request, *args, **kwargs):
        """
        🆕 MEJORADO: Obtener detalle COMPLETO de una notificación
        
        GET /api/notificaciones/{id}/
        
        Retorna:
        - Todos los datos de la notificación
        - Información del usuario
        - Información de la asignación relacionada (si existe)
        - Metadata adicional (días transcurridos, si puede marcarse como leída, etc.)
        - Marca automáticamente como leída al abrirla
        
        Response:
        {
            "id": "uuid",
            "usuario": {
                "id": "uuid",
                "email": "admin@example.com",
                "nombre": "Juan",
                "apellido": "Pérez",
                "nombre_completo": "Juan Pérez",
                "rol": "administrador"
            },
            "tipo": "asignacion_evaluacion",
            "tipo_display": "Asignación de Evaluación",
            "titulo": "Nueva evaluación asignada: ISO 27001",
            "mensaje": "Se te ha asignado la evaluación...",
            "prioridad": "alta",
            "prioridad_display": "Alta",
            "leida": false,
            "fecha_leida": null,
            "email_enviado": true,
            "url_accion": "/evaluaciones/uuid",
            "datos_adicionales": {...},
            "asignacion_info": {
                "id": "uuid",
                "tipo": "evaluacion_completa",
                "estado": "pendiente",
                "fecha_limite": "2025-01-15",
                "dias_restantes": 30,
                "esta_vencido": false,
                "progreso": "0%",
                "encuesta": {
                    "id": "uuid",
                    "nombre": "ISO 27001",
                    "descripcion": "..."
                },
                "asignado_a": {
                    "id": "uuid",
                    "nombre": "Juan Pérez",
                    "email": "admin@example.com"
                },
                "asignado_por": {
                    "id": "uuid",
                    "nombre": "SuperAdmin User"
                },
                "total_dimensiones": 10,
                "total_preguntas": 50
            },
            "fecha_creacion": "2025-12-13T10:30:00Z",
            "fecha_actualizacion": "2025-12-13T10:30:00Z",
            "tiempo_transcurrido": "Hace 2 horas",
            "dias_desde_creacion": 0,
            "activo": true,
            "puede_marcar_leida": true
        }
        """
        instance = self.get_object()
        
        # ⭐ Marcar como leída automáticamente al abrirla
        if not instance.leida:
            instance.marcar_como_leida()
        
        serializer = self.get_serializer(instance)
        
        return self.success_response(
            data=serializer.data,
            message='Detalle de notificación obtenido exitosamente'
        )
    
    @action(detail=False, methods=['get'], url_path='no_leidas')
    def no_leidas(self, request):
            # 🛡️ PROTECCIÓN adicional
            if request.user.is_anonymous:
                return Response({'count': 0, 'results': []})
                
            limite = int(request.query_params.get('limite', 50))
            notificaciones = NotificacionService.obtener_no_leidas(
                usuario=request.user,
                limite=limite
            )
            serializer = NotificacionListSerializer(notificaciones, many=True)
            return Response({
                'count': notificaciones.count(),
                'results': serializer.data
            })
    
    @action(detail=False, methods=['get'], url_path='contador')
    def contador(self, request):
            # 🛡️ PROTECCIÓN adicional
            if request.user.is_anonymous:
                return Response({'no_leidas': 0})
                
            count = NotificacionService.contar_no_leidas(usuario=request.user)
            return Response({'no_leidas': count})
    
    @action(detail=True, methods=['post'], url_path='marcar_leida')
    def marcar_leida(self, request, pk=None):
        """
        Marcar notificación específica como leída
        POST /api/notificaciones/{id}/marcar_leida/
        """
        notificacion = self.get_object()
        
        if notificacion.leida:
            return self.success_response(
                data=NotificacionSerializer(notificacion).data,
                message='La notificación ya estaba marcada como leída'
            )
        
        notificacion.marcar_como_leida()
        
        return self.success_response(
            data=NotificacionSerializer(notificacion).data,
            message='Notificación marcada como leída'
        )
    
    @action(detail=False, methods=['post'], url_path='marcar_todas_leidas')
    def marcar_todas_leidas(self, request):
        """
        Marcar todas las notificaciones del usuario como leídas
        POST /api/notificaciones/marcar_todas_leidas/
        """
        count = NotificacionService.marcar_todas_leidas(usuario=request.user)
        
        return self.success_response(
            data={'marcadas': count},
            message=f'{count} notificaciones marcadas como leídas'
        )
    
    @action(detail=False, methods=['get'], url_path='por_tipo')
    def por_tipo(self, request):
        """
        Filtrar notificaciones por tipo
        GET /api/notificaciones/por_tipo/?tipo=asignacion_evaluacion
        """
        tipo = request.query_params.get('tipo')
        
        if not tipo:
            return self.error_response(
                message='Parámetro "tipo" es requerido',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        notificaciones = self.get_queryset().filter(tipo=tipo)
        serializer = NotificacionListSerializer(notificaciones, many=True)
        
        return Response({
            'count': notificaciones.count(),
            'results': serializer.data
        })
    
    # ========================================================================
    # 🧪 ENDPOINT DE PRUEBA DE EMAIL (MAILTRAP)
    # ========================================================================
    
    @action(detail=False, methods=['post'], url_path='test_email', permission_classes=[AllowAny])
    def test_email(self, request):
        """
        🧪 Endpoint para probar envío de emails con Mailtrap
        
        Este endpoint es SOLO para verificar que la configuración de email funciona.
        NO afecta la lógica de asignaciones ni notificaciones reales.
        
        POST /api/notificaciones/test_email/
        
        Body (opcional):
        {
            "email": "test@example.com",     // Email destino (cualquiera, es solo prueba)
            "nombre": "Usuario Prueba"        // Nombre para personalizar
        }
        
        Uso:
        1. Configura Mailtrap en .env (EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        2. Llama a este endpoint
        3. Verifica en https://mailtrap.io/inboxes que llegó el email
        
        Returns:
        - success: True/False
        - message: Mensaje de resultado
        - detalles: Información de la configuración SMTP
        - instrucciones: Pasos para verificar en Mailtrap
        """
        email_destino = request.data.get('email', 'test@example.com')
        nombre_usuario = request.data.get('nombre', 'Usuario de Prueba')
        
        try:
            # ================================================================
            # HTML MEJORADO DEL EMAIL DE PRUEBA
            # ================================================================
            html_message = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Email de Prueba - Sistema GRC</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        background-color: #f4f4f4;
                    }}
                    .email-container {{
                        max-width: 600px;
                        margin: 40px auto;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        padding: 40px 30px;
                        text-align: center;
                        color: white;
                    }}
                    .header h1 {{
                        font-size: 28px;
                        font-weight: 700;
                        margin-bottom: 10px;
                    }}
                    .content {{
                        background: white;
                        padding: 40px 30px;
                    }}
                    .content h2 {{
                        color: #667eea;
                        font-size: 24px;
                        margin-bottom: 20px;
                    }}
                    .success-badge {{
                        background: #10b981;
                        color: white;
                        padding: 12px 24px;
                        border-radius: 6px;
                        display: inline-block;
                        font-weight: 600;
                        margin: 20px 0;
                    }}
                    .checklist {{
                        list-style: none;
                        margin: 20px 0;
                    }}
                    .checklist li {{
                        padding: 10px 0;
                        border-bottom: 1px solid #e5e7eb;
                    }}
                    .checklist li:last-child {{
                        border-bottom: none;
                    }}
                    .checklist li::before {{
                        content: '✅';
                        margin-right: 10px;
                    }}
                    .info-box {{
                        background: #f3f4f6;
                        border-left: 4px solid #667eea;
                        padding: 16px;
                        margin: 20px 0;
                        border-radius: 4px;
                    }}
                    .footer {{
                        background: #f9fafb;
                        padding: 20px 30px;
                        text-align: center;
                        font-size: 12px;
                        color: #6b7280;
                    }}
                    .button {{
                        display: inline-block;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 14px 32px;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 600;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="email-container">
                    <div class="header">
                        <h1>🧪 Email de Prueba</h1>
                        <p>Sistema GRC - Verificación de Notificaciones</p>
                    </div>
                    
                    <div class="content">
                        <h2>¡Hola, {nombre_usuario}!</h2>
                        
                        <p>Si estás viendo este email en tu bandeja de <strong>Mailtrap</strong>, significa que tu configuración está funcionando correctamente.</p>
                        
                        <div class="success-badge">
                            🎉 Sistema de notificaciones funcionando
                        </div>
                        
                        <h3>Verificaciones completadas:</h3>
                        <ul class="checklist">
                            <li>Django configurado correctamente</li>
                            <li>Credenciales SMTP válidas</li>
                            <li>Servidor puede enviar emails</li>
                            <li>Template HTML renderizando bien</li>
                            <li>Estilos CSS aplicados correctamente</li>
                        </ul>
                        
                        <div class="info-box">
                            <strong>📧 Email de destino:</strong> {email_destino}<br>
                            <strong>🕐 Enviado desde:</strong> Sistema GRC Backend<br>
                            <strong>🌐 Entorno:</strong> Desarrollo (Mailtrap)<br>
                            <strong>⚙️ Backend:</strong> {settings.EMAIL_BACKEND.split('.')[-1]}
                        </div>
                        
                        <center>
                            <a href="https://mailtrap.io/inboxes" class="button">
                                Ver en Mailtrap →
                            </a>
                        </center>
                        
                        <p style="margin-top: 30px; font-size: 14px; color: #6b7280;">
                            Este es un email de prueba. Las notificaciones reales se envían automáticamente 
                            cuando se asignan evaluaciones o tareas a los usuarios.
                        </p>
                    </div>
                    
                    <div class="footer">
                        <p>Sistema GRC Backend &copy; 2025</p>
                        <p>Powered by Django + Mailtrap</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # ================================================================
            # VERSIÓN TEXTO PLANO (FALLBACK)
            # ================================================================
            plain_message = f"""
            🧪 EMAIL DE PRUEBA - SISTEMA GRC
            
            ¡Hola, {nombre_usuario}!
            
            Si estás viendo este email en Mailtrap, tu configuración es correcta.
            
            ✅ Django configurado
            ✅ Credenciales SMTP válidas
            ✅ Servidor puede enviar emails
            
            Email: {email_destino}
            Entorno: Desarrollo (Mailtrap)
            Backend: {settings.EMAIL_BACKEND}
            
            Las notificaciones reales se envían automáticamente cuando se asignan 
            evaluaciones o tareas a los usuarios.
            
            ---
            Sistema GRC Backend © 2025
            """
            
            # ================================================================
            # ENVIAR EMAIL
            # ================================================================
            resultado = send_mail(
                subject='🧪 Email de Prueba - Sistema GRC',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_destino],
                fail_silently=False,
                html_message=html_message
            )
            
            if resultado == 1:  # 1 = email enviado exitosamente
                return Response({
                    'success': True,
                    'message': f'✅ Email de prueba enviado exitosamente a {email_destino}',
                    'detalles': {
                        'destinatario': email_destino,
                        'remitente': settings.DEFAULT_FROM_EMAIL,
                        'servidor': settings.EMAIL_HOST,
                        'puerto': settings.EMAIL_PORT,
                        'backend': settings.EMAIL_BACKEND,
                    },
                    'instrucciones': {
                        'paso_1': 'Ve a https://mailtrap.io/inboxes',
                        'paso_2': 'Click en "My Inbox" (o el nombre de tu inbox)',
                        'paso_3': '¡Deberías ver el email ahí! 🎉',
                        'nota': 'Este es solo un TEST. Las notificaciones reales se envían al asignar evaluaciones.'
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'send_mail retornó 0',
                    'message': 'No se pudo enviar el email'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'tipo_error': type(e).__name__,
                'sugerencias': {
                    'credenciales': 'Verifica EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en .env',
                    'conexion': 'Asegúrate de tener conexión a internet',
                    'puerto': f'Puerto actual: {settings.EMAIL_PORT}',
                    'host': f'Host actual: {settings.EMAIL_HOST}',
                    'backend': f'Backend actual: {settings.EMAIL_BACKEND}',
                },
                'mensaje': '❌ Error al enviar email de prueba. Verifica la configuración en .env'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=False, methods=['post'], url_path='enviar-personalizada', permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def enviar_personalizada(self, request):
        """
        Enviar notificación personalizada a usuarios
        
        POST /api/notificaciones/enviar-personalizada/
        
        Permisos:
        - SuperAdmin: Puede enviar a cualquier usuario/empresa
        - Administrador: Solo puede enviar a usuarios de su empresa
        
        Body:
        {
            // DESTINATARIOS (al menos uno requerido):
            "usuario_id": 123,                    // Un usuario específico
            "empresa_id": 456,                    // Todos los usuarios de una empresa
            "enviar_a_todos_admins": true,       // Todos los administradores
            "enviar_a_todos": true,              // Todos los usuarios (solo SuperAdmin)
            
            // CONTENIDO:
            "tipo": "mensaje_personalizado",     // o "anuncio"
            "titulo": "Importante: Mantenimiento del Sistema",
            "mensaje": "El sistema estará en mantenimiento...",
            "prioridad": "alta",                 // baja, normal, alta, urgente
            "url_accion": "https://app.example.com/anuncios/123",
            "enviar_email": true
        }
        
        Response:
        {
            "success": true,
            "message": "Notificación enviada exitosamente",
            "data": {
                "usuarios_notificados": 15,
                "emails_enviados": 15,
                "destinatarios": [
                    {"id": 1, "nombre": "Juan Pérez", "email": "juan@example.com"},
                    ...
                ]
            }
        }
        """
        serializer = EnviarNotificacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        user = request.user
        
        # ═══ DETERMINAR DESTINATARIOS ═══
        destinatarios = []
        
        # 1. Usuario individual
        if data.get('usuario_id'):
            try:
                usuario = Usuario.objects.get(id=data['usuario_id'], activo=True)
                
                # Validar permisos
                if user.rol == 'administrador':
                    if usuario.empresa != user.empresa:
                        return self.error_response(
                            message='No tienes permisos para enviar notificaciones a usuarios de otras empresas',
                            status_code=status.HTTP_403_FORBIDDEN
                        )
                
                destinatarios.append(usuario)
            except Usuario.DoesNotExist:
                return self.error_response(
                    message='Usuario no encontrado',
                    status_code=status.HTTP_404_NOT_FOUND
                )
        
        # 2. Todos los usuarios de una empresa
        if data.get('empresa_id'):
            if user.rol == 'administrador':
                if user.empresa and user.empresa.id != data['empresa_id']:
                    return self.error_response(
                        message='Solo puedes enviar notificaciones a tu propia empresa',
                        status_code=status.HTTP_403_FORBIDDEN
                    )
            
            usuarios_empresa = Usuario.objects.filter(
                empresa_id=data['empresa_id'],
                activo=True
            )
            destinatarios.extend(list(usuarios_empresa))
        
        # 3. Todos los administradores
        if data.get('enviar_a_todos_admins'):
            if user.rol == 'administrador':
                # Admin solo puede enviar a admins de su empresa
                admins = Usuario.objects.filter(
                    rol='administrador',
                    empresa=user.empresa,
                    activo=True
                )
            else:
                # SuperAdmin puede enviar a todos los admins
                admins = Usuario.objects.filter(
                    rol='administrador',
                    activo=True
                )
            destinatarios.extend(list(admins))
        
        # 4. Todos los usuarios (solo SuperAdmin)
        if data.get('enviar_a_todos'):
            if user.rol != 'superadmin':
                return self.error_response(
                    message='Solo SuperAdmin puede enviar notificaciones a todos los usuarios',
                    status_code=status.HTTP_403_FORBIDDEN
                )
            
            todos = Usuario.objects.filter(activo=True)
            destinatarios.extend(list(todos))
        
        # Eliminar duplicados
        destinatarios = list(set(destinatarios))
        
        if not destinatarios:
            return self.error_response(
                message='No se encontraron destinatarios válidos',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # ═══ CREAR NOTIFICACIONES ═══
        notificaciones_creadas = []
        emails_enviados = 0
        
        for destinatario in destinatarios:
            try:
                notificacion = NotificacionService.crear_notificacion(
                    usuario=destinatario,
                    tipo=data['tipo'],
                    titulo=data['titulo'],
                    mensaje=data['mensaje'],
                    prioridad=data['prioridad'],
                    url_accion=data.get('url_accion', ''),
                    datos_adicionales={
                        'enviado_por': user.nombre_completo,
                        'enviado_por_id': user.id,
                        'fecha_envio': timezone.now().isoformat(),
                    },
                    enviar_email=data['enviar_email']
                )
                notificaciones_creadas.append(notificacion)
                
                if notificacion.email_enviado:
                    emails_enviados += 1
                    
            except Exception as e:
                logger.error(f"Error al enviar notificación a {destinatario.email}: {str(e)}")
                continue
        
        # ═══ RESPUESTA ═══
        return self.success_response(
            data={
                'usuarios_notificados': len(notificaciones_creadas),
                'emails_enviados': emails_enviados,
                'destinatarios': [
                    {
                        'id': d.id,
                        'nombre': d.nombre_completo,
                        'email': d.email,
                        'rol': d.rol
                    }
                    for d in destinatarios
                ]
            },
            message=f'Notificación enviada exitosamente a {len(notificaciones_creadas)} usuario(s)'
        )


    @action(detail=False, methods=['get'], url_path='historial')
    def historial(self, request):
        """
        Obtener historial de notificaciones con filtros
        
        GET /api/notificaciones/historial/?periodo=nuevas&limite=50
        
        Parámetros:
        - periodo: nuevas | semana | mes | todas (default: nuevas)
        - limite: cantidad máxima (default: 50, max: 200)
        
        Periodos:
        - nuevas: No leídas
        - semana: Leídas en los últimos 7 días
        - mes: Leídas en los últimos 30 días
        - todas: Todas las notificaciones
        
        Response:
        {
            "success": true,
            "data": {
                "periodo": "semana",
                "total": 15,
                "nuevas": 5,
                "leidas": 10,
                "notificaciones": [...]
            }
        }
        """
        periodo = request.query_params.get('periodo', 'nuevas')
        limite = int(request.query_params.get('limite', 50))
        limite = min(limite, 200)  # Máximo 200
        
        user = request.user
        queryset = Notificacion.objects.filter(
            usuario=user,
            activo=True
        ).select_related('usuario').order_by('-fecha_creacion')
        
        # ═══ APLICAR FILTROS POR PERIODO ═══
        ahora = timezone.now()
        
        if periodo == 'nuevas':
            # Solo no leídas
            queryset = queryset.filter(leida=False)
        
        elif periodo == 'semana':
            # Leídas en los últimos 7 días
            hace_semana = ahora - timedelta(days=7)
            queryset = queryset.filter(
                Q(leida=False) |  # Incluir no leídas también
                Q(leida=True, fecha_leida__gte=hace_semana)
            )
        
        elif periodo == 'mes':
            # Leídas en los últimos 30 días
            hace_mes = ahora - timedelta(days=30)
            queryset = queryset.filter(
                Q(leida=False) |  # Incluir no leídas también
                Q(leida=True, fecha_leida__gte=hace_mes)
            )
        
        elif periodo == 'todas':
            # Todas (sin filtro adicional)
            pass
        
        # ═══ LIMITAR RESULTADOS ═══
        total = queryset.count()
        notificaciones = queryset[:limite]
        
        # ═══ CONTAR NUEVAS Y LEÍDAS ═══
        nuevas = queryset.filter(leida=False).count()
        leidas = queryset.filter(leida=True).count()
        
        # ═══ SERIALIZAR ═══
        serializer = NotificacionListSerializer(notificaciones, many=True)
        
        return self.success_response(
            data={
                'periodo': periodo,
                'total': total,
                'mostrando': len(notificaciones),
                'nuevas': nuevas,
                'leidas': leidas,
                'notificaciones': serializer.data
            }
        )


    @action(detail=False, methods=['get'], url_path='estadisticas')
    def estadisticas(self, request):
        """
        Estadísticas de notificaciones del usuario
        
        GET /api/notificaciones/estadisticas/
        
        Response:
        {
            "success": true,
            "data": {
                "total": 50,
                "nuevas": 5,
                "leidas_semana": 10,
                "leidas_mes": 20,
                "por_tipo": {
                    "mensaje_personalizado": 15,
                    "asignacion_evaluacion": 10,
                    ...
                },
                "por_prioridad": {
                    "urgente": 2,
                    "alta": 8,
                    "normal": 35,
                    "baja": 5
                }
            }
        }
        """
        user = request.user
        ahora = timezone.now()
        
        queryset = Notificacion.objects.filter(usuario=user, activo=True)
        
        # Contadores
        total = queryset.count()
        nuevas = queryset.filter(leida=False).count()
        
        hace_semana = ahora - timedelta(days=7)
        leidas_semana = queryset.filter(
            leida=True,
            fecha_leida__gte=hace_semana
        ).count()
        
        hace_mes = ahora - timedelta(days=30)
        leidas_mes = queryset.filter(
            leida=True,
            fecha_leida__gte=hace_mes
        ).count()
        
        # Por tipo
        from django.db.models import Count
        por_tipo = dict(
            queryset.values_list('tipo').annotate(count=Count('tipo'))
        )
        
        # Por prioridad
        por_prioridad = dict(
            queryset.values_list('prioridad').annotate(count=Count('prioridad'))
        )
        
        return self.success_response(
            data={
                'total': total,
                'nuevas': nuevas,
                'leidas_semana': leidas_semana,
                'leidas_mes': leidas_mes,
                'por_tipo': por_tipo,
                'por_prioridad': por_prioridad
            }
        )

    @action(detail=False, methods=['get'], url_path='usuarios-disponibles', permission_classes=[IsAuthenticated, EsAdminOSuperAdmin])
    def usuarios_disponibles(self, request):
        """
        Obtener lista de usuarios para enviar notificaciones
        GET /api/notificaciones/usuarios-disponibles/
        
        Admin: Solo ve usuarios de su empresa
        SuperAdmin: Ve todos los usuarios
        """
        user = request.user
        
        # Filtrar según rol
        if user.rol == 'superadmin':
            usuarios = Usuario.objects.filter(activo=True).select_related('empresa')
        elif user.rol == 'administrador':
            if user.empresa:
                usuarios = Usuario.objects.filter(empresa=user.empresa, activo=True).select_related('empresa')
            else:
                usuarios = Usuario.objects.none()
        else:
            return self.error_response(
                message='No tienes permisos para acceder a esta lista',
                status_code=status.HTTP_403_FORBIDDEN
            )
        
        # Construir lista de usuarios
        usuarios_list = []
        for u in usuarios:
            usuario_dict = {
                'id': u.id,
                'nombre_completo': u.nombre_completo,
                'email': u.email,
                'rol': u.rol,
            }
            
            if u.empresa:
                usuario_dict['empresa_info'] = {
                    'id': u.empresa.id,
                    'nombre': u.empresa.nombre
                }
            
            usuarios_list.append(usuario_dict)
        
        return self.success_response(
            data=usuarios_list
        )


    @action(detail=False, methods=['get'], url_path='empresas-disponibles', permission_classes=[IsAuthenticated, EsSuperAdmin])
    def empresas_disponibles(self, request):
        """
        Obtener lista de empresas (solo SuperAdmin)
        GET /api/notificaciones/empresas-disponibles/
        """
        from apps.empresas.models import Empresa
        
        empresas = Empresa.objects.filter(activo=True).values('id', 'nombre', 'ruc')
        
        return self.success_response(
            data=list(empresas)
        )


class PlantillaNotificacionViewSet(ResponseMixin, viewsets.ModelViewSet):
    """
    ViewSet para gestión de plantillas de notificaciones
    
    PERMISOS:
    - Solo SuperAdmin y Administradores pueden gestionar plantillas
    """
    queryset = PlantillaNotificacion.objects.all()
    serializer_class = PlantillaNotificacionSerializer
    permission_classes = [IsAuthenticated, EsAdminOSuperAdmin]
    
    def get_queryset(self):
        return PlantillaNotificacion.objects.filter(activo=True).order_by('nombre')
    
    @action(detail=True, methods=['post'], url_path='probar')
    def probar(self, request, pk=None):
        """
        Probar plantilla enviando notificación al usuario actual
        POST /api/plantillas-notificacion/{id}/probar/
        Body: {"contexto": {"nombre": "Juan", "encuesta": "Evaluación 2024"}}
        """
        plantilla = self.get_object()
        contexto = request.data.get('contexto', {})
        
        try:
            notificacion = NotificacionService.crear_desde_plantilla(
                usuario=request.user,
                tipo_plantilla=plantilla.tipo,
                contexto=contexto,
                url_accion='/test'
            )
            
            return self.success_response(
                data=NotificacionSerializer(notificacion).data,
                message='Notificación de prueba enviada'
            )
        except Exception as e:
            return self.error_response(
                message='Error al probar plantilla',
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
            