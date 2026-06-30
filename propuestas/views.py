import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import Propuesta, ObjetivoAlineado, Paquete, Entregable, Requisito, FormaPago, Aceptacion


def admin_login(request):
    if request.user.is_authenticated:
        return redirect('propuestas:admin_dashboard')
    error = None
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password'),
        )
        if user:
            login(request, user)
            return redirect('propuestas:admin_dashboard')
        error = 'Credenciales inválidas'
    return render(request, 'admin_panel/login.html', {'error': error})


def admin_logout(request):
    logout(request)
    return redirect('propuestas:admin_login')


@login_required
def admin_dashboard(request):
    estado_filtro = request.GET.get('estado', 'todas')
    propuestas = Propuesta.objects.all()
    if estado_filtro in ('borrador', 'publicada', 'archivada'):
        propuestas = propuestas.filter(estado=estado_filtro)
    conteos = {
        'todas':    Propuesta.objects.count(),
        'borrador': Propuesta.objects.filter(estado='borrador').count(),
        'publicada': Propuesta.objects.filter(estado='publicada').count(),
        'archivada': Propuesta.objects.filter(estado='archivada').count(),
    }
    return render(request, 'admin_panel/dashboard.html', {
        'propuestas': propuestas,
        'estado_filtro': estado_filtro,
        'conteos': conteos,
    })


def _guardar_propuesta(request, propuesta=None):
    data = request.POST
    es_nueva = propuesta is None

    with transaction.atomic():
        if es_nueva:
            propuesta = Propuesta()

        propuesta.nombre_proyecto = data.get('nombre_proyecto', '')
        propuesta.nombre_proyecto_subtitulo = data.get('nombre_proyecto_subtitulo', '')
        propuesta.dirigido_a = data.get('dirigido_a', '')
        propuesta.empresa_cliente = data.get('empresa_cliente', '')
        propuesta.de = data.get('de', 'Contexto Arquitectura')
        propuesta.fecha_presentacion = data.get('fecha_presentacion')
        propuesta.fecha_envio = data.get('fecha_envio') or None
        propuesta.objetivo_texto = data.get('objetivo_texto', '')
        propuesta.requisitos_texto = data.get('requisitos_texto', '')
        propuesta.consideraciones_texto = data.get('consideraciones_texto', '')
        propuesta.color_acento = data.get('color_acento', '#C8A96E')
        propuesta.estado = data.get('estado', 'borrador')
        propuesta.save()

        propuesta.objetivos.all().delete()
        idx = 0
        while f'obj_titulo_{idx}' in data:
            titulo = data.get(f'obj_titulo_{idx}', '').strip()
            if titulo:
                ObjetivoAlineado.objects.create(
                    propuesta=propuesta,
                    titulo=titulo,
                    descripcion=data.get(f'obj_desc_{idx}', ''),
                    icono=data.get(f'obj_icono_{idx}', 'star'),
                    orden=idx,
                )
            idx += 1

        propuesta.paquetes.all().delete()
        pkg_idx = 0
        while f'pkg_nombre_{pkg_idx}' in data:
            nombre = data.get(f'pkg_nombre_{pkg_idx}', '').strip()
            if nombre:
                paquete = Paquete.objects.create(
                    propuesta=propuesta,
                    nombre=nombre,
                    nombre_en=data.get(f'pkg_nombre_en_{pkg_idx}', ''),
                    que_es=data.get(f'pkg_que_es_{pkg_idx}', ''),
                    para_que=data.get(f'pkg_para_que_{pkg_idx}', ''),
                    incluye_texto=data.get(f'pkg_incluye_{pkg_idx}', ''),
                    dias_entrega=int(data.get(f'pkg_dias_{pkg_idx}', 15)),
                    precio_regular=data.get(f'pkg_precio_{pkg_idx}', 0),
                    precio_descuento=data.get(f'pkg_precio_desc_{pkg_idx}') or None,
                    moneda=data.get(f'pkg_moneda_{pkg_idx}', 'USD'),
                    aplica_iva=f'pkg_iva_{pkg_idx}' in data,
                    es_destacado=f'pkg_destacado_{pkg_idx}' in data,
                    orden=pkg_idx,
                )
                ent_idx = 0
                while f'ent_cat_{pkg_idx}_{ent_idx}' in data:
                    cat = data.get(f'ent_cat_{pkg_idx}_{ent_idx}', '').strip()
                    if cat:
                        Entregable.objects.create(
                            paquete=paquete,
                            categoria=cat,
                            descripcion=data.get(f'ent_desc_{pkg_idx}_{ent_idx}', ''),
                            orden=ent_idx,
                        )
                    ent_idx += 1
            pkg_idx += 1

        propuesta.requisitos.all().delete()
        req_idx = 0
        while f'req_texto_{req_idx}' in data:
            texto = data.get(f'req_texto_{req_idx}', '').strip()
            if texto:
                Requisito.objects.create(
                    propuesta=propuesta,
                    texto=texto,
                    orden=req_idx,
                )
            req_idx += 1

        propuesta.formas_pago.all().delete()
        pago_idx = 0
        while f'pago_concepto_{pago_idx}' in data:
            concepto = data.get(f'pago_concepto_{pago_idx}', '').strip()
            if concepto:
                FormaPago.objects.create(
                    propuesta=propuesta,
                    concepto=concepto,
                    porcentaje=int(data.get(f'pago_porcentaje_{pago_idx}', 0)),
                    fecha_pago=data.get(f'pago_fecha_{pago_idx}', ''),
                    orden=pago_idx,
                )
            pago_idx += 1

    return propuesta


@login_required
def admin_crear(request):
    if request.method == 'POST':
        propuesta = _guardar_propuesta(request)
        return redirect('propuestas:admin_dashboard')
    return render(request, 'admin_panel/form.html', {'propuesta': None})


@login_required
def admin_editar(request, pk):
    propuesta = get_object_or_404(Propuesta, pk=pk)
    if request.method == 'POST':
        _guardar_propuesta(request, propuesta)
        return redirect('propuestas:admin_dashboard')
    return render(request, 'admin_panel/form.html', {'propuesta': propuesta})


@login_required
@require_POST
def admin_eliminar(request, pk):
    propuesta = get_object_or_404(Propuesta, pk=pk)
    propuesta.delete()
    return redirect('propuestas:admin_dashboard')


@login_required
def admin_duplicar(request, pk):
    original = get_object_or_404(Propuesta, pk=pk)
    with transaction.atomic():
        nueva = Propuesta()
        nueva.nombre_proyecto = f"{original.nombre_proyecto} (copia)"
        nueva.nombre_proyecto_subtitulo = original.nombre_proyecto_subtitulo
        nueva.dirigido_a = original.dirigido_a
        nueva.empresa_cliente = original.empresa_cliente
        nueva.de = original.de
        nueva.fecha_presentacion = original.fecha_presentacion
        nueva.fecha_envio = original.fecha_envio
        nueva.objetivo_texto = original.objetivo_texto
        nueva.requisitos_texto = original.requisitos_texto
        nueva.consideraciones_texto = original.consideraciones_texto
        nueva.color_acento = original.color_acento
        nueva.estado = 'borrador'
        nueva.save()

        for obj in original.objetivos.all():
            ObjetivoAlineado.objects.create(
                propuesta=nueva, titulo=obj.titulo,
                descripcion=obj.descripcion, icono=obj.icono, orden=obj.orden,
            )
        for pkg in original.paquetes.all():
            nuevo_pkg = Paquete.objects.create(
                propuesta=nueva, nombre=pkg.nombre, nombre_en=pkg.nombre_en,
                que_es=pkg.que_es, para_que=pkg.para_que,
                incluye_texto=pkg.incluye_texto, dias_entrega=pkg.dias_entrega,
                precio_regular=pkg.precio_regular,
                precio_descuento=pkg.precio_descuento,
                moneda=pkg.moneda, aplica_iva=pkg.aplica_iva, es_destacado=pkg.es_destacado, orden=pkg.orden,
            )
            for ent in pkg.entregables.all():
                Entregable.objects.create(
                    paquete=nuevo_pkg, categoria=ent.categoria,
                    descripcion=ent.descripcion, orden=ent.orden,
                )
        for req in original.requisitos.all():
            Requisito.objects.create(
                propuesta=nueva, texto=req.texto, orden=req.orden,
            )
        for fp in original.formas_pago.all():
            FormaPago.objects.create(
                propuesta=nueva, concepto=fp.concepto,
                porcentaje=fp.porcentaje, fecha_pago=fp.fecha_pago, orden=fp.orden,
            )
    return redirect('propuestas:admin_editar', pk=nueva.pk)


@login_required
@require_POST
def admin_toggle_estado(request, pk):
    propuesta = get_object_or_404(Propuesta, pk=pk)
    if propuesta.estado == 'borrador':
        propuesta.estado = 'publicada'
    else:
        propuesta.estado = 'borrador'
    propuesta.save()
    return redirect(request.META.get('HTTP_REFERER', 'propuestas:admin_dashboard'))


@login_required
@require_POST
def admin_archivar(request, pk):
    propuesta = get_object_or_404(Propuesta, pk=pk)
    propuesta.estado = 'archivada' if propuesta.estado != 'archivada' else 'borrador'
    propuesta.save()
    return redirect(request.META.get('HTTP_REFERER', 'propuestas:admin_dashboard'))


def api_propuesta_json(request, pk):
    propuesta = get_object_or_404(Propuesta, pk=pk)
    data = {
        'id': str(propuesta.id),
        'nombre_proyecto': propuesta.nombre_proyecto,
        'subtitulo': propuesta.nombre_proyecto_subtitulo,
        'dirigido_a': propuesta.dirigido_a,
        'empresa_cliente': propuesta.empresa_cliente,
        'de': propuesta.de,
        'fecha_presentacion': str(propuesta.fecha_presentacion),
        'objetivo_texto': propuesta.objetivo_texto,
        'color_acento': propuesta.color_acento,
        'objetivos': list(propuesta.objetivos.values('titulo', 'descripcion', 'icono')),
        'paquetes': [],
        'requisitos': list(propuesta.requisitos.values('texto')),
        'formas_pago': list(propuesta.formas_pago.values('concepto', 'porcentaje', 'fecha_pago')),
    }
    for pkg in propuesta.paquetes.all():
        data['paquetes'].append({
            'nombre': pkg.nombre,
            'nombre_en': pkg.nombre_en,
            'que_es': pkg.que_es,
            'para_que': pkg.para_que,
            'dias_entrega': pkg.dias_entrega,
            'precio_regular': float(pkg.precio_regular),
            'precio_descuento': float(pkg.precio_descuento) if pkg.precio_descuento else None,
            'moneda': pkg.moneda,
            'es_destacado': pkg.es_destacado,
            'entregables': list(pkg.entregables.values('categoria', 'descripcion')),
        })
    return JsonResponse(data)


def propuesta_publica(request, slug):
    propuesta = get_object_or_404(Propuesta, slug=slug, estado='publicada')
    aceptacion = getattr(propuesta, 'aceptacion', None)
    paquetes_data = []
    for pkg in propuesta.paquetes.all():
        paquetes_data.append({
            'nombre': pkg.nombre,
            'nombre_en': pkg.nombre_en,
            'que_es': pkg.que_es,
            'para_que': pkg.para_que,
            'incluye_texto': pkg.incluye_texto,
            'dias_entrega': pkg.dias_entrega,
            'precio_regular': float(pkg.precio_regular),
            'precio_descuento': float(pkg.precio_descuento) if pkg.precio_descuento else None,
            'moneda': pkg.moneda,
            'es_destacado': pkg.es_destacado,
            'entregables': list(pkg.entregables.values('categoria', 'descripcion')),
        })
    context = {
        'propuesta': propuesta,
        'aceptacion': aceptacion,
        'paquetes_json': json.dumps(paquetes_data),
        'formas_pago_json': json.dumps(list(propuesta.formas_pago.values('concepto', 'porcentaje', 'fecha_pago'))),
    }
    return render(request, 'public/propuesta.html', context)


@require_POST
def aceptar_propuesta(request, slug):
    propuesta = get_object_or_404(Propuesta, slug=slug, estado='publicada')
    if hasattr(propuesta, 'aceptacion'):
        return JsonResponse({'ok': False, 'error': 'ya_aceptada'}, status=400)
    nombre = request.POST.get('nombre', '').strip()
    email = request.POST.get('email', '').strip()
    if not nombre:
        return JsonResponse({'ok': False, 'error': 'nombre_requerido'}, status=400)
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    Aceptacion.objects.create(propuesta=propuesta, nombre=nombre, email=email, ip=ip)
    return JsonResponse({'ok': True, 'nombre': nombre, 'fecha': propuesta.aceptacion.fecha.strftime('%d de %B de %Y, %H:%M')})
