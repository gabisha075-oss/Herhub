from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import CustomerSignupForm, ProviderSignupForm
from .models import User


def role_home(user):
    """Role-ku thagundha home page URL."""
    if user.role == User.Role.PROVIDER:
        return reverse("provider_dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("admin:index")
    return reverse("home")


def choose_role(request):
    if request.user.is_authenticated:
        return redirect(role_home(request.user))
    return render(request, "accounts/choose_role.html")


def register_customer(request):
    if request.user.is_authenticated:
        return redirect(role_home(request.user))

    if request.method == "POST":
        form = CustomerSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to HerHub, {user.first_name}!")
            return redirect(role_home(user))
    else:
        form = CustomerSignupForm()
    return render(request, "accounts/register_customer.html", {"form": form})


def register_provider(request):
    if request.user.is_authenticated:
        return redirect(role_home(request.user))

    if request.method == "POST":
        form = ProviderSignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, "Profile created! It will go live after our team reviews it."
            )
            return redirect(role_home(user))
    else:
        form = ProviderSignupForm()
    return render(request, "accounts/register_provider.html", {"form": form})

from django.contrib.auth.forms import AuthenticationForm
from .forms import BootstrapMixin, CustomerSignupForm, ProviderSignupForm


class BootstrapAuthForm(BootstrapMixin, AuthenticationForm):
    pass
class RoleLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = BootstrapAuthForm
    redirect_authenticated_user = True
    

    
    def get_success_url(self):
        # ?next=... irundha (login venam page-ku vandhirundha) adhukku, illati role home
        return self.get_redirect_url() or role_home(self.request.user)