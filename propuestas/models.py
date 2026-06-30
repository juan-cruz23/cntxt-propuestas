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
    propuesta = models.ForeignKey(Propuesta, on_delete=models.CASCADE, related_name='paquetes')
    nombre = models.CharField(max_length=200)
    nombre_en = models.CharField(max_length=200, blank=True)
    que_es = models.TextField(blank=True)
    para_que = models.TextField(blank=True)
    incluye_texto = models.TextField(blank=True)
    dias_entrega = models.PositiveIntegerField(default=15)
    precio_regular = models.DecimalField(max_digits=12, decimal_places=2)
    precio_descuento = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    moneda = models.CharField(max_length=10, default='USD')
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
    propuesta = models.OneToOneField(Propuesta, on_delete=models.CASCADE, related_name='aceptacion')
    nombre = models.CharField(max_length=300)
    email = models.EmailField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(blank=True, null=True)

    def __str__(self):
        return f"{self.propuesta.nombre_proyecto} — aceptada por {self.nombre}"
