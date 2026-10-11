from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('frontend_app', '0003_climberprofile_climbschedule')]

    operations = [
        migrations.AddField(
            model_name='climberprofile',
            name='experience_level',
            field=models.CharField(blank=True, choices=[('beginner', 'Beginner'), ('experienced', 'Experienced'), ('master', 'Master')], help_text='Selected after the climber first signs in.', max_length=12),
        ),
    ]
