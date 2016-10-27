from __future__ import unicode_literals, absolute_import
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from organisation.models import DepartmentUser
from .serializers import DepartmentUserSerializer
from django.conf import settings
from django.http import (
    HttpResponse, HttpResponseForbidden, HttpResponseBadRequest)
from rest_framework.response import Response
from django.utils.text import slugify
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
import json
from oim_cms.utils import FieldsFormatter, CSVDjangoResource
import logging

from .models import DepartmentUser, Location, SecondaryLocation, OrgUnit, CostCentre


ACCOUNT_TYPE_DICT = dict(DepartmentUser.ACCOUNT_TYPE_CHOICES)
logger  = logging.getLogger('ad_sync')

def format_fileField(request, value):
    if value:
        return request.build_absolute_uri(
            '{}{}'.format(settings.MEDIA_URL, value))
    else:
        return value


def format_position_type(request, value):
    position_type = dict(DepartmentUser.POSITION_TYPE_CHOICES)
    if value is not None:
        return position_type[value]
    else:
        return value


def format_account_type(request, value):
    if value is not None:
        return ACCOUNT_TYPE_DICT[value]
    else:
        return value




class DepartmentUserViewSet(viewsets.ModelViewSet):
    """docstring for DepartmentUserViewSet."""

    queryset = DepartmentUser.objects.all()
    serializer_class = DepartmentUserSerializer
    authentication_classes = []

    COMPACT_ARGS = (
        'pk', 'name', 'title', 'employee_id', 'email', 'telephone',
        'mobile_phone', 'extension', 'photo', 'photo_ad', 'org_data', 'parent__email',
        'parent__name', 'username', 'org_unit__location__id',
        'org_unit__location__name', 'org_unit__location__address',
        'org_unit__location__pobox', 'org_unit__location__phone',
        'org_unit__location__fax', 'ad_guid',
        'org_unit__secondary_location__name', 'preferred_name')
    VALUES_ARGS = COMPACT_ARGS + (
        'ad_dn', 'ad_data', 'date_updated', 'date_ad_updated', 'active',
        'ad_deleted', 'in_sync', 'given_name', 'surname', 'home_phone',
        'other_phone', 'notes', 'working_hours', 'position_type',
        'account_type')
    MINIMAL_ARGS = (
        'pk', 'name', 'preferred_name', 'title', 'email', 'telephone',
        'mobile_phone', 'photo', 'org_unit__location__name')
    PROPERTY_ARGS = ('password_age_days',)

    formatters = FieldsFormatter(formatters={
        'photo': format_fileField,
        'photo_ad': format_fileField,
        'position_type': format_position_type,
        'account_type': format_account_type,
    })

    def org_structure(self, sync_o365=False, exclude_populate_groups=False):
        qs = DepartmentUser.objects.filter(**DepartmentUser.ACTIVE_FILTER)
        if exclude_populate_groups:  # Exclude objects where populate_primary_group == False
            qs = qs.exclude(populate_primary_group=False)
        structure = []
        if sync_o365:
            orgunits = OrgUnit.objects.filter(sync_o365=True)
        else:
            orgunits = OrgUnit.objects.all()
        costcentres = CostCentre.objects.all()
        locations = Location.objects.all()
        slocations = SecondaryLocation.objects.all()
        defaultowner = 'support@dpaw.wa.gov.au'
        for obj in orgunits:
            structure.append({'id': 'db-org_{}'.format(obj.pk),
                              'name': str(obj),
                              'email': slugify(obj.name),
                              'owner': getattr(obj.manager, 'email', defaultowner),
                              'members': [d[0] for d in qs.filter(org_unit__in=obj.get_descendants(include_self=True)).values_list('email')]})
        for obj in costcentres:
            structure.append({'id': 'db-cc_{}'.format(obj.pk),
                              'name': str(obj),
                              'email': slugify(obj.name),
                              'owner': getattr(obj.manager, 'email', defaultowner),
                              'members': [d[0] for d in qs.filter(cost_centre=obj).values_list('email')]})
        for obj in locations:
            structure.append({'id': 'db-loc_{}'.format(obj.pk),
                              'name': str(obj),
                              'email': slugify(obj.name) + '-location',
                              'owner': getattr(obj.manager, 'email', defaultowner),
                              'members': [d[0] for d in qs.filter(org_unit__location=obj).values_list('email')]})
        for obj in slocations:
            structure.append({'id': 'db-locs_{}'.format(obj.pk),
                              'name': str(obj),
                              'email': slugify(obj.name) + '-location',
                              'owner': getattr(obj.manager, 'email', defaultowner),
                              'members': [d[0] for d in qs.filter(org_unit__secondary_location=obj).values_list('email')]})
        for row in structure:
            if row['members']:
                row['email'] = '{}@{}'.format(
                    row['email'], row['members'][0].split('@', 1)[1])
        return structure

    def list(self, request):
        """Pass query params to modify the API output.
        Include `org_structure=true` and `sync_o365=true` to output only
        OrgUnits with sync_o365 == True.
        Include `populate_groups=true` to output only DepartmentUsers
        with populate_primary_group == True.
        """
        sync_o365 = True
        if 'sync_o365' in self.request.GET and self.request.GET['sync_o365'] == 'false':
            sync_o365 = False
        else:
            sync_o365 = True
        if 'populate_groups' in self.request.GET and self.request.GET['populate_groups'] == 'true':
            exclude_populate_groups = True  # Will exclude populate_primary_group == False
        else:
            exclude_populate_groups = False  # Will ignore populate_primary_group
        if 'org_structure' in self.request.GET:
            return self.org_structure(sync_o365=sync_o365, exclude_populate_groups=exclude_populate_groups)

        if 'all' in self.request.GET:
            # Return all DU objects, including those deleted in AD.
            users = DepartmentUser.objects.all()
        elif 'ad_deleted' in self.request.GET:
            if self.request.GET['ad_deleted'] == 'false':
                # Return all DU objects that are not deleted in AD (inc. inactive, shared, etc.)
                users = DepartmentUser.objects.filter(ad_deleted=False)
            elif self.request.GET['ad_deleted'] == 'true':
                # Return all DU objects that are deleted in AD (inc. inactive, shared, etc.)
                users = DepartmentUser.objects.filter(ad_deleted=True)
        else:
            # Return 'active' DU objects only.
            FILTERS = DepartmentUser.ACTIVE_FILTER.copy()
            # Filters below are exclusive.
            if 'email' in self.request.GET:
                FILTERS['email__iexact'] = self.request.GET['email']
            elif 'ad_guid' in self.request.GET:
                FILTERS['ad_guid__endswith'] = self.request.GET['ad_guid']
            elif 'cost_centre' in self.request.GET:
                FILTERS['cost_centre__code'] = self.request.GET['cost_centre']
            # Exclude shared and role-based account types.
            users = DepartmentUser.objects.filter(**FILTERS).exclude(account_type__in=[5, 9])

        users = users.order_by('name')
        # Parameters to modify the API output.
        if 'compact' in self.request.GET:
            self.VALUES_ARGS = self.COMPACT_ARGS
        elif 'minimal' in self.request.GET:
            self.VALUES_ARGS = self.MINIMAL_ARGS

        user_values = list(users.values(*self.VALUES_ARGS))
        return Response(self.formatters.format(self.request, user_values))

    def is_authenticated(self):
        return True

    @csrf_exempt
    def put(self,request,pk=None):
        user = self.userExists()
        if user :
            if self.request.data.get('Deleted'):
                user.active = False
                user.ad_deleted = True
                user.ad_updated = True
                user.save()

                data = list(DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS))[0]
                logger.info("Removed user {} \n{}".format(user.name,self.formatters.format(self.request, data)))

                return Response(self.formatters.format(self.request, data))

            modified = make_aware(user._meta.get_field('date_updated').clean(self.request.data['Modified'], user))
            print user
            if user.date_ad_updated or modified < user.date_updated:
                old_user = list(DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS))[0]
                updated_user = self.updateUser(user)
                data = list(DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS))[0]
                log_data = {
                    'old_user' : old_user['ad_data'],
                    'updated_user': updated_user.ad_data
                }
                logger.info("Updated user {}\n{}".format(user.name,self.formatters.format(request, log_data)))

            return Response(self.formatters.format(self.request, data))
        logger.error("User Does Not Exist")
        return Response(self.formatters.format(self.request, {"Error":"User Does Not Exist"}))

    def create(self,request):
        user = self.userExists()
        if not user :
            try:
                user = DepartmentUser(ad_guid=self.request.data['ObjectGUID'])
                user = self.updateUser(user)
                data = list(DepartmentUser.objects.filter(pk=user.pk).values(*self.VALUES_ARGS))[0]
                logger.info("Created User {} \n{} ".format(user.name,self.formatters.format(self.request, data)))
                return Response(self.formatters.format(self.request, data))
            except Exception as e:
                data = self.data
                data['Error'] = repr(e)
                logger.error(repr(e))
        logger.error("User Already Exist")
        return Response(self.formatters.format(self.request, {"Error":"User Already Exist"}))


    def updateUser(self,user):
        try:
            user.email = self.request.data['EmailAddress']
            user.ad_guid = self.request.data['ObjectGUID']
            user.ad_dn = self.request.data['DistinguishedName']
            user.username = self.request.data['SamAccountName']
            user.expiry_date = self.request.data.get('AccountExpirationDate')
            user.active = self.request.data['Enabled']
            user.ad_deleted = False
            user.ad_data = self.request.data
            if not user.name:
                user.name = self.request.data['Name']
            if self.request.data['Title']:
                user.title = self.request.data['Title']
            if not user.given_name:
                user.given_name = self.request.data['GivenName']
            if not user.surname:
                user.surname = self.request.data['Surname']
            user.date_ad_updated = self.request.data['Modified']
            user.ad_updated = True
            user.save()
            return user
        except Exception as e:
            raise e
        return False

    def userExists(self):
        ''' check if a user  exists '''
        try:
            user = DepartmentUser.objects.get(
                email__iexact=self.request.data['EmailAddress'])
        except:
            try:
                user = DepartmentUser.objects.get(
                    ad_guid__iendswith=self.request.data['ObjectGUID'])
            except:
                try:
                    user = DepartmentUser.objects.get(
                        ad_dn=self.request.data['DistinguishedName'])
                except:
                    return False
        return user
