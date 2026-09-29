from django.contrib.auth import views as auth
from django.urls import path

from . import api, views

urlpatterns = [
    path('login/', auth.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('sair/', auth.LogoutView.as_view(), name='logout'),
    path('cadastro/', views.cadastro, name='cadastro'),
    path('', views.painel, name='painel'),
    path('chamados/', views.chamados, name='chamados'),
    path('chamados/novo/', views.novo_chamado, name='novo_chamado'),
    path('chamados/<int:pk>/', views.detalhe, name='chamado'),
    path('chamados/<int:pk>/acao/<str:nome>/', views.acao, name='acao'),
    path('anexos/<int:pk>/', views.anexo, name='anexo'),
    path('api/chamados', api.chamados_api),
    path('api/setores', api.setores_api),
    path('api/relatorio', api.relatorio_api),
]
