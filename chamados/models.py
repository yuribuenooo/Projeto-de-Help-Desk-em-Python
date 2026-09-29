from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone


class RegraDeNegocio(Exception):
    pass


def _com_pct(itens):
    """Acrescenta 'pct' (0-100) relativo ao maior valor, usado pelos gráficos de barras."""
    mx = max((i['total'] for i in itens), default=0) or 1
    for i in itens:
        i['pct'] = round(i['total'] * 100 / mx)
    return itens


class Setor(models.Model):
    nome = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ['nome']
        verbose_name_plural = 'setores'

    def __str__(self):
        return self.nome


class Chamado(models.Model):
    """MODEL: chamado de suporte, prazo (SLA) e ciclo de resolução."""
    ABERTO, EM_ANDAMENTO, PENDENTE, RESOLVIDO, FECHADO = 'aberto', 'em_andamento', 'pendente', 'resolvido', 'fechado'
    STATUS = [(ABERTO, 'Aberto'), (EM_ANDAMENTO, 'Em andamento'), (PENDENTE, 'Pendente'),
              (RESOLVIDO, 'Resolvido'), (FECHADO, 'Fechado')]
    MANUAIS = (ABERTO, EM_ANDAMENTO, PENDENTE)  # status que o técnico pode escolher diretamente
    PRIORIDADES = [('baixa', 'Baixa'), ('media', 'Média'), ('alta', 'Alta'), ('urgente', 'Urgente')]
    CATEGORIAS = [('hardware', 'Hardware'), ('software', 'Software'), ('rede', 'Rede'),
                  ('acesso', 'Acesso/Senha'), ('outros', 'Outros')]
    SLA_HORAS = {'urgente': 4, 'alta': 8, 'media': 24, 'baixa': 72}

    titulo = models.CharField('Título', max_length=150)
    descricao = models.TextField('Descrição')
    categoria = models.CharField('Categoria', max_length=20, choices=CATEGORIAS, default='outros')
    setor = models.ForeignKey(Setor, verbose_name='Setor responsável', on_delete=models.PROTECT, related_name='chamados')
    prioridade = models.CharField('Prioridade', max_length=10, choices=PRIORIDADES, default='media')
    status = models.CharField(max_length=15, choices=STATUS, default=ABERTO)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='chamados_abertos')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='chamados_atribuidos')
    solucao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f'#{self.pk} {self.titulo}'

    # ---- prazo (SLA) ----
    @property
    def encerrado(self):
        return self.status in (self.RESOLVIDO, self.FECHADO)

    @property
    def prazo_limite(self):
        return self.criado_em + timedelta(hours=self.SLA_HORAS[self.prioridade])

    @property
    def no_prazo(self):
        return None if not self.resolvido_em else self.resolvido_em <= self.prazo_limite

    @property
    def atrasado(self):
        return not self.encerrado and timezone.now() > self.prazo_limite

    # ---- ciclo de atendimento ----
    def _log(self, autor, texto):
        Comentario.objects.create(chamado=self, autor=autor, texto=texto, sistema=True)

    def assumir(self, tecnico):
        if self.encerrado:
            raise RegraDeNegocio('Chamado já encerrado. Reabra-o para assumir.')
        self.responsavel, self.status = tecnico, self.EM_ANDAMENTO
        self.save()
        self._log(tecnico, f'Chamado assumido por {tecnico.get_username()}.')

    def alterar_status(self, tecnico, novo):
        if self.encerrado:
            raise RegraDeNegocio('Chamado encerrado. Reabra-o para alterar o status.')
        if novo not in self.MANUAIS:
            raise RegraDeNegocio('Status inválido. Para finalizar, use "Marcar como resolvido".')
        antigo = self.get_status_display()
        self.status = novo
        if novo != self.ABERTO:
            self.responsavel = self.responsavel or tecnico
        self.save()
        self._log(tecnico, f'Status alterado de {antigo} para {self.get_status_display()} por {tecnico.get_username()}.')

    def alterar_prioridade(self, tecnico, nova):
        if self.encerrado:
            raise RegraDeNegocio('Chamado encerrado.')
        if nova not in self.SLA_HORAS:
            raise RegraDeNegocio('Prioridade inválida.')
        antiga = self.get_prioridade_display()
        self.prioridade = nova
        self.save()
        self._log(tecnico, f'Prioridade alterada de {antiga} para {self.get_prioridade_display()} por {tecnico.get_username()}.')

    def encaminhar(self, tecnico, setor):
        if self.encerrado:
            raise RegraDeNegocio('Chamado encerrado.')
        if setor.pk == self.setor_id:
            raise RegraDeNegocio('O chamado já está neste setor.')
        origem = self.setor.nome
        self.setor, self.responsavel, self.status = setor, None, self.ABERTO
        self.save()
        self._log(tecnico, f'Encaminhado de {origem} para {setor.nome} por {tecnico.get_username()}.')

    def resolver(self, tecnico, solucao):
        if self.encerrado:
            raise RegraDeNegocio('Chamado já encerrado.')
        if not solucao.strip():
            raise RegraDeNegocio('Descreva a solução aplicada.')
        self.responsavel = self.responsavel or tecnico
        self.status, self.solucao, self.resolvido_em = self.RESOLVIDO, solucao.strip(), timezone.now()
        self.save()
        self._log(tecnico, f'Chamado finalizado (resolvido) por {tecnico.get_username()}.')

    def fechar(self, usuario):
        if self.status != self.RESOLVIDO:
            raise RegraDeNegocio('Só é possível fechar chamados resolvidos.')
        self.status = self.FECHADO
        self.save()
        self._log(usuario, f'Solução confirmada e chamado fechado por {usuario.get_username()}.')

    def reabrir(self, usuario):
        if not self.encerrado:
            raise RegraDeNegocio('O chamado já está em atendimento.')
        self.status = self.EM_ANDAMENTO if self.responsavel_id else self.ABERTO
        self.resolvido_em, self.solucao = None, ''
        self.save()
        self._log(usuario, f'Chamado reaberto por {usuario.get_username()}.')

    def registrar_resposta(self, autor):
        """Se o solicitante responde a um chamado pendente, o atendimento é retomado."""
        if self.status == self.PENDENTE and autor.pk == self.solicitante_id:
            self.status = self.EM_ANDAMENTO
            self.save()
            self._log(autor, 'Solicitante respondeu; atendimento retomado.')

    # ---- consultas ----
    @classmethod
    def visiveis(cls, user):
        """Técnicos (is_staff) veem tudo; demais usuários veem só os próprios chamados."""
        return cls.objects.all() if user.is_staff else cls.objects.filter(solicitante=user)

    @classmethod
    def resumo(cls, qs):
        """Análise de dados para o dashboard."""
        n = lambda *st: qs.filter(status__in=st).count()
        resolvidos = list(qs.filter(resolvido_em__isnull=False))
        horas = [(c.resolvido_em - c.criado_em).total_seconds() / 3600 for c in resolvidos]
        no_prazo = sum(1 for c in resolvidos if c.no_prazo)
        grupo = lambda campo, rot: _com_pct([{'nome': dict(rot)[x[campo]], 'total': x['n']}
                                             for x in qs.order_by().values(campo).annotate(n=Count('id')).order_by('-n')])
        ab = {x['m']: x['n'] for x in qs.order_by().annotate(m=TruncMonth('criado_em')).values('m').annotate(n=Count('id'))}
        rs = {x['m']: x['n'] for x in qs.order_by().filter(resolvido_em__isnull=False)
              .annotate(m=TruncMonth('resolvido_em')).values('m').annotate(n=Count('id'))}
        meses = sorted(set(ab) | set(rs))[-12:]
        tecnicos = qs.order_by().filter(responsavel__isnull=False).values('responsavel__username').annotate(
            em_aberto=Count('id', filter=~Q(status__in=[cls.RESOLVIDO, cls.FECHADO])),
            resolvidos=Count('id', filter=Q(status__in=[cls.RESOLVIDO, cls.FECHADO]))).order_by('responsavel__username')
        return {
            'total': qs.count(), 'abertos': n(cls.ABERTO), 'em_andamento': n(cls.EM_ANDAMENTO), 'pendentes': n(cls.PENDENTE),
            'resolvidos': n(cls.RESOLVIDO, cls.FECHADO),
            'atrasados': sum(1 for c in qs.exclude(status__in=[cls.RESOLVIDO, cls.FECHADO]) if c.atrasado),
            'media_horas': round(sum(horas) / len(horas), 1) if horas else 0,
            'pct_no_prazo': round(no_prazo * 100 / len(resolvidos)) if resolvidos else None,
            'por_status': _com_pct([{'nome': l, 'total': n(v)} for v, l in cls.STATUS]),
            'por_prioridade': grupo('prioridade', cls.PRIORIDADES),
            'por_categoria': grupo('categoria', cls.CATEGORIAS),
            'por_setor': _com_pct([{'nome': x['setor__nome'], 'total': x['n']}
                                   for x in qs.order_by().values('setor__nome').annotate(n=Count('id')).order_by('-n')]),
            'por_mes': _com_pct([{'nome': m.strftime('%m/%Y'), 'total': ab.get(m, 0), 'resolvidos': rs.get(m, 0)} for m in meses]),
            'por_tecnico': [{'usuario': t['responsavel__username'], 'em_aberto': t['em_aberto'], 'resolvidos': t['resolvidos']} for t in tecnicos],
        }


class Comentario(models.Model):
    chamado = models.ForeignKey(Chamado, on_delete=models.CASCADE, related_name='comentarios')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    texto = models.TextField('Comentário')
    sistema = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em']


class Anexo(models.Model):
    chamado = models.ForeignKey(Chamado, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='anexos/%Y/%m/')
    nome = models.CharField(max_length=255)
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    criado_em = models.DateTimeField(auto_now_add=True)
