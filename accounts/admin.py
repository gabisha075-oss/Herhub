from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ("username", "first_name", "phone", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "first_name", "phone")

    fieldsets = UserAdmin.fieldsets + (
        ("HerHub", {"fields": ("phone", "role")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "first_name", "phone", "role", "password1", "password2"),
        }),
    )