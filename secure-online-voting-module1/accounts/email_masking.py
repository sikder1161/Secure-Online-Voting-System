"""Privacy-friendly display of email addresses in templates.

This is presentation masking only: actual account emails and SMTP recipients
remain unchanged. It is not encryption or an authorization mechanism.
"""


def mask_email_address(value):
    """Return a partially hidden email address without revealing the original.

    Examples: neutonsikder01@gmail.com -> ne**********01@g****.com
              a@b.co -> *@*.co
    """
    if not isinstance(value, str):
        return "Email unavailable"
    value = value.strip()
    if value.count("@") != 1:
        return "Email unavailable"
    local, host = value.rsplit("@", 1)
    if not local or "." not in host or host.startswith(".") or host.endswith("."):
        return "Email unavailable"
    host_name, suffix = host.rsplit(".", 1)
    if not host_name or not suffix:
        return "Email unavailable"

    if len(local) <= 2:
        local_masked = "*" * len(local)
    elif len(local) <= 4:
        local_masked = local[:1] + "*" * (len(local) - 1)
    elif len(local) <= 6:
        local_masked = local[:1] + "*" * (len(local) - 2) + local[-1:]
    else:
        local_masked = local[:2] + "*" * min(10, max(4, len(local) - 4)) + local[-2:]

    # Only the first character of the hostname and the public suffix remain.
    host_masked = (host_name[:1] + "****") if len(host_name) > 1 else "*"
    return f"{local_masked}@{host_masked}.{suffix}"
