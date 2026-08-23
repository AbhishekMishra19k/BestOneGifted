# BestOneGifted — Audit & Fixes Report

> **Stack correction up front:** the task brief referenced Next.js/React, Multer,
> JWT, `package.json`, and `next.config.js`. This project is actually **Django
> 5.0 + server-rendered templates + SQLite/Postgres**, deployed as a Python
> WSGI app (not Node). I've translated every objective in the brief to its
> real Django equivalent below rather than force-fitting Node-specific advice
> that doesn't apply to this codebase. Where the brief's exact ask doesn't
> exist in Django (e.g. `package.json`, `next.config.js`), I've noted the
> actual file that serves the same purpose (`requirements.txt`, `vercel.json`).

---

## 1. Executive Summary

**Project structure:** Django project `giftstore` with apps `accounts`, `cart`,
`orders`, `products`, `wishlist`. Session-based cart, Django's built-in auth,
server-rendered HTML with a hand-built AJAX layer (`main.js`) for cart drawer,
wishlist, search, and quick-view. `django-axes` (login lockout) and
`django-ratelimit` (endpoint throttling) already installed.

**Overall health before this audit:** Mixed. The backend (models, views,
security hardening from a prior audit) was in good shape. The **frontend
redesign work you uploaded had one file-corruption bug that made the cart page
completely unusable**, and a **migration file had a fatal syntax error** that
would crash `migrate` on first run in any fresh environment (including a
Vercel/CI build). Both are fixed below and re-verified.

**After this audit:** All 12 steps of a real signup→login→browse→cart→coupon→
checkout→WhatsApp-confirm→track→dashboard→logout flow pass end-to-end
(see §5). Razorpay is fully removed with zero dangling references. Cloudinary
support added (opt-in) so product/review photos survive on Vercel.

---

## 2. Issues Identified

### 🔴 Critical (would break the live site)

| # | Issue | Where |
|---|---|---|
| 1 | **`templates/cart/cart.html` contained pure CSS, not HTML.** The entire cart page template had been overwritten by a copy-paste of your new dark-theme stylesheet. Visiting `/cart/` would render as a blank/broken page — no cart items, no checkout button, nothing. This is the single most severe issue found: **customers could not check out at all.** | `templates/cart/cart.html` |
| 2 | **Migration `0004_order_access_token.py` had `max_length=...`** — a literal Python `Ellipsis` object instead of a number, plus a bad `default=''` on a `unique=True` field. Running `python manage.py migrate` on any fresh database (a new dev's machine, CI, or your first Vercel deploy) would crash immediately with `OperationalError: near "Ellipsis": syntax error`. | `orders/migrations/0004_order_access_token.py` |
| 3 | **Duplicate/conflicting migration branch.** Two different `0004_*.py` files existed for the `orders` app (one from an earlier session, one newly generated), merged via an empty `0005_merge_*.py`. This is fragile — the next `makemigrations` run could produce inconsistent results depending on which branch Django resolves first. | `orders/migrations/` |
| 4 | **Razorpay left in place** despite being requested for removal earlier — `razorpay` package in `requirements.txt`, `RAZORPAY_KEY_ID`/`SECRET`/`WEBHOOK_SECRET` in settings, a `razorpay_payment.html` template, and stale mentions in Privacy/Refund/Terms policy pages. | `requirements.txt`, `giftstore/settings.py`, `templates/orders/`, `templates/products/pages/` |

### 🟠 High (real problem, not yet fatal)

| # | Issue | Where |
|---|---|---|
| 5 | **Uploaded images (product photos, review photos, personalization uploads) use local disk storage only.** Vercel's serverless filesystem is read-only/ephemeral — anything an admin uploads through `/admin/` today will vanish on the next deploy or cold start. This matches exactly the "images failing to render" symptom described in the brief. | `giftstore/settings.py` (no cloud storage configured) |
| 6 | **New CSS classes used in templates weren't all defined** (`.whatsapp-confirm-box`, `.whatsapp-confirm-btn` were referenced by the order-success page but missing from the new dark-theme stylesheet — it hadn't been updated yet for the WhatsApp-confirmation feature added after the redesign started). | `static/css/style.css` |
| 7 | **WhatsApp number hardcoded in 5 separate template files** instead of one settings value — changing your business number meant editing 5 files and risking missing one. | `templates/base.html`, `templates/accounts/dashboard.html`, `templates/products/pages/contact.html` |

### 🟡 Medium (works, but worth knowing)

| # | Issue | Where |
|---|---|---|
| 8 | `.git`, `venv/`, `.venv/`, and `__pycache__/` folders were included in the uploaded zip (~100MB+ of bloat unrelated to the actual app). Not a bug, but worth excluding from future zips/commits — `.gitignore` already lists these correctly, they just weren't respected when zipping. | zip packaging |
| 9 | No automated tests exist for the checkout/cart flow — every verification in this report was done by me manually driving the app through Django's test client. Worth adding a small `tests.py` per app so regressions like #1/#2 above are caught automatically next time, not discovered by a customer. | `*/tests.py` (mostly empty stubs) |

---

## 3. Exact Code Changes Made

### Fix #1 — Rebuilt `templates/cart/cart.html`
Restored as a proper Django template extending `base.html`, using the **new
dark-theme class names** your redesign introduced elsewhere (`.ambient-card`,
`.cart-empty-state`, `.cart-table-wrap`) so it's visually consistent with the
rest of the redesigned site — not a revert to the old green theme. Cart line
items, personalization tags, coupon box, and totals all preserved from the
working backend logic.

### Fix #2 & #3 — Migration cleanup
Deleted the broken `0004_order_access_token.py` and its empty merge migration
`0005_merge_20260822_2044.py`. The *other* `0004_coupon_max_uses_...py` file
already defined `access_token` correctly (`max_length=64, unique=True,
editable=False, blank=True`) alongside the coupon usage-limit fields, so nothing
was lost — I just removed the broken duplicate branch and regenerated a clean
`0005_remove_order_razorpay_order_id_and_more.py` on top of the good history.
Verified with a **fresh `python manage.py migrate` from an empty database** —
zero errors, all 9 orders-app migrations apply cleanly in order.

### Fix #4 — Razorpay fully removed
- `orders/views.py`, `orders/models.py`, `orders/urls.py`, `orders/admin.py` —
  replaced with the Razorpay-free versions (COD-only checkout, atomic stock
  decrement, idempotency key, `access_token`-gated order-success page, and a
  new `Order.whatsapp_confirm_link()` method that builds a pre-filled `wa.me`
  URL with the order summary).
- `requirements.txt` — `razorpay==1.4.2` line removed.
- `giftstore/settings.py` — `RAZORPAY_*` settings replaced with
  `WHATSAPP_BUSINESS_NUMBER`.
- `templates/orders/razorpay_payment.html` — deleted.
- `templates/orders/checkout.html` — online-payment radio button replaced
  with a COD-only notice + WhatsApp mention.
- `templates/orders/order_success.html` — added the "Confirm Order on
  WhatsApp" button (pre-filled with order #, items, personalization notes,
  total, delivery address).
- `templates/products/pages/{privacy,refund,terms}.html` — Razorpay wording
  replaced with COD-accurate text.

### Fix #5 — Cloudinary support for uploaded media (opt-in, Vercel-safe)
Added conditional cloud storage in `giftstore/settings.py`:
```python
CLOUDINARY_URL = config('CLOUDINARY_URL', default='')
if CLOUDINARY_URL:
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
    STORAGES['default'] = {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'}
else:
    STORAGES['default'] = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
```
- If `CLOUDINARY_URL` is unset (local dev, or you haven't signed up yet),
  behavior is **unchanged** — uploads save to the local `media/` folder exactly
  as before. Verified this with a fresh `python manage.py check` — no errors.
- If `CLOUDINARY_URL` **is** set (production/Vercel), all `ImageField`/
  `FileField` uploads (products, reviews, personalization photos) go to
  Cloudinary automatically — no other code changes needed, since Django's
  storage abstraction routes every `.save()` call through this backend.
- Added `django-cloudinary-storage` + `cloudinary` to `requirements.txt`.
- Added `CLOUDINARY_URL=` to `.env.example` with setup instructions.

**Verified end-to-end:** uploaded a real JPEG through `/admin/`, confirmed
`product.image.url` resolves and the image is fetchable back with the correct
`image/jpeg` content-type (see §5, item 9).

### Fix #6 — Missing CSS added
Added `.whatsapp-confirm-box` / `.whatsapp-confirm-btn` styles to
`static/css/style.css`, matching the dark theme's existing glass/glow
conventions (not the old green theme).

### Fix #7 — WhatsApp number centralized
Added `products/context_processors.py` (`whatsapp_number`), registered it in
`TEMPLATES.OPTIONS.context_processors`, and replaced all 5 hardcoded
`wa.me/919201461413` occurrences with `wa.me/{{ whatsapp_number }}`. Changing
your business number is now a single line in `.env`
(`WHATSAPP_BUSINESS_NUMBER=91XXXXXXXXXX`).

---

## 4. Vercel Deployment Checklist

Same real limitation as before, now solved for images specifically:

1. **Database:** SQLite will not work on Vercel (read-only filesystem). Use a
   free Postgres database — [Neon.tech](https://neon.tech) is fastest, no
   card required. Copy its connection string as `DATABASE_URL`.
2. **Media storage:** sign up free at [cloudinary.com](https://cloudinary.com/users/register/free),
   copy the `CLOUDINARY_URL` shown on your dashboard, set it as an env var.
   This is what makes uploaded product/review/personalization photos actually
   persist and render on Vercel — **do this, it's the fix for the "images
   failing" issue.**
3. Push this project to GitHub.
4. Import into Vercel, set these **Environment Variables**:
   ```
   SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(50))">
   DEBUG=False
   ALLOWED_HOSTS=your-app.vercel.app,.vercel.app
   CSRF_TRUSTED_ORIGINS=https://your-app.vercel.app
   DATABASE_URL=<your Neon connection string>
   CLOUDINARY_URL=<your Cloudinary URL>
   WHATSAPP_BUSINESS_NUMBER=91XXXXXXXXXX
   SITE_DOMAIN=your-app.vercel.app
   ```
5. `vercel.json` and `build_files.sh` are already present and configured
   (static files build via `@vercel/static-build`, app served via
   `@vercel/python`) — no changes needed there.
6. From your **local machine**, point at the same `DATABASE_URL` temporarily
   and run migrations (Vercel has no "release phase" like Render, so this
   step must be done manually):
   ```
   $env:DATABASE_URL="<your Neon connection string>"
   $env:CLOUDINARY_URL="<your Cloudinary URL>"
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py loaddata products/fixtures/sample_data.json
   ```
7. Redeploy on Vercel so it picks up the new environment variables.
8. Log into `/admin/`, upload a real product photo, confirm it renders on the
   live homepage — this is the concrete test that the Cloudinary fix worked.

---

## 5. Testing Verification (actually run, not just described)

Every step below was executed against this exact codebase using Django's test
client (equivalent to a real browser session) immediately after each fix, not
just claimed:

```
1.  Signup                                          -> 302 (success)
2.  Login (fresh session)                           -> 302 (success)
3.  Profile update (name/email/phone/address/
    landmark/city/state/pincode)                    -> 302 (success)
4.  Homepage                                         -> 200
5.  Shop / catalog page                              -> 200
6.  Single product detail page                       -> 200
7.  Add to cart (with personalization text)          -> 200, cart count = 2
8.  View cart page  <-- THE PAGE THAT WAS BROKEN      -> 200
       - Renders real HTML (<html> tag present)       -> True
       - Shows the correct product name                -> True
       - Shows the coupon input box                     -> True
9.  Apply coupon "DIWALI25" (25% off)                -> 302 (success)
       - Coupon code shown on cart page                -> True
10. Wishlist toggle (AJAX)                           -> 200
11. Wishlist page                                     -> 200
12. Checkout (Cash on Delivery)                       -> 302 -> redirects to
       token-gated order-success URL
       Order total after 25% coupon: Rs. 1498 -> Rs. 1123.50 (correct math)
13. Order success page                                -> 200
       - "Confirm Order on WhatsApp" button present     -> True
14. Order tracking page (My Orders)                   -> 200
15. Dashboard shows the new order                      -> True
16. Logout                                             -> 302
17. Dashboard after logout (should redirect to login) -> 302 (correctly blocked)

18. Image upload via /admin/ (real JPEG, in-memory)    -> 200
       - product.image.url resolves                     -> True
       - Fetching that URL back                          -> 200,
         Content-Type: image/jpeg (confirmed correct)

19. Fresh `python manage.py migrate` on an empty DB     -> all 9 orders-app
    migrations + all other apps apply with zero errors
20. `python manage.py check`                            -> System check
    identified no issues (0 silenced)
```

**To verify this yourself locally:**
```
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py loaddata products/fixtures/sample_data.json
python manage.py runserver
```
Then manually walk: signup → browse → add to cart → view cart (confirm it's
no longer blank) → apply a coupon you create in `/admin/` → checkout → confirm
the WhatsApp button appears → check `/accounts/dashboard/` → log out.
