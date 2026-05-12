# notifications/signals.py
# ─────────────────────────────────────────────────────────────────────────────
# Connects Django model signals to notification creation.
# Import this in notifications/apps.py ready() method.
# ─────────────────────────────────────────────────────────────────────────────

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender='leads.Lead')
def on_lead_saved(sender, instance, created, **kwargs):
    """Notify agent when a lead is assigned to them."""
    try:
        from .service import notify_lead_assigned
        if instance.assigned_agent:
            # Only notify on assignment (new lead or assignment change)
            if created:
                notify_lead_assigned(instance, instance.assigned_agent)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error('Lead assignment notification failed: %s', e)


@receiver(post_save, sender='leads.LeadTask')
def on_task_saved(sender, instance, created, **kwargs):
    """Notify assigned agent when a task is created for them."""
    try:
        from .service import notify_task_assigned
        if created and instance.assigned_to and instance.assigned_to != instance.created_by:
            notify_task_assigned(instance, instance.assigned_to)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error('Task notification failed: %s', e)


@receiver(post_save, sender='leads.WAMessage')
def on_wa_message(sender, instance, created, **kwargs):
    """Notify the assigned agent on new inbound WhatsApp message."""
    try:
        if not created or instance.direction != 'inbound':
            return
        from .service import notify_whatsapp_received
        conv = instance.conversation
        lead = conv.lead
        agent = conv.assigned_agent or lead.assigned_agent
        if agent:
            notify_whatsapp_received(lead, agent, instance.body or '')
    except Exception as e:
        import logging
        logging.getLogger(__name__).error('WA message notification failed: %s', e)
