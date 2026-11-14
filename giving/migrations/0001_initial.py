from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Donor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=40)),
            ],
            options={'ordering': ['name', 'email']},
        ),
        migrations.CreateModel(
            name='DonationTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paypal_transaction_id', models.CharField(max_length=100, unique=True)),
                ('transaction_date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(max_length=3)),
                ('transaction_type', models.CharField(max_length=100)),
                ('is_recurring', models.BooleanField(default=False)),
                ('subscription_id', models.CharField(blank=True, max_length=100)),
                ('donor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='giving.donor')),
            ],
            options={'ordering': ['-transaction_date', '-id']},
        ),
    ]