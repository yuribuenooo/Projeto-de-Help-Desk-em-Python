from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from .models import Chamado, Comentario

EXTENSOES = ['pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'log', 'csv', 'doc', 'docx', 'xls', 'xlsx']
MAX_MB = 5


def _tamanho(f):
    if f.size > MAX_MB * 1024 * 1024:
        raise ValidationError(f'O arquivo deve ter no máximo {MAX_MB} MB.')


def campo_arquivo():
    return forms.FileField(required=False, label=f'Anexo (opcional, até {MAX_MB} MB)',
                           validators=[FileExtensionValidator(EXTENSOES), _tamanho],
                           help_text='Formatos: ' + ', '.join(EXTENSOES))


class CadastroForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'email')
        labels = {'first_name': 'Nome', 'email': 'E-mail'}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields['email'].required = True


class ChamadoForm(forms.ModelForm):
    arquivo = campo_arquivo()

    class Meta:
        model = Chamado
        fields = ['titulo', 'descricao', 'categoria', 'setor', 'prioridade']


class ComentarioForm(forms.ModelForm):
    arquivo = campo_arquivo()

    class Meta:
        model = Comentario
        fields = ['texto']
        widgets = {'texto': forms.Textarea(attrs={'rows': 3})}
