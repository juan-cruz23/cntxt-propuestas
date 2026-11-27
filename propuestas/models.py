from django.db import models
from slugify import slugify
import uuid


class Propuesta(models.Model):
    STATUS_CHOICES = [
        ('borrador', 'Borrador'),
        ('publicada', 'Publicada'),
        ('archivada', 'Archivada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.PositiveIntegerField(unique=True, blank=True, null=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    estado = models.CharField(max_length=20, choices=STATUS_CHOICES, default='borrador')

    nombre_proyecto = models.CharField(max_length=300)
    nombre_proyecto_subtitulo = models.CharField(max_length=300, blank=True)
    dirigido_a = models.CharField(max_length=300)
    empresa_cliente = models.CharField(max_length=300, blank=True)
    de = models.CharField(max_length=300, default='Contexto Arquitectura')
    fecha_presentacion = models.DateField()
    fecha_envio = models.DateField(blank=True, null=True)

    objetivo_texto = models.TextField()
    requisitos_texto = models.TextField(blank=True)
    consideraciones_texto = models.TextField(blank=True)

    color_acento = models.CharField(max_length=7, default='#C8A96E')

    # Tipos de propuesta: Casa de Diseño (formato actual) y/o Partners
    # (acompañamiento continuo). Una propuesta puede incluir uno o ambos.
    incluye_casa_diseno = models.BooleanField(default=True)
    incluye_partners = models.BooleanField(default=False)

    # Forma de pago de Partners: dos modos independientes y opcionales.
    partners_porcentaje_ventas = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    partners_fee_mensual = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    partners_fee_moneda = models.CharField(max_length=10, default='USD')

    # Duración del servicio Partners (ej. "12 meses"). Opcional.
    DURACION_UNIDAD_CHOICES = [
        ('semanas', 'Semanas'),
        ('meses', 'Meses'),
        ('anos', 'Años'),
    ]
    partners_duracion_numero = models.PositiveIntegerField(blank=True, null=True)
    partners_duracion_unidad = models.CharField(max_length=20, choices=DURACION_UNIDAD_CHOICES, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Propuestas'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nombre_proyecto)
            self.slug = f"{base_slug}-{str(self.id)[:8]}"
        if not self.numero:
            last = Propuesta.objects.order_by('-numero').first()
            self.numero = (last.numero + 1) if last and last.numero else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"#{self.numero} - {self.nombre_proyecto}"

    @property
    def paquetes_casa_diseno(self):
        return self.paquetes.filter(tipo='casa_diseno')

    @property
    def paquete_partners(self):
        return self.paquetes.filter(tipo='partners').first()


class ObjetivoAlineado(models.Model):
    propuesta = models.ForeignKey(Propuesta, on_delete=models.CASCADE, related_name='objetivos')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    icono = models.CharField(max_length=50, default='star', blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.titulo


class Paquete(models.Model):
    TIPO_CHOICES = [
        ('casa_diseno', 'Casa de Diseño'),
        ('partners', 'Partners'),
    ]

    propuesta = models.ForeignKey(Propuesta, on_delete=models.CASCADE, related_name='paquetes')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='casa_diseno')
    nombre = models.CharField(max_length=200)
    nombre_en = models.CharField(max_length=200, blank=True)
    que_es = models.TextField(blank=True)
    para_que = models.TextField(blank=True)
    incluye_texto = models.TextField(blank=True)
    dias_entrega = models.PositiveIntegerField(default=15)
    precio_regular = models.DecimalField(max_digits=12, decimal_places=2)
    precio_descuento = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    moneda = models.CharField(max_length=10, default='USD')
    aplica_iva = models.BooleanField(default=False)
    es_destacado = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.nombre} - {self.propuesta.nombre_proyecto}"


class Entregable(models.Model):
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE, related_name='entregables')
    categoria = models.CharField(max_length=200)
    descripcion = models.TextField()
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.categoria}: {self.descripcion[:50]}"


class Requisito(models.Model):
    propuesta = models.ForeignKey(Propuesta, on_delete=models.CASCADE, related_name='requisitos')
    texto = models.CharField(max_length=500)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.texto[:50]


class PartnersSeguimientoPaso(models.Model):
    """Un paso del ciclo mensual recurrente de acompañamiento Partners."""
    propuesta = models.ForeignKey(Propuesta, on_delete=models.CASCADE, related_name='partners_pasos')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return self.titulo


class FormaPago(models.Model):
    propuesta = models.ForeignKey(Propuesta, on_delete=models.CASCADE, related_name='formas_pago')
    concepto = models.CharField(max_length=300)
    porcentaje = models.PositiveIntegerField()
    fecha_pago = models.CharField(max_length=300)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.concepto} - {self.porcentaje}%"


class Aceptacion(models.Model):
    TIPO_CHOICES = [
        ('casa_diseno', 'Casa de Diseño'),
        ('partners', 'Partners'),
    ]

    propuesta = models.ForeignKey(Propuesta, on_delete=models.CASCADE, related_name='aceptaciones')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='casa_diseno')
    nombre = models.CharField(max_length=300)
    email = models.EmailField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        unique_together = [('propuesta', 'tipo')]

    def __str__(self):
        return f"{self.propuesta.nombre_proyecto} ({self.get_tipo_display()}) — aceptada por {self.nombre}"


class ServicioCatalogo(models.Model):
    """Catálogo maestro de servicios de CNTXT importado desde Portafolio 2026."""
    MODELO_CHOICES = [
        ('MADE', 'MADE'),
        ('SELECT', 'SELECT'),
        ('AMBOS', 'AMBOS'),
    ]

    codigo = models.CharField(max_length=40, db_index=True)
    categoria = models.CharField(max_length=120, db_index=True)
    subcategoria = models.CharField(max_length=120, blank=True, default='')
    nombre = models.CharField(max_length=300)
    modelo_negocio = models.CharField(max_length=20, choices=MODELO_CHOICES, default='MADE')
    fase = models.CharField(max_length=40, blank=True, default='')
    fases_aplicables = models.JSONField(default=list, blank=True)
    entregables = models.JSONField(default=list, blank=True)
    actividades_clave = models.JSONField(default=list, blank=True)
    roles = models.JSONField(default=list, blank=True)
    horas_totales = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    dias_estimados = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    valor_total_cop = models.BigIntegerField(default=0)
    requiere_cotizacion_manual = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['categoria', 'modelo_negocio', 'codigo']
        unique_together = [('codigo', 'categoria')]
        verbose_name = 'Servicio de Catálogo'
        verbose_name_plural = 'Catálogo de Servicios'

    def __str__(self):
        return f"[{self.codigo}] {self.nombre} ({self.categoria})"


class SolicitudPropuestaIA(models.Model):
    """Sesión de generación multimodal con IA ligada a una Propuesta."""
    ESTADO_IA_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('borrador_generado', 'Borrador Generado'),
        ('en_revision_slack', 'En Revisión (Slack)'),
        ('aprobada_archivada', 'Aprobada y Archivada'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    propuesta = models.OneToOneField(
        Propuesta, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitud_ia'
    )
    creado_por = models.CharField(max_length=150, blank=True, default='')
    cliente_nombre = models.CharField(max_length=300)
    empresa_cliente = models.CharField(max_length=300, blank=True, default='')
    nombre_proyecto_referencia = models.CharField(max_length=300, blank=True, default='')
    ubicacion = models.CharField(max_length=300, blank=True, default='')
    transcript_o_notas = models.TextField(blank=True, default='')

    # Resultados estructurados del Skill Multimodal
    brief_json = models.JSONField(default=dict, blank=True)
    diagnostico_json = models.JSONField(default=dict, blank=True)
    notas_ajuste_manual_json = models.JSONField(default=list, blank=True)
    raw_response_json = models.JSONField(default=dict, blank=True)
    historial_cambios_json = models.JSONField(default=list, blank=True)

    # Integraciones: Slack, Google Drive y CNTXT Briefs
    estado_ia = models.CharField(max_length=30, choices=ESTADO_IA_CHOICES, default='pendiente')
    error_mensaje = models.TextField(blank=True, default='')
    slack_channel_id = models.CharField(max_length=64, blank=True, default='')
    slack_thread_ts = models.CharField(max_length=64, blank=True, default='', db_index=True)
    drive_folder_id = models.CharField(max_length=128, blank=True, default='')
    drive_folder_url = models.URLField(max_length=500, blank=True, default='')
    drive_pdf_url = models.URLField(max_length=500, blank=True, default='')
    brief_externo_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Solicitud Propuesta IA'
        verbose_name_plural = 'Solicitudes Propuesta IA'

    def __str__(self):
        return f"IA: {self.nombre_proyecto_referencia or self.cliente_nombre} ({self.estado_ia})"


class InsumoPropuestaIA(models.Model):
    """Archivo multimedia (audio, foto, video, documento) subido como insumo."""
    TIPO_CHOICES = [
        ('audio', 'Audio'),
        ('imagen', 'Imagen'),
        ('video', 'Video'),
        ('documento', 'Documento'),
    ]

    solicitud = models.ForeignKey(SolicitudPropuestaIA, on_delete=models.CASCADE, related_name='insumos')
    archivo = models.FileField(upload_to='ia_insumos/%Y/%m/')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='imagen')
    nombre_original = models.CharField(max_length=300, blank=True, default='')
    mime_type = models.CharField(max_length=120, blank=True, default='')
    tamano_bytes = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.tipo}: {self.nombre_original}"
