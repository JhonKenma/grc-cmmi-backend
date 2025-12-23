import os
import uuid

def evidencia_upload_path(instance, filename):
    """
    Ruta de subida para archivos de evidencia.
    Formato: respuestas/evidencias/<respuesta_id>/<uuid>.<ext>
    """
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    respuesta_id = getattr(instance, 'respuesta', None)
    respuesta_id = getattr(respuesta_id, 'id', respuesta_id) if respuesta_id else 'no_respuesta'
    return f"respuestas/evidencias/{respuesta_id}/{unique_name}"