from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Min, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from urllib.parse import quote
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from .forms import BookingForm, ReviewForm
from .models import Area, Booking, Category, Provider, Review


def add_stats(queryset):
    """Provider list-ku rating, review count, starting price add pannum."""
    visible = Q(bookings__review__is_visible=True)
    return (
        queryset.select_related("area", "user")
        .prefetch_related("categories")
        .annotate(
            avg_rating=Avg("bookings__review__rating", filter=visible),
            review_count=Count("bookings__review", filter=visible, distinct=True),
            min_price=Min("services__price"),
        )
    )


def home(request):
    approved = Provider.objects.filter(is_approved=True)
    top_rated = F("avg_rating").desc(nulls_last=True)
    context = {
        "categories": Category.objects.all(),
        "areas": Area.objects.all(),
        "featured": add_stats(approved).order_by(top_rated, "-review_count")[:3],
        "bridal": add_stats(approved.filter(bridal_specialist=True)).order_by(top_rated)[:3],
    }
    return render(request, "services/home.html", context)


def provider_list(request):
    qs = add_stats(Provider.objects.filter(is_approved=True))

    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    area = request.GET.get("area", "")
    home_service = request.GET.get("home") == "1"
    bridal = request.GET.get("bridal") == "1"
    max_price = request.GET.get("max_price", "")
    sort = request.GET.get("sort", "recommended")

    if q:
        matches = Provider.objects.filter(
            Q(business_name__icontains=q)
            | Q(categories__name__icontains=q)
            | Q(services__name__icontains=q)
        ).values("pk")
        qs = qs.filter(pk__in=matches)
    if category:
        in_category = Provider.objects.filter(categories__slug=category).values("pk")
        qs = qs.filter(pk__in=in_category)
    if area.isdigit():
        qs = qs.filter(area_id=int(area))
    if home_service:
        qs = qs.filter(home_service=True)
    if bridal:
        qs = qs.filter(bridal_specialist=True)
    if max_price.isdigit():
        qs = qs.filter(min_price__lte=int(max_price))

    if sort == "rating":
        qs = qs.order_by(F("avg_rating").desc(nulls_last=True), "-review_count")
    elif sort == "price":
        qs = qs.order_by(F("min_price").asc(nulls_last=True))
    else:
        qs = qs.order_by(F("avg_rating").desc(nulls_last=True), "-review_count", "-created_at")

    page_obj = Paginator(qs, 9).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "categories": Category.objects.all(),
        "areas": Area.objects.all(),
        "q": q,
        "selected_category": category,
        "selected_area": area,
        "home_service": home_service,
        "bridal": bridal,
        "max_price": max_price,
        "sort": sort,
        "querystring": params.urlencode(),
    }
    return render(request, "services/provider_list.html", context)


def provider_detail(request, pk):
    provider = get_object_or_404(
        add_stats(Provider.objects.all()).prefetch_related("services", "images"),
        pk=pk,
    )
    is_owner = request.user.is_authenticated and provider.user_id == request.user.id
    if not provider.is_approved and not is_owner:
        raise Http404

    reviews = (
        Review.objects.filter(booking__provider=provider, is_visible=True)
        .select_related("booking__customer")[:5]
    )
    wa_text = quote(f"Hi {provider.business_name}, I found you on HerHub.")

    return render(request, "services/provider_detail.html", {
        "provider": provider,
        "reviews": reviews,
        "is_owner": is_owner,
        "wa_text": wa_text,
    })

# ---------------- Customer: booking ----------------
@role_required("customer")
def book_provider(request, pk):
    provider = get_object_or_404(Provider, pk=pk, is_approved=True)

    if not provider.services.exists():
        messages.warning(request, "This provider hasn't listed any services yet.")
        return redirect("provider_detail", pk=pk)

    booking = Booking(customer=request.user, provider=provider)
    if request.method == "POST":
        form = BookingForm(request.POST, provider=provider, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Request sent to {provider.business_name}. They will contact you to confirm.",
            )
            return redirect("my_bookings")
    else:
        form = BookingForm(provider=provider, instance=booking)

    return render(request, "services/book_provider.html", {"form": form, "provider": provider})


@role_required("customer")
def my_bookings(request):
    status = request.GET.get("status", "")
    bookings = Booking.objects.filter(customer=request.user).select_related(
        "provider", "service", "review"
    )
    if status in Booking.Status.values:
        bookings = bookings.filter(status=status)
    return render(request, "services/my_bookings.html", {
        "bookings": bookings,
        "status": status,
        "tabs": Booking.Status.choices,
    })


@role_required("customer")
@require_POST
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, customer=request.user)
    if booking.status in (Booking.Status.PENDING, Booking.Status.ACCEPTED):
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        messages.success(request, "Booking cancelled.")
    else:
        messages.error(request, "This booking can't be cancelled.")
    return redirect("my_bookings")


@role_required("customer")
@require_POST
def review_booking(request, pk):
    booking = get_object_or_404(
        Booking, pk=pk, customer=request.user, status=Booking.Status.COMPLETED
    )
    if hasattr(booking, "review"):
        messages.error(request, "You have already reviewed this booking.")
        return redirect("my_bookings")

    form = ReviewForm(request.POST, instance=Review(booking=booking))
    if form.is_valid():
        form.save()
        messages.success(request, "Thanks for your review!")
    else:
        messages.error(request, "Please choose a rating from 1 to 5.")
    return redirect("my_bookings")


# ---------------- Provider: dashboard ----------------
BOOKING_ACTIONS = {
    "accept": (Booking.Status.PENDING, Booking.Status.ACCEPTED),
    "reject": (Booking.Status.PENDING, Booking.Status.REJECTED),
    "complete": (Booking.Status.ACCEPTED, Booking.Status.COMPLETED),
}


@role_required("provider")
def provider_dashboard(request):
    provider = Provider.objects.filter(user=request.user).first()
    context = {"provider": provider}

    if provider:
        status = request.GET.get("status", "")
        all_bookings = provider.bookings.select_related("customer", "service")
        counts = dict(
            all_bookings.order_by().values_list("status").annotate(n=Count("id"))
        )
        bookings = all_bookings
        if status in Booking.Status.values:
            bookings = bookings.filter(status=status)

        context.update({
            "bookings": bookings,
            "status": status,
            "tabs": Booking.Status.choices,
            "counts": counts,
            "pending_count": counts.get(Booking.Status.PENDING, 0),
            "accepted_count": counts.get(Booking.Status.ACCEPTED, 0),
            "completed_count": counts.get(Booking.Status.COMPLETED, 0),
        })
    return render(request, "services/provider_dashboard.html", context)


@role_required("provider")
@require_POST
def booking_action(request, pk, action):
    if action not in BOOKING_ACTIONS:
        raise Http404

    booking = get_object_or_404(Booking, pk=pk, provider__user=request.user)
    required_status, new_status = BOOKING_ACTIONS[action]

    if booking.status != required_status:
        messages.error(request, "This request was already updated.")
    elif action == "complete" and booking.date > timezone.localdate():
        messages.error(request, "You can mark a booking completed only on or after its date.")
    else:
        booking.status = new_status
        booking.save(update_fields=["status"])
        messages.success(request, f"Booking marked as {booking.get_status_display().lower()}.")
    return redirect("provider_dashboard")
