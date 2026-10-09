from django.contrib import admin

from .models import Area, Booking, Category, Favorite, PortfolioImage, Provider, Review, Service


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 1


class PortfolioInline(admin.TabularInline):
    model = PortfolioImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "area", "is_approved", "created_at")
    list_filter = ("is_approved", "area", "categories", "home_service", "bridal_specialist")
    list_editable = ("is_approved",)
    search_fields = ("business_name", "user__username", "user__phone")
    inlines = [ServiceInline, PortfolioInline]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("customer", "provider", "service", "date", "time", "status")
    list_filter = ("status", "date")


admin.site.register([Area, Review, Favorite])