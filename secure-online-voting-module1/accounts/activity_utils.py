"""Small, privacy-conscious helpers for account security activity.

Do not trust user-supplied X-Forwarded-For; deployment behind a reverse proxy
requires a separately reviewed trusted-proxy configuration.
"""
import ipaddress

from django.utils.crypto import salted_hmac


def client_ip(request):
    if request is None:
        return None
    candidate = request.META.get('REMOTE_ADDR', '')
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_device(request):
    if request is None:
        return 'Unknown device', ''
    agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    if 'Edg/' in agent:
        browser = 'Edge'
    elif 'Firefox/' in agent:
        browser = 'Firefox'
    elif 'Chrome/' in agent:
        browser = 'Chrome'
    elif 'Safari/' in agent:
        browser = 'Safari'
    else:
        browser = 'Other browser'

    if 'Android' in agent:
        platform = 'Android'
    elif 'iPhone' in agent or 'iPad' in agent:
        platform = 'iOS'
    elif 'Windows' in agent:
        platform = 'Windows'
    elif 'Macintosh' in agent:
        platform = 'macOS'
    elif 'Linux' in agent:
        platform = 'Linux'
    else:
        platform = 'Unknown OS'
    name = f'{browser} / {platform}'
    # Fingerprinting can change when IP/UA changes. This signals a *context*,
    # not a proven physical device identity.
    ip = client_ip(request) or ''
    fingerprint = salted_hmac('voting-account-context-v1', f'{agent}|{ip}', algorithm='sha256').hexdigest()
    return name, fingerprint
