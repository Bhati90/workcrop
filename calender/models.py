from django.db import models
from django.core.validators import MinValueValidator


class Crop(models.Model):
    """Main crop table"""
    name = models.CharField(max_length=200, unique=True)
    name_marathi = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class CropVariety(models.Model):
    """Crop variety/cultivar table"""
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='varieties')
    name = models.CharField(max_length=200)
    name_marathi = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.crop.name} - {self.name}"

    class Meta:
        ordering = ['crop', 'name']
        unique_together = ['crop', 'name']
        verbose_name_plural = "Crop Varieties"


class Activity(models.Model):
    """Activity types for crop management"""
    name = models.CharField(max_length=200, unique=True)
    name_marathi = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Activities"


from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Product(models.Model):
    """Products used in crop management"""
    # Basic Information
    name = models.CharField(max_length=200, unique=True)
    name_marathi = models.CharField(max_length=200, blank=True, null=True)
    product_type = models.CharField(max_length=100, blank=True, null=True)  # fertilizer, pesticide, etc.
    
    # Product Details
    # description = models.TextField(blank=True, null=True, help_text="Product description")
    # description_marathi = models.TextField(blank=True, null=True, help_text="Product description in Marathi")
    
    # Pricing Information
    mrp = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True, 
        null=True,
        help_text="Maximum Retail Price"
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True, 
        null=True,
        help_text="Selling Price"
    )
    
    # Size/Quantity Information
    SIZE_UNIT_CHOICES = [
        ('gm', 'Gram'),
        ('kg', 'Kilogram'),
        ('ml', 'Milliliter'),
        ('liter', 'Liter'),
        ('piece', 'Piece'),
        ('pack', 'Pack'),
    ]
    
    size = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True, 
        null=True,
        help_text="Product size/quantity"
    )
    size_unit = models.CharField(
        max_length=20, 
        choices=SIZE_UNIT_CHOICES,
        blank=True, 
        null=True,
        help_text="Unit of measurement for size"
    )
    
    # Image (S3 URL or file path)
    
    # Image (S3 URL)
    image = models.CharField(max_length=500, blank=True, null=True)
    
    # Alternative: If you want to use FileField/ImageField with S3 storage
    # image = models.ImageField(upload_to='products/', blank=True, null=True)
    
    # Stock Information (Optional)
    # in_stock = models.BooleanField(default=True, help_text="Is product available in stock")
    
    # Manufacturer Information (Optional)
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    manufacturer_marathi = models.CharField(max_length=200, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.size and self.size_unit:
            return f"{self.name} ({self.size} {self.size_unit})"
        return self.name
    
    
    @property
    def display_size(self):
        """Return formatted size with unit"""
        if self.size and self.size_unit:
            return f"{self.size} {self.get_size_unit_display()}"
        return "N/A"

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['product_type']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['name', 'product_type']),
            models.Index(fields=['manufacturer']),
        ]
        ordering = ['-created_at']



class AuditLog(models.Model):
    """Audit log for tracking all changes"""
    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
    ]
    
    MODEL_CHOICES = [
        ('product', 'Product'),
        ('crop', 'Crop'),
        ('variety', 'Crop Variety'),
        ('activity', 'Activity'),
        ('dayrange', 'Day Range'),
        ('dayrange_product', 'Day Range Product'),  # ← ADD THIS LINE
    ]
    
    model_name = models.CharField(max_length=50, choices=MODEL_CHOICES)
    object_id = models.IntegerField()
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    changes = models.JSONField(default=dict)  # Store what changed
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_email = models.EmailField(blank=True, null=True)  # ← ADD THIS for tracking who made changes
    
    def __str__(self):
        return f"{self.get_action_display()} {self.get_model_name_display()} #{self.object_id} at {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['-timestamp']),
        ]


class DayRange(models.Model):
    """Day ranges for activities tracked from pruning/plantation"""
    TRACKING_FROM_CHOICES = [
        ('plantation', 'Plantation'),
        ('pruning', 'Pruning'),
    ]

    crop_variety = models.ForeignKey(CropVariety, on_delete=models.CASCADE, related_name='day_ranges', db_index=True)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='day_ranges', db_index=True)
    start_day = models.IntegerField(db_index=True)
    end_day = models.IntegerField(db_index=True)
    info = models.TextField(help_text="Information about what to do in this activity")
    info_marathi = models.TextField(blank=True, null=True, help_text="Information in Marathi")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.crop_variety} - {self.activity} (Day {self.start_day}-{self.end_day})"

    class Meta:
        indexes = [
            models.Index(fields=['crop_variety', 'activity']),  # ✅ Composite index
            models.Index(fields=['start_day', 'end_day']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_day > self.end_day:
            raise ValidationError("Start day cannot be greater than end day")


class DayRangeProduct(models.Model):
    """Products required for a specific day range activity with dosage"""
    DOSAGE_UNIT_CHOICES = [
        ('gm/acre', 'Gram per Acre'),
        ('kg/acre', 'Kilogram per Acre'),
        ('ml/acre', 'Milliliter per Acre'),
        ('liter/acre', 'Liter per Acre'),
        ('gm/liter', 'Gram per Liter'),
        ('ml/liter', 'Milliliter per Liter'),
        ('gm/plant', 'Gram per Plant'),
        ('ml/plant', 'Milliliter per Plant'),
    ]

    day_range = models.ForeignKey(DayRange, on_delete=models.CASCADE, related_name='products', db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='day_range_products', db_index=True)
    dosage = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    dosage_unit = models.CharField(max_length=20, choices=DOSAGE_UNIT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.dosage} {self.dosage_unit}"

    class Meta:
        ordering = ['day_range', 'product']
        verbose_name_plural = "Day Range Products"


