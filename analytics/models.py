from django.db import models
from django.core.validators import MinValueValidator


class Crop(models.Model):
    """Main crop table"""
    name = models.CharField(max_length=200, unique=True)
    name_marathi = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
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
    description = models.TextField(blank=True, null=True)
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
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Activities"


class Product(models.Model):
    """Products used in crop management"""
    name = models.CharField(max_length=200, unique=True)
    name_marathi = models.CharField(max_length=200, blank=True, null=True)
    product_type = models.CharField(max_length=100, blank=True, null=True)  # fertilizer, pesticide, etc.
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class DayRange(models.Model):
    """Day ranges for activities tracked from pruning/plantation"""
    TRACKING_FROM_CHOICES = [
        ('plantation', 'Plantation'),
        ('pruning', 'Pruning'),
    ]

    crop_variety = models.ForeignKey(CropVariety, on_delete=models.CASCADE, related_name='day_ranges')
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='day_ranges')
    tracking_from = models.CharField(max_length=20, choices=TRACKING_FROM_CHOICES)
    start_day = models.IntegerField(validators=[MinValueValidator(0)])
    end_day = models.IntegerField(validators=[MinValueValidator(0)])
    info = models.TextField(help_text="Information about what to do in this activity")
    info_marathi = models.TextField(blank=True, null=True, help_text="Information in Marathi")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.crop_variety} - {self.activity} (Day {self.start_day}-{self.end_day})"

    class Meta:
        ordering = ['crop_variety', 'start_day']
        verbose_name_plural = "Day Ranges"

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

    day_range = models.ForeignKey(DayRange, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='day_range_products')
    dosage = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    dosage_unit = models.CharField(max_length=20, choices=DOSAGE_UNIT_CHOICES)
    application_method = models.CharField(max_length=200, blank=True, null=True)  # spray, drip, etc.
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.dosage} {self.dosage_unit}"

    class Meta:
        ordering = ['day_range', 'product']
        verbose_name_plural = "Day Range Products"