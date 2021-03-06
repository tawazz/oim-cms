from __future__ import absolute_import
from django import forms
from django.conf.urls import url
from django.contrib import messages
from django.contrib.admin import register, site, ModelAdmin
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.html import format_html
from leaflet.admin import LeafletGeoAdmin
from mptt.admin import MPTTModelAdmin

from .models import DepartmentUser, Location, SecondaryLocation, OrgUnit, CostCentre
from .utils import logger_setup, alesco_data_import, departmentuser_csv_report


@register(DepartmentUser)
class DepartmentUserAdmin(ModelAdmin):
    list_display = [
        'email', 'employee_id', 'username', 'active', 'vip', 'executive',
        'cost_centre', 'account_type', 'date_ad_updated']
    list_filter = ['account_type', 'active', 'vip', 'executive']
    search_fields = ['name', 'email', 'username', 'employee_id', 'preferred_name']
    raw_id_fields = ['parent', 'cost_centre', 'org_unit']
    readonly_fields = [
        'username', 'email', 'org_data_pretty', 'ad_data_pretty',
        'active', 'in_sync', 'ad_deleted', 'date_ad_updated', 'expiry_date',
        'alesco_data_pretty']
    fieldsets = (
        ('Email/username', {
            'fields': ('email', 'username'),
        }),
        ('Name and organisational fields', {
            'description': '''<p class="errornote">Do not edit information in this section
            without written permission from People Services or the cost centre manager
            (forms are required).</p>''',
            'fields': (
                'given_name', 'surname', 'name', 'employee_id',
                'cost_centre', 'org_unit', 'security_clearance',
                'name_update_reference'),
        }),
        ('Other details', {
            'fields': (
                'preferred_name', 'photo', 'title', 'parent',
                'account_type', 'position_type',
                'cost_centres_secondary', 'org_units_secondary',
                'telephone', 'mobile_phone', 'extension', 'other_phone',
                'populate_primary_group', 'vip', 'executive', 'contractor',
                'secondary_locations', 'notes', 'working_hours', 'extra_data',
            )
        }),
        ('AD sync and HR data (read-only)', {
            'fields': (
                'active', 'in_sync', 'ad_deleted', 'date_ad_updated', 'expiry_date',
                'org_data_pretty', 'ad_data_pretty', 'alesco_data_pretty',
            )
        })
    )

    def save_model(self, request, obj, form, change):
        """Override save_model in order to log any changes to some fields:
        'given_name', 'surname', 'employee_id', 'cost_centre', 'name', 'org_unit'
        """
        logger = logger_setup('departmentuser_updates')
        l = 'DepartmentUser: {}, field: {}, original_value: {} new_value: {}, changed_by: {}, reference: {}'
        if obj._DepartmentUser__original_given_name != obj.given_name:
            logger.info(l.format(
                obj.email, 'given_name', obj._DepartmentUser__original_given_name, obj.given_name,
                request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_surname != obj.surname:
            logger.info(l.format(
                obj.email, 'surname', obj._DepartmentUser__original_surname, obj.surname,
                request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_employee_id != obj.employee_id:
            logger.info(l.format(
                obj.email, 'employee_id', obj._DepartmentUser__original_employee_id,
                obj.employee_id, request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_cost_centre != obj.cost_centre:
            logger.info(l.format(
                obj.email, 'cost_centre', obj._DepartmentUser__original_cost_centre,
                obj.cost_centre, request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_name != obj.name:
            logger.info(l.format(
                obj.email, 'name', obj._DepartmentUser__original_name, obj.name,
                request.user.username, obj.name_update_reference
            ))
        if obj._DepartmentUser__original_org_unit != obj.org_unit:
            logger.info(l.format(
                obj.email, 'org_unit', obj._DepartmentUser__original_org_unit, obj.org_unit,
                request.user.username, obj.name_update_reference
            ))
        obj.save()

    def get_urls(self):
        urls = super(DepartmentUserAdmin, self).get_urls()
        urls = [
            url(r'^alesco-import/$', self.admin_site.admin_view(self.alesco_import), name='alesco_import'),
            url(r'^export/$', self.admin_site.admin_view(self.export), name='departmentuser_export'),
        ] + urls
        return urls

    class AlescoImportForm(forms.Form):
        spreadsheet = forms.FileField()

    def alesco_import(self, request):
        """Displays a form prompting user to upload an Excel spreadsheet of
        employee data from Alesco. Temporary measure until database link is
        worked out.
        """
        context = dict(
            site.each_context(request),
            title='Alesco data import'
        )

        if request.method == 'POST':
            form = self.AlescoImportForm(request.POST, request.FILES)
            if form.is_valid():
                upload = request.FILES['spreadsheet']
                # Write the uploaded file to a temp file.
                f = open('/tmp/alesco-data.xlsx', 'w')
                f.write(upload.read())
                f.close()
                alesco_data_import(f.name)
                messages.info(request, 'Spreadsheet uploaded successfully!')
                return redirect('admin:organisation_departmentuser_changelist')
        else:
            form = self.AlescoImportForm()
        context['form'] = form

        return TemplateResponse(request, 'organisation/alesco_import.html', context)

    def export(self, request):
        """Exports DepartmentUser data to a CSV, and returns
        """
        data = departmentuser_csv_report()
        response = HttpResponse(data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=departmentuser_export.csv'
        return response


@register(Location)
class LocationAdmin(LeafletGeoAdmin):
    list_display = ('name', 'address', 'phone', 'fax', 'email', 'point')
    search_fields = ('name', 'address', 'phone', 'fax', 'email')
    settings_overrides = {
        'DEFAULT_CENTER': (-31.0, 115.0),
        'DEFAULT_ZOOM': 5
    }


@register(SecondaryLocation)
class SecondaryLocationAdmin(ModelAdmin):
    pass


@register(OrgUnit)
class OrgUnitAdmin(MPTTModelAdmin):
    list_display = (
        'name', 'unit_type', 'users', 'members', 'it_systems', 'cc', 'acronym',
        'manager')
    search_fields = ('name', 'acronym', 'manager__name', 'location__name')
    raw_id_fields = ('manager', 'parent', 'location')
    list_filter = ('unit_type',)

    def users(self, obj):
        from organisation.models import DepartmentUser
        dusers = obj.departmentuser_set.filter(**DepartmentUser.ACTIVE_FILTER)
        return format_html(
            '<a href="{}?org_unit={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            obj.pk, dusers.count())

    def members(self, obj):
        return format_html(
            '<a href="{}?org_unit__in={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            ','.join([str(o.pk)
                      for o in obj.get_descendants(include_self=True)]),
            obj.members().count()
        )

    def it_systems(self, obj):
        return format_html(
            '<a href="{}?org_unit={}">{}</a>',
            reverse('admin:registers_itsystem_changelist'),
            obj.pk, obj.itsystem_set.count())


@register(CostCentre)
class CostCentreAdmin(ModelAdmin):
    list_display = (
        'code', 'name', 'org_position', 'division', 'users', 'manager',
        'business_manager', 'admin', 'tech_contact')
    search_fields = (
        'code', 'name', 'org_position__name', 'division__name',
        'org_position__acronym', 'division__acronym')
    raw_id_fields = (
        'org_position',
        'manager',
        'business_manager',
        'admin',
        'tech_contact')

    def users(self, obj):
        return format_html(
            '<a href="{}?cost_centre={}">{}</a>',
            reverse('admin:organisation_departmentuser_changelist'),
            obj.pk, obj.departmentuser_set.count())
