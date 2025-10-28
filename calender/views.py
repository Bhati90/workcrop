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
# from django.db.models import Q, Prefetch
# from django.http import JsonResponse
# from .models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct
# from rest_framework import viewsets, filters
# from rest_framework.decorators import action
# from rest_framework.response import Response
# from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
# from rest_framework import viewsets, status
# from django_filters.rest_framework import DjangoFilterBackend
# from .models import Crop, CropVariety, Activity, Product, DayRange, DayRangeProduct,AuditLog
# from .serializers import (
#     CropSerializer, CropScheduleSerializer, CropVarietySerializer, 
#     CropVarietyDetailSerializer, ActivitySerializer, ProductListSerializer, ProductDetailSerializer,
#     DayRangeSerializer, DayRangeProductSerializer,AuditLogSerializer
# )
# from django.core.paginator import Paginator
# from .utils.s3_uploads import upload_image_to_s3


def add(request):
    return render(request, 'add.html')

# class DayRangeProductViewSet(viewsets.ModelViewSet):
#     """
#     API endpoint for day range products with full CRUD operations
#     """
#     queryset = DayRangeProduct.objects.all()
#     serializer_class = DayRangeProductSerializer
#     parser_classes = (JSONParser, MultiPartParser, FormParser)
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['day_range', 'product']
#     search_fields = ['product__name', 'dosage']
#     ordering_fields = ['created_at']
#     def get_queryset(self):  # ✅ Add this method
#         return DayRangeProduct.objects.select_related(
#             'day_range__crop_variety__crop',
#             'day_range__activity',
#             'product'
#         )
#     def create(self, request, *args, **kwargs):
#         try:
#             serializer = self.get_serializer(data=request.data)
#             serializer.is_valid(raise_exception=True)
#             drp = serializer.save()
            
#             # Create audit log
#             # AuditLog.objects.create(
#             #     model_name='dayrangeproduct',
#             #     object_id=drp.id,
#             #     action='create',
#             #     changes={'created': serializer.data},
#             # )
            
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
#     def update(self, request, *args, **kwargs):
#         try:
#             instance = self.get_object()
#             old_data = DayRangeProductSerializer(instance).data
            
#             serializer = self.get_serializer(instance, data=request.data, partial=True)
#             serializer.is_valid(raise_exception=True)
#             drp = serializer.save()
            
#             # Create audit log
#             changes = {
#                 'before': old_data,
#                 'after': serializer.data
#             }
            
#             # AuditLog.objects.create(
#             #     model_name='dayrangeproduct',
#             #     object_id=drp.id,
#             #     action='update',
#             #     changes=changes,
#             # )
            
#             return Response(serializer.data)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
#     def partial_update(self, request, *args, **kwargs):
#         """Handle PATCH requests"""
#         return self.update(request, *args, **kwargs)
    
#     def destroy(self, request, *args, **kwargs):
#         """Handle DELETE requests"""
#         try:
#             instance = self.get_object()
#             old_data = DayRangeProductSerializer(instance).data
            
#             # Create audit log before deletion
#             # AuditLog.objects.create(
#             #     model_name='dayrangeproduct',
#             #     object_id=instance.id,
#             #     action='delete',
#             #     changes={'deleted': old_data},
#             # )
            
#             instance.delete()
#             return Response(status=status.HTTP_204_NO_CONTENT)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
# class ProductViewSet(viewsets.ModelViewSet):
#     """
#     API endpoint for products with full CRUD operations
#     """
#     queryset = Product.objects.all()
#     serializer_class = ProductListSerializer  #
#     parser_classes = (MultiPartParser,JSONParser, FormParser)
    
#     def get_client_ip(self, request):
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             ip = x_forwarded_for.split(',')[0]
#         else:
#             ip = request.META.get('REMOTE_ADDR')
#         return ip
    
#     def create(self, request, *args, **kwargs):
#         try:
#             data = request.data.copy()
            
#             # Handle image upload
#             if 'image' in request.FILES:
#                 image_file = request.FILES['image']
#                 image_url = upload_image_to_s3(image_file, folder='media')
#                 data['image'] = image_url
            
#             serializer = self.get_serializer(data=data)
#             serializer.is_valid(raise_exception=True)
#             product = serializer.save()
            
#             # Create audit log
#             # AuditLog.objects.create(
#             #     model_name='product',
#             #     object_id=product.id,
#             #     action='create',
                
#             #     changes={'created': serializer.data},
                
#             # )
            
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
#     def get_serializer_class(self):  # ✅ Add this method
#         if self.action == 'retrieve':  # Only for detail view
#             return ProductDetailSerializer
#         return ProductListSerializer
    
#     def update(self, request, *args, **kwargs):
#         try:
#             instance = self.get_object()
#             old_data = ProductSerializer(instance).data
            
#             data = request.data.copy()
            
#             # Handle image upload
#             if 'image' in request.FILES:
#                 image_file = request.FILES['image']
#                 image_url = upload_image_to_s3(image_file, folder='media')
#                 data['image'] = image_url
            
#             serializer = self.get_serializer(instance, data=data, partial=True)
#             serializer.is_valid(raise_exception=True)
#             product = serializer.save()
            
#             # Create audit log
#             changes = {
#                 'before': old_data,
#                 'after': serializer.data
#             }
            
#             # AuditLog.objects.create(
#             #     model_name='product',
#             #     object_id=product.id,
#             #     action='update',
                
#             #     changes=changes,
                
#             # )
            
#             return Response(serializer.data)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
#     def partial_update(self, request, *args, **kwargs):
#         """Handle PATCH requests"""
#         return self.update(request, *args, **kwargs)
    
#     def destroy(self, request, *args, **kwargs):
#         """Handle DELETE requests"""
#         try:
#             instance = self.get_object()
#             old_data = ProductSerializer(instance).data
            
#             # Create audit log before deletion
#             # AuditLog.objects.create(
#             #     model_name='product',
#             #     object_id=instance.id,
#             #     action='delete',
#             #     changes={'deleted': old_data},
#             #    )
            
#             instance.delete()
#             return Response(status=status.HTTP_204_NO_CONTENT)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
#     @action(detail=True, methods=['get'])
#     def history(self, request, pk=None):
#         """Get audit history for a product"""
#         logs = AuditLog.objects.filter(model_name='product', object_id=pk)
#         serializer = AuditLogSerializer(logs, many=True)
#         return Response(serializer.data)
# class ProductReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     API endpoint for products
#     GET /api/products/ - List all products
#     GET /api/products/{id}/ - Get specific product
#     GET /api/products/?product_type={type} - Filter by type
#     """
#     queryset = Product.objects.all()
#     serializer_class = ProductListSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['product_type']
#     search_fields = ['name', 'name_marathi', 'product_type']
#     ordering_fields = ['name', 'created_at']



class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for audit logs
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    
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
        
        return queryset


# class CropViewSet(viewsets.ModelViewSet):  # ← Changed from ReadOnlyModelViewSet
#     queryset = Crop.objects.prefetch_related('varieties')
#     serializer_class = CropSerializer
#     parser_classes = (JSONParser, MultiPartParser, FormParser)
#     filter_backends = [filters.SearchFilter, filters.OrderingFilter]
#     search_fields = ['name', 'name_marathi']
#     ordering_fields = ['name', 'created_at']
    
#     @action(detail=True, methods=['get'])
#     def schedule(self, request, pk=None):
#         crop = self.get_object()
#         serializer = CropScheduleSerializer(crop)
#         return Response(serializer.data)

# class CropVarietyViewSet(viewsets.ModelViewSet):  # ← Changed from ReadOnlyModelViewSet
#     queryset = CropVariety.objects.all()
#     serializer_class = CropVarietySerializer
#     parser_classes = (JSONParser, MultiPartParser, FormParser)
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['crop']
#     search_fields = ['name', 'name_marathi', 'crop__name']
#     ordering_fields = ['name', 'created_at']
    
#     def get_queryset(self):  # ✅ Add this method
#         return CropVariety.objects.select_related('crop').prefetch_related(
#             'day_ranges__activity',
#             'day_ranges__products__product'
#         )
    
# class ActivityViewSet(viewsets.ModelViewSet):  # ← Changed from ReadOnlyModelViewSet
#     queryset = Activity.objects.all()
#     serializer_class = ActivitySerializer
#     parser_classes = (JSONParser, MultiPartParser, FormParser)
#     filter_backends = [filters.SearchFilter, filters.OrderingFilter]
#     search_fields = ['name', 'name_marathi']
#     ordering_fields = ['name', 'created_at']

# class DayRangeViewSet(viewsets.ModelViewSet):  # ← Changed from ReadOnlyModelViewSet
#     """
#     API endpoint for day ranges with full CRUD operations
#     """
#     queryset = DayRange.objects.all()
#     serializer_class = DayRangeSerializer
#     parser_classes = (JSONParser, MultiPartParser, FormParser)
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['crop_variety', 'activity', 'crop_variety__crop']
#     search_fields = ['info', 'info_marathi', 'activity__name', 'crop_variety__name']
#     ordering_fields = ['start_day', 'end_day', 'created_at']
    
#     def create(self, request, *args, **kwargs):
#         try:
#             serializer = self.get_serializer(data=request.data)
#             serializer.is_valid(raise_exception=True)
#             day_range = serializer.save()
            
#             # Create audit log
#             # AuditLog.objects.create(
#             #     model_name='dayrange',
#             #     object_id=day_range.id,
#             #     action='create',
#             #     changes={'created': serializer.data},
#             # )
            
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
#     def update(self, request, *args, **kwargs):
#         try:
#             instance = self.get_object()
#             old_data = DayRangeSerializer(instance).data
            
#             serializer = self.get_serializer(instance, data=request.data, partial=True)
#             serializer.is_valid(raise_exception=True)
#             day_range = serializer.save()
            
#             # Create audit log
#             changes = {
#                 'before': old_data,
#                 'after': serializer.data
#             }
            
#             # AuditLog.objects.create(
#             #     model_name='dayrange',
#             #     object_id=day_range.id,
#             #     action='update',
#             #     changes=changes,
#             # )
            
#             return Response(serializer.data)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
#     def get_queryset(self):  # ✅ Add this method
#         return DayRange.objects.select_related(
#             'crop_variety__crop',
#             'activity'
#         ).prefetch_related(
#             Prefetch(
#                 'products',
#                 queryset=DayRangeProduct.objects.select_related('product')
#             )
#         )
#     def partial_update(self, request, *args, **kwargs):
#         """Handle PATCH requests"""
#         return self.update(request, *args, **kwargs)
    
#     def destroy(self, request, *args, **kwargs):
#         """Handle DELETE requests"""
#         try:
#             instance = self.get_object()
#             old_data = DayRangeSerializer(instance).data
            
#             # Create audit log before deletion
#             # AuditLog.objects.create(
#             #     model_name='dayrange',
#             #     object_id=instance.id,
#             #     action='delete',
#             #     changes={'deleted': old_data},
#             # )
            
#             instance.delete()
#             return Response(status=status.HTTP_204_NO_CONTENT)
#         except Exception as e:
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
    paginator = Paginator(day_ranges, 25)  # 50 items per page
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


# def get_varieties_by_crop(request):
#     """AJAX endpoint to get varieties for a selected crop"""
#     crop_id = request.GET.get('crop_id')
    
#     if crop_id:
#         varieties = CropVariety.objects.filter(crop_id=crop_id).values('id', 'name')
#     else:
#         varieties = CropVariety.objects.all().values('id', 'name')
    
#     return JsonResponse(list(varieties), safe=False)


# def get_activities_by_variety(request):
#     """AJAX endpoint to get activities for a selected variety"""
#     variety_id = request.GET.get('variety_id')
    
#     if variety_id:
#         # Get only activities that exist in DayRange for this variety
#         activities = Activity.objects.filter(
#             day_ranges__crop_variety_id=variety_id
#         ).distinct().values('id', 'name').order_by('name')
#     else:
#         activities = Activity.objects.all().values('id', 'name').order_by('name')
    
#     return JsonResponse(list(activities), safe=False)


# def get_products_by_filters(request):
#     """AJAX endpoint to get products based on variety and/or activity"""
#     variety_id = request.GET.get('variety_id')
#     activity_id = request.GET.get('activity_id')
    
#     products = Product.objects.all()
    
#     if variety_id and activity_id:
#         # Both filters applied - most specific
#         products = products.filter(
#             day_range_products__day_range__crop_variety_id=variety_id,
#             day_range_products__day_range__activity_id=activity_id
#         )
#     elif variety_id:
#         # Only variety filter
#         products = products.filter(
#             day_rangep_roducts__day_range__crop_variety_id=variety_id
#         )
#     elif activity_id:
#         # Only activity filter
#         products = products.filter(
#             day_range_products__day_range__activity_id=activity_id
#         )
    
#     products = products.distinct().values('id', 'name').order_by('name')
    
#     return JsonResponse(list(products), safe=False)