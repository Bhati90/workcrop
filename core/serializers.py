from rest_framework import serializers
from .models import Mukkadam

class MukkadamFullSerializer(serializers.ModelSerializer):
    # Read-only fields to show names instead of just IDs
    referred_by_name = serializers.CharField(source='referred_by.mukkadam_name', read_only=True)
    
    # Get list of people this person has referred
    referrals_list = serializers.SerializerMethodField()

    class Meta:
        model = Mukkadam
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'referrals_list', 'referred_by_name']

    def get_referrals_list(self, obj):
        # Return a list of names and IDs of people this person referred
        return obj.referrals_made.values('id', 'mukkadam_name', 'village')

# Helper serializer for the Dropdown in the Form
class MukkadamDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mukkadam
        fields = ['id', 'mukkadam_name', 'mobile_numbers', 'village']

class MukkadamListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mukkadam
        # Exclude sensitive fields for the general list
        exclude = [
            'mobile_numbers', 
            'deputy_mukkadam_mobile', 
            'payment_details', 
            'team_members',
            'aadhar_card',
            'pan_card',
            'bank_proof'
        ]