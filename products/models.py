from django.db import models
from django.urls import reverse
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:category_detail', args=[self.slug])


class Product(models.Model):
    AUDIENCE_CHOICES = [
        ('', '— None —'),
        ('her', 'For Her'),
        ('him', 'For Him'),
        ('couple', 'For Couple'),
        ('newborn', 'For Newborn'),
        ('birthday', 'Birthday'),
        ('anniversary', 'Anniversary'),
    ]
    category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Selling price (Rs.)')
    mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Optional strike-through price')
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_bestseller = models.BooleanField(default=False)
    is_deal_of_day = models.BooleanField(default=False, help_text='Feature in the homepage Deal of the Day banner')
    audience_tag = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, blank=True, help_text='Used for "Shop by Occasion" homepage tiles')
    allow_personalization = models.BooleanField(default=True, help_text='Show custom text + photo upload fields on this product')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:product_detail', args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0


class ProductImage(models.Model):
    """Extra gallery photos for a product (in addition to the main `image`
    field above). Lets admin upload multiple photos per product — angles,
    close-ups, customization examples — shown as a thumbnail strip on the
    product detail page."""
    product = models.ForeignKey(Product, related_name='gallery_images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/gallery/')
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers show first')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'Image for {self.product.name} (#{self.order})'


class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    comment = models.TextField(max_length=500)
    photo = models.ImageField(upload_to='reviews/', blank=True, null=True)
    video_url = models.URLField(blank=True, help_text='Optional: link to a short unboxing/reaction video (YouTube/Instagram)')
    is_approved = models.BooleanField(default=True, help_text='Uncheck to hide a review from the site')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rating}★ by {self.user.username}'


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.created_at:%d %b %Y}'
