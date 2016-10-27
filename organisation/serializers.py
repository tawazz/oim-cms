from rest_framework import serializers
from organisation.models import DepartmentUser

class DepartmentUserSerializer(serializers.ModelSerializer):
    """docstring for DepartmentUserSerializer."""
    class Meta:
        model = DepartmentUser
        fields = '__all__'
