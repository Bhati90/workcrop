import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from reply.models import WhatsAppTemplate


class Command(BaseCommand):
    help = 'Sync WhatsApp templates from Meta Business API'

    def handle(self, *args, **options):
        access_token = settings.WHATSAPP_CONFIG['ACCESS_TOKEN']
        business_account_id = settings.WHATSAPP_CONFIG['BUSINESS_ACCOUNT_ID']
        api_version = settings.WHATSAPP_CONFIG['API_VERSION']
        
        url = f"https://graph.facebook.com/{api_version}/{business_account_id}/message_templates"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        params = {
            'limit': 100,
        }
        
        try:
            self.stdout.write('Fetching templates from Meta API...')
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            templates = data.get('data', [])
            
            self.stdout.write(f'Found {len(templates)} template(s)')
            
            synced_count = 0
            
            for template_data in templates:
                name = template_data['name']
                language = template_data['language']
                status = template_data['status'].lower()
                category = template_data['category'].lower()
                
                self.stdout.write(f'\nProcessing: {name} ({language}) - Status: {status}')
                
                # Parse components
                components = template_data.get('components', [])
                header_text = None
                body_text = ''
                footer_text = None
                header_type = None
                buttons = []
                header_params_count = 0
                body_params_count = 0
                
                for component in components:
                    comp_type = component['type']
                    
                    if comp_type == 'HEADER':
                        header_type = component.get('format', '').lower()
                        header_text = component.get('text', '')
                        if header_text:
                            header_params_count = header_text.count('{{')
                    
                    elif comp_type == 'BODY':
                        body_text = component.get('text', '')
                        body_params_count = body_text.count('{{')
                    
                    elif comp_type == 'FOOTER':
                        footer_text = component.get('text', '')
                    
                    elif comp_type == 'BUTTONS':
                        buttons = component.get('buttons', [])
                
                # Create or update template
                template, created = WhatsAppTemplate.objects.update_or_create(
                    name=name,
                    language=language,
                    defaults={
                        'status': status,
                        'category': category,
                        'header_type': header_type,
                        'header_text': header_text,
                        'body_text': body_text,
                        'footer_text': footer_text,
                        'buttons': buttons if buttons else None,
                        'header_params_count': header_params_count,
                        'body_params_count': body_params_count,
                    }
                )
                
                action = 'Created' if created else 'Updated'
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{action}: {name} ({language}) - Status: {status}'
                    )
                )
                synced_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully synced {synced_count} template(s)'
                )
            )
            
            # Show summary by status
            approved = WhatsAppTemplate.objects.filter(status='approved').count()
            pending = WhatsAppTemplate.objects.filter(status='pending').count()
            rejected = WhatsAppTemplate.objects.filter(status='rejected').count()
            
            self.stdout.write('\nSummary:')
            self.stdout.write(f'  Approved: {approved}')
            self.stdout.write(f'  Pending: {pending}')
            self.stdout.write(f'  Rejected: {rejected}')
            
        except requests.exceptions.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error fetching templates: {str(e)}')
            )
            if hasattr(e, 'response') and e.response is not None:
                self.stdout.write(
                    self.style.ERROR(f'Response: {e.response.text}')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error: {str(e)}')
            )