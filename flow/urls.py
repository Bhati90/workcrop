from django.contrib import admin
from . import views
from django.urls import path

urlpatterns = [
    path('api/upload-image-to-meta/', views.upload_image_to_meta_api, name='api_upload_image_to_meta'),
    path('api/upload-media-to-meta/', views.upload_media_to_meta_api, name='api_upload_media_to_meta'),
   
    # path('api/templates/', views.get_whatsapp_templates_api, name='get_whatsapp_templates_api'),
    # path('api/flows/save/', views.save_flow_api, name='save_flow_api'),
    path('webhook/', views.whatsapp_webhook_view, name='whatsapp_webhook'),
    # path('api/flows/list/', views.get_flows_list_api, name='api_list_flows'),
    path('api/attributes/', views.attribute_list_create_view, name='attribute-list-create'),
    path('api/attributes/<int:pk>/', views.attribute_detail_view, name='attribute-detail'),
    # path('api/initiate-call/', views.initiate_whatsapp_call_view, name='initiate_whatsapp_call'),
    # path('api/get-flow-details/<str:flow_id>/', views.get_flow_details_api_view, name='get_flow_details_api'),

#    path('api/whatsapp-forms/', views.get_whatsapp_forms_api, name='get_whatsapp_forms'),
    path('api/whatsapp-forms/<int:form_id>/', views.flow_form_detail_api, name='flow_form_detail'),
    
    # Webhook endpoints
    # path('webhook/whatsapp/', views.whatsapp_webhook_view, name='whatsapp_webhook'),
    # path('webhook/whatsapp-flows/', views.whatsapp_flow_webhook_view, name='whatsapp_flow_webhook'),
    # path('api/save-flow/', views.save_flow_api, name='save_flow'),
    # path('flow-builder/', views.flow_builder_view, name='flow_builder'),
    # 
    #  path('webhook/', views.webhook_verify, name='webhook_verify'),  # GET
    # path('webhook/', views.webhook_handler, name='webhook_handler'),  # POST
    
    # Twilio callback endpoints
   
    # Add test endpoint
    # path('twilio-status-test/', views.twilio_status_test, name='twilio_status_test'),
    
    # Manual controls
    # path('terminate-call/', views.terminate_call, name='terminate_call'),
    # path('webhook/', production_webhook_view, name='whatsapp_webhook'),
    # path('health/', production_health_check, name='health_check'),
    # path('api/flows/<int:flow_id>/update/', views.update_flow, name='update_flow'),
    # # In your urls.py file, add this to urlpatterns:
    # # path('echo/', views.test_echo_endpoint, name='test_echo'),
    # # --- ADD THESE NEW URLS ---
    # path('api/flows/<int:flow_id>/', views.get_flow_detail_api, name='api_get_flow_detail'),
    # path('api/flows/<int:flow_id>/status/', views.update_flow_status_api, name='api_update_flow_status'),
    # path('api/flows/<int:flow_id>/delete/', views.delete_flow_api, name='api_delete_flow'),
    

        # FIXED: Call handling webhooks
    # path('business-answer/<str:call_id>/', views.business_answer_webhook, name='business_answer'),
    # path('business-accept/<str:call_id>/', views.business_accept_webhook, name='business_accept'), 
    # path('business-decline/<str:call_id>/', views.business_decline_webhook, name='business_decline'),
    # path('bridge-connect/<str:call_id>/', views.bridge_connect_webhook, name='bridge_connect'),
    # path('conference-joined/<str:call_id>/', views.conference_joined_webhook, name='conference_joined'),

    # # FIXED: Status webhooks
    # path('call-status/<str:call_id>/<str:call_type>/', views.call_status_webhook, name='call_status'),
    # path('conference-status/<str:call_id>/', views.conference_status_webhook, name='conference_status'),
    # path('dial-result/<str:call_id>/<str:call_type>/', views.dial_result_webhook, name='dial_result'),
    
    # # Debug and utility endpoints
    # path('debug-calls/', views.debug_active_calls, name='debug_calls'),
    # path('test-business/', views.test_business_number, name='test_business'),
    # path('terminate-call/', views.terminate_call, name='terminate_call'),
    # path('health/', views.system_health, name='system_health'),
    path('api/flows/generate-ai/', views.generate_flow_with_ai, name='api_generate_flow_ai'),
    path('api/flows/ai-list/', views.get_ai_generated_flows, name='api_ai_flows_list'),
    

    path('api/template-generator/generate/', views.generate_multiple_templates, name='generate_templates'),
    path('api/template-generator/submit/', views.submit_customized_template, name='submit_customized_template'),
    

    path('api/template-flow/analyze/', views.analyze_and_generate_template, name='analyze_template'),
    path('api/template-flow/submit/', views.submit_template_to_meta, name='submit_template'),
    path('api/template-flow/status/<str:template_name>/', views.check_template_status, name='check_template_status'),
    path('api/template-flow/create-flow/', views.auto_create_flow_after_approval, name='auto_create_flow'),
    
   path('api/flows/analyze-with-language/', views.analyze_flow_with_language_preference, name='analyze_with_language'),
    path('api/flows/create-with-refinement/', views.create_flow_with_refined_requirements, name='create_with_refinement'),
    

    path('api/flows/generate-smart/', views.generate_flow_with_smart_template_detection, name='generate_smart_flow'),
    path('api/flows/resume-with-templates/', views.create_templates_and_resume_flow, name='resume_flow_creation'),
    
    

    path('api/flows/list/', views.get_flows_list_api, name='api_flows_list'),
    path('api/flows/save/', views.save_flow_api, name='api_save_flow'),
    path('api/flows/<int:flow_id>/', views.get_flow_detail_api, name='api_get_flow_detail'),
    path('api/flows/<int:flow_id>/update/', views.update_flow_api, name='api_update_flow'),
    path('api/flows/<int:flow_id>/status/', views.update_flow_status_api, name='api_update_flow_status'),
    path('api/flows/<int:flow_id>/delete/', views.delete_flow_api, name='api_delete_flow'),
    
    # WhatsApp Forms and Templates
    path('api/whatsapp-forms/', views.get_whatsapp_forms_api, name='api_whatsapp_forms'),
    path('api/templates/', views.get_whatsapp_templates_api, name='api_whatsapp_templates'),
    
    # Legacy/Alternative endpoints (if needed for backward compatibility)
    path('get-flow-details/<str:flow_id>/', views.get_flow_detail_api, name='get_flow_details'),
    

]