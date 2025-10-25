from django.shortcuts import render
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from .models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct
from .serializers import (
    CropSerializer, CropScheduleSerializer, CropVarietySerializer, 
    CropVarietyDetailSerializer, ActivitySerializer, ProductSerializer, 
    DayRangeSerializer, DayRangeProductSerializer
)


class CropViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for crops
    GET /api/crops/ - List all crops
    GET /api/crops/{id}/ - Get specific crop
    GET /api/crops/{id}/schedule/ - Get complete schedule for a crop
    """
    queryset = Crop.objects.all()
    serializer_class = CropSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'name_marathi']
    ordering_fields = ['name', 'created_at']
    
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """Get complete schedule with all activities and products for a crop"""
        crop = self.get_object()
        serializer = CropScheduleSerializer(crop)
        return Response(serializer.data)


class CropVarietyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for crop varieties
    GET /api/varieties/ - List all varieties
    GET /api/varieties/{id}/ - Get specific variety with schedule
    GET /api/varieties/?crop={crop_id} - Filter by crop
    """
    queryset = CropVariety.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['crop']
    search_fields = ['name', 'name_marathi', 'crop__name']
    ordering_fields = ['name', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CropVarietyDetailSerializer
        return CropVarietySerializer


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for activities
    GET /api/activities/ - List all activities
    GET /api/activities/{id}/ - Get specific activity
    """
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'name_marathi']
    ordering_fields = ['name', 'created_at']


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for products
    GET /api/products/ - List all products
    GET /api/products/{id}/ - Get specific product
    GET /api/products/?product_type={type} - Filter by type
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product_type']
    search_fields = ['name', 'name_marathi', 'product_type']
    ordering_fields = ['name', 'created_at']


class DayRangeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for day ranges
    GET /api/day-ranges/ - List all day ranges
    GET /api/day-ranges/{id}/ - Get specific day range
    GET /api/day-ranges/?crop_variety={id} - Filter by crop variety
    GET /api/day-ranges/?activity={id} - Filter by activity
    """
    queryset = DayRange.objects.all()
    serializer_class = DayRangeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['crop_variety', 'activity', 'crop_variety__crop']
    search_fields = ['info', 'info_marathi', 'activity__name', 'crop_variety__name']
    ordering_fields = ['start_day', 'end_day', 'created_at']


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
        filters = (
            Q(crop_variety__crop__name__icontains=search) |
            Q(crop_variety__name__icontains=search) |
            Q(activity__name__icontains=search) |
            Q(info__icontains=search) |
            Q(products__product__name__icontains=search)
        )

        # Allow numeric searches (for start_day, end_day)
        try:
            search_number = int(search)
            filters |= Q(start_day=search_number) | Q(end_day=search_number)
        except ValueError:
            pass  # if search is not a number, skip this part

        day_ranges = day_ranges.filter(filters).distinct()

    
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