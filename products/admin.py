from django.contrib import admin
from .models import Category, Product, ProductImage, Review, NewsletterSubscriber, ContactMessage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    """Lets you upload several gallery photos at once on the same page as the
    product itself — click "Add another Product image" for each extra photo,
    or select multiple files at once if your browser supports it, then Save."""
    model = ProductImage
    extra = 3  # shows 3 empty upload slots by default; add more as needed
    fields = ['image', 'order']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'mrp', 'stock', 'is_active', 'is_bestseller', 'is_deal_of_day', 'audience_tag']
    list_filter = ['category', 'is_active', 'is_bestseller', 'is_deal_of_day', 'audience_tag']
    list_editable = ['price', 'stock', 'is_active', 'is_bestseller', 'is_deal_of_day', 'audience_tag']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    inlines = [ProductImageInline]
    # Bulk delete is already available by default in Django admin: tick the
    # checkboxes on the left of the products you want to remove, choose
    # "Delete selected products" from the Action dropdown at the top of the
    # list, then click "Go". No extra code needed for that — it's built in.


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'subscribed_at']
    search_fields = ['email']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'created_at', 'is_resolved']
    list_editable = ['is_resolved']
    search_fields = ['name', 'email', 'message']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'rating', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'rating']
    list_editable = ['is_approved']
    search_fields = ['user__username', 'comment']
    fields = ['user', 'product', 'rating', 'comment', 'photo', 'video_url', 'is_approved']
