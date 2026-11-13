
from django.contrib.auth.models import User
from django.test import TestCase
from chamados.models import Chamado, Setor


class HashSenhaTest(TestCase):
    def test_senha_gravada_com_argon2(self):
        u = User.objects.create_user(
            'ana',
            password='Teste#Segura2026!'
        )

        self.assertTrue(u.password.startswith('argon2$'))
        self.assertNotIn('Teste#Segura2026!', u.password)
        self.assertTrue(u.check_password('Teste#Segura2026!'))

    def test_senha_curta_rejeitada(self):
        resp = self.client.post('/cadastro/', {
            'username': 'bia',
            'first_name': 'Bia',
            'email': 'bia@exemplo.com',
            'password1': 'Curta#1',
            'password2': 'Curta#1'
        })

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            User.objects.filter(username='bia').exists()
        )


class RateLimitTest(TestCase):
    def test_login_bloqueado_apos_5_falhas(self):
        User.objects.create_user(
            'lia',
            password='Teste#Segura2026!'
        )

        for _ in range(5):
            self.client.post('/login/', {
                'username': 'lia',
                'password': 'errada'
            })

        r = self.client.post('/login/', {
            'username': 'lia',
            'password': 'Teste#Segura2026!'
        })

        self.assertEqual(r.status_code, 429)

    def test_cadastro_limitado(self):
        codigos = [
            self.client.post('/cadastro/', {}).status_code
            for _ in range(6)
        ]

        self.assertEqual(codigos[-1], 429)


class SqlInjectionTest(TestCase):
    PAYLOADS = ["' OR '1'='1", "'; DROP TABLE chamados_chamado; --", '1 OR 1=1',
                "%' UNION SELECT username, password FROM auth_user --"]

    def setUp(self):
        self.a = User.objects.create_user('sqla', password='Teste#Segura2026!')
        b = User.objects.create_user('sqlb', password='Teste#Segura2026!')
        Chamado.objects.create(titulo='Segredo do B', descricao='confidencial' * 3,
                               setor=Setor.objects.first(), solicitante=b)
        self.client.force_login(self.a)

    def test_filtros_nao_vazam_nem_quebram(self):
        for payload in self.PAYLOADS:
            for parametro in ('q', 'status', 'setor'):
                r = self.client.get('/chamados/', {parametro: payload})
                self.assertEqual(r.status_code, 200)           
                self.assertNotContains(r, 'Segredo do B')      
        self.assertEqual(Chamado.objects.count(), 1)           

    def test_login_com_payload(self):
        r = self.client_class().post('/login/', {'username': "admin' --", 'password': "x' OR '1'='1"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', r.wsgi_request.session)   