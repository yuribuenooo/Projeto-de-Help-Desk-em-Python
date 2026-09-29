from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from chamados.models import Chamado, Setor

EXEMPLOS = [  # título, categoria, prioridade, dias atrás, status, horas até resolver
    ('Computador não liga', 'hardware', 'alta', 75, 'fechado', 5),
    ('Erro ao abrir planilha', 'software', 'media', 62, 'resolvido', 30),
    ('Sem acesso à rede', 'rede', 'urgente', 48, 'resolvido', 9),
    ('Esqueci minha senha', 'acesso', 'baixa', 33, 'fechado', 10),
    ('Impressora travando', 'hardware', 'media', 20, 'resolvido', 20),
    ('Instalar programa de vendas', 'software', 'baixa', 12, 'em_andamento', 0),
    ('Wi-Fi lento no 2º andar', 'rede', 'alta', 6, 'pendente', 0),
    ('Mouse com defeito', 'hardware', 'baixa', 2, 'aberto', 0),
]


class Command(BaseCommand):
    help = 'Cria usuários e chamados de demonstração (somente com DEBUG=true).'

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError('Comando permitido apenas em desenvolvimento.')
        U = get_user_model()
        for nome, staff in (('tecnico', True), ('cliente', False)):
            u, novo = U.objects.get_or_create(username=nome, defaults={'is_staff': staff})
            if novo:
                u.set_password('Senha@12345')
                u.save()
            self.stdout.write(f'{nome} / Senha@12345 ({"técnico" if staff else "solicitante"})')
        if Chamado.objects.exists():
            return
        tec, cli, setores = U.objects.get(username='tecnico'), U.objects.get(username='cliente'), list(Setor.objects.all())
        for i, (t, cat, pri, dias, st, h) in enumerate(EXEMPLOS):
            ini = timezone.now() - timedelta(days=dias)
            c = Chamado.objects.create(titulo=t, descricao='Chamado de demonstração.', categoria=cat, prioridade=pri,
                                       setor=setores[i % len(setores)], solicitante=cli)
            c.criado_em, c.status = ini, st
            if st != 'aberto':
                c.responsavel = tec
            if st in ('resolvido', 'fechado'):
                c.resolvido_em, c.solucao = ini + timedelta(hours=h), 'Solução aplicada (demonstração).'
            c.save()
        self.stdout.write(f'{len(EXEMPLOS)} chamados de exemplo criados.')
