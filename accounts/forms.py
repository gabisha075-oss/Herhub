from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db import transaction

from services.models import Area, Category, Provider

from .models import User


class BootstrapMixin:
    """Ellaa fields-kum Bootstrap CSS class add pannum."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                continue
            css = "form-select" if isinstance(widget, forms.Select) else "form-control"
            widget.attrs["class"] = css


# ---------- Admin forms (munnaadi irundhadhu) ----------
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "phone", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


# ---------- Website signup forms ----------
class CustomerSignupForm(BootstrapMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "username", "phone")
        labels = {"first_name": "Your name", "phone": "Mobile number"}

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CUSTOMER      # server-la set pannrom
        user.save()
        return user


class ProviderSignupForm(BootstrapMixin, UserCreationForm):
    business_name = forms.CharField(max_length=150)
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Your services",
    )
    area = forms.ModelChoiceField(
        queryset=Area.objects.all(), empty_label="Select your area"
    )
    profile_photo = forms.ImageField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "username", "phone")
        labels = {"first_name": "Your name", "phone": "Mobile number"}

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PROVIDER
        user.save()
        provider = Provider.objects.create(
            user=user,
            business_name=self.cleaned_data["business_name"],
            area=self.cleaned_data["area"],
            profile_photo=self.cleaned_data.get("profile_photo") or "",
        )
        provider.categories.set(self.cleaned_data["categories"])
        return user