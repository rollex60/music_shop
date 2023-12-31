# Generated by Django 4.0.4 on 2022-04-28 09:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('musicshop', '0003_alter_order_cart'),
    ]

    operations = [
        migrations.AlterField(
            model_name='album',
            name='offer_of_the_week',
            field=models.BooleanField(default=False, verbose_name='Предложение недели?'),
        ),
        migrations.AlterField(
            model_name='mediatype',
            name='name',
            field=models.CharField(max_length=100, verbose_name='Название медианосителя'),
        ),
        migrations.AlterField(
            model_name='order',
            name='comment',
            field=models.TextField(blank=True, null=True, verbose_name='Комментарий к заказу'),
        ),
    ]
