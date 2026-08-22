from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.template.loader import render_to_string
from django_ratelimit.core import is_ratelimited
from products.models import Product
from .cart import Cart

# Fix SECURITY_AUDIT.md #10: hard server-side ceiling on quantity per line,
# regardless of what the client sends (the HTML `max` attribute is cosmetic only).
MAX_QUANTITY_PER_LINE = 20

# Fix SECURITY_AUDIT.md #7: only these image types are accepted for
# personalization uploads, and only up to this size.
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'}
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _validate_photo_upload(photo_file):
    """Returns an error message string if invalid, or None if OK.
    Fixes SECURITY_AUDIT.md #7 — arbitrary file upload."""
    if not photo_file:
        return None
    if photo_file.content_type not in ALLOWED_IMAGE_TYPES:
        return 'Please upload a JPG, PNG, or WEBP image.'
    if photo_file.size > MAX_UPLOAD_SIZE_BYTES:
        return 'Image is too large — please upload a photo under 5MB.'
    try:
        from PIL import Image
        photo_file.seek(0)
        img = Image.open(photo_file)
        img.verify()  # raises if it's not actually a valid image (blocks disguised files)
        photo_file.seek(0)
    except Exception:
        return 'That file doesn\'t look like a valid image. Please try a different photo.'
    return None


@require_POST
def cart_add(request, product_id):
    if is_ratelimited(request, group='cart_add', key='ip', rate='60/m', method='POST', increment=True):
        return JsonResponse({'ok': False, 'message': 'Too many requests, please slow down.'}, status=429)

    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1
    # Fix #10 + part of #4: clamp to a sane range server-side. Final stock
    # check against live inventory still happens again at checkout time.
    quantity = max(1, min(quantity, MAX_QUANTITY_PER_LINE, max(product.stock, 1)))

    custom_text = request.POST.get('custom_text', '').strip()[:200]
    photo_file = request.FILES.get('custom_photo')

    error = _validate_photo_upload(photo_file)
    if error:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'message': error}, status=400)
        messages.error(request, error)
        return redirect(request.POST.get('next', 'cart:cart_detail'))

    if not product.in_stock:
        message = f'Sorry, "{product.name}" is currently out of stock.'
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect(request.POST.get('next', 'cart:cart_detail'))

    cart.add(product=product, quantity=quantity, custom_text=custom_text, photo_file=photo_file)

    if _is_ajax(request):
        drawer_html = render_to_string('cart/_drawer.html', {'cart': cart}, request=request)
        return JsonResponse({'ok': True, 'count': len(cart), 'drawer_html': drawer_html, 'message': f'{product.name} added to cart.'})

    messages.success(request, f'{product.name} added to cart.')
    return redirect(request.POST.get('next', 'cart:cart_detail'))


@require_POST
def cart_remove(request, key):
    cart = Cart(request)
    cart.remove(key)
    if _is_ajax(request):
        drawer_html = render_to_string('cart/_drawer.html', {'cart': cart}, request=request)
        return JsonResponse({'ok': True, 'count': len(cart), 'drawer_html': drawer_html})
    return redirect('cart:cart_detail')


@require_POST
def cart_update(request, key):
    cart = Cart(request)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = min(quantity, MAX_QUANTITY_PER_LINE)  # fix #10 (lower bound handled below)
    if key in cart.cart:
        if quantity <= 0:
            cart.remove(key)
        else:
            cart.cart[key]['quantity'] = quantity
            cart.save()
    if _is_ajax(request):
        drawer_html = render_to_string('cart/_drawer.html', {'cart': cart}, request=request)
        return JsonResponse({'ok': True, 'count': len(cart), 'drawer_html': drawer_html})
    return redirect('cart:cart_detail')


@require_POST
def cart_apply_coupon(request):
    if is_ratelimited(request, group='apply_coupon', key='ip', rate='15/m', method='POST', increment=True):
        messages.error(request, 'Too many attempts. Please wait a moment.')
        return redirect('cart:cart_detail')

    cart = Cart(request)
    code = request.POST.get('code', '').strip()
    from orders.models import Coupon
    try:
        coupon = Coupon.objects.get(code__iexact=code)
        email = request.user.email if request.user.is_authenticated else ''
        if coupon.is_valid(cart.get_subtotal(), user=request.user, email=email):
            cart.apply_coupon(coupon.code)
            messages.success(request, f'Coupon "{coupon.code}" applied!')
        else:
            messages.error(request, 'This coupon is invalid, expired, or you\'ve already used it.')
    except Coupon.DoesNotExist:
        messages.error(request, 'Invalid coupon code.')
    return redirect('cart:cart_detail')


@require_POST
def cart_remove_coupon(request):
    cart = Cart(request)
    cart.remove_coupon()
    messages.info(request, 'Coupon removed.')
    return redirect('cart:cart_detail')


def cart_detail(request):
    cart = Cart(request)
    return render(request, 'cart/cart.html', {'cart': cart})


def cart_drawer(request):
    cart = Cart(request)
    html = render_to_string('cart/_drawer.html', {'cart': cart}, request=request)
    return JsonResponse({'count': len(cart), 'drawer_html': html})
