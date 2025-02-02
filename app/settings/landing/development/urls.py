from django.urls import path
from exchange.ui.landing import LandingDevelopmentView

urlpatterns = [
    path('', LandingDevelopmentView.as_view(), name='index'),
]
