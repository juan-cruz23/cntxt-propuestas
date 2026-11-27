from django.contrib import admin
from .models import (
    Aceptacion,
    Entregable,
    FormaPago,
    InsumoPropuestaIA,
    ObjetivoAlineado,
    Paquete,
    PartnersSeguimientoPaso,
    Propuesta,
    Requisito,
    ServicioCatalogo,
    SolicitudPropuestaIA,
)

admin.site.register(Propuesta)
admin.site.register(ObjetivoAlineado)
admin.site.register(Paquete)
admin.site.register(Entregable)
admin.site.register(Requisito)
admin.site.register(FormaPago)
admin.site.register(PartnersSeguimientoPaso)
admin.site.register(Aceptacion)


@admin.register(ServicioCatalogo)
class ServicioCatalogoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'modelo_negocio', 'valor_total_cop', 'requiere_cotizacion_manual', 'activo')
    list_filter = ('categoria', 'modelo_negocio', 'requiere_cotizacion_manual', 'activo')
    search_fields = ('codigo', 'nombre', 'categoria')


@admin.register(SolicitudPropuestaIA)
class SolicitudPropuestaIAAdmin(admin.ModelAdmin):
    list_display = ('nombre_proyecto_referencia', 'cliente_nombre', 'estado_ia', 'created_at')
    list_filter = ('estado_ia',)
    search_fields = ('cliente_nombre', 'empresa_cliente', 'nombre_proyecto_referencia')


admin.site.register(InsumoPropuestaIA)
