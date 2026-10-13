from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from services.models import Area, Category, Provider

User = get_user_model()
PASSWORD = "Str0ng-pass-123"
FAST_HASHER = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class CustomerSignupTests(TestCase):
    url = "/accounts/signup/customer/"

    def data(self, **overrides):
        data = {
            "first_name": "Priya",
            "username": "priya",
            "phone": "9876543210",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_signup_creates_customer_and_logs_in(self):
        response = self.client.post(self.url, self.data())
        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(username="priya")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertIn("_auth_user_id", self.client.session)

    def test_user_cannot_choose_own_role(self):
        self.client.post(self.url, self.data(role="admin", is_staff="on", is_superuser="on"))
        user = User.objects.get(username="priya")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_invalid_phone_numbers_are_rejected(self):
        for phone in ["12345", "5876543210", "98765432101", "abcdefghij"]:
            with self.subTest(phone=phone):
                response = self.client.post(self.url, self.data(phone=phone))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(User.objects.count(), 0)

    def test_duplicate_phone_is_rejected(self):
        self.client.post(self.url, self.data())
        self.client.logout()
        self.client.post(self.url, self.data(username="other"))
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_is_rejected(self):
        response = self.client.post(self.url, self.data(password1="12345678", password2="12345678"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)

    def test_logged_in_user_is_redirected_away_from_signup(self):
        user = User.objects.create_user("priya", password=PASSWORD, phone="9876543210")
        self.client.force_login(user)
        self.assertRedirects(self.client.get(self.url), reverse("home"))


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class ProviderSignupTests(TestCase):
    url = "/accounts/signup/provider/"

    def setUp(self):
        self.category = Category.objects.create(name="Mehndi", slug="mehndi")
        self.area = Area.objects.create(name="Kottar")

    def data(self, **overrides):
        data = {
            "first_name": "Meena",
            "username": "meena",
            "phone": "9876543211",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "business_name": "Meena Mehndi",
            "categories": [self.category.pk],
            "area": self.area.pk,
        }
        data.update(overrides)
        return data

    def test_provider_signup_creates_unapproved_profile(self):
        response = self.client.post(self.url, self.data())
        self.assertRedirects(response, reverse("provider_dashboard"))
        user = User.objects.get(username="meena")
        self.assertEqual(user.role, User.Role.PROVIDER)
        provider = Provider.objects.get(user=user)
        self.assertFalse(provider.is_approved)
        self.assertEqual(list(provider.categories.all()), [self.category])

    def test_provider_must_choose_a_service(self):
        response = self.client.post(self.url, self.data(categories=[]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Provider.objects.count(), 0)


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class LoginLogoutTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            "priya", password=PASSWORD, phone="9876543210", role=User.Role.CUSTOMER
        )
        self.provider = User.objects.create_user(
            "meena", password=PASSWORD, phone="9876543211", role=User.Role.PROVIDER
        )

    def login(self, username, **extra):
        return self.client.post(
            reverse("login"), {"username": username, "password": PASSWORD, **extra}
        )

    def test_customer_lands_on_home(self):
        self.assertRedirects(self.login("priya"), reverse("home"))

    def test_provider_lands_on_dashboard(self):
        response = self.login("meena")
        self.assertRedirects(response, reverse("provider_dashboard"), fetch_redirect_response=False)

    def test_superuser_gets_admin_role(self):
        user = User.objects.create_superuser(
            "boss", password=PASSWORD, phone="9000000009", first_name="Boss"
        )
        self.assertEqual(user.role, User.Role.ADMIN)
        response = self.login("boss")
        self.assertRedirects(response, reverse("admin:index"), fetch_redirect_response=False)

    def test_next_url_is_honoured(self):
        response = self.login("priya", next="/bookings/")
        self.assertRedirects(response, "/bookings/", fetch_redirect_response=False)

    def test_external_next_url_is_ignored(self):
        response = self.login("priya", next="https://evil.example/")
        self.assertRedirects(response, reverse("home"))

    def test_wrong_password_does_not_login(self):
        response = self.client.post(reverse("login"), {"username": "priya", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_needs_post(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)