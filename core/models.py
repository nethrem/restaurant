from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Restaurant(models.Model):
    # Basic
    name = models.CharField(max_length=255, verbose_name="Restaurant Name")
    description = models.TextField(blank=True, verbose_name="Restaurant Description")
    address = models.CharField(max_length=500, blank=True, verbose_name="Restaurant Address")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Restaurant Phone")
    cover_image = models.ImageField(upload_to='restaurant_covers/', blank=True, null=True, verbose_name="Cover Image")
    # Owner
    owner_name = models.CharField(max_length=255, verbose_name="Owner Name")
    owner_email = models.EmailField(verbose_name="Owner Email")
    owner_phone = models.CharField(max_length=20, verbose_name="Owner Phone")
    owner_user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='restaurant', editable=False
    )
    # Order settings
    minimum_order = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Minimum Order ($)")
    avg_prepare_time = models.PositiveIntegerField(default=30, verbose_name="Average Prepare Time (minutes)")
    time_slot_interval = models.PositiveIntegerField(default=15, verbose_name="Time Slot Interval (minutes)")
    # Slug for public URL
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name="URL Slug")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'restaurant'
            slug = base
            counter = 1
            while Restaurant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self): return self.name
    class Meta:
        verbose_name = "Restaurant"
        verbose_name_plural = "Restaurants"


class DeliveryArea(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='delivery_areas')
    name = models.CharField(max_length=255)
    delivery_cost = models.DecimalField(max_digits=8, decimal_places=2)
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.name} — {self.restaurant.name}"
    class Meta: ordering = ['name']


class MenuCategory(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_categories')
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.name} — {self.restaurant.name}"
    class Meta: ordering = ['order', 'name']


class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="VAT % included in price")
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    enable_variants = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.name} ({self.category.name})"
    class Meta: ordering = ['name']


class MenuItemExtra(models.Model):
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='extras')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.name} (+${self.price})"
    class Meta: ordering = ['name']


class Order(models.Model):
    STATUS_NEW = 'new'
    STATUS_ACCEPTED = 'accepted'
    STATUS_DELIVERED = 'delivered'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='orders')
    order_number = models.PositiveIntegerField()
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=30)
    customer_email = models.EmailField(blank=True)
    delivery_area = models.ForeignKey(DeliveryArea, on_delete=models.SET_NULL, null=True, blank=True)
    delivery_address = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self): return f"#{self.order_number} — {self.restaurant.name}"

    class Meta:
        ordering = ['-created_at']
        unique_together = [('restaurant', 'order_number')]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)       # snapshot of name at order time
    price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    extras = models.TextField(blank=True)          # comma-separated extra names

    def line_total(self):
        return self.price * self.quantity

    def vat_amount(self):
        if not self.vat_percentage:
            return 0
        return self.line_total() - self.line_total() / (1 + self.vat_percentage / 100)

    def __str__(self): return f"{self.quantity}x {self.name}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    changed_by = models.CharField(max_length=255, default='Restaurant')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.order.order_number} → {self.status}"

    class Meta:
        ordering = ['created_at']
