import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from propuestas.models import ServicioCatalogo


class Command(BaseCommand):
    help = 'Carga o actualiza el catálogo maestro de servicios CNTXT 2026 en la base de datos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archivo',
            type=str,
            default=str(Path(settings.BASE_DIR) / 'propuestas' / 'ai_assets' / 'catalogo_maestro_cntxt_2026.json'),
            help='Ruta al JSON del catálogo maestro de servicios.',
        )

    def handle(self, *args, **options):
        ruta = Path(options['archivo'])
        if not ruta.exists():
            self.stderr.write(self.style.ERROR(f'Archivo no encontrado: {ruta}'))
            return

        with ruta.open('r', encoding='utf-8') as f:
            payload = json.load(f)

        servicios = payload.get('servicios', [])
        creados = 0
        actualizados = 0

        for item in servicios:
            _, created = ServicioCatalogo.objects.update_or_create(
                codigo=item['codigo'],
                categoria=item['categoria'],
                defaults={
                    'subcategoria': item.get('subcategoria') or '',
                    'nombre': item['nombre'],
                    'modelo_negocio': item.get('modelo_negocio') or 'MADE',
                    'fase': item.get('fase') or '',
                    'fases_aplicables': item.get('fases_aplicables') or [],
                    'entregables': item.get('entregables') or [],
                    'actividades_clave': item.get('actividades_clave') or [],
                    'roles': item.get('roles') or [],
                    'horas_totales': item.get('horas_totales') or 0,
                    'dias_estimados': item.get('dias_estimados') or 0,
                    'valor_total_cop': int(item.get('valor_total_cop') or 0),
                    'requiere_cotizacion_manual': bool(item.get('requiere_cotizacion_manual', False)),
                    'activo': True,
                },
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Catálogo CNTXT sincronizado: {creados} creados, {actualizados} actualizados (total {len(servicios)}).'
            )
        )
