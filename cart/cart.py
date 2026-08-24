from decimal import Decimal
from django.conf import settings
from django.core.files.storage import default_storage
from products.models import Product, ProductVariant


class Cart:
    """Session-based shopping cart. No login required (guest checkout).
    Each line item can carry a custom_text, a custom_photo, and a variant
    (size/color) — each unique combination is its own line item."""

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart
        self.coupon_code = self.session.get('coupon_code')

    def _line_key(self, product_id, variant_id, custom_text, has_photo_path):
        return f"{product_id}::{variant_id or ''}::{hash((custom_text or '', has_photo_path or ''))}"

    def add(self, product, quantity=1, override_quantity=False, custom_text='', photo_file=None, variant=None):
        photo_path = ''
        if photo_file:
            photo_path = default_storage.save(f'personalizations/{photo_file.name}', photo_file)

        variant_id = variant.id if variant else None
        price = variant.price if variant else product.price

        key = self._line_key(product.id, variant_id, custom_text, photo_path)
        if key not in self.cart:
            self.cart[key] = {
                'product_id': product.id,
                'variant_id': variant_id,
                'quantity': 0,
                'price': str(price),
                'custom_text': custom_text or '',
                'photo_path': photo_path,
            }
        if override_quantity:
            self.cart[key]['quantity'] = quantity
        else:
            self.cart[key]['quantity'] += quantity
        self.save()

    def save(self):
        self.session.modified = True

    def remove(self, key):
        if key in self.cart:
            del self.cart[key]
            self.save()

    def apply_coupon(self, code):
        self.session['coupon_code'] = code
        self.coupon_code = code
        self.save()

    def remove_coupon(self):
        self.session.pop('coupon_code', None)
        self.coupon_code = None
        self.save()

    def __iter__(self):
        product_ids = [v['product_id'] for v in self.cart.values()]
        variant_ids = [v['variant_id'] for v in self.cart.values() if v.get('variant_id')]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        variants = {v.id: v for v in ProductVariant.objects.filter(id__in=variant_ids)}
        for key, item in self.cart.items():
            data = item.copy()
            data['key'] = key
            data['product'] = products.get(item['product_id'])
            data['variant'] = variants.get(item.get('variant_id')) if item.get('variant_id') else None
            data['price'] = Decimal(item['price'])
            data['total_price'] = data['price'] * item['quantity']
            if data['product']:
                yield data

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def get_subtotal(self):
        return sum(Decimal(item['price']) * item['quantity'] for item in self.cart.values())

    def get_coupon_discount(self):
        if not self.coupon_code:
            return Decimal('0')
        from orders.models import Coupon
        try:
            coupon = Coupon.objects.get(code__iexact=self.coupon_code)
        except Coupon.DoesNotExist:
            return Decimal('0')
        subtotal = self.get_subtotal()
        if coupon.is_valid(subtotal):
            return Decimal(coupon.calculate_discount(subtotal))
        return Decimal('0')

    def get_total_price(self):
        return max(self.get_subtotal() - self.get_coupon_discount(), Decimal('0'))

    def clear(self):
        del self.session[settings.CART_SESSION_ID]
        self.session.pop('coupon_code', None)
        self.save()