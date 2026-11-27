from django.urls import path
from django.views.generic import RedirectView
from . import views, views_ia

app_name = 'propuestas'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='propuestas:admin_dashboard'), name='home'),
    path('admin-panel/login/', views.admin_login, name='admin_login'),
    path('admin-panel/logout/', views.admin_logout, name='admin_logout'),
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/nueva/', views.admin_crear, name='admin_crear'),
    path('admin-panel/nueva-ia/', views_ia.admin_nueva_ia, name='admin_nueva_ia'),
    path('admin-panel/ia/<uuid:pk>/', views_ia.admin_ia_detalle, name='admin_ia_detalle'),
    path('admin-panel/ia/<uuid:pk>/reintentar/', views_ia.admin_ia_reintentar, name='admin_ia_reintentar'),
    path('admin-panel/ia/<uuid:pk>/ajustar/', views_ia.admin_ia_ajustar, name='admin_ia_ajustar'),
    path('admin-panel/ia/<uuid:pk>/slack/', views_ia.admin_ia_enviar_slack, name='admin_ia_enviar_slack'),
    path('admin-panel/ia/<uuid:pk>/aprobar/', views_ia.admin_ia_aprobar_archivar, name='admin_ia_aprobar_archivar'),
    path('admin-panel/ia/<uuid:pk>/excel/', views_ia.admin_ia_excel, name='admin_ia_excel'),
    path('admin-panel/ia/<uuid:pk>/print/', views_ia.admin_ia_print, name='admin_ia_print'),
    path('admin-panel/catalogo/', views_ia.admin_catalogo, name='admin_catalogo'),
    path('api/slack/events/', views_ia.slack_events_webhook, name='slack_events'),
    path('api/slack/interactions/', views_ia.slack_interactions_webhook, name='slack_interactions'),
    path('api/slack/command/', views_ia.slack_slash_command, name='slack_command'),
    path('admin-panel/editar/<uuid:pk>/', views.admin_editar, name='admin_editar'),
    path('admin-panel/eliminar/<uuid:pk>/', views.admin_eliminar, name='admin_eliminar'),
    path('admin-panel/duplicar/<uuid:pk>/', views.admin_duplicar, name='admin_duplicar'),
    path('admin-panel/toggle/<uuid:pk>/', views.admin_toggle_estado, name='admin_toggle'),
    path('admin-panel/archivar/<uuid:pk>/', views.admin_archivar, name='admin_archivar'),
    path('admin-panel/api/propuesta/<uuid:pk>/', views.api_propuesta_json, name='api_propuesta'),
    path('p/<slug:slug>/', views.propuesta_publica, name='propuesta_publica'),
    path('p/<slug:slug>/casa-diseno/', views.propuesta_casa_diseno, name='propuesta_casa_diseno'),
    path('p/<slug:slug>/partners/', views.propuesta_partners, name='propuesta_partners'),
    path('p/<slug:slug>/casa-diseno/aceptar/', views.aceptar_propuesta, {'tipo': 'casa_diseno'}, name='aceptar_casa_diseno'),
    path('p/<slug:slug>/partners/aceptar/', views.aceptar_propuesta, {'tipo': 'partners'}, name='aceptar_partners'),
]
