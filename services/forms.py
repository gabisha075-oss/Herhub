import re
from django import forms
from django.utils import timezone

from accounts.forms import BootstrapMixin

from .models import Booking, Review, PortfolioImage, Provider, Service


class BookingForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["service", "date", "time", "venue", "notes"]
        labels = {
            "service": "Select a service",
            "date": "Preferred date",
            "time": "Preferred time",
            "venue": "Where should the service happen?",
            "notes": "Anything else they should know?",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
            "venue": forms.RadioSelect,
            "notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Tell us about your event, preferred look, or any questions..."}
            ),
        }

    def __init__(self, *args, provider, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = provider.services.all()
        self.fields["service"].empty_label = "Choose a service"
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()
        if not provider.home_service:
            self.fields["venue"].choices = [
                c for c in self.fields["venue"].choices if c[0] == Booking.Venue.STUDIO
            ]

    def clean(self):
        cleaned = super().clean()
        date, time = cleaned.get("date"), cleaned.get("time")
        if date == timezone.localdate() and time and time <= timezone.localtime().time():
            self.add_error("time", "Please choose a time in the future.")
        return cleaned


class ReviewForm(BootstrapMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i} ★") for i in range(5, 0, -1)], coerce=int
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]

MAX_IMAGE_MB = 5


def validate_image_size(file):
    if file.size > MAX_IMAGE_MB * 1024 * 1024:
        raise forms.ValidationError(f"Image must be smaller than {MAX_IMAGE_MB} MB.")


class ServiceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ["category", "name", "description", "price"]
        labels = {
            "category": "Category",
            "name": "Service name",
            "description": "Short description",
            "price": "Starting price (₹)",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Bridal Makeup"}),
            "description": forms.TextInput(attrs={"placeholder": "e.g. Makeup, hair & saree draping"}),
        }

    def __init__(self, *args, provider, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = provider.categories.all()
        self.fields["category"].empty_label = "Select category"

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price <= 0:
            raise forms.ValidationError("Price must be more than 0.")
        return price


class PortfolioImageForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PortfolioImage
        fields = ["image", "caption"]
        labels = {"image": "Choose a photo", "caption": "Caption (optional)"}

    def clean_image(self):
        image = self.cleaned_data["image"]
        validate_image_size(image)
        return image


class ProviderProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Provider
        fields = [
            "business_name", "categories", "area", "about", "years_experience",
            "whatsapp", "home_service", "bridal_specialist", "profile_photo",
        ]
        labels = {
            "business_name": "Business name",
            "categories": "Your services",
            "about": "About your work",
            "years_experience": "Years of experience",
            "whatsapp": "WhatsApp number (optional)",
            "home_service": "I offer home service",
            "bridal_specialist": "I'm a bridal specialist",
            "profile_photo": "Profile photo",
        }
        help_texts = {"whatsapp": "10 digits. Leave empty to use your login mobile number."}
        widgets = {
            "categories": forms.CheckboxSelectMultiple,
            "about": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_whatsapp(self):
        number = self.cleaned_data["whatsapp"].strip()
        if number and not re.fullmatch(r"[6-9]\d{9}", number):
            raise forms.ValidationError("Enter a valid 10-digit mobile number.")
        return number

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if photo and hasattr(photo, "content_type"):   # puthusa upload panna mattum
            validate_image_size(photo)
        return photo