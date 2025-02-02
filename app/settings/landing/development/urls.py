from django.urls import path
from ui.landing import LandingDevelopmentView

urlpatterns = [
    path('', LandingDevelopmentView.as_view(), name='index'),
]
