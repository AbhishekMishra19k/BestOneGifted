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
    actions = ['mark_as_placed', 'mark_as_packed', 'mark_as_shipped', 'mark_as_delivered', 'mark_as_paid']

    @admin.action(description='Mark selected orders as Packed')
    def mark_as_packed(self, request, queryset):
        updated = queryset.update(status=Order.STATUS_PACKED)
        self.message_user(request, f'{updated} order(s) marked as Packed.')

    @admin.action(description='Mark selected orders as Shipped')
    def mark_as_shipped(self, request, queryset):
        updated = queryset.update(status=Order.STATUS_SHIPPED)
        self.message_user(request, f'{updated} order(s) marked as Shipped.')

    @admin.action(description='Mark selected orders as Delivered')
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status=Order.STATUS_DELIVERED)
        self.message_user(request, f'{updated} order(s) marked as Delivered.')

    @admin.action(description='Mark selected orders as Placed')
    def mark_as_placed(self, request, queryset):
        updated = queryset.update(status=Order.STATUS_PLACED)
        self.message_user(request, f'{updated} order(s) marked as Placed.')

    @admin.action(description='Mark selected orders as Paid')
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(is_paid=True)
        self.message_user(request, f'{updated} order(s) marked as Paid.')