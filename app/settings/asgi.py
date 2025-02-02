import django
from django.conf import settings
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from django.urls import path


django.setup()
django_asgi_app = get_asgi_application()

if settings.SENTRY_ON:
    django_asgi_app = SentryAsgiMiddleware(django_asgi_app)


websocket_urlpatterns = [

]


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket":
        URLRouter(websocket_urlpatterns)
})
