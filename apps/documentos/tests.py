from rest_framework import status
from rest_framework.test import APITestCase

from apps.documentos.models import Norma
from apps.empresas.models import Empresa
from apps.usuarios.models import Usuario


class NormaCrudTests(APITestCase):
	def setUp(self):
		self.empresa_1 = Empresa.objects.create(nombre='Empresa Norma 1')
		self.empresa_2 = Empresa.objects.create(nombre='Empresa Norma 2')

		self.admin_empresa_1 = Usuario.objects.create_user(
			username='admin_norma_1',
			email='admin_norma_1@example.com',
			password='Test1234!',
			first_name='Admin',
			last_name='Uno',
			rol='administrador',
			empresa=self.empresa_1,
		)
		self.admin_empresa_2 = Usuario.objects.create_user(
			username='admin_norma_2',
			email='admin_norma_2@example.com',
			password='Test1234!',
			first_name='Admin',
			last_name='Dos',
			rol='administrador',
			empresa=self.empresa_2,
		)

		self.norma_empresa_1 = Norma.objects.create(
			nombre='ISO 9001:2015',
			descripcion='Sistema de gestion de calidad',
			empresa=self.empresa_1,
		)
		self.norma_empresa_2 = Norma.objects.create(
			nombre='ISO 27001:2022',
			descripcion='Seguridad de la informacion',
			empresa=self.empresa_2,
		)

	def test_lista_normas_filtra_por_empresa(self):
		self.client.force_authenticate(user=self.admin_empresa_1)

		response = self.client.get('/api/documentos/normas/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]['id'], str(self.norma_empresa_1.id))

	def test_crea_norma_asignando_empresa_del_usuario(self):
		self.client.force_authenticate(user=self.admin_empresa_1)

		response = self.client.post(
			'/api/documentos/normas/',
			{
				'nombre': 'ISO 14001:2015',
				'descripcion': 'Gestion ambiental',
				'empresa_id': str(self.empresa_2.id),
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		norma = Norma.objects.get(id=response.data['id'])
		self.assertEqual(norma.empresa_id, self.empresa_1.id)

	def test_no_puede_editar_norma_de_otra_empresa(self):
		self.client.force_authenticate(user=self.admin_empresa_1)

		response = self.client.patch(
			f'/api/documentos/normas/{self.norma_empresa_2.id}/',
			{'descripcion': 'Intento invalido'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
