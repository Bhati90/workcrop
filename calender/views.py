from django.shortcuts import render
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from .models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct


def crop_management_dashboard(request):
    """Main dashboard with comprehensive filtering"""
    
    # Get filter parameters
    crop_id = request.GET.get('crop')
    variety_id = request.GET.get('variety')
    activity_id = request.GET.get('activity')
    product_id = request.GET.get('product')
    day_from = request.GET.get('day_from')
    day_to = request.GET.get('day_to')
    search = request.GET.get('search')
    
    # Base queryset with optimized queries
    day_ranges = DayRange.objects.select_related(
        'crop_variety__crop',
        'activity'
    ).prefetch_related(
        Prefetch(
            'products',
            queryset=DayRangeProduct.objects.select_related('product')
        )
    )
    
    # Apply filters
    if crop_id:
        day_ranges = day_ranges.filter(crop_variety__crop_id=crop_id)
    
    if variety_id:
        day_ranges = day_ranges.filter(crop_variety_id=variety_id)
    
    if activity_id:
        day_ranges = day_ranges.filter(activity_id=activity_id)
    
    if product_id:
        day_ranges = day_ranges.filter(products__product_id=product_id).distinct()
    
    if day_from:
        day_ranges = day_ranges.filter(end_day__gte=day_from)
    
    if day_to:
        day_ranges = day_ranges.filter(start_day__lte=day_to)
    
    if search:
        day_ranges = day_ranges.filter(
            Q(crop_variety__crop__name__icontains=search) |
            Q(crop_variety__name__icontains=search) |
            Q(activity__name__icontains=search) |
            Q(info__icontains=search) |
            Q(products__product__name__icontains=search)
        ).distinct()
    
    # Get all filter options
    crops = Crop.objects.all()
    varieties = CropVariety.objects.select_related('crop').all()
    activities = Activity.objects.all()
    products = Product.objects.all()
    
    # Filter varieties based on selected crop
    if crop_id:
        varieties = varieties.filter(crop_id=crop_id)
    
    context = {
        'day_ranges': day_ranges,
        'crops': crops,
        'varieties': varieties,
        'activities': activities,
        'products': products,
        'selected_crop': crop_id,
        'selected_variety': variety_id,
        'selected_activity': activity_id,
        'selected_product': product_id,
        'day_from': day_from,
        'day_to': day_to,
        'search': search,
    }
    
    return render(request, 'dashboard.html', context)


def get_varieties_by_crop(request):
    """AJAX endpoint to get varieties for a selected crop"""
    crop_id = request.GET.get('crop_id')
    varieties = CropVariety.objects.filter(crop_id=crop_id).values('id', 'name')
    return JsonResponse(list(varieties), safe=False)