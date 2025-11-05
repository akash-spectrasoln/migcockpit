from rest_framework import serializers
from .models import SourceDB, SourceForm, Customer, Country, User , ValidationRules

class SqlConnectionSerializer(serializers.Serializer):
    sql_hostname = serializers.CharField(required=True)
    sql_database = serializers.CharField(required=True)
    sql_username = serializers.CharField(required=True)
    sql_password = serializers.CharField(required=True)
    
    

class SourceDbSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceDB
        fields = ['id', 'src_db']


class SourceFormSerializer(serializers.ModelSerializer):
    src_db = SourceDbSerializer(read_only=True)  # Nested representation of Source

    class Meta:
        model = SourceForm
        fields = ['id', 'src_db', 'attribute_name', 'input_type', 'label_name', 'is_required']

class ValidationRulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationRules
        fields = ['id', 'question', 'expression','category']


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['country_id', 'name']


class SourceConnectionSerializer(serializers.Serializer):

    source_name = serializers.CharField(required=True)
    hostname = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    port = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=65535)
    user = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    schema = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    def validate(self, data):
        """Validate that if any connection fields are provided, all required ones are present."""
        hostname = data.get('hostname')
        port = data.get('port')
        user = data.get('user')
        password = data.get('password')
        
        # If any connection field is provided, all required fields must be present
        connection_fields = [hostname, port, user, password]
        provided_fields = [field for field in connection_fields if field is not None and field != '']
        
        if provided_fields:  # If any connection field is provided
            if not hostname or not hostname.strip():
                raise serializers.ValidationError({
                    'hostname': 'Hostname is required when providing connection details.'
                })
            if port is None:
                raise serializers.ValidationError({
                    'port': 'Port is required when providing connection details.'
                })
            if not user or not user.strip():
                raise serializers.ValidationError({
                    'user': 'Username is required when providing connection details.'
                })
            if not password:
                raise serializers.ValidationError({
                    'password': 'Password is required when providing connection details.'
                })
        
        return data


class DestinationConnectionSerializer(serializers.Serializer):
    destination_name = serializers.CharField(required=True)
    hostname = serializers.CharField(required=True)
    instance_number = serializers.IntegerField(required=True)
    mode = serializers.ChoiceField(
        choices=['single_container', 'multiple_containers'],
        required=True
    )
    database_type = serializers.ChoiceField(
        choices=['tenant_database', 'system_database'],
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Required only when mode is 'multiple_containers'"
    )
    tenant_db_name = serializers.CharField(
        required=False, 
        allow_blank=True, 
        allow_null=True,
        help_text="Required when database_type is 'tenant_database'"
    )
    system_db_name = serializers.CharField(
        required=False, 
        allow_blank=True, 
        allow_null=True,
        help_text="Required when database_type is 'system_database'"
    )
    destination_schema_name = serializers.CharField(
        required=True,
        help_text="Schema name for the destination database"
    )
    s4_schema_name = serializers.CharField(
        required=True,
        help_text="S4 schema name for the destination database"
    )
    
    def validate(self, data):
        """Validate database type and names based on mode."""
        mode = data.get('mode')
        database_type = data.get('database_type')
        tenant_db_name = data.get('tenant_db_name')
        system_db_name = data.get('system_db_name')
        
        # If mode is multiple_containers, database_type is required
        if mode == 'multiple_containers' and not database_type:
            raise serializers.ValidationError({
                'database_type': 'This field is required when mode is multiple_containers.'
            })
        
        # If database_type is tenant_database, tenant_db_name is required
        if database_type == 'tenant_database' and not tenant_db_name:
            raise serializers.ValidationError({
                'tenant_db_name': 'This field is required when database_type is tenant_database.'
            })
        
        # If database_type is system_database, system_db_name is required
        if database_type == 'system_database' and not system_db_name:
            raise serializers.ValidationError({
                'system_db_name': 'This field is required when database_type is system_database.'
            })
        
        return data


class FileUploadSerializer(serializers.Serializer):
    """Serializer for file upload handling CSV and Excel files."""
    file = serializers.FileField(
        required=True,
        help_text="Upload a CSV (.csv) or Excel (.xlsx) file"
    )
    
    def validate_file(self, value):
        """Validate that the uploaded file is CSV or Excel format."""
        if not value:
            raise serializers.ValidationError("No file provided.")
        
        # Get file extension
        file_extension = value.name.lower().split('.')[-1]
        
        # Check if file extension is supported
        if file_extension not in ['csv', 'xlsx']:
            raise serializers.ValidationError(
                "Only CSV (.csv) and Excel (.xlsx) files are supported."
            )
        
        return value

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = "__all__"
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','email', 'first_name', 'last_name', 'cust_id', 'created_by', 'created_on', 'modified_on', 'modified_by', 'is_active']
        read_only_fields = ['created_on', 'modified_on', 'created_by', 'modified_by']
        
    def create(self, validated_data):
        user= User(**validated_data)
        user.set_password("defaultpassword")
        user.save()
        return user