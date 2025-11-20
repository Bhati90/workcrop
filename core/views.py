from rest_framework import viewsets, parsers, status, permissions
from rest_framework.response import Response
from .models import Mukkadam,ActivityLog
from .serializers import MukkadamFullSerializer, MukkadamListSerializer,MukkadamDropdownSerializer
from rest_framework.decorators import action
import json

class MukkadamViewSet(viewsets.ModelViewSet):
    queryset = Mukkadam.objects.all().order_by('-updated_at')
    permission_classes = [permissions.IsAuthenticated]
    
    # Essential for handling Files + JSON data together
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def get_serializer_class(self):
        # Use ListSerializer for list view, Full for everything else
        if self.action == 'list':
            return MukkadamListSerializer
        return MukkadamFullSerializer

    def create(self, request, *args, **kwargs):
        return self.save_mukkadam(request, is_update=False)

    def update(self, request, *args, **kwargs):
        return self.save_mukkadam(request, is_update=True)

    def save_mukkadam(self, request, is_update=False):
        try:
            data_str = request.data.get('data')
            if not data_str:
                return Response({"error": "No 'data' field provided"}, status=400)

            data = json.loads(data_str)

            # Handle Files
            file_fields = ['profile_photo', 'aadhar_card', 'pan_card', 'bank_proof']
            for field in file_fields:
                if field in request.FILES:
                    data[field] = request.FILES[field]

            if is_update:
                instance = self.get_object()
                serializer = MukkadamFullSerializer(instance, data=data, partial=True)
            else:
                serializer = MukkadamFullSerializer(data=data)

            if serializer.is_valid():
                if is_update:
                    mukkadam = serializer.save()
                    
                    # --- TRACKING LOGIC STARTS HERE ---
                    # Check if availability specifically was changed
                    if 'team_availabilities' in data:
                        ActivityLog.objects.create(
                            mukkadam=mukkadam,
                            user=request.user,
                            action_type="Availability Update",
                            details=f"Updated availability slots. Total slots: {len(data['team_availabilities'])}"
                        )
                    else:
                        # Generic Profile Update
                        ActivityLog.objects.create(
                            mukkadam=mukkadam,
                            user=request.user,
                            action_type="Profile Update",
                            details="Updated general profile details"
                        )
                    # --- TRACKING LOGIC ENDS HERE ---
                    
                else:
                    # New Registration
                    mukkadam = serializer.save(created_by=request.user)
                    ActivityLog.objects.create(
                        mukkadam=mukkadam,
                        user=request.user,
                        action_type="Registration",
                        details="Created new Mukkadam profile"
                    )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED if not is_update else status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
        

    @action(detail=False, methods=['get'])
    def dropdown_list(self, request):
        mukkadams = Mukkadam.objects.all().only('id', 'mukkadam_name', 'mobile_numbers', 'village')
        serializer = MukkadamDropdownSerializer(mukkadams, many=True)
        return Response(serializer.data)