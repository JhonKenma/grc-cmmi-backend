from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.asignaciones_iq.models import AsignacionEvaluacionIQ, RespuestaEvaluacionIQ
from apps.empresas.models import Empresa
from apps.evaluaciones.models import Evaluacion, Framework, PreguntaEvaluacion
from apps.respuestas.models import Evidencia
from apps.usuarios.models import Usuario


class EvidenciaIQDeleteTests(APITestCase):
	def setUp(self):
		self.empresa_1 = Empresa.objects.create(nombre='Empresa Uno')
		self.empresa_2 = Empresa.objects.create(nombre='Empresa Dos')

		self.owner = Usuario.objects.create_user(
			username='owner_iq',
			email='owner_iq@example.com',
			password='Test1234!',
			first_name='Owner',
			last_name='IQ',
			rol='usuario',
			empresa=self.empresa_1,
		)
		self.other_user = Usuario.objects.create_user(
			username='other_iq',
			email='other_iq@example.com',
			password='Test1234!',
			first_name='Other',
			last_name='IQ',
			rol='usuario',
			empresa=self.empresa_2,
		)

		self.framework = Framework.objects.create(codigo='ISO27001', nombre='ISO 27001')

		self.pregunta = PreguntaEvaluacion.objects.create(
			correlativo=1,
			framework=self.framework,
			framework_base_nombre='ISO 27001',
			codigo_control='A.5.1',
			seccion_general='Politicas',
			nombre_control='Politicas de seguridad',
			tags='seguridad,politicas',
			frameworks_referenciales='ISO27001:A.5.1',
			objetivo_evaluacion='Verificar existencia de politicas de seguridad',
			pregunta='Existe una politica formal de seguridad?',
			nivel_madurez=1,
		)

		self.evaluacion = Evaluacion.objects.create(
			empresa=self.empresa_1,
			nombre='Evaluacion IQ Demo',
			descripcion='Demo',
			creado_por=self.owner,
			nivel_deseado=3,
		)
		self.evaluacion.frameworks.add(self.framework)

		self.asignacion = AsignacionEvaluacionIQ.objects.create(
			evaluacion=self.evaluacion,
			usuario_asignado=self.owner,
			empresa=self.empresa_1,
			fecha_inicio=timezone.now().date(),
			fecha_limite=timezone.now().date() + timedelta(days=7),
			asignado_por=self.owner,
			total_preguntas=1,
		)

		self.respuesta_iq = RespuestaEvaluacionIQ.objects.create(
			asignacion=self.asignacion,
			pregunta=self.pregunta,
			respuesta=None,
			justificacion='Justificacion valida para borrador',
			respondido_por=self.owner,
			estado='borrador',
		)

	def _crear_evidencia_iq(self):
		return Evidencia.objects.create(
			respuesta_iq=self.respuesta_iq,
			archivo='evidencias/iq/test.pdf',
			codigo_documento='DOC-IQ-001',
			tipo_documento_enum='otro',
			titulo_documento='Documento de prueba',
			objetivo_documento='Objetivo de prueba',
			nombre_archivo_original='test.pdf',
			tamanio_bytes=1234,
			subido_por=self.owner,
		)

	def test_delete_evidencia_iq_ok_en_borrador(self):
		evidencia = self._crear_evidencia_iq()
		self.client.force_authenticate(user=self.owner)

		url = reverse('evidencia-iq-detail', kwargs={'id': str(evidencia.id)})
		response = self.client.delete(url)

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		evidencia.refresh_from_db()
		self.assertFalse(evidencia.activo)

	def test_delete_evidencia_iq_falla_si_respuesta_no_esta_en_borrador(self):
		evidencia = self._crear_evidencia_iq()
		self.respuesta_iq.estado = 'enviado'
		self.respuesta_iq.save(update_fields=['estado'])

		self.client.force_authenticate(user=self.owner)
		url = reverse('evidencia-iq-detail', kwargs={'id': str(evidencia.id)})
		response = self.client.delete(url)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('detail', response.data)

	def test_delete_evidencia_iq_falla_si_es_de_otra_empresa_u_otro_usuario(self):
		evidencia = self._crear_evidencia_iq()
		self.client.force_authenticate(user=self.other_user)

		url = reverse('evidencia-iq-detail', kwargs={'id': str(evidencia.id)})
		response = self.client.delete(url)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertIn('detail', response.data)

	def test_id_listado_en_preguntas_asignacion_es_eliminable(self):
		evidencia_activa = self._crear_evidencia_iq()
		evidencia_inactiva = Evidencia.objects.create(
			respuesta_iq=self.respuesta_iq,
			archivo='evidencias/iq/inactiva.pdf',
			codigo_documento='DOC-IQ-002',
			tipo_documento_enum='otro',
			titulo_documento='Documento inactivo',
			objetivo_documento='Objetivo inactivo',
			nombre_archivo_original='inactiva.pdf',
			tamanio_bytes=1234,
			subido_por=self.owner,
			activo=False,
		)

		self.client.force_authenticate(user=self.owner)

		url_preguntas = reverse(
			'respuesta-evaluacion-iq-preguntas-asignacion',
			kwargs={'asignacion_id': str(self.asignacion.id)},
		)
		response_preguntas = self.client.get(url_preguntas)

		self.assertEqual(response_preguntas.status_code, status.HTTP_200_OK)
		preguntas = response_preguntas.data.get('preguntas', [])
		self.assertTrue(len(preguntas) > 0)

		ids_listados = []
		for p in preguntas:
			respuesta = p.get('respuesta') or {}
			for ev in (respuesta.get('evidencias') or []):
				ids_listados.append(str(ev.get('id')))

		self.assertIn(str(evidencia_activa.id), ids_listados)
		self.assertNotIn(str(evidencia_inactiva.id), ids_listados)

		url_delete = reverse('evidencia-iq-detail', kwargs={'id': str(evidencia_activa.id)})
		response_delete = self.client.delete(url_delete)

		self.assertEqual(response_delete.status_code, status.HTTP_204_NO_CONTENT)
