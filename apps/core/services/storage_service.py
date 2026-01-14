# apps/core/services/storage_service.py - CREAR

from django.conf import settings
from supabase import create_client, Client
from typing import Optional, BinaryIO
import uuid
import os
from datetime import datetime

class StorageService:
    """
    Servicio para gestionar archivos en Supabase Storage
        """
    def __init__(self):
            # Intentar obtener el cliente ya creado en settings
            self.supabase = getattr(settings, 'supabase', None)
            self.bucket = getattr(settings, 'SUPABASE_BUCKET', 'evidencias')

            # Si por alguna razón settings.supabase es None, lo creamos aquí mismo
            if self.supabase is None:
                url = getattr(settings, 'SUPABASE_URL', None)
                key = getattr(settings, 'SUPABASE_KEY', None)
                
                if url and key:
                    self.supabase = create_client(url, key)
                else:
                    raise ValueError("No se encontraron credenciales de Supabase en settings.py ni en .env")
            
    def upload_file(self, file: BinaryIO, folder: str, filename: Optional[str] = None) -> dict:
        try:
            # 1. Limpiar el folder para evitar duplicar el nombre del bucket
            # Si el bucket es 'evidencias', quitamos 'evidencias/' del inicio del folder
            clean_folder = folder.strip('/')
            if clean_folder.startswith(self.bucket):
                clean_folder = clean_folder[len(self.bucket):].strip('/')

            # 2. Generar nombre único si no existe
            if not filename:
                ext = os.path.splitext(file.name)[1]
                filename = f"{uuid.uuid4()}{ext}"
            
            # 3. El path final NO debe repetir el bucket
            file_path = f"{clean_folder}/{filename}"
            
            # Log para que verifiques en consola
            print(f"🚀 Subiendo a: {self.bucket} -> {file_path}")

            file.seek(0)
            file_content = file.read()
            
            # Subir a Supabase
            response = self.supabase.storage.from_(self.bucket).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": getattr(file, 'content_type', 'image/png'),
                    "upsert": "false"
                }
            )
            # Devolver resultado claro al llamador
            return {'success': True, 'path': file_path, 'response': response}
        except Exception as e:
            print(f"❌ Error al subir archivo: {e}")
            return {'success': False, 'error': str(e)}
        
    def delete_file(self, file_path: str) -> dict:
        """
        Eliminar archivo de Supabase Storage
        
        Args:
            file_path: Ruta del archivo en el bucket
        
        Returns:
            dict: {'success': bool, 'error': str}
        """
        try:
            self.supabase.storage.from_(self.bucket).remove([file_path])
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_file_url(self, file_path: str, expires_in: int = 3600) -> str:
        """
        Obtener URL firmada temporal para archivo privado
        
        Args:
            file_path: Ruta del archivo
            expires_in: Segundos de validez (default: 1 hora)
        
        Returns:
            str: URL firmada temporal
        """
        try:
            signed_url = self.supabase.storage.from_(self.bucket).create_signed_url(
                path=file_path,
                expires_in=expires_in
            )
            return signed_url.get('signedURL', '')
        except Exception as e:
            print(f"❌ Error al generar URL firmada: {e}")
            return ''
    
    def list_files(self, folder: str) -> list:
        """
        Listar archivos en una carpeta
        
        Args:
            folder: Ruta de la carpeta
        
        Returns:
            list: Lista de archivos
        """
        try:
            files = self.supabase.storage.from_(self.bucket).list(folder)
            return files
        except Exception as e:
            print(f"❌ Error al listar archivos: {e}")
            return []