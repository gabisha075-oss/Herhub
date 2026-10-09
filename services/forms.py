from django import forms
from django.utils import timezone

from accounts.forms import BootstrapMixin

from .models import Booking, Review


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