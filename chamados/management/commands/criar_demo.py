from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chamados.models import Chamado, Setor

DESCRICAO_DEMO = 'Chamado de demonstração.'

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
    help = 'Cria ou sincroniza usuários e chamados de demonstração (somente com DEBUG=true).'

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError('Comando permitido apenas em desenvolvimento.')
        User = get_user_model()
        setores = list(Setor.objects.all())
        if not setores:
            raise CommandError('Nenhum setor cadastrado. Execute "python manage.py migrate" primeiro.')

        with transaction.atomic():
            for nome, staff in (('tecnico', True), ('cliente', False)):
                usuario, novo = User.objects.get_or_create(
                    username=nome,
                    defaults={'is_staff': staff},
                )
                if novo:
                    usuario.set_password('Senha@12345')
                    usuario.save()
                elif usuario.is_staff != staff:
                    usuario.is_staff = staff
                    usuario.save(update_fields=['is_staff'])
                self.stdout.write(
                    f'{nome} / Senha@12345 ({"técnico" if staff else "solicitante"})'
                )

            tecnico = User.objects.get(username='tecnico')
            cliente = User.objects.get(username='cliente')
            titulos = [exemplo[0] for exemplo in EXEMPLOS]

            for i, (titulo, categoria, prioridade, dias, status, horas) in enumerate(EXEMPLOS):
                inicio = timezone.now() - timedelta(days=dias)
                resolvido_em = (
                    inicio + timedelta(hours=horas)
                    if status in ('resolvido', 'fechado')
                    else None
                )
                chamado, _ = Chamado.objects.update_or_create(
                    titulo=titulo,
                    descricao=DESCRICAO_DEMO,
                    solicitante=cliente,
                    defaults={
                        'categoria': categoria,
                        'prioridade': prioridade,
                        'setor': setores[i % len(setores)],
                        'status': status,
                        'responsavel': tecnico if status != 'aberto' else None,
                        'solucao': (
                            'Solução aplicada (demonstração).'
                            if resolvido_em
                            else ''
                        ),
                        'resolvido_em': resolvido_em,
                    },
                )
                Chamado.objects.filter(pk=chamado.pk).update(criado_em=inicio)

            Chamado.objects.filter(
                solicitante=cliente,
                descricao=DESCRICAO_DEMO,
            ).exclude(titulo__in=titulos).delete()

        self.stdout.write(f'Demonstração sincronizada: {len(EXEMPLOS)} chamados de exemplo.')
