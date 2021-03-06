from __future__ import unicode_literals, absolute_import
from django.conf import settings
from django.conf.urls import url
from django.contrib.admin import register
from django.http import HttpResponse
from django.template.loader import render_to_string
from reversion.admin import VersionAdmin
from StringIO import StringIO
import unicodecsv
from .utils import OimModelAdmin
from .models import (
    Software, Hardware, UserGroup, DocumentApproval, ITSystemHardware,
    ITSystem, ITSystemDependency, Backup, BusinessService, BusinessFunction,
    BusinessProcess, ProcessITSystemRelationship)


@register(Software)
class SoftwareAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('name', 'url', 'os')
    list_filter = ('os',)
    search_fields = ('name', 'url',)


@register(Hardware)
class HardwareAdmin(VersionAdmin, OimModelAdmin):
    list_display = (
        'device_type', 'name', 'username', 'email', 'cost_centre', 'ipv4',
        'ports', 'serials', 'os')
    list_filter = ('device_type', 'os', 'cost_centre')
    search_fields = (
        'name', 'username', 'email', 'ipv4', 'serials', 'ports', 'os__name')


@register(UserGroup)
class UserGroupAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('name', 'user_count')
    search_fields = ('name',)


@register(DocumentApproval)
class DocumentApprovalAdmin(OimModelAdmin):
    list_diplay = ('department_user', 'approval_role', 'date_created')
    raw_id_fields = ('department_user',)


@register(ITSystemHardware)
class ITSystemHardwareAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('hostname', 'role', 'affected_itsystems')
    list_filter = ('role',)
    raw_id_fields = ('host',)
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/registers/itsystemhardware/change_list.html'

    def affected_itsystems(self, obj):
        return obj.itsystem_set.all().exclude(status=3).count()
    affected_itsystems.short_description = 'IT Systems'

    def get_urls(self):
        urls = super(ITSystemHardwareAdmin, self).get_urls()
        urls = [
            url(r'^export/$',
                self.admin_site.admin_view(self.export),
                name='itsystemhardware_export'),
        ] + urls
        return urls

    def export(self, request):
        """Exports ITSystemHardware data to a CSV.
        """
        # Define fields to output.
        fields = [
            'hostname', 'location', 'role', 'it_system_system_id',
            'it_system_name', 'itsystem_availability', 'itsystem_criticality']

        # Write data for ITSystemHardware objects to the CSV.
        stream = StringIO()
        wr = unicodecsv.writer(stream, encoding='utf-8')
        wr.writerow(fields)  # CSV header row.
        for i in ITSystemHardware.objects.all():
            # Write a row for each linked ITSystem (non-decommissioned).
            for it in i.itsystem_set.all().exclude(status=3):
                wr.writerow([
                    i.hostname, i.host.location, i.get_role_display(),
                    it.system_id, it.name, it.get_availability_display(),
                    it.get_criticality_display()])

        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=itsystemhardware_export.csv'
        return response


@register(ITSystem)
class ITSystemAdmin(VersionAdmin, OimModelAdmin):
    list_display = (
        'system_id', 'name', 'acronym', 'status', 'cost_centre', 'owner', 'custodian',
        'preferred_contact', 'access', 'authentication')
    list_filter = (
        'access',
        'authentication',
        'status',
        'contingency_plan_status',
        'system_type')
    search_fields = (
        'system_id', 'owner__username', 'owner__email', 'name', 'acronym', 'description',
        'custodian__username', 'custodian__email', 'link', 'documentation', 'cost_centre__code')
    raw_id_fields = (
        'owner', 'custodian', 'data_custodian', 'preferred_contact', 'cost_centre',
        'bh_support', 'ah_support')
    readonly_fields = ('extra_data_pretty', 'description_html')
    filter_horizontal = ('contingency_plan_approvals',)
    fields = [
        ('system_id', 'acronym'),
        ('name', 'status'),
        'link',
        ('cost_centre', 'owner'),
        ('custodian', 'data_custodian'),
        'preferred_contact',
        ('bh_support', 'ah_support'),
        'documentation',
        'technical_documentation',
        'status_html',
        ('authentication', 'access'),
        'description',
        'notes',
        ('criticality', 'availability'),
        'schema_url',
        ('softwares', 'hardwares'),
        'user_groups',
        'system_reqs',
        'system_type',
        'request_access',
        ('vulnerability_docs', 'recovery_docs'),
        'workaround',
        ('mtd', 'rto', 'rpo'),
        ('contingency_plan', 'contingency_plan_status'),
        'contingency_plan_approvals',
        'contingency_plan_last_tested',
        'system_health',
        'system_creation_date',
        'backup_info',
        'risks',
        'critical_period',
        'alt_processing',
        'technical_recov',
        'post_recovery',
        'variation_iscp',
        'user_notification',
        'other_projects',
        'function',
        'use',
        'capability',
        'unique_evidence',
        'point_of_truth',
        'legal_need_to_retain',
        'extra_data',
    ]
    # Override the default reversion/change_list.html template:
    change_list_template = 'admin/registers/itsystem/change_list.html'

    def save_model(self, request, obj, form, change):
        """Override save_model in order to log any changes to the
        contingency_plan field.
        """
        # If contingency_plan changes, delete any associated DocumentApproval
        # objects.
        if obj._ITSystem__original_contingency_plan != obj.contingency_plan:
            # Clear the selected approvals from the modeladmin form.
            form.cleaned_data['contingency_plan_approvals'] = []
            approvals = [i for i in obj.contingency_plan_approvals.all()]
            obj.contingency_plan_approvals.clear()  # Remove M2M relationships
            obj.save()
            for i in approvals:
                i.delete()  # Delete each approval object.
        super(ITSystemAdmin, self).save_model(request, obj, form, change)

    def get_urls(self):
        urls = super(ITSystemAdmin, self).get_urls()
        urls = [
            # Note that we don't wrap the view below in AdminSite.admin_view()
            # on purpose, as we want it generally accessible.
            url(r'^export/$', self.export, name='itsystem_export'),
        ] + urls
        return urls

    def export(self, request):
        """Exports ITSystem data to a CSV.
        """
        # Define fields to output.
        fields = [
            'system_id', 'name', 'acronym', 'status_display', 'description',
            'criticality_display', 'availability_display', 'system_type_display',
            'cost_centre', 'division_name', 'owner', 'custodian', 'data_custodian', 'preferred_contact',
            'link', 'documentation', 'technical_documentation', 'authentication_display',
            'access_display', 'request_access', 'status_html', 'schema_url',
            'bh_support', 'ah_support', 'system_reqs', 'vulnerability_docs',
            'workaround', 'recovery_docs', 'date_updated']

        # Write data for ITSystem objects to the CSV:
        stream = StringIO()
        wr = unicodecsv.writer(stream, encoding='utf-8')
        wr.writerow(fields)
        for i in ITSystem.objects.all().order_by(
                'system_id').exclude(status=3):  # Exclude decommissioned
            wr.writerow([getattr(i, f) for f in fields])

        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=itsystem_export.csv'
        return response


@register(ITSystemDependency)
class ITSystemDependencyAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('itsystem', 'dependency', 'criticality')
    list_filter = ('criticality',)
    search_fields = ('itsystem__name', 'dependency__name')


@register(Backup)
class BackupAdmin(VersionAdmin, OimModelAdmin):
    raw_id_fields = ('system', 'parent_host')
    list_display = (
        'name', 'host', 'operating_system', 'role', 'status', 'last_tested', 'backup_documentation')
    list_editable = ('operating_system', 'role', 'status', 'last_tested')
    search_fields = ('system__name', 'parent_host__name')
    list_filter = ('role', 'status', 'operating_system')
    date_hierarchy = 'last_tested'

    def name(self, obj):
        return obj.system.name.split('.')[0]

    def host(self, obj):
        if not obj.parent_host:
            return None
        return obj.parent_host.name.split('.')[0]

    def backup_documentation(self, obj):
        return render_to_string('registers/backup_snippet.html', {
            'obj': obj, 'settings': settings, 'name': self.name(obj)}
        )


@register(BusinessService)
class BusinessServiceAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('number', 'name')
    search_fields = ('name', 'description')


@register(BusinessFunction)
class BusinessFunctionAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('name', 'function_services')
    list_filter = ('services',)
    search_fields = ('name', 'description')

    def function_services(self, obj):
        return ', '.join([str(i.number) for i in obj.services.all()])
    function_services.short_description = 'services'


@register(BusinessProcess)
class BusinessProcessAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('name', 'criticality')
    list_filter = ('criticality', 'functions')
    search_fields = ('name', 'description', 'functions__name')


@register(ProcessITSystemRelationship)
class ProcessITSystemRelationshipAdmin(VersionAdmin, OimModelAdmin):
    list_display = ('process', 'itsystem', 'importance')
    list_filter = ('importance', 'process', 'itsystem')
    search_fields = ('process__name', 'itsystem__name')
