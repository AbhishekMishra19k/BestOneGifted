from .models import WishlistItem


def wishlist(request):
    if request.user.is_authenticated:
        ids = set(WishlistItem.objects.filter(user=request.user).values_list('product_id', flat=True))
        return {'wishlist_product_ids': ids, 'wishlist_count': len(ids)}
    return {'wishlist_product_ids': set(), 'wishlist_count': 0}
