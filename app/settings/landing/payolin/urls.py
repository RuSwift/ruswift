from django.urls import path
from ui.landing import LandingPayolinView

urlpatterns = [
    path('', LandingPayolinView.as_view(), name='index'),
]
