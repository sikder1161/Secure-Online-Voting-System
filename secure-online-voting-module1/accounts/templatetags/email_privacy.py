"""Django template filter for safely displaying masked email addresses."""
from django import template
from accounts.email_masking import mask_email_address

register = template.Library()


@register.filter(name="mask_email")
def mask_email(value):
    return mask_email_address(value)
