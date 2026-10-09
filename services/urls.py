from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("providers/", views.provider_list, name="provider_list"),
    path("providers/<int:pk>/", views.provider_detail, name="provider_detail"),
    path("providers/<int:pk>/book/", views.book_provider, name="book_provider"),
    path("bookings/", views.my_bookings, name="my_bookings"),
    path("bookings/<int:pk>/cancel/", views.cancel_booking, name="cancel_booking"),
    path("bookings/<int:pk>/review/", views.review_booking, name="review_booking"),
    path("dashboard/", views.provider_dashboard, name="provider_dashboard"),
    path("dashboard/bookings/<int:pk>/<slug:action>/", views.booking_action, name="booking_action"),
]