from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Area(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Provider(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_profile",
        limit_choices_to={"role": "provider"},
    )
    business_name = models.CharField(max_length=150)
    categories = models.ManyToManyField(Category, related_name="providers")
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, related_name="providers")
    about = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True)
    years_experience = models.PositiveSmallIntegerField(default=0)
    whatsapp = models.CharField(max_length=10, blank=True)
    home_service = models.BooleanField(default=False)
    bridal_specialist = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.business_name

    @property
    def whatsapp_number(self):
        return self.whatsapp or self.user.phone


class Service(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="services")
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.name} - {self.provider}"


class PortfolioImage(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="portfolio/")
    caption = models.CharField(max_length=150, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    class Venue(models.TextChoices):
        HOME = "home", "At my home"
        STUDIO = "studio", "At the studio"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        limit_choices_to={"role": "customer"},
    )
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    date = models.DateField()
    time = models.TimeField()
    venue = models.CharField(max_length=10, choices=Venue.choices, default=Venue.STUDIO)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self._state.adding and self.date and self.date < timezone.localdate():
            raise ValidationError({"date": "You cannot book a past date."})

        if self.service_id and self.provider_id and self.service.provider_id != self.provider_id:
            raise ValidationError("This service does not belong to the selected provider.")

        if self.provider_id and self.date and self.time:
            clash = Booking.objects.filter(
                provider=self.provider,
                date=self.date,
                time=self.time,
                status__in=[self.Status.PENDING, self.Status.ACCEPTED],
            ).exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError("This time slot is already booked.")

    def __str__(self):
        return f"{self.customer} → {self.provider} ({self.date})"


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="review")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.booking_id and self.booking.status != Booking.Status.COMPLETED:
            raise ValidationError("You can review only completed bookings.")

    def __str__(self):
        return f"{self.rating}★ for {self.booking.provider}"


class Favorite(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["customer", "provider"], name="unique_favorite")
        ]