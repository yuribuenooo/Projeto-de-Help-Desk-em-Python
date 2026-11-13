from axes.helpers import get_client_ip_address


def ip_cliente(group, request):
    """Mesmo cálculo de IP do django-axes (respeita AXES_IPWARE_PROXY_COUNT)."""
    return get_client_ip_address(request)


def usuario_ou_ip(group, request):
    return f'u{request.user.pk}' if request.user.is_authenticated else ip_cliente(group, request)