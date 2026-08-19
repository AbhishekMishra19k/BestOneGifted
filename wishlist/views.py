from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from products.models import Product
from .models import WishlistItem


@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    item, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
        in_wishlist = False
    else:
        in_wishlist = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        count = WishlistItem.objects.filter(user=request.user).count()
        return JsonResponse({'in_wishlist': in_wishlist, 'count': count})

    messages.success(request, 'Added to wishlist.' if in_wishlist else 'Removed from wishlist.')
    return redirect(request.POST.get('next') or 'products:home')


@login_required
def wishlist_page(request):
    items = WishlistItem.objects.filter(user=request.user).select_related('product')
    return render(request, 'wishlist/wishlist.html', {'items': items})
