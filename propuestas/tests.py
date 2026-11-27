import json
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from propuestas.models import Propuesta, ServicioCatalogo, SolicitudPropuestaIA
from propuestas.services.ai_engine import sincronizar_propuesta_desde_json


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class AIProposalEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin_test', 'admin@cntxt.co', 'pass1234')
        self.client = Client()
        self.client.force_login(self.user)

    def test_cargar_catalogo_cntxt_idempotente(self):
        call_command('cargar_catalogo_cntxt')
        count1 = ServicioCatalogo.objects.count()
        self.assertEqual(count1, 140)
        call_command('cargar_catalogo_cntxt')
        self.assertEqual(ServicioCatalogo.objects.count(), 140)

    def test_sincronizar_propuesta_desde_json_crea_3_niveles(self):
        sol = SolicitudPropuestaIA.objects.create(
            creado_por='admin_test',
            cliente_nombre='Carlos Pérez',
            empresa_cliente='Promotora Oriente S.A.S',
            nombre_proyecto_referencia='Reserva El Retiro',
            ubicacion='El Retiro, Antioquia',
        )
        sample_json = {
            'brief': {
                'title': 'Reserva El Retiro',
                'subtitle': 'El Retiro, Antioquia',
                'project_category': 'Parcelaciones y Condominios',
                'estimated_area': 45000,
                'operative_line': 'DISENO',
                'scope_phase': 'FASE_1',
                'status': 'PRECONTRACTUAL',
                'description': 'Parcelación campestre de 25 lotes con enfoque wellness.',
                'completitud_pct': 75,
                'campos_faltantes': [
                    {'campo': 'condicionamiento_temporal', 'criticidad': 'media', 'pregunta_para_red': '¿Fecha objetivo de lanzamiento?'}
                ],
            },
            'diagnostico': {
                'tipo_proyecto': 'Parcelación Campestre Wellness',
                'modelo_negocio': 'MADE',
                'segmento': 'B2B',
                'perfil_cliente': 'ICP Corporativo - Promotora Inmobiliaria',
                'dolores': ['Evitar comoditización', 'Acelerar preventas sobre planos'],
                'deseos': ['Diferenciación absoluta', 'Mayor precio por m²'],
                'retos_principales': ['Topografía inclinada'],
                'conceptos_maestros': ['Well Being', 'Context', 'Storytelling'],
            },
            'propuesta': {
                'nombre_proyecto': 'Reserva El Retiro',
                'nombre_proyecto_subtitulo': 'El Retiro, Antioquia',
                'dirigido_a': 'Carlos Pérez',
                'empresa_cliente': 'Promotora Oriente S.A.S',
                'objetivo_texto': '<p>Transformar el predio en un referente de <strong>Slow Life</strong>.</p>',
                'objetivos_alineados': [
                    {'titulo': 'Diferenciación', 'descripcion': 'Romper el molde tradicional.', 'icono': 'star'},
                    {'titulo': 'ROI Premium', 'descripcion': 'Justificar mayor valor por m².', 'icono': 'target'},
                    {'titulo': 'Preventas Rápidas', 'descripcion': 'Enamorar sobre planos.', 'icono': 'sparkles'},
                ],
                'niveles_acceso': [
                    {
                        'orden': 1,
                        'nombre': 'Acceso Integral Full',
                        'que_es': '<p>Diseño completo + visualización + web.</p>',
                        'para_que': '<p>Máxima velocidad de absorción.</p>',
                        'bloques_que_incluye': [{'numero': '01', 'titulo': 'Urbanismo', 'items': ['Cabida', 'Modelo 3D']}],
                        'dias_entrega': 60,
                        'precio_regular': 45000000,
                        'moneda': 'COP',
                        'aplica_iva': True,
                    },
                    {
                        'orden': 2,
                        'nombre': 'Acceso Estratégico',
                        'es_destacado': True,
                        'que_es': '<p>Diseño Fase 1-2 + visualización comercial.</p>',
                        'para_que': '<p>Lanzamiento comercial sólido.</p>',
                        'bloques_que_incluye': [{'numero': '01', 'titulo': 'Conceptualización', 'items': ['Masterplan']}],
                        'dias_entrega': 40,
                        'precio_regular': 28000000,
                        'moneda': 'COP',
                        'aplica_iva': True,
                    },
                    {
                        'orden': 3,
                        'nombre': 'Acceso Esencial',
                        'que_es': '<p>Prefactibilidad y conceptualización inicial.</p>',
                        'para_que': '<p>Validar business case.</p>',
                        'bloques_que_incluye': [{'numero': '01', 'titulo': 'Diagnóstico', 'items': ['Estudio de cabida']}],
                        'dias_entrega': 20,
                        'precio_regular': 14000000,
                        'moneda': 'COP',
                        'aplica_iva': True,
                    },
                ],
                'requisitos_previos': ['Levantamiento topográfico', 'Certificado de tradición'],
                'consideraciones_texto': '<ul><li>No incluye licencias.</li></ul>',
                'formas_pago': [
                    {'concepto': 'Anticipo', 'porcentaje': 50, 'fecha_pago': 'A la firma'},
                    {'concepto': 'Entrega 1', 'porcentaje': 25, 'fecha_pago': 'Avance 50%'},
                    {'concepto': 'Entrega Final', 'porcentaje': 25, 'fecha_pago': 'A la entrega'},
                ],
            },
            'notas_ajuste_manual': ['Validar multiplicador por 25 lotes.'],
        }

        prop = sincronizar_propuesta_desde_json(sol, sample_json)
        self.assertIsInstance(prop, Propuesta)
        self.assertEqual(prop.estado, 'borrador')
        self.assertEqual(prop.objetivos.count(), 3)
        paquetes = list(prop.paquetes_casa_diseno)
        self.assertEqual(len(paquetes), 3)
        # Verificar orden de más a menos
        self.assertGreater(paquetes[0].precio_regular, paquetes[1].precio_regular)
        self.assertGreater(paquetes[1].precio_regular, paquetes[2].precio_regular)
        self.assertEqual(sum(fp.porcentaje for fp in prop.formas_pago.all()), 100)

        # Smoke test de vistas IA
        self.assertEqual(self.client.get(reverse('propuestas:admin_nueva_ia')).status_code, 200)
        self.assertEqual(self.client.get(reverse('propuestas:admin_catalogo')).status_code, 200)
        self.assertEqual(self.client.get(reverse('propuestas:admin_ia_detalle', args=[sol.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('propuestas:admin_ia_print', args=[sol.pk])).status_code, 200)
        excel_resp = self.client.get(reverse('propuestas:admin_ia_excel', args=[sol.pk]))
        self.assertEqual(excel_resp.status_code, 200)
        self.assertIn('spreadsheetml.sheet', excel_resp['Content-Type'])
        self.assertGreater(len(excel_resp.content), 2000)

    def test_slack_url_verification_challenge(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'SLACK_SIGNING_SECRET': ''}):
            resp = self.client.post(
                reverse('propuestas:slack_events'),
                data=json.dumps({'type': 'url_verification', 'challenge': 'abc123'}),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'challenge': 'abc123'})

    def test_slack_slash_command_properto(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'SLACK_SIGNING_SECRET': ''}):
            resp = self.client.post(
                reverse('propuestas:slack_command'),
                data={'command': '/properto', 'text': 'Casa El Retiro', 'user_name': 'simon'},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['response_type'], 'ephemeral')
        self.assertIn('/admin-panel/nueva-ia/?proyecto=Casa+El+Retiro', body['text'])
