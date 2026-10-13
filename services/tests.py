import datetime
import itertools
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Area, Booking, Category, Favorite, Provider, Review, Service

User = get_user_model()
PASSWORD = "Str0ng-pass-123"
FAST_HASHER = ["django.contrib.auth.hashers.MD5PasswordHasher"]
_numbers = itertools.count(1)


# ---------- helpers: test data fast-a create panna ----------
def make_user(username, role=User.Role.CUSTOMER):
    return User.objects.create_user(
        username=username,
        password=PASSWORD,
        role=role,
        phone=f"9{next(_numbers):09d}",
        first_name=username.title(),
    )


def make_provider(username="nila", approved=True, **extra):
    user = make_user(username, User.Role.PROVIDER)
    area, _ = Area.objects.get_or_create(name="Vadasery")
    category, _ = Category.objects.get_or_create(slug="makeup", defaults={"name": "Makeup Artist"})
    provider = Provider.objects.create(
        user=user,
        business_name=f"{username.title()} Studio",
        area=area,
        is_approved=approved,
        **extra,
    )
    provider.categories.add(category)
    return provider


def make_service(provider, name="Bridal Makeup", price=8000):
    return Service.objects.create(
        provider=provider, category=provider.categories.first(), name=name, price=price
    )


def days_from_today(n):
    return timezone.localdate() + timedelta(days=n)


def make_booking(customer, service, status=Booking.Status.PENDING, date=None,
                 time=datetime.time(10, 0)):
    return Booking.objects.create(
        customer=customer,
        provider=service.provider,
        service=service,
        date=date or days_from_today(3),
        time=time,
        status=status,
    )


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class BaseTestCase(TestCase):
    def login(self, user):
        self.client.force_login(user)


# ---------- 1. Role-based access ----------
class AccessControlTests(BaseTestCase):
    def test_anonymous_users_are_sent_to_login(self):
        for name in ["provider_dashboard", "my_bookings", "my_favorites",
                     "my_services", "my_portfolio", "edit_profile"]:
            with self.subTest(page=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_customer_is_blocked_from_provider_pages(self):
        self.login(make_user("priya"))
        for name in ["provider_dashboard", "my_services", "my_portfolio", "edit_profile"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_provider_is_blocked_from_customer_pages(self):
        provider = make_provider()
        self.login(provider.user)
        urls = [
            reverse("my_bookings"),
            reverse("my_favorites"),
            reverse("book_provider", args=[provider.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)


# ---------- 2. Public visibility ----------
class PublicVisibilityTests(BaseTestCase):
    def test_unapproved_provider_is_hidden_from_search(self):
        make_provider("live", approved=True)
        make_provider("pending", approved=False)
        response = self.client.get(reverse("provider_list"))
        self.assertContains(response, "Live Studio")
        self.assertNotContains(response, "Pending Studio")

    def test_unapproved_profile_is_404_for_public(self):
        provider = make_provider(approved=False)
        response = self.client.get(reverse("provider_detail", args=[provider.pk]))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_preview_own_unapproved_profile(self):
        provider = make_provider(approved=False)
        self.login(provider.user)
        response = self.client.get(reverse("provider_detail", args=[provider.pk]))
        self.assertEqual(response.status_code, 200)

    def test_hidden_reviews_are_not_counted_in_rating(self):
        provider = make_provider()
        service = make_service(provider)
        customer = make_user("priya")
        first = make_booking(customer, service, Booking.Status.COMPLETED, date=days_from_today(-5))
        second = make_booking(customer, service, Booking.Status.COMPLETED, date=days_from_today(-4))
        Review.objects.create(booking=first, rating=5)
        Review.objects.create(booking=second, rating=1, is_visible=False)

        response = self.client.get(reverse("provider_list"))
        card = response.context["page_obj"][0]
        self.assertAlmostEqual(float(card.avg_rating), 5.0)
        self.assertEqual(card.review_count, 1)


# ---------- 3. Customer creates a booking ----------
class BookingCreationTests(BaseTestCase):
    def setUp(self):
        self.provider = make_provider()
        self.service = make_service(self.provider)
        self.customer = make_user("priya")
        self.url = reverse("book_provider", args=[self.provider.pk])
        self.login(self.customer)

    def payload(self, **overrides):
        data = {
            "service": self.service.pk,
            "date": days_from_today(3).isoformat(),
            "time": "10:00",
            "venue": "studio",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_customer_can_book(self):
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, reverse("my_bookings"))
        booking = Booking.objects.get()
        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.provider, self.provider)
        self.assertEqual(booking.status, Booking.Status.PENDING)

    def test_anonymous_user_is_sent_to_login_and_back(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_past_date_is_rejected(self):
        response = self.client.post(self.url, self.payload(date=days_from_today(-1).isoformat()))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "past date")
        self.assertEqual(Booking.objects.count(), 0)

    def test_same_slot_cannot_be_double_booked(self):
        make_booking(make_user("divya"), self.service)   # same date + 10:00
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already booked")
        self.assertEqual(Booking.objects.count(), 1)

    def test_cancelled_slot_can_be_booked_again(self):
        make_booking(make_user("divya"), self.service, Booking.Status.CANCELLED)
        self.client.post(self.url, self.payload())
        self.assertEqual(Booking.objects.filter(customer=self.customer).count(), 1)

    def test_service_of_another_provider_is_rejected(self):
        other_service = make_service(make_provider("meena"), name="Party Makeup")
        response = self.client.post(self.url, self.payload(service=other_service.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 0)

    def test_home_venue_rejected_if_provider_has_no_home_service(self):
        response = self.client.post(self.url, self.payload(venue="home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 0)

    def test_unapproved_provider_cannot_be_booked(self):
        self.provider.is_approved = False
        self.provider.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_provider_without_services_redirects_to_profile(self):
        Service.objects.all().delete()
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("provider_detail", args=[self.provider.pk]))


# ---------- 4. Provider accepts / rejects / completes ----------
class ProviderBookingActionTests(BaseTestCase):
    def setUp(self):
        self.provider = make_provider("nila")
        self.service = make_service(self.provider)
        self.customer = make_user("priya")
        self.booking = make_booking(self.customer, self.service)

    def act(self, action):
        return self.client.post(reverse("booking_action", args=[self.booking.pk, action]))

    def set_booking(self, **fields):
        Booking.objects.filter(pk=self.booking.pk).update(**fields)

    def test_provider_can_accept(self):
        self.login(self.provider.user)
        self.act("accept")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.ACCEPTED)

    def test_provider_can_reject(self):
        self.login(self.provider.user)
        self.act("reject")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.REJECTED)

    def test_another_provider_cannot_touch_this_booking(self):
        self.login(make_provider("meena").user)
        self.assertEqual(self.act("accept").status_code, 404)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PENDING)

    def test_customer_cannot_use_provider_actions(self):
        self.login(self.customer)
        self.assertEqual(self.act("accept").status_code, 403)

    def test_cannot_complete_before_booking_date(self):
        self.set_booking(status=Booking.Status.ACCEPTED)      # date = 3 days later
        self.login(self.provider.user)
        self.act("complete")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.ACCEPTED)

    def test_can_complete_on_booking_date(self):
        self.set_booking(status=Booking.Status.ACCEPTED, date=days_from_today(0))
        self.login(self.provider.user)
        self.act("complete")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.COMPLETED)

    def test_accepted_booking_cannot_be_rejected(self):
        self.set_booking(status=Booking.Status.ACCEPTED)
        self.login(self.provider.user)
        self.act("reject")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.ACCEPTED)

    def test_status_change_needs_post_not_get(self):
        self.login(self.provider.user)
        url = reverse("booking_action", args=[self.booking.pk, "accept"])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_unknown_action_is_404(self):
        self.login(self.provider.user)
        self.assertEqual(self.act("delete").status_code, 404)


# ---------- 5. Provider dashboard privacy ----------
class ProviderDashboardTests(BaseTestCase):
    def setUp(self):
        self.provider = make_provider("nila")
        self.service = make_service(self.provider)
        self.customer = make_user("priya")
        self.login(self.provider.user)

    def test_shows_only_own_bookings(self):
        other_service = make_service(make_provider("meena"), name="Party Makeup", price=2500)
        make_booking(self.customer, self.service)
        make_booking(make_user("divya"), other_service)
        response = self.client.get(reverse("provider_dashboard"))
        self.assertContains(response, "Priya")
        self.assertNotContains(response, "Divya")

    def test_customer_phone_is_hidden_after_completion(self):
        booking = make_booking(self.customer, self.service)
        url = reverse("provider_dashboard")
        self.assertContains(self.client.get(url), self.customer.phone)
        booking.status = Booking.Status.COMPLETED
        booking.save()
        self.assertNotContains(self.client.get(url), self.customer.phone)


# ---------- 6. Customer cancels / reviews ----------
class CustomerBookingTests(BaseTestCase):
    def setUp(self):
        self.provider = make_provider("nila")
        self.service = make_service(self.provider)
        self.customer = make_user("priya")
        self.booking = make_booking(self.customer, self.service)
        self.completed = make_booking(
            self.customer, self.service, Booking.Status.COMPLETED, date=days_from_today(-2)
        )
        self.login(self.customer)

    def test_customer_can_cancel_own_pending_booking(self):
        self.client.post(reverse("cancel_booking", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)

    def test_other_customer_cannot_cancel(self):
        self.login(make_user("divya"))
        response = self.client.post(reverse("cancel_booking", args=[self.booking.pk]))
        self.assertEqual(response.status_code, 404)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PENDING)

    def test_completed_booking_cannot_be_cancelled(self):
        self.client.post(reverse("cancel_booking", args=[self.completed.pk]))
        self.completed.refresh_from_db()
        self.assertEqual(self.completed.status, Booking.Status.COMPLETED)

    def test_review_only_for_completed_bookings(self):
        response = self.client.post(
            reverse("review_booking", args=[self.booking.pk]), {"rating": 5}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Review.objects.count(), 0)

    def test_customer_can_review_completed_booking(self):
        self.client.post(
            reverse("review_booking", args=[self.completed.pk]),
            {"rating": 5, "comment": "Great work"},
        )
        review = Review.objects.get()
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.booking, self.completed)

    def test_booking_cannot_be_reviewed_twice(self):
        url = reverse("review_booking", args=[self.completed.pk])
        self.client.post(url, {"rating": 5})
        self.client.post(url, {"rating": 1})
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.get().rating, 5)

    def test_rating_outside_1_to_5_is_rejected(self):
        self.client.post(reverse("review_booking", args=[self.completed.pk]), {"rating": 6})
        self.assertEqual(Review.objects.count(), 0)

    def test_my_bookings_shows_only_own_bookings(self):
        other_service = make_service(self.provider, name="Party Makeup", price=2500)
        make_booking(make_user("divya"), other_service)
        response = self.client.get(reverse("my_bookings"))
        self.assertContains(response, "Bridal Makeup")
        self.assertNotContains(response, "Party Makeup")


# ---------- 7. Favorites ----------
class FavoriteTests(BaseTestCase):
    def setUp(self):
        self.provider = make_provider()
        self.customer = make_user("priya")
        self.url = reverse("toggle_favorite", args=[self.provider.pk])

    def test_toggle_on_and_off(self):
        self.login(self.customer)
        self.client.post(self.url)
        self.assertEqual(Favorite.objects.count(), 1)
        self.client.post(self.url)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_anonymous_user_must_login(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")
        self.assertEqual(Favorite.objects.count(), 0)

    def test_provider_cannot_favorite(self):
        self.login(make_provider("meena").user)
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_unapproved_provider_cannot_be_favorited(self):
        self.provider.is_approved = False
        self.provider.save()
        self.login(self.customer)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_external_next_url_is_ignored(self):
        self.login(self.customer)
        response = self.client.post(self.url, {"next": "https://evil.example/"})
        self.assertRedirects(response, reverse("provider_detail", args=[self.provider.pk]))

    def test_local_next_url_is_used(self):
        self.login(self.customer)
        response = self.client.post(self.url, {"next": "/providers/"})
        self.assertRedirects(response, "/providers/")

    def test_favorites_page_lists_saved_provider(self):
        Favorite.objects.create(customer=self.customer, provider=self.provider)
        self.login(self.customer)
        self.assertContains(self.client.get(reverse("my_favorites")), "Nila Studio")


# ---------- 8. Provider self-service ownership ----------
class ProviderSelfServiceTests(BaseTestCase):
    def setUp(self):
        self.provider = make_provider("nila")
        self.other = make_provider("meena")
        self.service = make_service(self.provider)
        self.category = self.provider.categories.first()
        self.login(self.provider.user)

    def test_provider_can_edit_own_service(self):
        response = self.client.post(
            reverse("service_edit", args=[self.service.pk]),
            {"category": self.category.pk, "name": "Bridal Makeup", "description": "", "price": "9500"},
        )
        self.assertRedirects(response, reverse("my_services"))
        self.service.refresh_from_db()
        self.assertEqual(self.service.price, 9500)

    def test_cannot_edit_another_providers_service(self):
        self.login(self.other.user)
        url = reverse("service_edit", args=[self.service.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_cannot_delete_another_providers_service(self):
        self.login(self.other.user)
        response = self.client.post(reverse("service_delete", args=[self.service.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Service.objects.filter(pk=self.service.pk).exists())

    def test_service_with_bookings_cannot_be_deleted(self):
        make_booking(make_user("priya"), self.service)
        self.client.post(reverse("service_delete", args=[self.service.pk]))
        self.assertTrue(Service.objects.filter(pk=self.service.pk).exists())

    def test_zero_price_is_rejected(self):
        response = self.client.post(
            reverse("service_add"),
            {"category": self.category.pk, "name": "Free", "description": "", "price": "0"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "more than 0")
        self.assertEqual(Service.objects.filter(provider=self.provider).count(), 1)

    def test_category_must_belong_to_provider(self):
        mehndi = Category.objects.create(name="Mehndi", slug="mehndi")
        response = self.client.post(
            reverse("service_add"),
            {"category": mehndi.pk, "name": "Mehndi", "description": "", "price": "500"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Service.objects.filter(provider=self.provider).count(), 1)

    def test_provider_cannot_approve_own_profile(self):
        self.provider.is_approved = False
        self.provider.save()
        response = self.client.post(reverse("edit_profile"), {
            "business_name": "Nila Bridal",
            "categories": [self.category.pk],
            "area": self.provider.area_id,
            "about": "",
            "years_experience": 4,
            "whatsapp": "",
            "is_approved": "on",             # hacker idhai anuppa try pannum
        })
        self.assertRedirects(response, reverse("edit_profile"))
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.business_name, "Nila Bridal")   # edit work aachu
        self.assertFalse(self.provider.is_approved)                    # approve aagala

    def test_invalid_whatsapp_number_is_rejected(self):
        response = self.client.post(reverse("edit_profile"), {
            "business_name": "Nila Bridal",
            "categories": [self.category.pk],
            "area": self.provider.area_id,
            "years_experience": 4,
            "whatsapp": "12345",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid 10-digit")