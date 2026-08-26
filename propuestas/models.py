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
