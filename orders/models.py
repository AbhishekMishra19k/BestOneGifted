import secrets
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from products.models import Product


class Coupon(models.Model):
    code = models.CharField(max_length=30, unique=True)
    discount_percent = models.PositiveIntegerField(help_text='e.g. 10 for 10% off', default=0)
    flat_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Flat Rs. off instead of percent (optional)')
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text='Leave blank for unlimited total uses across all customers')
    max_uses_per_user = models.PositiveIntegerField(default=1, help_text='How many times ONE customer/email may use this code')
    times_used = models.PositiveIntegerField(default=0, editable=False)

    def __str__(self):
        return self.code

    def is_valid(self, order_total, user=None, email=''):
        if not self.active:
            return False
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if order_total < self.min_order_value:
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        if user is not None and user.is_authenticated:
            used_by_user = Order.objects.filter(coupon=self, user=user).exclude(status=Order.STATUS_CANCELLED).count()
            if used_by_user >= self.max_uses_per_user:
                return False
        elif email:
            used_by_email = Order.objects.filter(coupon=self, email__iexact=email).exclude(status=Order.STATUS_CANCELLED).count()
            if used_by_email >= self.max_uses_per_user:
                return False
        return True

    def calculate_discount(self, order_total):
        if self.flat_discount:
            return min(self.flat_discount, order_total)
        if self.discount_percent:
            return (order_total * self.discount_percent) / 100
        return 0


class Order(models.Model):
    PAYMENT_COD = 'cod'
    PAYMENT_CHOICES = [
        (PAYMENT_COD, 'Cash on Delivery'),
    ]

    STATUS_PLACED = 'placed'
    STATUS_PACKED = 'packed'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PLACED, 'Placed'),
        (STATUS_PACKED, 'Packed'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    STATUS_STEPS = [STATUS_PLACED, STATUS_PACKED, STATUS_SHIPPED, STATUS_DELIVERED]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')

    # Security: random, unguessable token for guest order-confirmation access (fixes IDOR — see SECURITY_AUDIT.md #2)
    access_token = models.CharField(max_length=64, unique=True, editable=False, blank=True)
    # Security: prevents duplicate orders from double-clicks / retried requests (fixes #5)
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)

    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_instructions = models.TextField(blank=True, help_text='Gifting notes / personalization instructions from customer')

    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=PAYMENT_COD)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PLACED)
    is_paid = models.BooleanField(default=False, help_text='Tick once payment/COD amount is collected')
    whatsapp_confirmed = models.BooleanField(default=False, help_text='Customer confirmed this order via WhatsApp')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Order #{self.id} - {self.full_name}'

    def get_total_cost(self):
        subtotal = sum(item.get_cost() for item in self.items.all())
        return max(subtotal - self.discount_amount, 0)

    def get_subtotal(self):
        return sum(item.get_cost() for item in self.items.all())

    @property
    def delivery_min_date(self):
        return self.created_at + timedelta(days=5)

    @property
    def delivery_max_date(self):
        return self.created_at + timedelta(days=8)

    @property
    def status_step_index(self):
        if self.status in self.STATUS_STEPS:
            return self.STATUS_STEPS.index(self.status)
        return -1

    def whatsapp_confirm_link(self):
        """Build a wa.me deep link pre-filled with this order's summary, so the
        customer can confirm/finalize the order directly with the business."""
        import urllib.parse
        from django.conf import settings
        business_number = getattr(settings, 'WHATSAPP_BUSINESS_NUMBER', '919201461413')
        lines = [f"Hi! I've placed Order #{self.id} on BestOneGifted."]
        for item in self.items.all():
            name = item.product.name if item.product else 'Item'
            line = f"- {name} x{item.quantity}"
            if item.custom_text:
                line += f' ("{item.custom_text}")'
            lines.append(line)
        lines.append(f"Total: Rs. {self.get_total_cost()}")
        lines.append(f"Delivery to: {self.city}, {self.pincode}")
        lines.append("Please confirm my order. Thank you!")
        message = "\n".join(lines)
        return f"https://wa.me/{business_number}?text={urllib.parse.quote(message)}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    custom_text = models.CharField(max_length=200, blank=True, help_text='Custom name/text requested by customer')
    custom_photo = models.ImageField(upload_to='personalizations/', blank=True, null=True)

    def __str__(self):
        return str(self.id)

    def get_cost(self):
        return self.price * self.quantity
