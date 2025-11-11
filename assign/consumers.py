import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

class JobUpdatesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join job updates group
        self.room_group_name = 'job_updates'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        # Leave job updates group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        # We don't expect clients to send messages in this implementation
        pass

    # Handlers for different types of updates
    async def job_status_changed(self, event):
        await self.send(text_data=json.dumps({
            'type': 'job_status_changed',
            'data': event['data']
        }))

    async def new_bid(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_bid', 
            'data': event['data']
        }))

    async def bid_updated(self, event):
        await self.send(text_data=json.dumps({
            'type': 'bid_updated',
            'data': event['data']
        }))

    async def job_assigned(self, event):
        await self.send(text_data=json.dumps({
            'type': 'job_assigned',
            'data': event['data']
        }))