"""CONTROLLER (no Django chamado de "view"): regras de acesso, uso do Model/Form e escolha do Template."""
import os

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CadastroForm, ChamadoForm, ComentarioForm
from .models import Anexo, Chamado, Comentario, RegraDeNegocio, Setor

ACOES_TECNICO = {'assumir', 'resolver', 'status', 'prioridade', 'encaminhar'}


def _chamado(request, pk):
    """Busca o chamado respeitando a visibilidade (404 se o usuário não pode vê-lo)."""
    return get_object_or_404(Chamado.visiveis(request.user).select_related('solicitante', 'responsavel', 'setor'), pk=pk)


def _anexar(chamado, arquivo, usuario):
    if arquivo:
        Anexo.objects.create(chamado=chamado, arquivo=arquivo, nome=os.path.basename(arquivo.name), enviado_por=usuario)


def cadastro(request):
    form = CadastroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        messages.success(request, 'Conta criada. Bem-vindo(a)!')
        return redirect('painel')
    return render(request, 'chamados/cadastro.html', {'titulo': 'Criar conta', 'form': form})


@login_required
def painel(request):
    qs = Chamado.visiveis(request.user)
    return render(request, 'chamados/painel.html', {
        'titulo': 'Painel', 'resumo': Chamado.resumo(qs), 'recentes': qs.select_related('solicitante')[:5]})


@login_required
def chamados(request):
    qs = Chamado.visiveis(request.user).select_related('solicitante', 'responsavel', 'setor')
    status, q, meus, setor = (request.GET.get('status', ''), request.GET.get('q', '').strip(),
                              request.GET.get('meus'), request.GET.get('setor', ''))
    if status in dict(Chamado.STATUS):
        qs = qs.filter(status=status)
    if setor.isdigit():
        qs = qs.filter(setor_id=int(setor))
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(descricao__icontains=q))
    if meus and request.user.is_staff:
        qs = qs.filter(responsavel=request.user)
    return render(request, 'chamados/chamados.html', {
        'titulo': 'Chamados', 'chamados': qs, 'status': status, 'q': q, 'meus': meus, 'setor': setor,
        'status_opcoes': Chamado.STATUS, 'setores': Setor.objects.all()})


@login_required
def novo_chamado(request):
    form = ChamadoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        c = form.save(commit=False)
        c.solicitante = request.user
        c.save()
        _anexar(c, form.cleaned_data.get('arquivo'), request.user)
        messages.success(request, f'Chamado #{c.pk} aberto.')
        return redirect('chamado', pk=c.pk)
    return render(request, 'chamados/novo.html', {'titulo': 'Novo chamado', 'form': form})


@login_required
def detalhe(request, pk):
    c = _chamado(request, pk)
    form = ComentarioForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        if c.status == Chamado.FECHADO:
            messages.error(request, 'Chamado fechado: reabra-o para responder.')
        else:
            Comentario.objects.create(chamado=c, autor=request.user, texto=form.cleaned_data['texto'])
            _anexar(c, form.cleaned_data.get('arquivo'), request.user)
            c.registrar_resposta(request.user)
            messages.success(request, 'Resposta enviada.')
        return redirect('chamado', pk=pk)
    return render(request, 'chamados/detalhe.html', {
        'titulo': f'Chamado #{c.pk}', 'c': c, 'form': form, 'comentarios': c.comentarios.select_related('autor'),
        'anexos': c.anexos.select_related('enviado_por'), 'setores': Setor.objects.all(), 'prioridades': Chamado.PRIORIDADES,
        'status_manuais': [(v, l) for v, l in Chamado.STATUS if v in Chamado.MANUAIS]})


@login_required
@require_POST
def acao(request, pk, nome):
    c, u, post = _chamado(request, pk), request.user, request.POST
    if nome in ACOES_TECNICO and not u.is_staff:
        raise PermissionDenied
    try:
        if nome == 'assumir':
            c.assumir(u)
        elif nome == 'resolver':
            c.resolver(u, post.get('solucao', ''))
        elif nome == 'status':
            c.alterar_status(u, post.get('status', ''))
        elif nome == 'prioridade':
            c.alterar_prioridade(u, post.get('prioridade', ''))
        elif nome == 'encaminhar':
            s = post.get('setor', '')
            setor = Setor.objects.filter(pk=int(s)).first() if s.isdigit() else None
            if not setor:
                raise RegraDeNegocio('Setor inválido.')
            c.encaminhar(u, setor)
        elif nome == 'fechar':
            c.fechar(u)
        elif nome == 'reabrir':
            c.reabrir(u)
        else:
            raise Http404
        messages.success(request, 'Ação realizada.')
    except RegraDeNegocio as e:
        messages.error(request, str(e))
    return redirect('chamado', pk=pk)


@login_required
def anexo(request, pk):
    """Download protegido: só o solicitante e os técnicos acessam os arquivos do chamado."""
    a = get_object_or_404(Anexo.objects.select_related('chamado'), pk=pk)
    if not (request.user.is_staff or a.chamado.solicitante_id == request.user.id):
        raise Http404
    return FileResponse(a.arquivo.open('rb'), as_attachment=True, filename=a.nome)
