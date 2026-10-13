# HerHub

A local services marketplace for women in Nagercoil, Tamil Nadu. Customers discover and book trusted women service providers (tailoring, boutique, mehndi, aari work, makeup, nail art), and providers manage their own profile, services and bookings.

![Home page](docs/screenshots/home.png)

## Why I built this

Many women running tailoring, mehndi and makeup businesses in small towns depend on word of mouth and WhatsApp. Customers struggle to find, compare and book them. HerHub gives these providers a simple online presence and gives customers one place to search, check prices and request a booking.

## Features

**Customers**
- Browse and search providers without logging in
- Filter by service, area, budget, home service and bridal specialist; sort by rating or price
- Provider profile with portfolio, price list, reviews and a WhatsApp button
- Request a booking (login required), track status, cancel, and review completed bookings
- Save favourite providers

**Providers**
- Sign up and manage their own profile, services, prices and portfolio photos
- Dashboard to accept, reject or complete booking requests
- Profiles go live only after admin approval

**Admin**
- Approve providers and manage categories, areas, bookings and reviews from Django admin

## Screenshots

| Search | Provider profile |
|---|---|
| ![Search](docs/screenshots/search.png) | ![Profile](docs/screenshots/provider-profile.png) |

| Booking form | Provider dashboard |
|---|---|
| ![Booking](docs/screenshots/booking-form.png) | ![Dashboard](docs/screenshots/dashboard.png) |

## Tech stack

- Python, Django 5.2 (LTS)
- MySQL
- Bootstrap 5, custom CSS (mobile-first, responsive)
- Django's built-in auth with a custom user model (username login, role: customer / provider / admin)

## Security and design decisions

- **Roles are assigned on the server**, never from form input, so users can't make themselves providers or admins.
- **Object-level ownership checks** on every provider and customer action (a provider can't accept or edit another provider's booking or service).
- **State-changing actions are POST-only** with CSRF protection (accept, reject, cancel, favourite, logout).
- **Booking rules**: no past dates, no double-booking of the same slot, services must belong to the chosen provider, valid status transitions only.
- **Open-redirect protection** for `next` URLs after login and favourite actions.
- **Upload validation**: image type and a 5 MB size limit, max 12 portfolio photos.
- **Environment-based configuration** (`python-decouple`): secrets and `DEBUG` never live in code.
- Query optimisation: ratings, review counts and starting prices are computed in a single annotated query to avoid N+1 queries.

## Automated tests

```bash
python manage.py test
```

<XX> tests cover access control, public visibility, booking rules, provider actions, favourites, signup and login.

## Run locally

Requirements: Python 3.12+, MySQL 8.0+

```bash
git clone https://github.com/<your-username>/herhub.git
cd herhub
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Create the database in MySQL:

```sql
CREATE DATABASE herhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Copy `.env.example` to `.env` and fill in your values (generate a secret key with
`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`). For local development use `DEBUG=True` and `USE_HTTPS=False`.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/admin/`, add a few **Categories** (e.g. Tailoring, Mehndi, Makeup Artist) and **Areas**, then sign up as a provider or customer from the site. Approve providers from the admin panel (`is_approved`).

## Project structure

```
config/      project settings and root URLs
accounts/    custom user model, signup, login, role-based redirects
services/    providers, services, bookings, reviews, favourites, public pages
templates/   shared base template, partials and page templates
static/      CSS
```

## Known limitations and roadmap

- No reschedule flow yet (provider can only accept, reject or complete)
- No email / SMS notifications for new booking requests
- Two customers submitting the same slot at the exact same moment could both pass validation (a database-level lock is the next fix)
- Favourite button reloads the page; could use JavaScript for a smoother experience
- Planned: Tamil language support, OTP login, online payments

## Author

**Abisha** · <LinkedIn or email>