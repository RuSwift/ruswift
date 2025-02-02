from django.urls import path
from exchange.ui.landing import LandingPayolinView

urlpatterns = [
    path('', LandingPayolinView.as_view(), name='index'),
]
