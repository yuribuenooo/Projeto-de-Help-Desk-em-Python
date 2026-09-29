import json
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Anexo, Chamado, Setor

SENHA = 'Senha@12345'


class HelpDeskTests(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        cfg = override_settings(MEDIA_ROOT=media)
        cfg.enable()
        self.addCleanup(cfg.disable)
        self.addCleanup(shutil.rmtree, media, True)
        self.ti, self.redes = Setor.objects.get(nome='Suporte TI'), Setor.objects.get(nome='Infraestrutura e Redes')
        self.ana = User.objects.create_user('ana', password=SENHA)
        self.beto = User.objects.create_user('beto', password=SENHA)
        self.tec = User.objects.create_user('tecnico', password=SENHA, is_staff=True)
        self.c1 = Chamado.objects.create(titulo='PC não liga', descricao='Sem energia', solicitante=self.ana, setor=self.ti)
        self.c2 = Chamado.objects.create(titulo='Sem internet', descricao='Rede caiu', solicitante=self.beto, setor=self.redes, prioridade='alta')

    def entrar(self, user):
        self.client.force_login(user)

    def acao(self, c, nome, **dados):
        return self.client.post(f'/chamados/{c.pk}/acao/{nome}/', dados)

    # ---------- autenticação ----------
    def test_exige_login(self):
        self.assertRedirects(self.client.get('/'), '/login/?next=/')
        self.assertEqual(self.client.get('/api/chamados').status_code, 401)

    def test_login_individual_com_senha(self):
        self.assertFalse(self.client.login(username='ana', password='errada'))
        self.assertTrue(self.client.login(username='ana', password=SENHA))
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_cadastro_cria_usuario_e_autentica(self):
        r = self.client.post('/cadastro/', {'username': 'carla', 'first_name': 'Carla', 'email': 'c@x.com',
                                           'password1': 'Outra#Senha77', 'password2': 'Outra#Senha77'})
        self.assertRedirects(r, '/')
        self.assertTrue(User.objects.get(username='carla').check_password('Outra#Senha77'))

    # ---------- visibilidade ----------
    def test_usuario_ve_apenas_os_proprios_chamados(self):
        self.entrar(self.ana)
        self.assertEqual(self.client.get(f'/chamados/{self.c1.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'/chamados/{self.c2.pk}/').status_code, 404)
        self.assertNotContains(self.client.get('/chamados/'), 'Sem internet')

    def test_tecnico_ve_todos(self):
        self.entrar(self.tec)
        self.assertEqual(self.client.get(f'/chamados/{self.c2.pk}/').status_code, 200)

    # ---------- abertura, anexos e respostas ----------
    def test_abrir_chamado_com_anexo(self):
        self.entrar(self.ana)
        arq = SimpleUploadedFile('erro.txt', b'stack trace')
        r = self.client.post('/chamados/novo/', {'titulo': 'Impressora', 'descricao': 'Travou', 'categoria': 'hardware',
                                                'setor': self.ti.pk, 'prioridade': 'baixa', 'arquivo': arq})
        c = Chamado.objects.get(titulo='Impressora')
        self.assertRedirects(r, f'/chamados/{c.pk}/')
        self.assertEqual((c.solicitante, c.anexos.count()), (self.ana, 1))

    def test_download_de_anexo_e_protegido(self):
        self.c1_anexo = Anexo.objects.create(chamado=self.c1, arquivo=SimpleUploadedFile('a.txt', b'conteudo'), nome='a.txt', enviado_por=self.ana)
        url = f'/anexos/{self.c1_anexo.pk}/'
        self.assertEqual(self.client.get(url).status_code, 302)  # sem login
        self.entrar(self.beto)
        self.assertEqual(self.client.get(url).status_code, 404)  # outro usuário
        self.entrar(self.ana)
        r = self.client.get(url)
        self.assertEqual(b''.join(r.streaming_content), b'conteudo')
        self.entrar(self.tec)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_rejeita_extensao_e_tamanho_invalidos(self):
        self.entrar(self.ana)
        base = {'titulo': 'X', 'descricao': 'Y', 'categoria': 'outros', 'setor': self.ti.pk, 'prioridade': 'baixa'}
        self.client.post('/chamados/novo/', {**base, 'arquivo': SimpleUploadedFile('virus.exe', b'MZ')})
        self.client.post('/chamados/novo/', {**base, 'arquivo': SimpleUploadedFile('grande.txt', b'x' * (5 * 1024 * 1024 + 1))})
        self.assertFalse(Chamado.objects.filter(titulo='X').exists())

    def test_resposta_com_anexo(self):
        self.entrar(self.ana)
        self.client.post(f'/chamados/{self.c1.pk}/', {'texto': 'Segue foto', 'arquivo': SimpleUploadedFile('foto.png', b'\x89PNG')})
        self.assertContains(self.client.get(f'/chamados/{self.c1.pk}/'), 'Segue foto')
        self.assertEqual(self.c1.anexos.count(), 1)

    # ---------- atendimento (técnico) ----------
    def test_fluxo_completo_de_resolucao(self):
        self.entrar(self.tec)
        self.acao(self.c1, 'assumir')
        self.c1.refresh_from_db()
        self.assertEqual((self.c1.status, self.c1.responsavel), ('em_andamento', self.tec))
        self.acao(self.c1, 'resolver', solucao='Trocada a fonte')
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 'resolvido')
        self.assertIsNotNone(self.c1.resolvido_em)
        self.entrar(self.ana)
        self.acao(self.c1, 'fechar')
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 'fechado')
        self.assertGreaterEqual(self.c1.comentarios.filter(sistema=True).count(), 3)

    def test_tecnico_altera_prioridade_e_prazo(self):
        self.entrar(self.tec)
        antes = self.c1.prazo_limite
        self.acao(self.c1, 'prioridade', prioridade='urgente')
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.prioridade, 'urgente')
        self.assertLess(self.c1.prazo_limite, antes)

    def test_encaminhar_para_outro_setor(self):
        self.c1.assumir(self.tec)
        self.entrar(self.tec)
        self.acao(self.c1, 'encaminhar', setor=self.redes.pk)
        self.c1.refresh_from_db()
        self.assertEqual((self.c1.setor, self.c1.responsavel, self.c1.status), (self.redes, None, 'aberto'))

    def test_pendente_e_retomada_quando_solicitante_responde(self):
        self.entrar(self.tec)
        self.acao(self.c1, 'status', status='pendente')
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 'pendente')
        self.entrar(self.ana)
        self.client.post(f'/chamados/{self.c1.pk}/', {'texto': 'Já testei outra tomada'})
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 'em_andamento')

    def test_status_manual_nao_finaliza(self):
        self.entrar(self.tec)
        self.acao(self.c1, 'status', status='resolvido')
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 'aberto')

    def test_usuario_comum_nao_gerencia(self):
        self.entrar(self.ana)
        for nome, dados in (('resolver', {'solucao': 'x'}), ('assumir', {}), ('prioridade', {'prioridade': 'baixa'}),
                            ('status', {'status': 'pendente'}), ('encaminhar', {'setor': self.redes.pk})):
            self.assertEqual(self.acao(self.c1, nome, **dados).status_code, 403, nome)
        self.c1.refresh_from_db()
        self.assertEqual((self.c1.status, self.c1.setor), ('aberto', self.ti))

    def test_resolver_exige_solucao(self):
        self.entrar(self.tec)
        self.acao(self.c1, 'resolver', solucao='   ')
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 'aberto')

    def test_reabrir_chamado_resolvido(self):
        self.c1.assumir(self.tec)
        self.c1.resolver(self.tec, 'ok')
        self.entrar(self.ana)
        self.acao(self.c1, 'reabrir')
        self.c1.refresh_from_db()
        self.assertEqual((self.c1.status, self.c1.solucao), ('em_andamento', ''))

    # ---------- prazo e dashboard ----------
    def test_percentual_resolvido_no_prazo_e_atrasados(self):
        agora = timezone.now()
        Chamado.objects.filter(pk=self.c1.pk).update(criado_em=agora - timedelta(hours=100), prioridade='baixa',
                                                     status='resolvido', resolvido_em=agora)  # 100h > 72h: fora do prazo
        Chamado.objects.filter(pk=self.c2.pk).update(criado_em=agora - timedelta(hours=30), prioridade='alta',
                                                     status='resolvido', resolvido_em=agora - timedelta(hours=25))  # 5h < 8h: no prazo
        c3 = Chamado.objects.create(titulo='Atrasado', descricao='d', solicitante=self.ana, setor=self.ti, prioridade='urgente')
        Chamado.objects.filter(pk=c3.pk).update(criado_em=agora - timedelta(hours=10))
        r = Chamado.resumo(Chamado.objects.all())
        self.assertEqual(r['pct_no_prazo'], 50)
        self.assertEqual(r['atrasados'], 1)
        self.assertEqual(r['media_horas'], 52.5)

    def test_relatorio_respeita_escopo_e_agrupa(self):
        self.c1.assumir(self.tec)
        self.c1.resolver(self.tec, 'ok')
        self.entrar(self.tec)
        r = self.client.get('/api/relatorio').json()
        self.assertEqual((r['total'], r['resolvidos'], r['abertos']), (2, 1, 1))
        self.assertEqual({x['nome'] for x in r['por_setor']}, {'Suporte TI', 'Infraestrutura e Redes'})
        self.assertEqual(r['por_mes'][0]['total'], 2)
        self.assertEqual(r['por_mes'][0]['resolvidos'], 1)
        self.assertEqual(r['por_tecnico'][0]['usuario'], 'tecnico')
        self.entrar(self.beto)
        self.assertEqual(self.client.get('/api/relatorio').json()['total'], 1)

    def test_paginas_renderizam(self):
        self.c1.assumir(self.tec)
        self.c1.resolver(self.tec, 'ok')
        for user in (self.ana, self.tec):
            self.entrar(user)
            for rota in ('/', '/chamados/', '/chamados/novo/', f'/chamados/{self.c1.pk}/', f'/chamados/?setor={self.ti.pk}&status=resolvido'):
                self.assertEqual(self.client.get(rota).status_code, 200, rota)

    def test_api_cria_e_lista_chamados(self):
        self.entrar(self.ana)
        dados = {'titulo': 'Wi-Fi', 'descricao': 'Lento', 'categoria': 'rede', 'setor': self.redes.pk, 'prioridade': 'media'}
        r = self.client.post('/api/chamados', json.dumps(dados), content_type='application/json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.client.get('/api/chamados').json()), 2)
        self.assertEqual(len(self.client.get('/api/setores').json()), 5)
        r = self.client.post('/api/chamados', json.dumps({'titulo': ''}), content_type='application/json')
        self.assertEqual(r.status_code, 422)
