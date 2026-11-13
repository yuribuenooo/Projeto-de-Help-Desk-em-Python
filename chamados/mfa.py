from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit


@login_required
@ratelimit(key='chamados.limites.usuario_ou_ip', rate='10/m', method='POST', block=True)
def verificar(request):
	pass
