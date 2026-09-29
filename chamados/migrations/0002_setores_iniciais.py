from django.db import migrations

SETORES = ['Suporte TI', 'Infraestrutura e Redes', 'Sistemas', 'Financeiro', 'Recursos Humanos']


def criar(apps, schema_editor):
    Setor = apps.get_model('chamados', 'Setor')
    for nome in SETORES:
        Setor.objects.get_or_create(nome=nome)


class Migration(migrations.Migration):
    dependencies = [('chamados', '0001_initial')]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
