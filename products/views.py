from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Product, Category, Review, NewsletterSubscriber, ContactMessage
from .models import Product, Category, Review, NewsletterSubscriber, ContactMessage, ProductVariant
from products.models import Product, ProductVariant

PRODUCTS_PER_PAGE = 24


def home(request):
    bestsellers = Product.objects.filter(is_active=True, is_bestseller=True)[:8]
    new_arrivals = Product.objects.filter(is_active=True).order_by('-created_at')[:8]
    categories = Category.objects.all()
    reviews = Review.objects.filter(is_approved=True)[:6]
    gallery = Product.objects.filter(is_active=True, is_bestseller=True)[:6]
    deal_of_day = Product.objects.filter(is_active=True, is_deal_of_day=True).first()
    occasions = [c for c in Product.AUDIENCE_CHOICES if c[0]]
    return render(request, 'products/home.html', {
        'bestsellers': bestsellers,
        'new_arrivals': new_arrivals,
        'categories': categories,
        'reviews': reviews,
        'gallery': gallery,
        'deal_of_day': deal_of_day,
        'occasions': occasions,
    })


def occasion_detail(request, tag):
    products = Product.objects.filter(is_active=True, audience_tag=tag)
    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    label = dict(Product.AUDIENCE_CHOICES).get(tag, tag)
    categories = Category.objects.all()
    return render(request, 'products/product_list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'categories': categories,
        'occasion_label': label,
    })


def product_list(request):
    products = Product.objects.filter(is_active=True)
    query = request.GET.get('q')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    sort = request.GET.get('sort')
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('-created_at')

    # Fix SECURITY_AUDIT.md #12: paginate instead of loading the entire
    # catalog in one response — protects both DB and page-weight at scale.
    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Category.objects.all()
    return render(request, 'products/product_list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'categories': categories,
        'query': query or '',
        'sort': sort or '',
    })


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, is_active=True)
    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))
    categories = Category.objects.all()
    return render(request, 'products/product_list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'category': category,
        'categories': categories,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    related = Product.objects.filter(category=product.category, is_active=True).exclude(id=product.id)[:4]
    product_reviews = product.reviews.filter(is_approved=True)

    variants = product.variants.filter(is_active=True)
    sizes = sorted({v.size for v in variants if v.size})
    colors = sorted({v.color for v in variants if v.color})
    variants_data = [
        {'id': v.id, 'size': v.size, 'color': v.color, 'price': str(v.price), 'stock': v.stock}
        for v in variants
    ]

    if request.method == 'POST' and request.user.is_authenticated:
        rating = request.POST.get('rating', 5)
        comment = request.POST.get('comment', '').strip()
        if comment:
            Review.objects.create(user=request.user, product=product, rating=rating, comment=comment)
            messages.success(request, 'Thanks! Your review has been posted.')
            return redirect('products:product_detail', slug=product.slug)

    return render(request, 'products/product_detail.html', {
        'product': product,
        'related': related,
        'product_reviews': product_reviews,
        'sizes': sizes,
        'colors': colors,
        'variants_json': variants_data,
    })

def quick_view(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    html = render_to_string('products/_quick_view.html', {'product': product}, request=request)
    return JsonResponse({'html': html})


def search_suggest(request):
    query = request.GET.get('q', '').strip()
    results = []
    if len(query) >= 2:
        products = Product.objects.filter(is_active=True).filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )[:6]
        for p in products:
            results.append({
                'name': p.name,
                'price': str(p.price),
                'url': p.get_absolute_url(),
                'image': p.image.url if p.image else '',
            })
    return JsonResponse({'results': results})


@require_POST
def newsletter_subscribe(request):
    # Fix SECURITY_AUDIT.md #8 (partial): honeypot field catches basic bots;
    # a session cooldown stops rapid repeat submissions without needing a
    # separate cache/redis backend (works the same on serverless or a VM).
    if request.POST.get('website'):  # honeypot — real users never fill this hidden field
        return JsonResponse({'ok': True, 'message': 'Subscribed! Watch your inbox for 10% off.'}) if request.headers.get('x-requested-with') == 'XMLHttpRequest' else redirect(request.POST.get('next', 'products:home'))

    last_submit = request.session.get('newsletter_last_submit')
    now_ts = timezone.now().timestamp()
    if last_submit and (now_ts - last_submit) < 10:
        return JsonResponse({'ok': False, 'message': 'Please wait a moment before trying again.'})
    request.session['newsletter_last_submit'] = now_ts

    email = request.POST.get('email', '').strip()
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if not email or '@' not in email:
        if is_ajax:
            return JsonResponse({'ok': False, 'message': 'Please enter a valid email.'})
        messages.error(request, 'Please enter a valid email.')
        return redirect(request.POST.get('next', 'products:home'))

    NewsletterSubscriber.objects.get_or_create(email=email)
    if is_ajax:
        return JsonResponse({'ok': True, 'message': 'Subscribed! Watch your inbox for 10% off.'})
    messages.success(request, 'Subscribed! Watch your inbox for 10% off your first order.')
    return redirect(request.POST.get('next', 'products:home'))


def about(request):
    return render(request, 'products/pages/about.html')


def contact(request):
    if request.method == 'POST':
        # Same lightweight anti-spam pattern as newsletter_subscribe.
        if request.POST.get('website'):
            return redirect('products:contact')

        last_submit = request.session.get('contact_last_submit')
        now_ts = timezone.now().timestamp()
        if last_submit and (now_ts - last_submit) < 15:
            messages.error(request, 'Please wait a moment before sending another message.')
            return redirect('products:contact')
        request.session['contact_last_submit'] = now_ts

        ContactMessage.objects.create(
            name=request.POST.get('name', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            message=request.POST.get('message', ''),
        )
        messages.success(request, 'Thanks for reaching out! We will get back to you within 24 hours.')
        return redirect('products:contact')
    return render(request, 'products/pages/contact.html')


def privacy_policy(request):
    return render(request, 'products/pages/privacy.html')


def refund_policy(request):
    return render(request, 'products/pages/refund.html')


def shipping_policy(request):
    return render(request, 'products/pages/shipping.html')


def terms(request):
    return render(request, 'products/pages/terms.html')
