# BestOneGifted — Django Ecommerce (Customized Gifts)

Django + HTML/CSS/JS ecommerce site: product catalog, cart, user accounts, order
tracking, customer reviews, Cash on Delivery + Razorpay online payment, and a
Django admin for managing everything. Green theme throughout.

---

## 1. Local Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file and edit it
cp .env.example .env

# 4. Run migrations
python manage.py makemigrations
python manage.py migrate

# 5. Create admin login
python manage.py createsuperuser

# 6. (Optional) Load sample products so the store isn't empty
python manage.py loaddata products/fixtures/sample_data.json

# 7. Run the server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` for the store and `http://127.0.0.1:8000/admin/` for admin.

---

## 2. What's included

| Feature | Where |
|---|---|
| Product catalog, categories | `products/` |
| Cart (session-based, works for guests) | `cart/` |
| Checkout, COD + Razorpay online payment | `orders/` |
| **User signup / login / logout** | `accounts/` |
| **User dashboard** — edit profile, see order history | `/accounts/dashboard/` |
| **Order tracking** — Placed to Packed to Shipped to Delivered | `/orders/my-orders/<id>/` |
| **Delivery estimate** — auto-calculated 5-8 days from order date | shown on order success + tracking page |
| **Customer reviews** — logged-in users can review products; shown on homepage + product page | `products/models.py` -> `Review` |
| **SEO** — sitemap.xml, robots.txt, meta description per page | `products/sitemaps.py`, `templates/robots.txt` |
| **Green theme** | `static/css/style.css` — all colors are CSS variables at the top |

Checkout auto-fills the shipping form from the logged-in user's saved profile
(still editable). Guest checkout without login also still works.

---

## 3. Add Your Real Products

Go to `/admin/` -> Products -> Add Product.
- Add Category first (Mugs, T-Shirts, Name Plates, Frames, Bottles, Pens, etc.)
- Upload product image, set price, MRP (optional strike-through), stock
- Tick "is_bestseller" to feature it on the homepage best-seller + gallery sections

## 4. Manage Orders / Update Tracking Status

Go to `/admin/` -> Orders -> open an order -> change **Status** dropdown
(Placed / Packed / Shipped / Delivered / Cancelled) -> Save. The customer's
tracking page updates automatically.

## 5. Moderate Reviews

Go to `/admin/` -> Reviews. Uncheck "is_approved" on any review you want hidden
from the site (spam, inappropriate, etc). Approved reviews appear on the
homepage and the relevant product page.

---

## 6. Finish these yourself (design/content, not code)

- **Hero banner video**: put a short looping MP4 at `static/videos/banner.mp4`
  (and a poster image at `static/images/hero-poster.jpg`). Keep it under ~5MB
  and 5-8 seconds so the homepage stays fast.
- **Social links**: open `templates/base.html`, find the WhatsApp/Instagram/YouTube
  `<a href>` tags in the footer, replace with your real profile URLs and WhatsApp number.
- **Site tagline/About text**: edit the `#about` section in `templates/products/home.html`.

---

## 7. Payment Gateway — Razorpay

1. Sign up at https://razorpay.com and complete KYC (can take 1-2 days — start early!)
2. Go to Dashboard -> Settings -> API Keys -> Generate Test Keys first
3. Put them in `.env`:
   ```
   RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
   RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
   ```
4. Test with Razorpay's test card: `4111 1111 1111 1111`, any future expiry, any CVV
5. Once KYC is approved, switch to Live keys (`rzp_live_...`) in production env vars

**COD works immediately with no setup** — launch with COD and switch on Razorpay later.

---

## 8. Deploy to Production

### Option A — Render.com (recommended, simplest)

1. Push this project to a GitHub repo
2. On Render.com -> New -> Web Service -> connect your repo
3. Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
4. Start command: `gunicorn giftstore.wsgi`
5. Add a free PostgreSQL database (Render -> New -> PostgreSQL) — copy its "Internal Database URL"
6. Set Environment Variables on Render:
   ```
   SECRET_KEY=<generate a strong random string>
   DEBUG=False
   ALLOWED_HOSTS=yourdomain.com,your-app.onrender.com
   CSRF_TRUSTED_ORIGINS=https://your-app.onrender.com
   DATABASE_URL=<paste from Render Postgres>
   RAZORPAY_KEY_ID=...
   RAZORPAY_KEY_SECRET=...
   SITE_DOMAIN=your-app.onrender.com
   ```
7. Deploy. Render runs migrations automatically via the `release` line in `Procfile`.
8. Once live, go to **Google Search Console**, verify your site, and submit
   `https://your-domain/sitemap.xml` so Google starts indexing it.
9. (Optional, paid) Buy domain `bestonegifted.com` and connect it under
   Render -> Settings -> Custom Domain.

### Option B — Vercel (serverless — has real limitations, read this first)

Vercel's filesystem is **read-only** except a temporary `/tmp` folder, and every
request may hit a fresh server instance. This means:
- **SQLite will not work** — you must use an external Postgres database
  (e.g. [Neon.tech](https://neon.tech), free, no card required).
- **Uploaded media** (product photos, review photos, personalization uploads)
  will **not persist** between deployments or reliably between requests. For a
  real store, connect an external media host (Cloudinary, AWS S3) — not
  included in this project yet.
- There is no "release phase" like Render — you must run `migrate` yourself
  against the remote database from your own machine.

Steps:
1. Create a free Postgres database at neon.tech, copy its connection string (`DATABASE_URL`).
2. Push this project to GitHub, import it into Vercel.
3. In Vercel -> Project -> Settings -> Environment Variables, add:
   ```
   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
   DEBUG=False
   ALLOWED_HOSTS=your-app.vercel.app,.vercel.app
   CSRF_TRUSTED_ORIGINS=https://your-app.vercel.app
   DATABASE_URL=<your Neon connection string>
   SITE_DOMAIN=your-app.vercel.app
   ```
4. From your **local machine**, point at the same database temporarily and run migrations:
   ```
   $env:DATABASE_URL="<your Neon connection string>"    (PowerShell)
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py loaddata products/fixtures/sample_data.json
   ```
5. Redeploy on Vercel (Deployments tab -> "..." -> Redeploy) so it picks up the new environment variables.
6. `vercel.json` and `build_files.sh` are already included in this project and
   handle static file collection during the Vercel build.

If the site still 500s after this, check Vercel -> Deployments -> latest ->
**Runtime Logs** for the exact Python traceback.

### Final checklist before calling it "live":
- [ ] `DEBUG=False` in production
- [ ] Real `SECRET_KEY` (not the default one)
- [ ] `ALLOWED_HOSTS` includes your real domain
- [ ] PostgreSQL connected (not SQLite)
- [ ] Placed one real test order (COD) end-to-end, checked tracking page works
- [ ] Signed up a test user account, confirmed dashboard + review submission works
- [ ] Submitted sitemap to Google Search Console

---

## Project Structure

```
giftstore/
  giftstore/       -> settings, urls, wsgi
  accounts/         -> signup, login, user dashboard, Profile model
  products/         -> Category, Product, Review models + views + admin + sitemap
  cart/              -> session-based cart logic
  orders/            -> checkout, Order/OrderItem, tracking, Razorpay integration
  templates/         -> all HTML templates (base.html has the green theme + nav)
  static/            -> css/js (put banner.mp4 in static/videos/)
  media/             -> uploaded product & review images
```
