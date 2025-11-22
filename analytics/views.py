import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from datetime import datetime, timedelta

# --- Setup ---
load_dotenv()
genai.configure(api_key='AIzaSyCh0DeWCZr8m3kF4LDB2A_xoAlqbmKjvgs')
# genai.configure(api_key='AIzaSyCh0DeWCZr8m3kF4LDB2A_xoAlqbmKjvgs')
# --- Helper Functions ---

def get_db_schema():
    """
    Connects to the database and retrieves the CREATE TABLE statements
    for a predefined list of allowed tables.
    """
    allowed_tables = ['registration_chatcontact','registration_farmer','registration_cropdetails',
                      'registration_intervention', 'flow_flows', 'registration_message',
                      'registration_labourer', 'registration_job','user_profiles'] 
    
    schema_str = ""
    with connection.cursor() as cursor:
        for table_name in allowed_tables:
            cursor.execute(f"""
                SELECT 'CREATE TABLE ' || '{table_name}' || ' (' || string_agg(column_name || ' ' || data_type, ', ') || ');'
                FROM information_schema.columns
                WHERE table_name = '{table_name}';
            """)
            row = cursor.fetchone()
            if row and row[0]:
                schema_str += row[0] + "\n\n"
    return schema_str

def get_comprehensive_farmer_data():
    """
    Retrieves comprehensive farmer data matching EXACT database schema:
    - registration_farmer (id, farmer_name, phone_number, farm_size_acres, created_at)
    - registration_cropdetails (id, farmer_id, crop_name, seeding_date, germination_date, 
                                vegetative_stage_start, flowering_stage_start, 
                                fruiting_stage_start, harvesting_date, next_crop_recommendation, 
                                soil_improvement_tip)
    - registration_intervention (id, crop_details_id, intervention_type, date, product_used, notes)
    """
    with connection.cursor() as cursor:
        try:
            # Get farmer demographics with crop details
            # Note: registration_cropdetails has farmer_id (FK to registration_farmer.id)
            cursor.execute("""
                SELECT 
                    f.id as farmer_id,
                    f.farmer_name as name,
                    f.phone_number,
                    f.farm_size_acres as farm_size,
                    f.created_at,
                    cd.crop_name,
                    cd.seeding_date,
                    cd.germination_date,
                    cd.vegetative_stage_start,
                    cd.flowering_stage_start,
                    cd.fruiting_stage_start,
                    cd.harvesting_date,
                    cd.next_crop_recommendation,
                    cd.soil_improvement_tip,
                    COUNT(DISTINCT i.id) as total_interventions
                FROM registration_farmer f
                LEFT JOIN registration_cropdetails cd ON f.id = cd.farmer_id
                LEFT JOIN registration_intervention i ON cd.id = i.crop_details_id
                GROUP BY 
                    f.id, f.farmer_name, f.phone_number, f.farm_size_acres, f.created_at,
                    cd.crop_name, cd.seeding_date, cd.germination_date, cd.vegetative_stage_start,
                    cd.flowering_stage_start, cd.fruiting_stage_start, cd.harvesting_date,
                    cd.next_crop_recommendation, cd.soil_improvement_tip
            """)
            
            columns = [col[0] for col in cursor.description]
            farmer_data = [dict(zip(columns, row)) for row in cursor.fetchall()]
            print(f"Fetched {len(farmer_data)} farmer records")
            
        except Exception as e:
            print(f"Error fetching farmer data: {e}")
            return {'farmers': [], 'crop_details': [], 'interventions': []}
        
        # Get crop-specific details with growth stage calculation
        try:
            cursor.execute("""
                SELECT 
                    cd.id as crop_id,
                    cd.farmer_id,
                    cd.crop_name,
                    cd.seeding_date,
                    cd.germination_date,
                    cd.vegetative_stage_start,
                    cd.flowering_stage_start,
                    cd.fruiting_stage_start,
                    cd.harvesting_date,
                    cd.next_crop_recommendation,
                    cd.soil_improvement_tip,
                    CASE 
                        WHEN CURRENT_DATE < cd.germination_date THEN 'Seeding'
                        WHEN CURRENT_DATE < cd.vegetative_stage_start THEN 'Germination'
                        WHEN CURRENT_DATE < cd.flowering_stage_start THEN 'Vegetative'
                        WHEN CURRENT_DATE < cd.fruiting_stage_start THEN 'Flowering'
                        WHEN CURRENT_DATE < cd.harvesting_date THEN 'Fruiting'
                        ELSE 'Ready for Harvest'
                    END as current_growth_stage,
                    cd.harvesting_date - CURRENT_DATE as days_until_harvest
                FROM registration_cropdetails cd
            """)
            columns = [col[0] for col in cursor.description]
            crop_details = [dict(zip(columns, row)) for row in cursor.fetchall()]
            print(f"Fetched {len(crop_details)} crop details")
            
        except Exception as e:
            print(f"Error fetching crop details: {e}")
            crop_details = []
        
        # Get intervention history
        # registration_intervention has: crop_details_id (FK to registration_cropdetails.id)
        try:
            cursor.execute("""
                SELECT 
                    i.id as intervention_id,
                    cd.farmer_id,
                    i.crop_details_id,
                    i.intervention_type,
                    i.date as intervention_date,
                    i.day_number_from_planting,
                    i.activity_name,
                    i.main_input_values,
                    i.secondary_input_values,
                    i.how_to_do_it,
                    i.price_cost,
                    i.product_catalog_brand,
                    i.purpose_goal,
                    i.product_used,
                    i.notes,
                    cd.crop_name
                FROM registration_intervention i
                JOIN registration_cropdetails cd ON i.crop_details_id = cd.id
                ORDER BY i.date DESC
            """)
            columns = [col[0] for col in cursor.description]
            interventions = [dict(zip(columns, row)) for row in cursor.fetchall()]
            print(f"Fetched {len(interventions)} interventions")
            
        except Exception as e:
            print(f"Error fetching interventions: {e}")
            interventions = []
        
        return {
            'farmers': farmer_data,
            'crop_details': crop_details,
            'interventions': interventions
        }

def generate_flow_prompts_from_segments(segments_data):
    """
    Converts AI segment analysis into ready-to-use flow creation prompts.
    """
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    prompt = f"""
Based on the farmer segment analysis, generate specific, ready-to-execute prompts for creating WhatsApp flows.

SEGMENT ANALYSIS:
{json.dumps(segments_data, indent=2)}

Generate detailed prompts that can be directly used to create flows. Each prompt should be complete and actionable.

OUTPUT FORMAT (JSON):
{{
  "flow_prompts": [
    {{
      "prompt_id": "unique_id",
      "segment_targeted": "segment name",
      "priority": "HIGH/MEDIUM/LOW",
      "prompt_title": "Short title",
      "full_prompt": "Complete prompt ready to paste for flow creation",
      "expected_templates": number,
      "language": "hi/en/both",
      "estimated_conversion_rate": "X%",
      "implementation_notes": ["note1", "note2"]
    }}
  ]
}}

Generate ONLY valid JSON.
"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error generating flow prompts: {e}")
        return None


# Add this at the top with other imports
import requests
import logging

logger = logging.getLogger(__name__)

# Add this function to fetch existing templates
def get_existing_whatsapp_templates():
    """
    Fetches all approved WhatsApp templates from Meta API
    Returns a list of template names and their details
    """
    try:
        META_ACCESS_TOKEN = "EAAhMBt21QaMBPCyLtJj6gwjDy6Gai4fZApb3MXuZBZCCm0iSEd8ZCZCJdkRt4cOtvhyeFLZCNUwitFaLZA3ZCwv7enN6FBFgDMAOKl7LMx0J2kCjy6Qd6AqnbnhB2bo2tgsdGmn9ZCN5MD6yCgE3shuP62t1spfSB6ZALy1QkNLvIaeWZBcvPH00HHpyW6US4kil2ENZADL4ZCvDLVWV9seSbZCxXYzVCezIenCjhSYtoKTIlJ"
        WABA_ID = "1477047197063313"
        url = f"https://graph.facebook.com/v19.0/{WABA_ID}/message_templates?fields=name,components,status,category,language"
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        all_templates = response.json().get('data', [])
        approved_templates = [t for t in all_templates if t.get('status') == 'APPROVED']
        
        # Extract template names and basic info
        template_list = []
        for t in approved_templates:
            template_list.append({
                'name': t.get('name'),
                'language': t.get('language'),
                'category': t.get('category'),
                'components': t.get('components', [])
            })
        
        print(f"Fetched {len(template_list)} approved templates")
        return template_list
    
    except Exception as e:
        logger.error(f"Failed to fetch WhatsApp templates: {e}")
        return []



def analyze_farmer_segments_with_ai(farmer_data):
    """
    ENHANCED: Dynamic segment discovery - finds NEW patterns automatically
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
    except:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    from datetime import datetime, timedelta
    from collections import Counter
    
    total_farmers = len(farmer_data['farmers'])
    
    # Enhanced intervention analysis
    intervention_types = Counter([i['intervention_type'] for i in farmer_data['interventions']])
    
    # Analyze intervention patterns by crop
    intervention_by_crop = {}
    for intervention in farmer_data['interventions']:
        crop = intervention.get('crop_name')
        if crop:
            if crop not in intervention_by_crop:
                intervention_by_crop[crop] = []
            intervention_by_crop[crop].append({
                'type': intervention['intervention_type'],
                'activity': intervention.get('activity_name'),
                'product': intervention.get('product_used'),
                'cost': intervention.get('price_cost'),
                'purpose': intervention.get('purpose_goal')
            })
    
    # NEW: Discover unique crop types
    unique_crops = list(set([f['crop_name'] for f in farmer_data['farmers'] if f.get('crop_name')]))
    
    # NEW: Discover unique intervention activities (beyond types)
    unique_activities = list(set([i.get('activity_name') for i in farmer_data['interventions'] if i.get('activity_name')]))
    
    # NEW: Discover unique products being used
    unique_products = list(set([i.get('product_used') for i in farmer_data['interventions'] if i.get('product_used')]))
    
    # NEW: Discover cost-based segments
    high_value_interventions = [i for i in farmer_data['interventions'] if i.get('price_cost') and float(i.get('price_cost', 0)) > 1000]
    low_cost_interventions = [i for i in farmer_data['interventions'] if i.get('price_cost') and float(i.get('price_cost', 0)) < 200]
    
    # Recent interventions for upsell opportunities
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_interventions = [
        i for i in farmer_data['interventions']
        if i.get('intervention_date') and i['intervention_date'] >= thirty_days_ago
    ]
    
    # Identify farmers needing interventions (no recent activity)
    farmers_needing_intervention = []
    for farmer in farmer_data['farmers']:
        farmer_interventions = [
            i for i in recent_interventions
            if i.get('farmer_id') == farmer['farmer_id']
        ]
        if len(farmer_interventions) == 0:
            farmers_needing_intervention.append(farmer['farmer_id'])
    
    # Get existing WhatsApp templates
    existing_templates = get_existing_whatsapp_templates()
    existing_template_names = [t['name'] for t in existing_templates]
    
    # Calculate summary statistics
    crops_counter = Counter([f['crop_name'] for f in farmer_data['farmers'] if f.get('crop_name')])
    farm_sizes = [float(f['farm_size']) for f in farmer_data['farmers'] if f.get('farm_size')]
    avg_farm_size = sum(farm_sizes) / len(farm_sizes) if farm_sizes else 0
    growth_stages = Counter([c['current_growth_stage'] for c in farmer_data['crop_details']])
    harvest_soon = [c for c in farmer_data['crop_details'] if c.get('days_until_harvest') and c['days_until_harvest'] <= 30]
    harvest_within_week = [c for c in farmer_data['crop_details'] if c.get('days_until_harvest') and c['days_until_harvest'] <= 7]
    farmers_with_next_crop = [f for f in farmer_data['farmers'] if f.get('next_crop_recommendation')]
    
    summary_data = {
        'total_farmers': total_farmers,
        'crop_distribution': dict(crops_counter.most_common(10)),
        'unique_crops_in_system': unique_crops,
        'unique_intervention_activities': unique_activities[:20],
        'unique_products_used': unique_products[:20],
        'average_farm_size': round(avg_farm_size, 2),
        'farm_size_ranges': {
            'small_0_2_acres': len([f for f in farm_sizes if f <= 2]),
            'medium_2_5_acres': len([f for f in farm_sizes if 2 < f <= 5]),
            'large_5plus_acres': len([f for f in farm_sizes if f > 5])
        },
        'growth_stage_distribution': dict(growth_stages),
        'harvest_insights': {
            'harvesting_within_30_days': len(harvest_soon),
            'harvesting_within_7_days': len(harvest_within_week),
            'harvest_soon_crops': [{'crop': c['crop_name'], 'days': c['days_until_harvest']} 
                                  for c in harvest_within_week[:10]]
        },
        'intervention_insights': {
            'total_interventions': len(farmer_data['interventions']),
            'recent_interventions_30_days': len(recent_interventions),
            'intervention_types': dict(intervention_types),
            'intervention_by_crop': {k: len(v) for k, v in intervention_by_crop.items()},
            'farmers_needing_intervention': len(farmers_needing_intervention),
            'avg_interventions_per_farmer': round(len(farmer_data['interventions']) / total_farmers, 2),
            'most_common_products': list(set([i.get('product_used') for i in farmer_data['interventions'][:20] if i.get('product_used')])),
            'avg_intervention_cost': round(sum([float(i.get('price_cost', 0)) for i in farmer_data['interventions'] if i.get('price_cost')]) / len(farmer_data['interventions']), 2) if farmer_data['interventions'] else 0,
            'high_value_intervention_count': len(high_value_interventions),
            'low_cost_intervention_count': len(low_cost_interventions),
        },
        'next_crop_opportunities': {
            'farmers_with_recommendations': len(farmers_with_next_crop),
            'sample_recommendations': list(set([f['next_crop_recommendation'] 
                                               for f in farmers_with_next_crop[:20] 
                                               if f.get('next_crop_recommendation')]))
        },
        'existing_whatsapp_templates': existing_template_names,
        'sample_farmers': farmer_data['farmers'][:5]
    }
    
    prompt = f"""
You are an expert agricultural business analyst for a FARMER-LABOR PLATFORM with INTERVENTION TRACKING.

🔄 CRITICAL: This is a DYNAMIC ANALYSIS SYSTEM. You must:
1. Discover NEW segment opportunities from the data (don't just use pre-defined segments)
2. Create segments for UNIQUE crop types you haven't seen before
3. Identify EMERGING patterns (new products, new interventions, seasonal trends)
4. Generate INNOVATIVE marketing opportunities based on actual farmer behavior

DATABASE STRUCTURE:
- Farmer: farmer_name, phone_number, farm_size_acres, created_at
- CropDetails: One crop per farmer with growth stages (seeding → germination → vegetative → flowering → fruiting → harvesting)
- Intervention: Detailed farm activities with:
  * intervention_type: Fertilizer, Pesticide, Pruning/Weeding, Irrigation
  * activity_name: Specific activity (e.g., "Urea Application", "Fungicide Spray")
  * main_input_values: Primary products used
  * product_used: Brand/product details
  * price_cost: Cost of intervention
  * purpose_goal: Why intervention was done
  * how_to_do_it: Instructions given

EXISTING WHATSAPP TEMPLATES:
{json.dumps(existing_template_names, indent=2)}

FARMER DATA SUMMARY (based on {total_farmers} farmers):
{json.dumps(summary_data, indent=2, default=str)}

🎯 YOUR TASK - DYNAMIC SEGMENT DISCOVERY:

1. **ALWAYS CREATE THESE CORE SEGMENTS** (if data supports):
   - Pre-Harvest Farmers (7-30 days to harvest)
   - Fertilizer Upsell (active crops needing nutrition)
   - Pesticide Service (flowering/fruiting stage)
   - Inactive Farmers (no activity 30+ days)
   - High-Value Customers (avg spend >₹500)
   - Next Crop Upsell (has recommendations)

2. **DISCOVER AND CREATE NEW SEGMENTS** based on:
   
   A. UNIQUE CROPS FOUND ({len(summary_data['unique_crops_in_system'])} crops):
   {json.dumps(summary_data['unique_crops_in_system'][:15], indent=2)}
   
   → For EACH unique/specialty crop (e.g., Strawberry, Pomegranate, Dragon Fruit):
      Create crop-specific segment like "Strawberry Growers - Premium Care"
   
   B. UNIQUE INTERVENTION ACTIVITIES ({len(summary_data['unique_intervention_activities'])} activities):
   {json.dumps(summary_data['unique_intervention_activities'][:15], indent=2)}
   
   → For specialized activities (e.g., "Drip Irrigation Setup", "Greenhouse Maintenance"):
      Create service-specific segments
   
   C. PRODUCT USAGE PATTERNS:
   {json.dumps(summary_data['unique_products_used'][:15], indent=2)}
   
   → Identify brand loyalists, premium product users, generic product users
   → Create brand-specific upsell segments

3. **SEGMENT PRIORITIZATION**:
   - HIGH Priority: Revenue >₹50k potential, Easy to implement
   - MEDIUM Priority: Revenue ₹20-50k, Moderate effort  
   - LOW Priority: <₹20k or requires infrastructure

OUTPUT FORMAT (JSON):
{{
  "analysis_summary": {{
    "total_farmers": {total_farmers},
    "analysis_date": "{datetime.now().strftime('%Y-%m-%d')}",
    "new_patterns_discovered": [
      "List any NEW crops, products, or behaviors you found",
      "Highlight opportunities that weren't pre-defined"
    ],
    "key_insights": [
      "intervention-based insights",
      "product upsell opportunities",
      "service gaps identified"
    ]
  }},
  "segments": [
    {{
      "segment_id": "unique_id",
      "segment_name": "Descriptive Name",
      "segment_type": "CORE/NEW/EMERGING",
      "priority": "HIGH/MEDIUM/LOW",
      "farmer_count": 100,
      "conversion_potential": "HIGH (25-35%)",
      "estimated_revenue": "₹5,000 per farmer/month",
      "revenue_calculation": "Based on avg intervention cost × conversion rate",
      "characteristics": ["unique patterns"],
      "intervention_insights": {{
        "avg_intervention_cost": 850,
        "most_used_products": ["Product A", "Product B"],
        "upsell_products": ["Premium Product X", "Service Y"]
      }}
    }}
  ],
  
  "immediate_opportunities": [
    {{
      "opportunity": "Pre-Harvest Labor Booking",
      "potential_revenue": "₹2,50,000 (50 farmers × ₹5,000)",
      "implementation_difficulty": "EASY",
      "timeline": "1-2 weeks",
      "target_segment": "Pre-Harvest Farmers",
      "action_items": [
        "Send WhatsApp template to {len(harvest_within_week)} farmers harvesting within 7 days",
        "Create labor booking flow",
        "Follow up after 48 hours"
      ],
      "why_now": "7 farmers harvesting within week - urgent window",
      "conversion_estimate": "30-40% (based on urgency)",
      "required_resources": ["WhatsApp template", "Labor availability data"]
    }},
    {{
      "opportunity": "Fertilizer Upsell to Active Crops",
      "potential_revenue": "₹1,50,000 (estimate)",
      "implementation_difficulty": "MEDIUM",
      "timeline": "2-3 weeks",
      "target_segment": "Vegetative/Flowering Stage Farmers",
      "action_items": [
        "Identify farmers at vegetative/flowering stage",
        "Create personalized fertilizer recommendations",
        "Send targeted WhatsApp campaigns"
      ],
      "why_now": "Optimal growth stage for nutrient boost",
      "conversion_estimate": "20-25%",
      "required_resources": ["Product catalog", "Stage-based recommendations"]
    }},
    {{
      "opportunity": "Re-engage Inactive Farmers",
      "potential_revenue": "₹3,00,000 (estimate)",
      "implementation_difficulty": "MEDIUM",
      "timeline": "3-4 weeks",
      "target_segment": "Inactive Farmers (30+ days)",
      "action_items": [
        "Send re-engagement campaign to {len(farmers_needing_intervention)} inactive farmers",
        "Offer special discount/incentive",
        "Survey to understand inactivity reasons"
      ],
      "why_now": "Risk of losing customers permanently",
      "conversion_estimate": "15-20%",
      "required_resources": ["Discount budget", "Survey tool"]
    }}
  ],
  
  "automation_recommendations": [
    {{
      "automation_type": "Harvest Alert System",
      "description": "Automatically notify farmers 14, 7, and 3 days before harvest date with labor booking options",
      "target_segments": ["Pre-Harvest Farmers"],
      "implementation_priority": "HIGH",
      "expected_impact": "40% increase in labor bookings",
      "technical_requirements": [
        "WhatsApp Business API integration",
        "Scheduled message triggers based on harvesting_date",
        "Labor availability API"
      ],
      "estimated_setup_time": "2-3 weeks",
      "recurring_benefit": "Automated engagement for every harvest cycle"
    }},
    {{
      "automation_type": "Growth Stage Interventions",
      "description": "Auto-send stage-specific care tips and product recommendations when crops transition growth stages",
      "target_segments": ["All Active Crop Farmers"],
      "implementation_priority": "HIGH",
      "expected_impact": "25% increase in intervention adoption",
      "technical_requirements": [
        "Growth stage tracking",
        "Stage-specific template library (5-7 templates)",
        "Product recommendation engine"
      ],
      "estimated_setup_time": "3-4 weeks",
      "recurring_benefit": "Continuous engagement throughout crop lifecycle"
    }},
    {{
      "automation_type": "Inactive Farmer Win-Back",
      "description": "Automatically identify farmers with no activity for 30+ days and trigger re-engagement sequence",
      "target_segments": ["Inactive Farmers"],
      "implementation_priority": "MEDIUM",
      "expected_impact": "15-20% reactivation rate",
      "technical_requirements": [
        "Activity tracking system",
        "Multi-step re-engagement flow (3-4 touchpoints)",
        "Incentive/discount management"
      ],
      "estimated_setup_time": "2 weeks",
      "recurring_benefit": "Reduces churn, maintains customer base"
    }},
    {{
      "automation_type": "High-Value Customer VIP Program",
      "description": "Auto-identify high-spending farmers (avg cost >₹500) and enroll in VIP program with exclusive benefits",
      "target_segments": ["High-Value Customers"],
      "implementation_priority": "MEDIUM",
      "expected_impact": "30% increase in repeat purchases",
      "technical_requirements": [
        "Spending analytics",
        "VIP tier definition",
        "Exclusive product/service catalog"
      ],
      "estimated_setup_time": "3 weeks",
      "recurring_benefit": "Increased customer lifetime value"
    }}
  ]
}}

Generate ONLY valid JSON. Be thorough and create at least 7-10 segments.
"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        result = json.loads(response.text)
        return result
    except Exception as e:
        print(f"Error in AI analysis: {e}")
        return None


def generate_detailed_segment_analysis(segment, farmer_data):
    """
    COMPLETE VERSION: Generates deep personalized analysis for a specific segment
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
    except:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # Get matched farmers for this segment
    matched_farmers = get_farmers_for_segment(segment, farmer_data)
    
    if not matched_farmers:
        return {
            'error': 'No farmers matched this segment',
            'stage_distribution': {'breakdown': [], 'key_insights': []},
            'template_requirements': [],
            'flow_creation_prompts': []
        }
    
    # Extract ALL available personalization data
    available_farmer_fields = set()
    for farmer in matched_farmers[:10]:
        available_farmer_fields.update(farmer.keys())
    
    # Get growth stage distribution for matched farmers
    stage_counts = {}
    for farmer in matched_farmers:
        stage = farmer.get('current_stage', 'Unknown')
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    
    prompt = f"""
You are creating HIGHLY PERSONALIZED WhatsApp templates and flows for a farmer engagement platform.

⚠️ CRITICAL REQUIREMENTS:
1. Make templates feel SPECIFICALLY written for each farmer using their ACTUAL DATA
2. Create COMPLETE, COPY-PASTE ready flow prompts
3. Use MAXIMUM personalization (10+ variables per template)
4. Generate templates that feel like personal conversations, not mass broadcasts

SEGMENT INFORMATION:
{json.dumps(segment, indent=2, default=str)}

MATCHED FARMERS DATA:
- Total farmers in segment: {len(matched_farmers)}
- Available personalization fields: {list(available_farmer_fields)}
- Growth stage distribution: {json.dumps(stage_counts, indent=2)}

SAMPLE FARMERS (showing what data we have):
{json.dumps(matched_farmers[:3], indent=2, default=str)}

YOUR TASK:
Generate COMPLETE analysis with:
1. Stage distribution breakdown
2. Highly personalized WhatsApp templates (with 10+ variables each)
3. Complete, ready-to-execute flow creation prompts

TEMPLATE PERSONALIZATION EXAMPLE:

❌ BAD (Generic):
"नमस्कार, आपकी फसल की कटाई जल्द है। मजदूर चाहिए?"

✅ GOOD (Hyper-Personalized):
"नमस्कार {{{{farmer_name}}}},

आपकी {{{{farm_size}}}} एकड़ की {{{{crop_name}}}} फसल अब {{{{current_stage}}}} में है। {{{{days_until_harvest}}}} दिनों में कटाई होगी! 🌾

पिछली बार {{{{last_intervention_date}}}} को {{{{last_intervention_type}}}} किया था ({{{{product_used}}}})।

अब कटाई के लिए तैयारी का समय!

✅ {{{{estimated_workers}}}} अनुभवी मजदूर
✅ अनुमानित लागत: ₹{{{{estimated_labor_cost}}}}
✅ {{{{harvest_date}}}} को तैयार

अभी बुक करें!"

OUTPUT FORMAT (COMPLETE JSON):
{{
  "stage_distribution": {{
    "breakdown": [
      {{
        "stage": "Fruiting",
        "percentage": 65,
        "farmer_count": 295,
        "urgency": "HIGH/MEDIUM/LOW",
        "action_needed": "What to do for these farmers"
      }}
    ],
    "key_insights": [
      "Most farmers are at X stage",
      "Urgent action needed for Y farmers",
      "Revenue opportunity: ₹Z"
    ]
  }},
  "template_requirements": [
    {{
      "template_name": "segment_action_language (e.g., pre_harvest_labor_hi)",
      "likely_exists": false,
      "template_type": "UTILITY/MARKETING",
      "language": "hi/en",
      "priority": "HIGH/MEDIUM/LOW",
      "personalization_level": "VERY_HIGH",
      "body_text": "Complete Hindi/English template with {{{{1}}}}, {{{{2}}}}, etc placeholders",
      "variables": [
        {{
          "position": "{{{{1}}}}",
          "field_name": "farmer_name",
          "data_source": "matched_farmers[].farmer_name",
          "example": "रमेश पाटील",
          "why_personalized": "Makes farmer feel recognized"
        }},
        {{
          "position": "{{{{2}}}}",
          "field_name": "farm_size",
          "data_source": "matched_farmers[].farm_size",
          "example": "3.5",
          "why_personalized": "Shows we know their farm"
        }},
        {{
          "position": "{{{{3}}}}",
          "field_name": "crop_name",
          "data_source": "matched_farmers[].crop_name",
          "example": "अंगूर",
          "why_personalized": "Crop-specific"
        }},
        {{
          "position": "{{{{4}}}}",
          "field_name": "current_stage",
          "data_source": "matched_farmers[].current_stage",
          "example": "Fruiting",
          "why_personalized": "Real-time crop monitoring"
        }},
        {{
          "position": "{{{{5}}}}",
          "field_name": "days_until_harvest",
          "data_source": "CALCULATED from matched_farmers[].days_until_harvest",
          "example": "7",
          "why_personalized": "Creates urgency"
        }},
        {{
          "position": "{{{{6}}}}",
          "field_name": "last_intervention_date",
          "data_source": "matched_farmers[].last_intervention_date",
          "example": "15 सितंबर",
          "why_personalized": "Proves we track their activities"
        }},
        {{
          "position": "{{{{7}}}}",
          "field_name": "last_intervention_type",
          "data_source": "matched_farmers[].last_intervention",
          "example": "Pesticide स्प्रे",
          "why_personalized": "References their actions"
        }},
        {{
          "position": "{{{{8}}}}",
          "field_name": "product_used",
          "data_source": "matched_farmers[].last_product_used OR match_reason",
          "example": "Bayer Confidor",
          "why_personalized": "Shows we remember products"
        }},
        {{
          "position": "{{{{9}}}}",
          "field_name": "estimated_workers",
          "data_source": "CALCULATED: farm_size * 3",
          "example": "10-12",
          "why_personalized": "Customized to farm size"
        }},
        {{
          "position": "{{{{10}}}}",
          "field_name": "estimated_labor_cost",
          "data_source": "CALCULATED: farm_size * ₹5000",
          "example": "17,500",
          "why_personalized": "Budget-relevant pricing"
        }}
      ],
      "buttons": [
        {{"type": "QUICK_REPLY", "text": "मजदूर बुक करें"}},
        {{"type": "QUICK_REPLY", "text": "बाद में बात करें"}}
      ],
      "usage_context": "When to send this template",
      "personalization_impact": "Expected engagement increase",
      "data_requirements": [
        "farmer_name (REQUIRED)",
        "farm_size (REQUIRED)",
        "crop_name (REQUIRED)",
        "List all REQUIRED and OPTIONAL fields"
      ]
    }}
  ],
  "flow_creation_prompts": [
    {{
      "prompt_id": "unique_flow_id",
      "prompt_title": "Descriptive Flow Name",
      "complete_prompt": "**COMPLETE MULTI-STEP FLOW SPECIFICATION**\\n\\nTARGET AUDIENCE:\\n- Farmers: {len(matched_farmers)} in segment '{segment['segment_name']}'\\n- Characteristics: [list from matched_farmers data]\\n\\nPERSONALIZATION DATA AVAILABLE:\\n1. Farmer name: matched_farmers[].farmer_name\\n2. Farm size: matched_farmers[].farm_size acres\\n3. Crop: matched_farmers[].crop_name\\n4. Growth stage: matched_farmers[].current_stage\\n5. Days to harvest: matched_farmers[].days_until_harvest\\n6. Last intervention: matched_farmers[].last_intervention\\n7. Last intervention date: matched_farmers[].last_intervention_date\\n8. Product used: matched_farmers[].last_product_used\\n9. Match reason: matched_farmers[].match_reason\\n10. Total interventions: matched_farmers[].total_interventions\\n\\nFLOW STRUCTURE:\\n\\n**STEP 1: Initial Outreach** (Template: template_name_step1_hi)\\nObjective: Get farmer's attention with personalized message\\n\\nTemplate Text:\\n\\\"नमस्कार {{{{farmer_name}}}},\\n\\nआपकी {{{{farm_size}}}} एकड़ की {{{{crop_name}}}} फसल {{{{current_stage}}}} में है।\\n{{{{days_until_harvest}}}} दिनों में कटाई!\\n\\nपिछली बार: {{{{last_intervention_date}}}} - {{{{last_intervention_type}}}}\\n\\n[YOUR SPECIFIC OFFER/MESSAGE]\\n\\nक्या आप रुचि रखते हैं?\\\"\\n\\nButtons:\\n- \\\"हाँ, बताएं\\\" → Go to STEP 2\\n- \\\"नहीं, धन्यवाद\\\" → End flow\\n- \\\"बाद में\\\" → Schedule follow-up\\n\\n---\\n\\n**STEP 2: Details Collection** (Template: template_name_step2_hi)\\nObjective: Gather specific requirements\\n\\nTemplate Text:\\n\\\"बहुत अच्छा {{{{farmer_name}}}}!\\n\\nआपके {{{{farm_size}}}} एकड़ के {{{{crop_name}}}} के लिए:\\n\\n[SPECIFIC QUESTIONS BASED ON SEGMENT]\\n\\nकृपया बताएं:\\\"\\n\\nButtons:\\n- Option 1\\n- Option 2\\n- Option 3\\n\\n---\\n\\n**STEP 3: Confirmation** (Template: template_name_confirm_hi)\\nObjective: Confirm and close\\n\\nTemplate Text:\\n\\\"धन्यवाद {{{{farmer_name}}}}!\\n\\n✅ Confirmed for {{{{harvest_date}}}}\\n✅ Details: [SUMMARY]\\n✅ Cost: ₹{{{{estimated_cost}}}}\\n\\nहमारी टीम {{{{contact_time}}}} को संपर्क करेगी।\\n\\nकोई सवाल?\\\"\\n\\nButtons:\\n- \\\"सब ठीक है\\\"\\n- \\\"बदलाव चाहिए\\\"\\n- \\\"मदद चाहिए\\\"\\n\\n---\\n\\nSUCCESS METRICS:\\n- Step 1→2 conversion: 35%\\n- Step 2→3 conversion: 75%\\n- Overall completion: 26%\\n- Expected revenue per farmer: ₹{segment.get('estimated_revenue', '5,000')}\\n\\nIMPLEMENTATION:\\n1. Create 3 templates in WhatsApp Business API\\n2. Set up flow with conditional logic\\n3. Map personalization variables from database\\n4. Test with 10 farmers first\\n5. Roll out to full segment\\n\\nTRIGGER LOGIC:\\n- When: [SPECIFIC CONDITION]\\n- Frequency: [HOW OFTEN]\\n- Exclusions: [WHO NOT TO SEND TO]",
      "required_templates": ["template_step1_hi", "template_step2_hi", "template_confirm_hi"],
      "expected_outcome": "Detailed outcome expectation",
      "implementation_notes": [
        "Step-by-step implementation guide",
        "What to prepare first",
        "How to test",
        "When to scale"
      ]
    }}
  ],
  "implementation_checklist": [
    {{
      "step": 1,
      "action": "Create WhatsApp Templates",
      "details": "Submit 3 templates to Meta for approval (24-48 hours)",
      "timeline": "Day 1",
      "responsible": "Admin"
    }},
    {{
      "step": 2,
      "action": "Map Database Fields",
      "details": "Connect template variables to farmer data fields",
      "timeline": "Day 2",
      "responsible": "Tech Team"
    }},
    {{
      "step": 3,
      "action": "Build Flow Logic",
      "details": "Set up conditional routing and button responses",
      "timeline": "Day 2-3",
      "responsible": "Tech Team"
    }},
    {{
      "step": 4,
      "action": "Test Campaign",
      "details": "Send to 10 test farmers and verify personalization",
      "timeline": "Day 3",
      "responsible": "QA Team"
    }},
    {{
      "step": 5,
      "action": "Launch to Segment",
      "details": "Roll out to all {len(matched_farmers)} farmers",
      "timeline": "Day 4",
      "responsible": "Marketing"
    }}
  ],
  "revenue_breakdown": {{
    "per_farmer_value": "₹5,000",
    "total_potential": "₹{len(matched_farmers) * 5000}",
    "conversion_assumptions": "Based on segment characteristics",
    "calculation_basis": "Historical data + segment behavior"
  }}
}}

Be EXTREMELY thorough. Generate COMPLETE, ACTIONABLE content that can be used immediately.
Generate ONLY valid JSON.
"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error generating detailed segment analysis: {e}")
        return {
            'error': str(e),
            'stage_distribution': {'breakdown': [], 'key_insights': ['Error generating analysis']},
            'template_requirements': [],
            'flow_creation_prompts': []
        }

# Add template name registry for consistency
TEMPLATE_NAME_REGISTRY = {}

def _store_template_names(analysis_result):
    """Store template names from analysis for future consistency"""
    global TEMPLATE_NAME_REGISTRY
    
    for segment in analysis_result.get('segments', []):
        flow_strategy = segment.get('whatsapp_flow_strategy', {})
        for step in flow_strategy.get('steps', []):
            template_name = step.get('template_name_required')
            if template_name:
                segment_key = segment['segment_id']
                TEMPLATE_NAME_REGISTRY[segment_key] = template_name


def _get_stored_template_name(segment_id):
    """Retrieve previously stored template name"""
    return TEMPLATE_NAME_REGISTRY.get(segment_id)


# ENHANCED: Include intervention context in segment matching
def get_farmers_for_segment(segment_data, farmer_data):
    """
    Enhanced to match farmers based on intervention patterns
    """
    segment_name = segment_data['segment_name'].lower()
    matched_farmers = []
    
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    
    for farmer in farmer_data['farmers']:
        farmer_interventions = [
            i for i in farmer_data['interventions']
            if i.get('farmer_id') == farmer['farmer_id']
        ]
        
        recent_farmer_interventions = [
            i for i in farmer_interventions
            if i.get('intervention_date') and i['intervention_date'] >= thirty_days_ago
        ]
        
        # Pre-Harvest matching
        if 'harvest' in segment_name or 'pre-harvest' in segment_name:
            for crop in farmer_data['crop_details']:
                if crop.get('farmer_id') == farmer['farmer_id']:
                    days_until = crop.get('days_until_harvest')
                    if days_until and 7 <= days_until <= 30:
                        # Add intervention context
                        last_intervention = recent_farmer_interventions[0] if recent_farmer_interventions else None
                        matched_farmers.append({
                            'farmer_id': farmer['farmer_id'],
                            'farmer_name': farmer['name'],
                            'phone_number': farmer['phone_number'],
                            'farm_size': farmer['farm_size'],
                            'crop_name': crop['crop_name'],
                            'current_stage': crop.get('current_growth_stage'),
                            'days_until_harvest': days_until,
                            'harvesting_date': crop.get('harvesting_date'),
                            'last_intervention': last_intervention.get('intervention_type') if last_intervention else 'None',
                            'last_intervention_date': last_intervention.get('intervention_date') if last_intervention else None,
                            'total_interventions': len(farmer_interventions),
                            'match_reason': f"Harvesting {crop['crop_name']} in {days_until} days | {len(recent_farmer_interventions)} interventions in 30 days"
                        })
                        break
        
        # Fertilizer Upsell
        elif 'fertilizer' in segment_name:
            for crop in farmer_data['crop_details']:
                if crop.get('farmer_id') == farmer['farmer_id']:
                    stage = crop.get('current_growth_stage')
                    if stage in ['Vegetative', 'Flowering', 'Fruiting']:
                        fertilizer_interventions = [i for i in farmer_interventions if i.get('intervention_type') == 'Fertilizer']
                        last_fertilizer = fertilizer_interventions[-1] if fertilizer_interventions else None
                        
                        matched_farmers.append({
                            'farmer_id': farmer['farmer_id'],
                            'farmer_name': farmer['name'],
                            'phone_number': farmer['phone_number'],
                            'farm_size': farmer['farm_size'],
                            'crop_name': crop['crop_name'],
                            'current_stage': stage,
                            'last_fertilizer_used': last_fertilizer.get('product_used') if last_fertilizer else 'None',
                            'last_fertilizer_cost': last_fertilizer.get('price_cost') if last_fertilizer else 0,
                            'total_interventions': len(farmer_interventions),
                            'match_reason': f"{crop['crop_name']} at {stage} | Last fertilizer: {last_fertilizer.get('activity_name') if last_fertilizer else 'Never used'}"
                        })
                        break
        
        # Pesticide Service
        elif 'pesticide' in segment_name or 'pest' in segment_name:
            for crop in farmer_data['crop_details']:
                if crop.get('farmer_id') == farmer['farmer_id']:
                    stage = crop.get('current_growth_stage')
                    if stage in ['Flowering', 'Fruiting']:
                        pesticide_interventions = [i for i in farmer_interventions if i.get('intervention_type') == 'Pesticide']
                        last_pesticide = pesticide_interventions[-1] if pesticide_interventions else None
                        
                        matched_farmers.append({
                            'farmer_id': farmer['farmer_id'],
                            'farmer_name': farmer['name'],
                            'phone_number': farmer['phone_number'],
                            'farm_size': farmer['farm_size'],
                            'crop_name': crop['crop_name'],
                            'current_stage': stage,
                            'last_pesticide_used': last_pesticide.get('product_used') if last_pesticide else 'None',
                            'days_since_pesticide': (datetime.now().date() - last_pesticide['intervention_date']).days if last_pesticide and last_pesticide.get('intervention_date') else 999,
                            'total_interventions': len(farmer_interventions),
                            'match_reason': f"{crop['crop_name']} at {stage} | Pest control needed"
                        })
                        break
        
        # Inactive Farmers
        elif 'inactive' in segment_name:
            if len(recent_farmer_interventions) == 0 and farmer.get('crop_name'):
                matched_farmers.append({
                    'farmer_id': farmer['farmer_id'],
                    'farmer_name': farmer['name'],
                    'phone_number': farmer['phone_number'],
                    'farm_size': farmer['farm_size'],
                    'crop_name': farmer.get('crop_name'),
                    'last_intervention_date': farmer_interventions[-1].get('intervention_date') if farmer_interventions else 'Never',
                    'days_inactive': (datetime.now().date() - farmer_interventions[-1]['intervention_date']).days if farmer_interventions and farmer_interventions[-1].get('intervention_date') else 999,
                    'total_interventions': len(farmer_interventions),
                    'match_reason': f"No interventions in 30+ days | Last activity: {farmer_interventions[-1].get('intervention_type') if farmer_interventions else 'Never'}"
                })
        
        # High-Value Customers
        elif 'high-value' in segment_name or 'premium' in segment_name:
            if len(farmer_interventions) >= 3:
                avg_cost = sum([float(i.get('price_cost', 0)) for i in farmer_interventions]) / len(farmer_interventions)
                if avg_cost > 500:
                    matched_farmers.append({
                        'farmer_id': farmer['farmer_id'],
                        'farmer_name': farmer['name'],
                        'phone_number': farmer['phone_number'],
                        'farm_size': farmer['farm_size'],
                        'crop_name': farmer.get('crop_name'),
                        'total_interventions': len(farmer_interventions),
                        'avg_intervention_cost': round(avg_cost, 2),
                        'total_spend': round(sum([float(i.get('price_cost', 0)) for i in farmer_interventions]), 2),
                        'most_used_service': max(set([i.get('intervention_type') for i in farmer_interventions]), key=[i.get('intervention_type') for i in farmer_interventions].count),
                        'match_reason': f"High-value customer | Avg spend: ₹{round(avg_cost, 2)} | {len(farmer_interventions)} interventions"
                    })
        
        # Continue with other segment types...
        elif 'next crop' in segment_name:
            if farmer.get('next_crop_recommendation'):
                matched_farmers.append({
                    'farmer_id': farmer['farmer_id'],
                    'farmer_name': farmer['name'],
                    'phone_number': farmer['phone_number'],
                    'farm_size': farmer['farm_size'],
                    'crop_name': farmer.get('crop_name'),
                    'next_crop_recommendation': farmer['next_crop_recommendation'],
                    'soil_improvement_tip': farmer.get('soil_improvement_tip'),
                    'total_interventions': len(farmer_interventions),
                    'match_reason': f"Ready for next crop: {farmer['next_crop_recommendation']}"
                })
    
    # Remove duplicates
    seen = set()
    unique_farmers = []
    for f in matched_farmers:
        if f['farmer_id'] not in seen:
            seen.add(f['farmer_id'])
            unique_farmers.append(f)
    
    return unique_farmers[:100]
    



@csrf_exempt
def check_existing_templates_view(request):
    """
    API to check which templates exist in WhatsApp
    """
    if request.method == 'GET':
        try:
            templates = get_existing_whatsapp_templates()
            return JsonResponse({
                'status': 'success',
                'total_templates': len(templates),
                'templates': templates
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# --- API Views ---
# Add these imports at the top of your views file
from django.core.cache import cache
from datetime import datetime, timedelta
import hashlib

# Add this helper function to cache AI results
def get_cached_analysis_key():
    """Generate a cache key for AI analysis"""
    return 'farmer_ai_analysis_cache'

def get_cached_analysis():
    """Get cached AI analysis if available and not expired"""
    cache_key = get_cached_analysis_key()
    cached_data = cache.get(cache_key)
    
    if cached_data:
        # Check if cache is less than 24 hours old
        cache_time = cached_data.get('cached_at')
        if cache_time:
            cache_age = datetime.now() - datetime.fromisoformat(cache_time)
            if cache_age < timedelta(hours=24):
                return cached_data.get('data')
    
    return None

def set_cached_analysis(analysis_data):
    """Cache AI analysis for 24 hours"""
    cache_key = get_cached_analysis_key()
    cache_data = {
        'data': analysis_data,
        'cached_at': datetime.now().isoformat()
    }
    # Cache for 24 hours
    cache.set(cache_key, cache_data, 60 * 60 * 24)

def clear_analysis_cache():
    """Clear the cached analysis"""
    cache_key = get_cached_analysis_key()
    cache.delete(cache_key)
def generate_template_and_flow_prompts_combined(segments_data, farmer_data):
    """
    Generates BOTH template creation prompts AND flow prompts for each segment.
    Returns them linked by segment_id.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # Get sample farmers for context
        total_farmers = len(farmer_data.get('farmers', []))
        sample_farmers = farmer_data.get('farmers', [])[:3]
        
        # Extract segments properly
        segments = segments_data.get('segments', [])
        
        # Validate we have segments
        if not segments:
            print("WARNING: No segments found in segments_data")
            return {'segment_packages': []}
        
        print(f"Processing {len(segments)} segments for template generation")
        
        prompt = f"""
You are generating COMPLETE engagement packages for farmer segments. Each package must include:
1. Template creation prompts (Step 1)
2. Flow creation prompts (Step 2)

SEGMENTS TO PROCESS:
{json.dumps(segments, indent=2, default=str)}

SAMPLE FARMER DATA (for personalization context):
{json.dumps(sample_farmers, indent=2, default=str)}

For EACH segment, generate:

**STEP 1: TEMPLATE CREATION PROMPTS**
- 1-3 WhatsApp templates needed for this segment
- Complete Marathi/Hindi text with {{{{1}}}}, {{{{2}}}} variables
- All variable mappings to database fields
- Buttons in Marathi/Hindi
- Meta API ready JSON

**STEP 2: FLOW CREATION PROMPT**
- Complete flow structure using the templates from Step 1
- Node-by-node specification
- Edge connections

CRITICAL REQUIREMENTS:
1. Generate templates for ALL {len(segments)} segments
2. Each segment MUST have step_1_templates array (1-3 templates)
3. Each segment MUST have step_2_flow_prompt string
4. Use ONLY these database fields: registration_farmer.farmer_name, registration_farmer.phone_number, registration_farmer.farm_size_acres, registration_cropdetails.crop_name, registration_cropdetails.current_growth_stage, registration_cropdetails.harvesting_date, registration_intervention.intervention_type, registration_intervention.date
5. Language: Use 'hi' for Hindi and 'mr' for Marathi

OUTPUT FORMAT (MUST BE VALID JSON):
{{
  "segment_packages": [
    {{
      "segment_id": "segment_identifier",
      "segment_name": "Segment Name",
      "priority": "HIGH",
      "farmer_count": 100,
      "language": "hi",
      "estimated_conversion_rate": "25%",
      
      "step_1_templates": [
        {{
          "template_name": "template_name_hi",
          "template_category": "UTILITY",
          "template_language": "hi",
          "template_body": "नमस्कार {{{{1}}}},\\n\\nआपकी {{{{2}}}} एकड़ की फसल के लिए महत्वपूर्ण जानकारी...\\n\\nधन्यवाद!",
          "variables": [
            {{
              "position": 1,
              "variable_name": "farmer_name",
              "data_field": "registration_farmer.farmer_name",
              "example": "राजू पाटील"
            }},
            {{
              "position": 2,
              "variable_name": "farm_size",
              "data_field": "registration_farmer.farm_size_acres",
              "example": "3.5"
            }}
          ],
          "buttons": [
            {{"type": "QUICK_REPLY", "text": "अधिक जानकारी"}},
            {{"type": "QUICK_REPLY", "text": "बाद में बात करें"}}
          ],
          "meta_template_creation_prompt": "Complete prompt for creating this template in Meta Business Manager with all details..."
        }}
      ],
      
      "step_2_flow_prompt": "**COMPLETE FLOW SPECIFICATION**\\n\\nFLOW NAME: Flow Name\\n\\nREQUIRED TEMPLATES: template_name_hi\\n\\nFLOW STRUCTURE:\\n\\nNODE 1: Template Start\\nType: templateNode\\nData: {{selectedTemplateName: 'template_name_hi'}}\\n\\n[Complete node specifications]\\n\\nEDGES: [Complete edge specifications]",
      
      "implementation_notes": [
        "Send 7-10 days before event",
        "Follow up after 48 hours",
        "Track conversion by crop type"
      ]
    }}
  ]
}}

Generate ONLY valid JSON. Ensure ALL {len(segments)} segments have templates.
"""
        
        print("Sending prompt to Gemini API...")
        
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.7
            }
        )
        
        print("Received response from Gemini API")
        print(f"Response text length: {len(response.text)}")
        
        # Parse the JSON response
        result = json.loads(response.text)
        
        # Validate the response structure
        if not result or 'segment_packages' not in result:
            print("ERROR: Invalid response structure from AI")
            print(f"Response keys: {result.keys() if result else 'None'}")
            return {'segment_packages': []}
        
        segment_packages = result.get('segment_packages', [])
        print(f"Successfully generated {len(segment_packages)} segment packages")
        
        # Validate each package has required fields
        valid_packages = []
        for pkg in segment_packages:
            if 'step_1_templates' in pkg and 'step_2_flow_prompt' in pkg:
                print(f"✓ Package '{pkg.get('segment_name')}' has {len(pkg['step_1_templates'])} templates")
                valid_packages.append(pkg)
            else:
                print(f"✗ Package '{pkg.get('segment_name')}' is missing required fields")
        
        return {'segment_packages': valid_packages}
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Response text: {response.text[:500]}...")  # Print first 500 chars
        return {'segment_packages': []}
    except Exception as e:
        print(f"Error generating combined prompts: {e}")
        import traceback
        print(traceback.format_exc())
        return {'segment_packages': []}


@csrf_exempt
def auto_analyze_farmers_view(request):
    if request.method == 'POST':
        try:
            force_refresh = request.POST.get('force_refresh', 'false').lower() == 'true'
            
            # Check cache first
            if not force_refresh:
                cached_analysis = get_cached_analysis()
                if cached_analysis:
                    print("Returning cached analysis")
                    return JsonResponse({
                        'status': 'success',
                        'from_cache': True,
                        'cached_at': cache.get(get_cached_analysis_key()).get('cached_at'),
                        'analysis': cached_analysis.get('analysis'),
                        'segment_packages': cached_analysis.get('segment_packages'),
                        'flow_prompts': cached_analysis.get('flow_prompts'),  # Include flow prompts
                        'raw_data_summary': cached_analysis.get('raw_data_summary')
                    })
            
            print("Fetching farmer data...")
            farmer_data = get_comprehensive_farmer_data()
            
            if not farmer_data['farmers']:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No farmer data found'
                }, status=404)
            
            print(f"Analyzing {len(farmer_data['farmers'])} farmers...")
            
            # Generate analysis
            analysis_result = analyze_farmer_segments_with_ai(farmer_data)
            
            if not analysis_result:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Analysis failed'
                }, status=500)
            
            print("Analysis complete. Generating template packages...")
            
            # Generate COMBINED template + flow prompts
            try:
                segment_packages_result = generate_template_and_flow_prompts_combined(analysis_result, farmer_data)
                print(f"Template generation complete. Packages: {len(segment_packages_result.get('segment_packages', []))}")
            except Exception as pkg_error:
                print(f"Template generation failed: {pkg_error}")
                segment_packages_result = {'segment_packages': []}
            
            # Also generate flow prompts (for backward compatibility and more options)
            try:
                flow_prompts = generate_flow_prompts_from_segments(analysis_result)
                print(f"Flow prompts generated: {len(flow_prompts.get('flow_prompts', []))}")
            except Exception as flow_error:
                print(f"Flow prompt generation failed: {flow_error}")
                flow_prompts = {'flow_prompts': []}
            
            # Prepare result with ALL data
            result_data = {
                'analysis': analysis_result,
                'segment_packages': segment_packages_result,
                'flow_prompts': flow_prompts,  # Keep for backward compatibility
                'raw_data_summary': {
                    'total_farmers': len(farmer_data['farmers']),
                    'total_crops': len(farmer_data['crop_details']),
                    'total_interventions': len(farmer_data['interventions'])
                }
            }
            
            # Cache the result
            set_cached_analysis(result_data)
            
            print("Analysis cached successfully")
            
            return JsonResponse({
                'status': 'success',
                'from_cache': False,
                'cached_at': datetime.now().isoformat(),
                **result_data
            })
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Analysis failed: {e}")
            print(error_trace)
            return JsonResponse({
                'status': 'error',
                'message': str(e),
                'trace': error_trace
            }, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)
# @csrf_exempt
# def auto_analyze_farmers_view(request):
#     if request.method == 'POST':
#         try:
#             force_refresh = request.POST.get('force_refresh', 'false').lower() == 'true'
            
#             if not force_refresh:
#                 cached_analysis = get_cached_analysis()
#                 if cached_analysis:
#                     return JsonResponse({
#                         'status': 'success',
#                         'from_cache': True,
#                         'cached_at': cache.get(get_cached_analysis_key()).get('cached_at'),
#                         'analysis': cached_analysis.get('analysis'),
#                         'segment_packages': cached_analysis.get('segment_packages'),  # NEW
#                         'raw_data_summary': cached_analysis.get('raw_data_summary')
#                     })
            
#             farmer_data = get_comprehensive_farmer_data()
            
#             if not farmer_data['farmers']:
#                 return JsonResponse({
#                     'status': 'error',
#                     'message': 'No farmer data found'
#                 }, status=404)
            
#             # Generate analysis
#             analysis_result = analyze_farmer_segments_with_ai(farmer_data)
            
#             if not analysis_result:
#                 return JsonResponse({
#                     'status': 'error',
#                     'message': 'Analysis failed'
#                 }, status=500)
            
#             # Generate COMBINED template + flow prompts
#             segment_packages = generate_template_and_flow_prompts_combined(analysis_result, farmer_data)
            
#             result_data = {
#                 'analysis': analysis_result,
#                 'segment_packages': segment_packages,  # NEW - replaces flow_prompts
#                 'raw_data_summary': {
#                     'total_farmers': len(farmer_data['farmers']),
#                     'total_crops': len(farmer_data['crop_details']),
#                     'total_interventions': len(farmer_data['interventions'])
#                 }
#             }
            
#             set_cached_analysis(result_data)
            
#             return JsonResponse({
#                 'status': 'success',
#                 'from_cache': False,
#                 'cached_at': datetime.now().isoformat(),
#                 **result_data
#             })
            
#         except Exception as e:
#             import traceback
#             print(f"Analysis failed: {e}")
#             print(traceback.format_exc())
#             return JsonResponse({
#                 'status': 'error',
#                 'message': str(e)
#             }, status=500)
    
#     return JsonResponse({'error': 'Invalid method'}, status=405)


def generate_template_prompts_from_segments(segments_data, farmer_data):
    """
    Generates ready-to-use template creation prompts for each segment.
    """
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    prompt = f"""
Based on the farmer segment analysis, generate COMPLETE template creation prompts for each segment.

SEGMENT ANALYSIS:
{json.dumps(segments_data, indent=2)}

For each segment, create a DETAILED template creation prompt that includes:
1. Complete Marathi/Hindi template text with {{{{1}}}}, {{{{2}}}} variables
2. All variable mappings to database fields
3. Example values for each variable
4. Meta API JSON payload (ready to submit)
5. Button text in Marathi

OUTPUT FORMAT (JSON):
{{
  "template_prompts": [
    {{
      "segment_id": "segment_id_here",
      "segment_name": "segment name",
      "templates": [
        {{
          "template_name": "template_name_hi",
          "template_category": "UTILITY",
          "template_language": "hi",
          "template_body": "नमस्कार {{{{1}}}},\\n\\nआपकी {{{{2}}}} एकड़ की {{{{3}}}} फसल...",
          "variables": [
            {{
              "position": 1,
              "variable_name": "farmer_name",
              "data_field": "registration_farmer.farmer_name",
              "example": "राजू पाटील"
            }}
          ],
          "buttons": [
            {{"type": "QUICK_REPLY", "text": "मजदूर बुक करें"}},
            {{"type": "QUICK_REPLY", "text": "बाद में"}}
          ],
          "meta_template_creation_prompt": "**COMPLETE META API TEMPLATE SPECIFICATION**\\n\\nTemplate Name: template_name_hi\\nLanguage: hi\\nCategory: UTILITY\\n\\nBody Text:\\n[Complete text with variables]\\n\\nVariables:\\n1. {{{{1}}}} = farmer_name | Example: राजू पाटील\\n2. {{{{2}}}} = farm_size | Example: 3.5\\n\\nMeta API JSON:\\n```json\\n{{\\n  \\"name\\": \\"template_name_hi\\",\\n  \\"language\\": \\"hi\\",\\n  \\"category\\": \\"UTILITY\\",\\n  \\"components\\": [...]\\n}}\\n```"
        }}
      ]
    }}
  ]
}}

Generate ONLY valid JSON with COMPLETE template specifications.
"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error generating template prompts: {e}")
        return {'template_prompts': []}
@csrf_exempt
def refresh_analysis_cache_view(request):
    """
    Manually refresh the AI analysis cache with COMPLETE data.
    Returns same structure as auto_analyze_farmers_view.
    """
    if request.method == 'POST':
        try:
            print("Starting cache refresh...")
            
            # Clear existing cache
            clear_analysis_cache()
            print("Cache cleared")
            
            # Get fresh farmer data
            farmer_data = get_comprehensive_farmer_data()
            
            if not farmer_data['farmers']:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No farmer data found in database'
                }, status=404)
            
            print(f"Fetched {len(farmer_data['farmers'])} farmers")
            
            # Perform AI analysis
            try:
                print("Starting AI analysis...")
                analysis_result = analyze_farmer_segments_with_ai(farmer_data)
                print("AI analysis complete")
            except Exception as ai_error:
                error_msg = str(ai_error)
                print(f"AI analysis error: {error_msg}")
                
                if '429' in error_msg or 'quota' in error_msg.lower() or 'RESOURCE_EXHAUSTED' in error_msg:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'API quota exceeded. Free tier limit: 50 requests/day.',
                        'quota_info': {
                            'quota_exceeded': True,
                            'retry_message': 'Please try again tomorrow or upgrade to paid tier',
                            'daily_limit': '50 requests per day (free tier)',
                            'error_details': error_msg
                        }
                    }, status=429)
                raise ai_error
            
            if not analysis_result:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to analyze farmer data'
                }, status=500)
            
            # Validate analysis has required fields
            if not analysis_result.get('segments'):
                print("WARNING: No segments in analysis result")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Analysis did not generate segments'
                }, status=500)
            
            print(f"Analysis generated {len(analysis_result['segments'])} segments")
            
            # Generate COMBINED template + flow prompts
            try:
                print("Generating segment packages (templates + flows)...")
                segment_packages_result = generate_template_and_flow_prompts_combined(
                    analysis_result, 
                    farmer_data
                )
                
                if segment_packages_result and segment_packages_result.get('segment_packages'):
                    print(f"Generated {len(segment_packages_result['segment_packages'])} segment packages")
                else:
                    print("WARNING: No segment packages generated")
                    segment_packages_result = {'segment_packages': []}
                    
            except Exception as pkg_error:
                print(f"Segment package generation failed: {pkg_error}")
                import traceback
                print(traceback.format_exc())
                segment_packages_result = {'segment_packages': []}
            
            # Generate flow prompts (for backward compatibility)
            try:
                print("Generating flow prompts...")
                flow_prompts =generate_flow_prompts_from_segments(analysis_result)
                print(f"Generated {len(flow_prompts.get('flow_prompts', []))} flow prompts")
            except Exception as flow_error:
                print(f"Flow prompt generation failed: {flow_error}")
                flow_prompts = {'flow_prompts': []}
            
            # Prepare complete result data
            result_data = {
                'analysis': analysis_result,
                'segment_packages': segment_packages_result,  # NEW: Complete templates + flows
                'flow_prompts': flow_prompts,  # Keep for compatibility
                'raw_data_summary': {
                    'total_farmers': len(farmer_data['farmers']),
                    'total_crops': len(farmer_data['crop_details']),
                    'total_interventions': len(farmer_data['interventions'])
                }
            }
            
            # Cache the complete result
            set_cached_analysis(result_data)
            print("Result cached successfully")
            
            current_time = datetime.now().isoformat()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Analysis cache refreshed successfully',
                'from_cache': False,
                'cached_at': current_time,
                'analysis': analysis_result,
                'segment_packages': segment_packages_result,
                'flow_prompts': flow_prompts,
                'raw_data_summary': result_data['raw_data_summary']
            })
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Refresh failed: {e}")
            print(error_trace)
            return JsonResponse({
                'status': 'error',
                'message': f"Refresh failed: {str(e)}",
                'trace': error_trace
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# ADD this view to check cache status
@csrf_exempt
def get_cache_status_view(request):
    """
    Get information about the current cache status
    """
    if request.method == 'GET':
        cache_key = get_cached_analysis_key()
        cached_data = cache.get(cache_key)
        
        if cached_data:
            cache_time = datetime.fromisoformat(cached_data.get('cached_at'))
            cache_age = datetime.now() - cache_time
            
            return JsonResponse({
                'status': 'success',
                'has_cache': True,
                'cached_at': cached_data.get('cached_at'),
                'cache_age_hours': cache_age.total_seconds() / 3600,
                'cache_valid': cache_age < timedelta(hours=24),
                'expires_in_hours': max(0, 24 - (cache_age.total_seconds() / 3600))
            })
        else:
            return JsonResponse({
                'status': 'success',
                'has_cache': False,
                'message': 'No cached analysis available'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def get_segment_details_view(request):
    """
    Get detailed information about a specific farmer segment
    OPTIMIZED: Uses cached analysis instead of regenerating
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            segment_id = data.get('segment_id')
            
            if not segment_id:
                return JsonResponse({'error': 'Segment ID not provided'}, status=400)
            
            # Try to get cached analysis first
            cached_analysis = get_cached_analysis()
            
            if not cached_analysis:
                # If no cache, get fresh data
                farmer_data = get_comprehensive_farmer_data()
                
                if not farmer_data['farmers']:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'No farmer data found'
                    }, status=404)
                
                try:
                    analysis_result = analyze_farmer_segments_with_ai(farmer_data)
                except Exception as e:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Analysis failed: {str(e)}'
                    }, status=500)
                
                if not analysis_result:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Failed to analyze data'
                    }, status=500)
            else:
                # Use cached analysis
                analysis_result = cached_analysis.get('analysis')
                farmer_data = get_comprehensive_farmer_data()  # Get fresh farmer data for matching
            
            # Find specific segment
            target_segment = None
            for segment in analysis_result.get('segments', []):
                if segment['segment_id'] == segment_id:
                    target_segment = segment
                    break
            
            if not target_segment:
                return JsonResponse({'error': 'Segment not found'}, status=404)
            
            # Get detailed analysis for this segment
            # Use cached if available
            cache_key = f'segment_details_{segment_id}'
            cached_details = cache.get(cache_key)
            
            if cached_details:
                segment_details = cached_details
            else:
                try:
                    segment_details = generate_detailed_segment_analysis(
                        segment=target_segment,
                        farmer_data=farmer_data
                    )
                    # Cache for 6 hours
                    cache.set(cache_key, segment_details, 60 * 60 * 6)
                except Exception as e:
                    print(f"Error generating segment details: {e}")
                    segment_details = {
                        'error': 'Could not generate detailed analysis',
                        'message': str(e)
                    }
            
            return JsonResponse({
                'status': 'success',
                'segment': target_segment,
                'detailed_analysis': segment_details
            })
            
        except Exception as e:
            import traceback
            print(f"Error in get_segment_details_view: {e}")
            print(traceback.format_exc())
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def get_segment_farmers_view(request):
    """
    Returns the actual farmer list for a specific segment
    OPTIMIZED: Uses cached analysis, only fetches fresh farmer data
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            segment_id = data.get('segment_id')
            
            if not segment_id:
                return JsonResponse({'error': 'Segment ID not provided'}, status=400)
            
            # Get all farmer data
            farmer_data = get_comprehensive_farmer_data()
            
            if not farmer_data['farmers']:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No farmer data found'
                }, status=404)
            
            # Try to get cached analysis
            cached_analysis = get_cached_analysis()
            
            if not cached_analysis:
                # If no cache, generate new analysis
                try:
                    analysis_result = analyze_farmer_segments_with_ai(farmer_data)
                except Exception as e:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Analysis failed: {str(e)}'
                    }, status=500)
                
                if not analysis_result:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Failed to analyze data'
                    }, status=500)
            else:
                # Use cached analysis
                analysis_result = cached_analysis.get('analysis')
            
            # Find the segment
            target_segment = None
            for segment in analysis_result.get('segments', []):
                if segment['segment_id'] == segment_id:
                    target_segment = segment
                    break
            
            if not target_segment:
                return JsonResponse({'error': 'Segment not found'}, status=404)
            
            # Check if farmers are cached for this segment
            farmers_cache_key = f'segment_farmers_{segment_id}'
            cached_farmers = cache.get(farmers_cache_key)
            
            if cached_farmers:
                farmers = cached_farmers
            else:
                # Get matched farmers
                farmers = get_farmers_for_segment(target_segment, farmer_data)
                # Cache for 1 hour
                cache.set(farmers_cache_key, farmers, 60 * 60)
            
            return JsonResponse({
                'status': 'success',
                'segment_name': target_segment['segment_name'],
                'total_farmers': len(farmers),
                'farmers': farmers
            })
            
        except Exception as e:
            import traceback
            print(f"Error in get_segment_farmers_view: {e}")
            print(traceback.format_exc())
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def generate_calendar_events(farmer_data):
    """
    Generates a calendar view of all important dates for farmers
    """
    from datetime import datetime, timedelta
    
    events = []
    today = datetime.now().date()
    
    # Harvest dates
    for crop in farmer_data['crop_details']:
        if crop.get('harvesting_date'):
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == crop['farmer_id']), None)
            if farmer:
                events.append({
                    'date': crop['harvesting_date'],
                    'event_type': 'harvest',
                    'priority': 'HIGH' if (crop['harvesting_date'] - today).days <= 7 else 'MEDIUM',
                    'title': f"Harvest: {crop['crop_name']}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']} harvesting {crop['crop_name']}",
                    'action_needed': 'Contact for labor booking',
                    'days_until': (crop['harvesting_date'] - today).days
                })
        
        # Growth stage transitions
        if crop.get('flowering_stage_start'):
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == crop['farmer_id']), None)
            if farmer and crop['flowering_stage_start'] >= today:
                events.append({
                    'date': crop['flowering_stage_start'],
                    'event_type': 'growth_stage',
                    'priority': 'MEDIUM',
                    'title': f"Flowering Stage: {crop['crop_name']}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']}'s {crop['crop_name']} entering flowering stage",
                    'action_needed': 'Send flowering care tips',
                    'days_until': (crop['flowering_stage_start'] - today).days
                })
        
        if crop.get('fruiting_stage_start'):
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == crop['farmer_id']), None)
            if farmer and crop['fruiting_stage_start'] >= today:
                events.append({
                    'date': crop['fruiting_stage_start'],
                    'event_type': 'growth_stage',
                    'priority': 'MEDIUM',
                    'title': f"Fruiting Stage: {crop['crop_name']}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']}'s {crop['crop_name']} entering fruiting stage",
                    'action_needed': 'Send fruiting care tips & nutrient recommendations',
                    'days_until': (crop['fruiting_stage_start'] - today).days
                })
    
    # Scheduled interventions (if any future interventions exist)
    for intervention in farmer_data['interventions']:
        if intervention.get('date') and intervention['date'] >= today:
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == intervention['farmer_id']), None)
            if farmer:
                events.append({
                    'date': intervention['date'],
                    'event_type': 'intervention',
                    'priority': 'HIGH',
                    'title': f"{intervention['intervention_type']}: {intervention.get('crop_name')}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']} scheduled {intervention['intervention_type']}",
                    'action_needed': f"Remind about {intervention['intervention_type']}",
                    'days_until': (intervention['date'] - today).days
                })
    
    # Sort events by date
    events.sort(key=lambda x: x['date'])
    
    # Filter to next 90 days
    ninety_days_later = today + timedelta(days=90)
    events = [e for e in events if e['date'] <= ninety_days_later]
    
    return events



import requests
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from collections import defaultdict
from datetime import datetime, timedelta
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Helper function to match templates to event types
def match_template_to_event(event, approved_templates):
    """
    Intelligently matches approved WhatsApp templates to calendar events
    Returns best matching template or None
    """
    event_type = event.get('event_type')
    event_title = event.get('title', '').lower()
    
    # Define template matching rules
    template_keywords = {
        'harvest': ['harvest', 'labor', 'labour', 'worker', 'booking', 'pre_harvest'],
        'growth_stage': ['growth', 'stage', 'flowering', 'fruiting', 'vegetative', 'care', 'tips'],
        'intervention': ['intervention', 'pesticide', 'fertilizer', 'spray', 'treatment']
    }
    
    # Find matching templates
    matched_templates = []
    keywords = template_keywords.get(event_type, [])
    
    for template in approved_templates:
        template_name = template['name'].lower()
        
        # Check if any keyword matches
        for keyword in keywords:
            if keyword in template_name:
                matched_templates.append({
                    'template_name': template['name'],
                    'template_language': template['language'],
                    'template_category': template['category'],
                    'match_reason': f"Matched keyword: {keyword}",
                    'confidence': 'HIGH' if keyword in event_title else 'MEDIUM'
                })
                break
    
    return matched_templates[0] if matched_templates else None


def match_flow_to_event(event, approved_flows):
    """
    Matches WhatsApp flows to calendar events
    Returns best matching flow or None
    """
    event_type = event.get('event_type')
    event_title = event.get('title', '').lower()
    
    # Define flow matching rules
    flow_keywords = {
        'harvest': ['labor', 'labour', 'booking', 'harvest', 'worker'],
        'growth_stage': ['care', 'tips', 'recommendation', 'stage'],
        'intervention': ['intervention', 'service', 'consultation', 'diagnostic']
    }
    
    matched_flows = []
    keywords = flow_keywords.get(event_type, [])
    
    for flow in approved_flows:
        flow_name = flow['name'].lower()
        
        for keyword in keywords:
            if keyword in flow_name:
                matched_flows.append({
                    'flow_name': flow['name'],
                    'flow_id': flow['flow_id'],
                    'match_reason': f"Matched keyword: {keyword}",
                    'confidence': 'HIGH' if keyword in event_title else 'MEDIUM'
                })
                break
    
    return matched_flows[0] if matched_flows else None


def generate_template_creation_prompt(event, farmer_data):
    """
    Generates AI prompt to create a new WhatsApp template for an event
    when no suitable template exists
    """
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    prompt = f"""
Generate a WhatsApp template creation prompt for the following farming event:

EVENT DETAILS:
- Event Type: {event.get('event_type')}
- Title: {event.get('title')}
- Date: {event.get('date')}
- Priority: {event.get('priority')}
- Action Needed: {event.get('action_needed')}
- Farmer: {event.get('farmer_name')}
- Details: {event.get('details')}

FARMER CONTEXT:
- Phone: {farmer_data.get('phone_number')}
- Farm Size: {farmer_data.get('farm_size')} acres
- Crop: {farmer_data.get('crop_name', 'Unknown')}

Generate a SINGLE WhatsApp template (not a flow) in this format:

OUTPUT (JSON):
{{
  "template_name": "descriptive_name_hi",
  "template_category": "UTILITY or MARKETING",
  "template_language": "hi",
  "template_body": "नमस्ते {{{{1}}}},\\n\\n[Personalized message in Hindi about the event]\\n\\nधन्यवाद!",
  "variables": [
    {{
      "position": 1,
      "variable_name": "farmer_name",
      "data_field": "registration_farmer.farmer_name",
      "example": "राजू पाटील"
    }},
    {{
      "position": 2,
      "variable_name": "relevant_field",
      "data_field": "database.field",
      "example": "example value"
    }}
  ],
  "buttons": [
    {{"type": "QUICK_REPLY", "text": "हाँ, रुचि है"}},
    {{"type": "QUICK_REPLY", "text": "बाद में"}}
  ],
  "meta_template_creation_prompt": "Complete prompt for Meta Business Manager..."
}}

Make the template:
1. Highly relevant to the event type
2. Personalized with at least 3-5 variables
3. Action-oriented with clear call-to-action
4. In Hindi (hi) language
5. Ready to submit to Meta

Generate ONLY valid JSON.
"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        import json
        template_prompt = json.loads(response.text)
        return template_prompt
    except Exception as e:
        logger.error(f"Template prompt generation failed: {e}")
        return {
            "error": "Could not generate template prompt",
            "message": str(e)
        }


def generate_calendar_events(farmer_data):
    """
    Generates a calendar view of all important dates for farmers
    """
    from datetime import datetime, timedelta
    
    events = []
    today = datetime.now().date()
    
    # Harvest dates
    for crop in farmer_data['crop_details']:
        if crop.get('harvesting_date'):
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == crop['farmer_id']), None)
            if farmer:
                events.append({
                    'date': crop['harvesting_date'],
                    'event_type': 'harvest',
                    'priority': 'HIGH' if (crop['harvesting_date'] - today).days <= 7 else 'MEDIUM',
                    'title': f"Harvest: {crop['crop_name']}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']} harvesting {crop['crop_name']}",
                    'action_needed': 'Contact for labor booking',
                    'days_until': (crop['harvesting_date'] - today).days
                })
        
        # Growth stage transitions
        if crop.get('flowering_stage_start'):
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == crop['farmer_id']), None)
            if farmer and crop['flowering_stage_start'] >= today:
                events.append({
                    'date': crop['flowering_stage_start'],
                    'event_type': 'growth_stage',
                    'priority': 'MEDIUM',
                    'title': f"Flowering Stage: {crop['crop_name']}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']}'s {crop['crop_name']} entering flowering stage",
                    'action_needed': 'Send flowering care tips',
                    'days_until': (crop['flowering_stage_start'] - today).days
                })
        
        if crop.get('fruiting_stage_start'):
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == crop['farmer_id']), None)
            if farmer and crop['fruiting_stage_start'] >= today:
                events.append({
                    'date': crop['fruiting_stage_start'],
                    'event_type': 'growth_stage',
                    'priority': 'MEDIUM',
                    'title': f"Fruiting Stage: {crop['crop_name']}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']}'s {crop['crop_name']} entering fruiting stage",
                    'action_needed': 'Send fruiting care tips & nutrient recommendations',
                    'days_until': (crop['fruiting_stage_start'] - today).days
                })
    
    # Scheduled interventions (if any future interventions exist)
    for intervention in farmer_data['interventions']:
        if intervention.get('date') and intervention['date'] >= today:
            farmer = next((f for f in farmer_data['farmers'] if f['farmer_id'] == intervention['farmer_id']), None)
            if farmer:
                events.append({
                    'date': intervention['date'],
                    'event_type': 'intervention',
                    'priority': 'HIGH',
                    'title': f"{intervention['intervention_type']}: {intervention.get('crop_name')}",
                    'farmer_name': farmer['name'],
                    'farmer_phone': farmer['phone_number'],
                    'farmer_id': farmer['farmer_id'],
                    'details': f"{farmer['name']} scheduled {intervention['intervention_type']}",
                    'action_needed': f"Remind about {intervention['intervention_type']}",
                    'days_until': (intervention['date'] - today).days
                })
    
    # Sort events by date
    events.sort(key=lambda x: x['date'])
    
    # Filter to next 90 days
    ninety_days_later = today + timedelta(days=90)
    events = [e for e in events if e['date'] <= ninety_days_later]
    
    return events




@csrf_exempt
def get_calendar_view(request):
    """
    Returns calendar events for all important farmer dates
    """
    if request.method == 'GET':
        try:
            farmer_data = get_comprehensive_farmer_data()
            events = generate_calendar_events(farmer_data)
            
            # Group events by date for easier frontend rendering
            from collections import defaultdict
            events_by_date = defaultdict(list)
            
            for event in events:
                date_str = event['date'].strftime('%Y-%m-%d')
                events_by_date[date_str].append(event)
            
            return JsonResponse({
                'status': 'success',
                'total_events': len(events),
                'events': events,
                'events_by_date': dict(events_by_date)
            })
            
        except Exception as e:
            import traceback
            print(f"Error in get_calendar_view: {e}")
            print(traceback.format_exc())
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def generate_query_view(request):
    """
    API View to generate an SQL query from a natural language request.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('query')
            if not query:
                return JsonResponse({'error': 'Query not provided'}, status=400)

            sql_query, used_tables = generate_sql_from_llm(query)

            # # Security Check: Ensure the generated query is safe
            # if not sql_query.strip().upper().startswith('SELECT'):
            #     return JsonResponse({'error': 'Generated query is not a SELECT statement. Aborting.'}, status=400)

            return JsonResponse({
                'sql_query': sql_query,
                'used_tables': used_tables,
                'full_schema': get_db_schema()
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def execute_query_view(request):
    """
    API View to execute a SQL query (either as a test or full run).
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            sql_query = data.get('sql_query')
            test_run = data.get('test_run', False)

            if not sql_query:
                return JsonResponse({'error': 'SQL query not provided'}, status=400)

            # # Security Check: Double-check that it's a safe query
            # if not sql_query.strip().upper().startswith('SELECT'):
            #     return JsonResponse({'error': 'Only SELECT statements can be executed.'}, status=403)

            final_query = sql_query
            if test_run:
                # Add a LIMIT clause for the test run
                final_query = f"{sql_query.rstrip(';')} LIMIT 100;"

            with connection.cursor() as cursor:
                cursor.execute(final_query)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Suggest a chart type based on the results
            chart_type = 'table'
            if len(results) > 0:
                first_row = results[0]
                if len(first_row.keys()) == 2:
                    key1, key2 = list(first_row.keys())
                    # If one column is text-like and the other is numeric, suggest bar or pie
                    if isinstance(first_row[key1], str) and isinstance(first_row[key2], (int, float)):
                        chart_type = 'bar' if len(results) > 5 else 'pie'

            return JsonResponse({'results': results, 'chart_type': chart_type})
        except Exception as e:
            return JsonResponse({'error': f"Database query failed: {e}"}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def generate_sql_from_llm(user_query: str):
    """
    Generates a secure, read-only SQL query from a natural language prompt using the Gemini API.
    """
    db_schema = get_db_schema()
    if not db_schema:
        return "-- Failed to retrieve database schema.", []

    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    json_output_config = {
        "response_mime_type": "application/json",
    }

    prompt = f"""
    You are a PostgreSQL expert data analyst. Your task is to convert a user's question into a valid, performant, and secure PostgreSQL query and identify which tables were used.

    Here is the database schema you must use:
    {db_schema}

    Analyze the user's question and the schema to construct a read-only SQL query.

    Rules:
    1.  CRITICAL: Only generate `SELECT` statements. Never generate `INSERT`, `UPDATE`, `DELETE`, `DROP`, `GRANT`, or any other data-modifying statements.
    2.  Only use tables and columns present in the provided schema.
    3.  If a table name includes a prefix (like 'registration_'), you must include it in the query.
    4.  Return the result as a JSON object with two keys: "sql_query" which contains the generated SQL string, and "used_tables" which is a list of the table names you used in the query.
    5. MOST IMPORTANT CRITICAL: If the user's question cannot be answered with the provided schema, return a JSON object with "sql_query" set to "-- Unable to generate a valid SQL query with the provided schema." and "used_tables" as an empty list.
    
    User Question: "{user_query}"

    JSON Response:
    """
    
    try:
        response = model.generate_content(prompt, generation_config=json_output_config)
        print(response.text)
        
        result_json = json.loads(response.text)
        sql_query = result_json.get("sql_query", "-- Failed to generate SQL.")
        used_tables = result_json.get("used_tables", [])
        
        return sql_query, used_tables

    except Exception as e:
        print(f"An error occurred with the Gemini API call: {e}")
        return f"-- An error occurred: {e}", []       