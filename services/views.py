from django.shortcuts import render

from accounts.decorators import role_required

from .models import Provider


def home(request):
    return render(request, "services/home.html")


@role_required("provider")
def provider_dashboard(request):
    provider = Provider.objects.filter(user=request.user).first()
    return render(request, "services/provider_dashboard.html", {"provider": provider})