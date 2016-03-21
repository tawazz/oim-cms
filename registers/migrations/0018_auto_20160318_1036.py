# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-03-18 02:36
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('registers', '0017_auto_20160318_1009'),
    ]

    operations = [
        migrations.CreateModel(
            name='ITSystemDependency',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criticality', models.PositiveIntegerField(choices=[(1, 'Critical'), (2, 'Moderate'), (3, 'Low')], help_text='How critical is the dependency')),
            ],
            options={
                'verbose_name_plural': 'IT System dependencies',
            },
        ),
        migrations.RemoveField(
            model_name='itsystem',
            name='itsystems',
        ),
        migrations.AlterField(
            model_name='processitsystemrelationship',
            name='importance',
            field=models.PositiveIntegerField(choices=[(1, 'High'), (2, 'Medium'), (3, 'Low')]),
        ),
        migrations.AddField(
            model_name='itsystemdependency',
            name='dependency',
            field=models.ForeignKey(help_text='The system which is depended upon by', on_delete=django.db.models.deletion.PROTECT, related_name='dependency', to='registers.ITSystem'),
        ),
        migrations.AddField(
            model_name='itsystemdependency',
            name='itsystem',
            field=models.ForeignKey(help_text='The IT System', on_delete=django.db.models.deletion.PROTECT, to='registers.ITSystem'),
        ),
        migrations.AlterUniqueTogether(
            name='itsystemdependency',
            unique_together=set([('itsystem', 'dependency')]),
        ),
    ]