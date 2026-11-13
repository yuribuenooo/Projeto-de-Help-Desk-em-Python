
"""API REST em JSON. Exige sessão autenticada; cada usuário só enxerga o que tem permissão."""

import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods
from django_ratelimit.decorators import ratelimit

from .forms import ChamadoForm
from .models import Chamado, Setor


def autenticado(view):
    @wraps(view)
    def interno(request, *a, **k):
        if not request.user.is_authenticated:
            return JsonResponse(
                {'erro': 'Autenticação necessária'},
                status=401
            )
        return view(request, *a, **k)

    return interno


def _dict(c):
    return {
        'id': c.id,
        'titulo': c.titulo,
        'status': c.status,
        'prioridade': c.prioridade,
        'categoria': c.categoria,
        'setor': c.setor.nome,
        'solicitante': c.solicitante.get_username(),
        'responsavel': c.responsavel.get_username() if c.responsavel else None,
        'criado_em': c.criado_em.isoformat(),
        'prazo_limite': c.prazo_limite.isoformat(),
        'atrasado': c.atrasado
    }


@ratelimit(
    key='chamados.limites.usuario_ou_ip',
    rate='60/m',
    block=True
)
@autenticado
@require_http_methods(['GET', 'POST'])
def chamados_api(request):
    if request.method == 'GET':
        qs = Chamado.visiveis(request.user).select_related(
            'solicitante', 'responsavel', 'setor'
        )
        return JsonResponse(
            [_dict(c) for c in qs],
            safe=False
        )

    try:
        dados = json.loads(request.body or b'{}')
    except ValueError:
        dados = {}

    form = ChamadoForm(dados)

    if not form.is_valid():
        return JsonResponse(
            {'erros': form.errors},
            status=422
        )

    c = form.save(commit=False)
    c.solicitante = request.user
    c.save()

    return JsonResponse(_dict(c), status=201)


@ratelimit(
    key='chamados.limites.usuario_ou_ip',
    rate='60/m',
    block=True
)
@autenticado
@require_GET
def setores_api(request):
    return JsonResponse(
        list(Setor.objects.values('id', 'nome')),
        safe=False
    )


@ratelimit(
    key='chamados.limites.usuario_ou_ip',
    rate='60/m',
    block=True
)
@autenticado
@require_GET
def relatorio_api(request):
    return JsonResponse(
        Chamado.resumo(Chamado.visiveis(request.user))
    )
