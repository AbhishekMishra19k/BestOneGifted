import secrets
from decimal import Decimal

from django.contrib.auth import get_user_model
import time

from django.db import transaction
from django.db.models import F
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django_ratelimit.core import is_ratelimited
from products.models import Product
from cart.cart import Cart
from .models import Order, OrderItem, Coupon


class InsufficientStock(Exception):
    def __init__(self, product_name, available):
        self.product_name = product_name
        self.available = available
        super().__init__(f'Only {available} left for "{product_name}"')


def _create_order_from_cart(request, cart, form_data, idempotency_key):
    """
    Creates Order + OrderItems atomically, validating & decrementing stock
    under row locks. Raises InsufficientStock if any item can't be fulfilled —
    caller must catch this and show the user a friendly message (nothing is
    partially committed, since it's all inside one transaction.atomic() block).
    Fixes SECURITY_AUDIT.md #3 (orphan orders / no rollback) and #4 (overselling).
    """
    # Idempotency: if this exact submission already produced an order, return it
    # instead of creating a duplicate (fixes #5 — double-click / retry safe).
    existing = Order.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing, False

    coupon_obj = None
    discount_amount = Decimal('0')
    if cart.coupon_code:
        try:
            coupon_obj = Coupon.objects.get(code__iexact=cart.coupon_code)
            if coupon_obj.is_valid(cart.get_subtotal(), user=request.user, email=form_data['email']):
                discount_amount = cart.get_coupon_discount()
            else:
                coupon_obj = None
        except Coupon.DoesNotExist:
            coupon_obj = None

    with transaction.atomic():
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            idempotency_key=idempotency_key,
            full_name=form_data['full_name'], email=form_data['email'], phone=form_data['phone'],
            address=form_data['address'], city=form_data['city'], state=form_data['state'],
            pincode=form_data['pincode'], payment_method=Order.PAYMENT_COD,
            coupon=coupon_obj, discount_amount=discount_amount,
            special_instructions=form_data['special_instructions'],
        )

        for item in cart:
            # Row-lock the product so two concurrent checkouts can't both
            # read "stock available" before either one decrements it.
            product = Product.objects.select_for_update().get(id=item['product'].id)

            requested_qty = item['quantity']
            if requested_qty < 1:
                requested_qty = 1
            if product.stock < requested_qty:
                raise InsufficientStock(product.name, product.stock)

            product.stock -= requested_qty
            product.save(update_fields=['stock'])

            # Use the CURRENT live price at checkout, not the price frozen
            # when the item was added to cart (fixes #13 — stale pricing).
            order_item = OrderItem.objects.create(
                order=order, product=product,
                price=product.price, quantity=requested_qty,
                custom_text=item.get('custom_text', ''),
            )
            if item.get('photo_path'):
                order_item.custom_photo.name = item['photo_path']
                order_item.save(update_fields=['custom_photo'])

        if coupon_obj:
            Coupon.objects.filter(pk=coupon_obj.pk).update(times_used=F('times_used') + 1)

    return order, True

def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, 'Your cart is empty.')
        return redirect('products:home')

    # Fix SECURITY_AUDIT.md #8: re-confirm identity if this session has been
    # idle a while before letting it reach checkout (shared/public device risk).
    if request.user.is_authenticated:
        last_active = request.session.get('_last_checkout_reauth', 0)
        if time.time() - last_active > 60 * 60 * 6:  # 6 hours since last confirm
            if request.method == 'POST' and 'reauth_password' in request.POST:
                from django.contrib.auth import authenticate
                user = authenticate(request, username=request.user.username, password=request.POST.get('reauth_password'))
                if user:
                    request.session['_last_checkout_reauth'] = time.time()
                else:
                    messages.error(request, 'Incorrect password. Please try again.')
                    return render(request, 'orders/reauth.html')
            else:
                return render(request, 'orders/reauth.html')

    initial = {}
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        initial = {
            'full_name': request.user.first_name or request.user.username,
            'email': request.user.email,
            'phone': profile.phone if profile else '',
            'address': profile.address if profile else '',
            'city': profile.city if profile else '',
            'state': profile.state if profile else '',
            'pincode': profile.pincode if profile else '',
        }

    if request.method == 'POST' and 'idempotency_key' in request.POST:
        # Fix SECURITY_AUDIT.md #8: throttle checkout submissions per IP —
        # legitimate shoppers never need more than a handful of attempts a
        # minute; this blocks scripted order-spam / stock-exhaustion floods.
        if is_ratelimited(request, group='checkout', key='ip', rate='10/m', method='POST', increment=True):
            messages.error(request, 'Too many checkout attempts. Please wait a minute and try again.')
            return redirect('cart:cart_detail')

        form_data = {
            'full_name': request.POST.get('full_name', '').strip(),
            'email': request.POST.get('email', '').strip(),
            'phone': request.POST.get('phone', '').strip(),
            'address': request.POST.get('address', '').strip(),
            'city': request.POST.get('city', '').strip(),
            'state': request.POST.get('state', '').strip(),
            'pincode': request.POST.get('pincode', '').strip(),
            'special_instructions': request.POST.get('special_instructions', '').strip(),
        }

        # Idempotency key: one hidden form field, generated fresh only on a
        # full page load (see checkout.html). A double-click resubmits the
        # SAME key, so _create_order_from_cart returns the existing order
        # instead of creating a second one (fixes #5).
        idempotency_key = request.POST.get('idempotency_key') or secrets.token_urlsafe(32)

        try:
            order, created = _create_order_from_cart(request, cart, form_data, idempotency_key)
        except InsufficientStock as e:
            messages.error(
                request,
                f'Sorry, only {e.available} unit(s) of "{e.product_name}" are left in stock. '
                f'Please update the quantity in your cart and try again.'
            )
            return redirect('cart:cart_detail')

        cart.clear()
        return redirect('orders:order_success', order_id=order.id, token=order.access_token)

    return render(request, 'orders/checkout.html', {
        'cart': cart,
        'initial': initial,
        'idempotency_key': secrets.token_urlsafe(32),
    })

def order_success(request, order_id, token):
    """
    Fixes SECURITY_AUDIT.md #2 (IDOR/PII leak): this page is no longer
    reachable by guessing/incrementing order_id. A random access_token
    (generated per-order, see Order.save()) must also match.
    """
    order = get_object_or_404(Order, id=order_id, access_token=token)
    return render(request, 'orders/order_success.html', {'order': order})


@login_required
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .order_by('-created_at')
        .prefetch_related('items__product')  # fixes #11 — N+1 queries
    )
    return render(request, 'orders/order_history.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        id=order_id, user=request.user,
    )
    return render(request, 'orders/order_detail.html', {'order': order})
