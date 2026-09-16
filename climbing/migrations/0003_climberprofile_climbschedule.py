# Generated manually for Go Climb's profile and booking features.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('frontend_app', '0002_alter_crag_rock_type_forumpost_forumcomment_and_more')]

    operations = [
        migrations.CreateModel(
            name='ClimberProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_name', models.CharField(blank=True, max_length=80)),
                ('birthday', models.DateField(blank=True, null=True)),
                ('bio', models.TextField(blank=True)),
                ('home_gym', models.CharField(blank=True, max_length=120)),
                ('climbing_since', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='climber_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ClimbSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('climb_at', models.DateTimeField()),
                ('friends', models.TextField(blank=True)), ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('crag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_climbs', to='frontend_app.crag')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='climb_schedules', to=settings.AUTH_USER_MODEL)),
            ], options={'ordering': ['climb_at']},
        ),
    ]
