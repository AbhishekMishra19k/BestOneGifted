import hashlib
import hmac
import json
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django_ratelimit.core import is_ratelimited
from products.models import Product
from cart.cart import Cart
from .models import Order, OrderItem, Coupon

try:
    import razorpay
except ImportError:
    razorpay = None


class InsufficientStock(Exception):
    def __init__(self, product_name, available):
        self.product_name = product_name
        self.available = available
        super().__init__(f'Only {available} left for "{product_name}"')


def _get_razorpay_client():
    if razorpay and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    return None


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
            pincode=form_data['pincode'], payment_method=form_data['payment_method'],
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

    razorpay_enabled = bool(_get_razorpay_client())

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

    if request.method == 'POST':
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
            'payment_method': request.POST.get('payment_method', Order.PAYMENT_COD),
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

        if form_data['payment_method'] == Order.PAYMENT_ONLINE and razorpay_enabled:
            client = _get_razorpay_client()
            if created and not order.razorpay_order_id:
                amount_paise = int(order.get_total_cost() * 100)
                razorpay_order = client.order.create({
                    'amount': amount_paise,
                    'currency': 'INR',
                    'payment_capture': 1,
                    # Tie the Razorpay order back to OUR order id so payment_verify()
                    # can never be tricked into confirming the wrong order (fixes #1).
                    'notes': {'internal_order_id': str(order.id)},
                })
                order.razorpay_order_id = razorpay_order['id']
                order.save(update_fields=['razorpay_order_id'])
            amount_paise = int(order.get_total_cost() * 100)
            return render(request, 'orders/razorpay_payment.html', {
                'order': order,
                'razorpay_order_id': order.razorpay_order_id,
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount_paise': amount_paise,
            })
        else:
            cart.clear()
            return redirect('orders:order_success', order_id=order.id, token=order.access_token)

    return render(request, 'orders/checkout.html', {
        'cart': cart,
        'razorpay_enabled': razorpay_enabled,
        'initial': initial,
        'idempotency_key': secrets.token_urlsafe(32),
    })


@csrf_exempt
def payment_verify(request):
    """
    Verifies a client-relayed Razorpay payment confirmation.
    Fixes SECURITY_AUDIT.md #1: the razorpay_order_id in the request is now
    cross-checked against the ONE internal Order it was created for, and the
    payment is re-fetched server-side from Razorpay to confirm the amount and
    capture status, instead of trusting the client's word for it.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)

    if is_ratelimited(request, group='payment_verify', key='ip', rate='20/m', method='POST', increment=True):
        return JsonResponse({'status': 'error', 'message': 'Too many requests'}, status=429)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Malformed request'}, status=400)

    order_id = data.get('order_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    order = get_object_or_404(Order, id=order_id)

    client = _get_razorpay_client()
    if not client:
        return JsonResponse({'status': 'error', 'message': 'Payment gateway not configured'}, status=400)

    # --- Fix #1, step 1: the Razorpay order referenced MUST be the one we
    # created for THIS order. Without this check, a signature that is valid
    # for a different (e.g. cheaper) order could be replayed here. ---
    if not order.razorpay_order_id or order.razorpay_order_id != razorpay_order_id:
        return JsonResponse({'status': 'error', 'message': 'Order mismatch'}, status=400)

    if order.is_paid:
        # Already confirmed (e.g. by the webhook) — idempotent success response.
        return JsonResponse({'status': 'ok', 'redirect_url': f'/orders/success/{order.id}/{order.access_token}/'})

    params = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature,
    }
    try:
        client.utility.verify_payment_signature(params)
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({'status': 'error', 'message': 'Signature verification failed'}, status=400)

    # --- Fix #1, step 2: don't just trust the signature math — re-fetch the
    # payment from Razorpay's servers and confirm it was actually captured
    # for the expected amount before marking the order paid. ---
    try:
        payment = client.payment.fetch(razorpay_payment_id)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Could not verify payment with Razorpay'}, status=400)

    expected_paise = int(order.get_total_cost() * 100)
    if payment.get('status') != 'captured' or int(payment.get('amount', 0)) != expected_paise:
        return JsonResponse({'status': 'error', 'message': 'Payment amount/status mismatch'}, status=400)

    order.razorpay_payment_id = razorpay_payment_id
    order.razorpay_signature = razorpay_signature
    order.is_paid = True
    order.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'is_paid'])

    cart = Cart(request)
    cart.clear()

    return JsonResponse({'status': 'ok', 'redirect_url': f'/orders/success/{order.id}/{order.access_token}/'})


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """
    Server-to-server Razorpay webhook. Fixes SECURITY_AUDIT.md #6: payment
    confirmation no longer depends on the customer's browser staying open
    and calling payment_verify() — Razorpay calls this directly the moment
    a payment is captured, even if the client-side JS never fires.

    Set this URL in your Razorpay Dashboard -> Settings -> Webhooks:
        https://yourdomain.com/orders/razorpay-webhook/
    Subscribe to the 'payment.captured' event, and set RAZORPAY_WEBHOOK_SECRET
    in your environment to the same secret you configure there.
    """
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return HttpResponse(status=503)

    signature = request.headers.get('X-Razorpay-Signature', '')
    body = request.body

    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        return HttpResponseForbidden('Invalid webhook signature')

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    if payload.get('event') == 'payment.captured':
        payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        razorpay_order_id = payment_entity.get('order_id')
        razorpay_payment_id = payment_entity.get('id')
        amount = payment_entity.get('amount')

        try:
            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
        except Order.DoesNotExist:
            return HttpResponse(status=200)  # unknown order, nothing to do, but ack so Razorpay stops retrying

        expected_paise = int(order.get_total_cost() * 100)
        if amount == expected_paise and not order.is_paid:
            order.razorpay_payment_id = razorpay_payment_id
            order.is_paid = True
            order.save(update_fields=['razorpay_payment_id', 'is_paid'])

    return HttpResponse(status=200)


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
