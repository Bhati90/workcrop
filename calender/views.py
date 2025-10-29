# views.py - OPTIMIZED VERSION

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Prefetch, Q
from django.core.paginator import Paginator
from .models import Product, Crop, CropVariety, Activity, DayRange, DayRangeProduct, AuditLog
from .serializers import (
    ProductListSerializer, 
    ProductDetailSerializer,
    CropSerializer,
    CropVarietySerializer,
    ActivitySerializer,
    DayRangeSerializer,
    DayRangeProductSerializer,
    AuditLogSerializer
)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from .utils.s3_uploads import upload_image_to_s3  # Import the upload function

class ImageUploadAPIView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, format=None):
        image_file = request.FILES.get('file')
        if not image_file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            s3_key = upload_image_to_s3(image_file)
            return Response({'key': s3_key})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================
# SOLUTION 6: Optimized ProductViewSet
# ============================================
class ProductViewSet(viewsets.ModelViewSet):
    """
    Optimized product viewset with:
    - Server-side search/filtering
    - Selective field loading
    - Efficient queryset
    """
    queryset = Product.objects.all()
    
    def get_serializer_class(self):
        # Use lightweight serializer for list, full for detail/create/update
        if self.action == 'list':
            return ProductListSerializer  # No presigned URLs
        return ProductDetailSerializer
    
    def get_queryset(self):
        """
        Optimized queryset with:
        - Server-side filtering
        - Only select needed fields
        - Proper indexing assumed
        """
        queryset = Product.objects.all()
        
        # Server-side search
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(name_marathi__icontains=search) |
                Q(product_type__icontains=search)
            )
        
        # Filter by product type
        product_type = self.request.query_params.get('product_type', None)
        if product_type:
            queryset = queryset.filter(product_type=product_type)
        
        # Order by newest first
        queryset = queryset.order_by('-created_at')
        
        # For list view, only select necessary fields
        if self.action == 'list':
            queryset = queryset.only(
                'id', 'name', 'name_marathi', 'product_type',
                'mrp', 'price', 'size', 'size_unit', 'image',
                'created_at', 'updated_at'
            )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get audit history for specific product"""
        logs = AuditLog.objects.filter(
            model_name='product',
            object_id=pk
        ).order_by('-timestamp')[:50]  # Limit to last 50 entries
        
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)


# ============================================
# SOLUTION 7: Read-Only Optimized ViewSet for Frontend
# ============================================
class ProductReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    
    def get_queryset(self):
        queryset = Product.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """Override list to add cache headers"""
        response = super().list(request, *args, **kwargs)
        
        # Add cache headers (5 minutes)
        response['Cache-Control'] = 'public, max-age=300'
        
        return response


# ============================================
# SOLUTION 8: Optimized Crop ViewSets with Prefetching
# ============================================
class CropViewSet(viewsets.ModelViewSet):
    serializer_class = CropSerializer
    
    def get_queryset(self):
        """Prefetch related data to avoid N+1 queries"""
        return Crop.objects.prefetch_related('varieties').all()


class CropVarietyViewSet(viewsets.ModelViewSet):
    serializer_class = CropVarietySerializer
    
    def get_queryset(self):
        queryset = CropVariety.objects.select_related('crop')
        
        crop_id = self.request.query_params.get('crop', None)
        if crop_id:
            queryset = queryset.filter(crop_id=crop_id)
        
        return queryset


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer


class DayRangeViewSet(viewsets.ModelViewSet):
    serializer_class = DayRangeSerializer
    
    def get_queryset(self):
        """Prefetch activity and products to avoid N+1"""
        queryset = DayRange.objects.select_related('activity').prefetch_related(
            Prefetch(
                'products',
                queryset=DayRangeProduct.objects.select_related('product')
            )
        )
        
        variety_id = self.request.query_params.get('variety', None)
        if variety_id:
            queryset = queryset.filter(crop_variety_id=variety_id)
        
        return queryset


class DayRangeProductViewSet(viewsets.ModelViewSet):
    serializer_class = DayRangeProductSerializer
    
    def get_queryset(self):
        """Optimize with select_related"""
        return DayRangeProduct.objects.select_related(
            'day_range', 
            'product'
        ).all()


# ============================================
# SOLUTION 9: Optimized Utility Functions
# ============================================
def get_varieties_by_crop(request):
    """Optimized variety lookup"""
    crop_id = request.GET.get('crop_id')
    if not crop_id:
        return Response({'error': 'crop_id required'}, status=400)
    
    varieties = CropVariety.objects.filter(crop_id=crop_id).only(
        'id', 'name', 'name_marathi'
    )
    
    serializer = CropVarietySerializer(varieties, many=True)
    return Response(serializer.data)


def get_activities_by_variety(request):
    """Optimized activity lookup"""
    variety_id = request.GET.get('variety_id')
    if not variety_id:
        return Response({'error': 'variety_id required'}, status=400)
    
    day_ranges = DayRange.objects.filter(
        crop_variety_id=variety_id
    ).select_related('activity').only(
        'id', 'activity__id', 'activity__name', 'activity__name_marathi'
    )
    
    activities = [dr.activity for dr in day_ranges if dr.activity]
    serializer = ActivitySerializer(activities, many=True)
    return Response(serializer.data)


def get_products_by_filters(request):
    """Optimized product filtering"""
    queryset = Product.objects.all()
    
    # Apply filters
    product_type = request.GET.get('product_type')
    if product_type:
        queryset = queryset.filter(product_type=product_type)
    
    search = request.GET.get('search')
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | 
            Q(name_marathi__icontains=search)
        )
    
    # Limit fields
    queryset = queryset.only('id', 'name', 'name_marathi', 'product_type')
    
    serializer = ProductListSerializer(queryset, many=True)
    return Response(serializer.data)
from django.shortcuts import render


def add(request):
    return render(request, 'add.html')


from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend



class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Enhanced API endpoint for audit logs with filtering
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['model_name', 'action', 'object_id']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']  # Default ordering
    search_fields = ['changes', 'user_email', 'ip_address']
    
    def get_queryset(self):
        queryset = AuditLog.objects.all()
        
        # Filter by model
        model_name = self.request.query_params.get('model', None)
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        
        # Filter by object_id
        object_id = self.request.query_params.get('object_id', None)
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        
        # Filter by action
        action = self.request.query_params.get('action', None)
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        
        end_date = self.request.query_params.get('end_date', None)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Filter by user
        user_email = self.request.query_params.get('user_email', None)
        if user_email:
            queryset = queryset.filter(user_email=user_email)
        
        return queryset.select_related().order_by('-timestamp')


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
            pass

        day_ranges = day_ranges.filter(filters).distinct()

    day_ranges = day_ranges.order_by('crop_variety__crop__name', 'start_day')
    
    # Get all filter options
    crops = Crop.objects.all()
    varieties = CropVariety.objects.select_related('crop').all()
    
    # Filter varieties based on selected crop
    if crop_id:
        varieties = varieties.filter(crop_id=crop_id)
    
    # Get activities based on selected variety
    # Only show activities that exist in DayRange for the selected variety
    if variety_id:
        activities = Activity.objects.filter(
            day_ranges__crop_variety_id=variety_id
        ).distinct()
    else:
        activities = Activity.objects.all()
    
    # Get products based on selected variety and activity
    # Only show products that exist in DayRange for the selected variety/activity
    if variety_id and activity_id:
        # Both variety and activity selected - most specific
        products = Product.objects.filter(
            day_range_products__day_range__crop_variety_id=variety_id,
            day_range_products__day_range__activity_id=activity_id
        ).distinct()
    elif variety_id:
        # Only variety selected
        products = Product.objects.filter(
            day_range_products__day_range__crop_variety_id=variety_id
        ).distinct()
    elif activity_id:
        # Only activity selected
        products = Product.objects.filter(
            day_range_products__day_range__activity_id=activity_id
        ).distinct()
    else:
        # No filters - show all
        products = Product.objects.all()
    paginator = Paginator(day_ranges, 10)  # 50 items per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    context = {
        'day_ranges': page_obj,  # Use page_obj instead of day_ranges
        'page_obj': page_obj,
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

def edit(request):
    return render(request, 'edit.html')

