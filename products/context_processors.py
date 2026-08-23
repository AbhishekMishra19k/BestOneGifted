from django.conf import settings


def whatsapp(request):
    """Expose the business WhatsApp number to every template as
    {{ whatsapp_number }}, so it's set in one place (settings/.env) instead
    of being hardcoded in multiple template files."""
    return {'whatsapp_number': getattr(settings, 'WHATSAPP_BUSINESS_NUMBER', '919201461413')}
