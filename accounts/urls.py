from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.choose_role, name="signup"),
    path("signup/customer/", views.register_customer, name="register_customer"),
    path("signup/provider/", views.register_provider, name="register_provider"),
    path("login/", views.RoleLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]