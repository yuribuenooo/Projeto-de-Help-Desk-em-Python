from django.contrib import admin
from .models import Anexo, Chamado, Comentario, Setor

for m in (Setor, Chamado, Comentario, Anexo):
    admin.site.register(m)
