from django.urls import path
from django.conf import settings

from ui.views import (
    TestView, KYCView, LoginView, ScenarioView, LogoutView
)
from api import api_router


urlpatterns = [
    path('verify', KYCView.as_view(), name='kyc'),
    path(settings.LOGIN_URL, LoginView.as_view(), name='login'),
    path(settings.LOGOUT_URL, LogoutView.as_view(), name='logout'),
]

urlpatterns += api_router.paths

urlpatterns += [
    # path('test', TestView.as_view(), name='test'),
    path('<scenario>/<str:id>', ScenarioView.as_view(), name='scenario-detailed'),
    path('<scenario>', ScenarioView.as_view(), name='scenario'),
    path('', ScenarioView.as_view(), name='index'),
]
