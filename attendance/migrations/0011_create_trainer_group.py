from django.db import migrations


def create_trainer_group(apps, schema_editor):
    """Make sure the 'Trainer' role exists on every new database."""
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Trainer')


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0010_classgroup_class_days_per_week'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # Reversing leaves the group in place: it may have users in it.
        migrations.RunPython(create_trainer_group, migrations.RunPython.noop),
    ]
