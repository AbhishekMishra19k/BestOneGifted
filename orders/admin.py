from django.contrib import admin
from .models import Order, OrderItem, Coupon


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0
    fields = ['product', 'quantity', 'price', 'custom_text', 'custom_photo']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_percent', 'flat_discount', 'min_order_value', 'active', 'valid_to']
    list_editable = ['active']
    search_fields = ['code']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'phone', 'city', 'payment_method', 'status', 'is_paid', 'whatsapp_confirmed', 'discount_amount', 'created_at']
    list_filter = ['status', 'is_paid', 'whatsapp_confirmed', 'created_at']
    list_editable = ['status', 'is_paid', 'whatsapp_confirmed']
    search_fields = ['full_name', 'phone', 'email']
    inlines = [OrderItemInline]
