from django.conf import settings


def hub_url(request):
    return {"HUB_URL": settings.HUB_URL}
