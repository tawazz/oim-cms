# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-05-09 05:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0015_departmentuser_name_update_reference'),
    ]

    operations = [
        migrations.AlterField(
            model_name='departmentuser',
            name='name_update_reference',
            field=models.CharField(blank=True, help_text='Reference for name/CC change request', max_length=512, null=True, verbose_name='update reference'),
        ),
    ]
