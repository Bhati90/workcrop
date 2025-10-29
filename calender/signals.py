# signals.py - Comprehensive Audit Logging

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.serializers.json import DjangoJSONEncoder
from .models import (
    Product, Crop, CropVariety, Activity, 
    DayRange, DayRangeProduct, AuditLog
)
import json

# Store original values before save
_original_values = {}


def get_client_ip(request):
    """Extract client IP from request"""
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    return None


def serialize_model_data(instance, exclude_fields=None):
    """
    Convert model instance to dictionary for comparison
    """
    if exclude_fields is None:
        exclude_fields = ['created_at', 'updated_at', 'id']
    
    data = {}
    for field in instance._meta.fields:
        if field.name not in exclude_fields:
            value = getattr(instance, field.name)
            
            # Handle foreign keys
            if hasattr(value, 'pk'):
                data[field.name] = {
                    'id': value.pk,
                    'name': str(value)
                }
            # Handle decimal and other types
            elif value is not None:
                data[field.name] = str(value)
            else:
                data[field.name] = None
    
    return data


def get_changed_fields(old_data, new_data):
    """
    Compare old and new data and return only changed fields
    """
    changes = {}
    
    for key in new_data.keys():
        old_value = old_data.get(key)
        new_value = new_data.get(key)
        
        if old_value != new_value:
            changes[key] = {
                'old': old_value,
                'new': new_value
            }
    
    return changes


# ============================================
# PRE_SAVE: Store original values
# ============================================
@receiver(pre_save, sender=Product)
@receiver(pre_save, sender=Crop)
@receiver(pre_save, sender=CropVariety)
@receiver(pre_save, sender=Activity)
@receiver(pre_save, sender=DayRange)
@receiver(pre_save, sender=DayRangeProduct)
def store_original_values(sender, instance, **kwargs):
    """
    Store original values before update
    """
    if instance.pk:  # Only for updates
        try:
            original = sender.objects.get(pk=instance.pk)
            _original_values[f"{sender.__name__}_{instance.pk}"] = serialize_model_data(original)
        except sender.DoesNotExist:
            pass


# ============================================
# POST_SAVE: Log creates and updates
# ============================================
@receiver(post_save, sender=Product)
def log_product_changes(sender, instance, created, **kwargs):
    model_name = 'product'
    
    if created:
        # Log creation
        AuditLog.objects.create(
            model_name=model_name,
            object_id=instance.id,
            action='create',
            changes={
                'created': serialize_model_data(instance),
                'summary': f'Created product: {instance.name}'
            }
        )
    else:
        # Log update
        key = f"{sender.__name__}_{instance.pk}"
        old_data = _original_values.get(key)
        
        if old_data:
            new_data = serialize_model_data(instance)
            changed_fields = get_changed_fields(old_data, new_data)
            
            if changed_fields:
                AuditLog.objects.create(
                    model_name=model_name,
                    object_id=instance.id,
                    action='update',
                    changes={
                        'updated_fields': changed_fields,
                        'summary': f'Updated product: {instance.name}',
                        'field_count': len(changed_fields)
                    }
                )
            
            # Clean up
            _original_values.pop(key, None)


@receiver(post_save, sender=Crop)
def log_crop_changes(sender, instance, created, **kwargs):
    model_name = 'crop'
    
    if created:
        AuditLog.objects.create(
            model_name=model_name,
            object_id=instance.id,
            action='create',
            changes={
                'created': serialize_model_data(instance),
                'summary': f'Created crop: {instance.name}'
            }
        )
    else:
        key = f"{sender.__name__}_{instance.pk}"
        old_data = _original_values.get(key)
        
        if old_data:
            new_data = serialize_model_data(instance)
            changed_fields = get_changed_fields(old_data, new_data)
            
            if changed_fields:
                AuditLog.objects.create(
                    model_name=model_name,
                    object_id=instance.id,
                    action='update',
                    changes={
                        'updated_fields': changed_fields,
                        'summary': f'Updated crop: {instance.name}',
                        'field_count': len(changed_fields)
                    }
                )
            
            _original_values.pop(key, None)


@receiver(post_save, sender=CropVariety)
def log_variety_changes(sender, instance, created, **kwargs):
    model_name = 'variety'
    
    if created:
        AuditLog.objects.create(
            model_name=model_name,
            object_id=instance.id,
            action='create',
            changes={
                'created': serialize_model_data(instance),
                'summary': f'Created variety: {instance.name} for {instance.crop.name}'
            }
        )
    else:
        key = f"{sender.__name__}_{instance.pk}"
        old_data = _original_values.get(key)
        
        if old_data:
            new_data = serialize_model_data(instance)
            changed_fields = get_changed_fields(old_data, new_data)
            
            if changed_fields:
                AuditLog.objects.create(
                    model_name=model_name,
                    object_id=instance.id,
                    action='update',
                    changes={
                        'updated_fields': changed_fields,
                        'summary': f'Updated variety: {instance.name}',
                        'field_count': len(changed_fields)
                    }
                )
            
            _original_values.pop(key, None)


@receiver(post_save, sender=Activity)
def log_activity_changes(sender, instance, created, **kwargs):
    model_name = 'activity'
    
    if created:
        AuditLog.objects.create(
            model_name=model_name,
            object_id=instance.id,
            action='create',
            changes={
                'created': serialize_model_data(instance),
                'summary': f'Created activity: {instance.name}'
            }
        )
    else:
        key = f"{sender.__name__}_{instance.pk}"
        old_data = _original_values.get(key)
        
        if old_data:
            new_data = serialize_model_data(instance)
            changed_fields = get_changed_fields(old_data, new_data)
            
            if changed_fields:
                AuditLog.objects.create(
                    model_name=model_name,
                    object_id=instance.id,
                    action='update',
                    changes={
                        'updated_fields': changed_fields,
                        'summary': f'Updated activity: {instance.name}',
                        'field_count': len(changed_fields)
                    }
                )
            
            _original_values.pop(key, None)


@receiver(post_save, sender=DayRange)
def log_dayrange_changes(sender, instance, created, **kwargs):
    model_name = 'dayrange'
    
    if created:
        AuditLog.objects.create(
            model_name=model_name,
            object_id=instance.id,
            action='create',
            changes={
                'created': serialize_model_data(instance),
                'summary': f'Created day range: {instance.crop_variety} - {instance.activity} (Day {instance.start_day}-{instance.end_day})'
            }
        )
    else:
        key = f"{sender.__name__}_{instance.pk}"
        old_data = _original_values.get(key)
        
        if old_data:
            new_data = serialize_model_data(instance)
            changed_fields = get_changed_fields(old_data, new_data)
            
            if changed_fields:
                AuditLog.objects.create(
                    model_name=model_name,
                    object_id=instance.id,
                    action='update',
                    changes={
                        'updated_fields': changed_fields,
                        'summary': f'Updated day range: {instance.crop_variety} - {instance.activity}',
                        'field_count': len(changed_fields)
                    }
                )
            
            _original_values.pop(key, None)


@receiver(post_save, sender=DayRangeProduct)
def log_dayrange_product_changes(sender, instance, created, **kwargs):
    model_name = 'dayrange_product'
    
    if created:
        AuditLog.objects.create(
            model_name=model_name,
            object_id=instance.id,
            action='create',
            changes={
                'created': serialize_model_data(instance),
                'summary': f'Added product: {instance.product.name} ({instance.dosage} {instance.dosage_unit}) to day range'
            }
        )
    else:
        key = f"{sender.__name__}_{instance.pk}"
        old_data = _original_values.get(key)
        
        if old_data:
            new_data = serialize_model_data(instance)
            changed_fields = get_changed_fields(old_data, new_data)
            
            if changed_fields:
                AuditLog.objects.create(
                    model_name=model_name,
                    object_id=instance.id,
                    action='update',
                    changes={
                        'updated_fields': changed_fields,
                        'summary': f'Updated day range product: {instance.product.name}',
                        'field_count': len(changed_fields)
                    }
                )
            
            _original_values.pop(key, None)


# ============================================
# POST_DELETE: Log deletions
# ============================================
@receiver(post_delete, sender=Product)
def log_product_deletion(sender, instance, **kwargs):
    AuditLog.objects.create(
        model_name='product',
        object_id=instance.id,
        action='delete',
        changes={
            'deleted': serialize_model_data(instance),
            'summary': f'Deleted product: {instance.name}'
        }
    )


@receiver(post_delete, sender=Crop)
def log_crop_deletion(sender, instance, **kwargs):
    AuditLog.objects.create(
        model_name='crop',
        object_id=instance.id,
        action='delete',
        changes={
            'deleted': serialize_model_data(instance),
            'summary': f'Deleted crop: {instance.name}'
        }
    )


@receiver(post_delete, sender=CropVariety)
def log_variety_deletion(sender, instance, **kwargs):
    AuditLog.objects.create(
        model_name='variety',
        object_id=instance.id,
        action='delete',
        changes={
            'deleted': serialize_model_data(instance),
            'summary': f'Deleted variety: {instance.name}'
        }
    )


@receiver(post_delete, sender=Activity)
def log_activity_deletion(sender, instance, **kwargs):
    AuditLog.objects.create(
        model_name='activity',
        object_id=instance.id,
        action='delete',
        changes={
            'deleted': serialize_model_data(instance),
            'summary': f'Deleted activity: {instance.name}'
        }
    )


@receiver(post_delete, sender=DayRange)
def log_dayrange_deletion(sender, instance, **kwargs):
    AuditLog.objects.create(
        model_name='dayrange',
        object_id=instance.id,
        action='delete',
        changes={
            'deleted': serialize_model_data(instance),
            'summary': f'Deleted day range: {instance.crop_variety} - {instance.activity}'
        }
    )


@receiver(post_delete, sender=DayRangeProduct)
def log_dayrange_product_deletion(sender, instance, **kwargs):
    AuditLog.objects.create(
        model_name='dayrange_product',
        object_id=instance.id,
        action='delete',
        changes={
            'deleted': serialize_model_data(instance),
            'summary': f'Deleted product from day range: {instance.product.name}'
        }
    )