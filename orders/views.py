import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from cart.cart import Cart
from .models import Order, OrderItem

try:
    import razorpay
except ImportError:
    razorpay = None


def _get_razorpay_client():
    if razorpay and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    return None


def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, 'Your cart is empty.')
        return redirect('products:home')

    razorpay_enabled = bool(_get_razorpay_client())

    # Auto-fill from saved profile if logged in
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
        full_name = request.POST.get('full_name')
        email = request.POST.get('email', '')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        city = request.POST.get('city')
        state = request.POST.get('state')
        pincode = request.POST.get('pincode')
        payment_method = request.POST.get('payment_method', Order.PAYMENT_COD)
        special_instructions = request.POST.get('special_instructions', '').strip()

        from .models import Coupon
        coupon_obj = None
        discount_amount = 0
        if cart.coupon_code:
            try:
                coupon_obj = Coupon.objects.get(code__iexact=cart.coupon_code)
                discount_amount = cart.get_coupon_discount()
            except Coupon.DoesNotExist:
                coupon_obj = None

        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            full_name=full_name, email=email, phone=phone, address=address,
            city=city, state=state, pincode=pincode, payment_method=payment_method,
            coupon=coupon_obj, discount_amount=discount_amount,
            special_instructions=special_instructions,
        )
        for item in cart:
            order_item = OrderItem.objects.create(
                order=order, product=item['product'],
                price=item['price'], quantity=item['quantity'],
                custom_text=item.get('custom_text', ''),
            )
            if item.get('photo_path'):
                order_item.custom_photo.name = item['photo_path']
                order_item.save()

        if payment_method == Order.PAYMENT_ONLINE and razorpay_enabled:
            client = _get_razorpay_client()
            amount_paise = int(order.get_total_cost() * 100)
            razorpay_order = client.order.create({
                'amount': amount_paise,
                'currency': 'INR',
                'payment_capture': 1,
            })
            order.razorpay_order_id = razorpay_order['id']
            order.save()
            return render(request, 'orders/razorpay_payment.html', {
                'order': order,
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount_paise': amount_paise,
            })
        else:
            cart.clear()
            return redirect('orders:order_success', order_id=order.id)

    return render(request, 'orders/checkout.html', {
        'cart': cart,
        'razorpay_enabled': razorpay_enabled,
        'initial': initial,
    })


@csrf_exempt
def payment_verify(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)

    data = json.loads(request.body)
    order_id = data.get('order_id')
    order = get_object_or_404(Order, id=order_id)

    client = _get_razorpay_client()
    if not client:
        return JsonResponse({'status': 'error', 'message': 'Payment gateway not configured'}, status=400)

    params = {
        'razorpay_order_id': data.get('razorpay_order_id'),
        'razorpay_payment_id': data.get('razorpay_payment_id'),
        'razorpay_signature': data.get('razorpay_signature'),
    }
    try:
        client.utility.verify_payment_signature(params)
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({'status': 'error', 'message': 'Signature verification failed'}, status=400)

    order.razorpay_payment_id = params['razorpay_payment_id']
    order.razorpay_signature = params['razorpay_signature']
    order.is_paid = True
    order.save()

    cart = Cart(request)
    cart.clear()

    return JsonResponse({'status': 'ok', 'redirect_url': f'/orders/success/{order.id}/'})


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'orders/order_success.html', {'order': order})


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/order_history.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})
