from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'propuestas'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='propuestas:admin_dashboard'), name='home'),
    path('admin-panel/login/', views.admin_login, name='admin_login'),
    path('admin-panel/logout/', views.admin_logout, name='admin_logout'),
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/nueva/', views.admin_crear, name='admin_crear'),
    path('admin-panel/editar/<uuid:pk>/', views.admin_editar, name='admin_editar'),
    path('admin-panel/eliminar/<uuid:pk>/', views.admin_eliminar, name='admin_eliminar'),
    path('admin-panel/duplicar/<uuid:pk>/', views.admin_duplicar, name='admin_duplicar'),
    path('admin-panel/toggle/<uuid:pk>/', views.admin_toggle_estado, name='admin_toggle'),
    path('admin-panel/archivar/<uuid:pk>/', views.admin_archivar, name='admin_archivar'),
    path('admin-panel/api/propuesta/<uuid:pk>/', views.api_propuesta_json, name='api_propuesta'),
    path('p/<slug:slug>/', views.propuesta_publica, name='propuesta_publica'),
    path('p/<slug:slug>/aceptar/', views.aceptar_propuesta, name='aceptar_propuesta'),
]
