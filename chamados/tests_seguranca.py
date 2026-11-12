from django.contrib.auth.models import User
from django.test import TestCase


class HashSenhaTest(TestCase):
    def test_senha_gravada_com_argon2(self):
        u = User.objects.create_user('ana', password='Teste#Segura2026!')
        self.assertTrue(u.password.startswith('argon2$'))
        self.assertNotIn('Teste#Segura2026!', u.password)
        self.assertTrue(u.check_password('Teste#Segura2026!'))

    def test_senha_curta_rejeitada(self):
        resp = self.client.post('/cadastro/', {
            'username': 'bia', 'first_name': 'Bia', 'email': 'bia@exemplo.com',
            'password1': 'Curta#1', 'password2': 'Curta#1'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='bia').exists())