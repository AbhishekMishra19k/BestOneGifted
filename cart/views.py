from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.template.loader import render_to_string
from products.models import Product
from .cart import Cart


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    custom_text = request.POST.get('custom_text', '').strip()
    photo_file = request.FILES.get('custom_photo')

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
    quantity = int(request.POST.get('quantity', 1))
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
    cart = Cart(request)
    code = request.POST.get('code', '').strip()
    from orders.models import Coupon
    try:
        coupon = Coupon.objects.get(code__iexact=code)
        if coupon.is_valid(cart.get_subtotal()):
            cart.apply_coupon(coupon.code)
            messages.success(request, f'Coupon "{coupon.code}" applied!')
        else:
            messages.error(request, 'This coupon is not valid for your order.')
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
