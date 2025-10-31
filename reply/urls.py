from django.urls import path
from . import views

urlpatterns = [
    path('webhook/', views.whatsapp_webhook, name='webhook'),
    path('chat', views.chat_list_view, name='chat_list'),
    path('chat/<int:user_id>/', views.chat_detail_view, name='chat_detail'),
    path('api/send-message/', views.send_message_api, name='send_message'),
    path('api/upload-media/', views.upload_media_api, name='upload_media'),
    path('api/add-contact/', views.add_contact_api, name='add_contact'), 
]