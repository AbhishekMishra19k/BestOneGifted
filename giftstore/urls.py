from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from decouple import config
from products.sitemaps import ProductSitemap, CategorySitemap, StaticViewSitemap

admin.site.site_header = 'BestOneGifted Admin'
admin.site.site_title = 'BestOneGifted Admin'
admin.site.index_title = 'Manage Products, Orders & Reviews'

sitemaps = {
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
}

# Fix SECURITY_AUDIT.md #15: default admin path is publicly known and
# unthrottled-by-obscurity. Set ADMIN_URL in your environment to something
# private (e.g. "staff-portal-x7k2/") before going live. Falls back to the
# default 'admin/' for local development if not set.
ADMIN_URL = config('ADMIN_URL', default='admin/')

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('cart/', include('cart.urls')),
    path('wishlist/', include('wishlist.urls')),
    path('orders/', include('orders.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('', include('products.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
