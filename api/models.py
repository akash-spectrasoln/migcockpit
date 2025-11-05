from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.db import connection


class SourceDB(models.Model):
    src_db = models.CharField(max_length=255)

    def __str__(self):
        return self.src_db

    class Meta:
        db_table = 'sourcedb' 

class SourceForm(models.Model):
    src_db = models.ForeignKey(SourceDB, on_delete=models.CASCADE)
    attribute_name = models.CharField(max_length=100)
    input_type = models.CharField(max_length=100)
    label_name = models.CharField(max_length=100)
    is_required = models.BooleanField(default=False)

    class Meta:
        db_table = 'sourceform' 


class Country(models.Model):
    """Model representing countries."""
    
    country_id = models.CharField(max_length=100, verbose_name='Country ID')
    name = models.CharField(max_length=100, verbose_name='Country Name')

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'country'


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication without username."""
    
    def create_user(self, email, first_name, last_name, created_by, password=None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            created_by=created_by,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, first_name, last_name, created_by, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, first_name, last_name, created_by, password, **extra_fields)


class User(AbstractUser):
    """Custom User model extending AbstractUser with additional fields."""
    
    # username = models.CharField(max_length=50, unique=True, verbose_name='Username' , null=True)
    username = None  # Remove username field from AbstractUser
    cust_id = models.ForeignKey('Customer', on_delete=models.CASCADE, verbose_name='Customer ID', null=True, blank=True)
    email = models.EmailField(max_length=50, unique=True, verbose_name='Email')
    first_name = models.CharField(max_length=50, verbose_name='First Name')
    last_name = models.CharField(max_length=50, verbose_name='Last Name')
    created_by = models.CharField(max_length=50, verbose_name='Created By'  )
    created_on = models.DateTimeField(default=timezone.now, verbose_name='Created On')
    modified_on = models.DateTimeField(auto_now=True, verbose_name='Modified On')
    modified_by = models.CharField(max_length=50, blank=True, null=True, verbose_name='Modified By')
    is_active = models.BooleanField(default=True, verbose_name='active',)
    download_format_choice = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('tsv', 'TSV')
    ]
    file_format = models.CharField(max_length=10, choices=download_format_choice, default='csv')
    date_format = models.CharField(max_length=10, default='MM-DD-YYYY')
    objects = UserManager()  # Use custom manager for email-based authentication

    USERNAME_FIELD = 'email' # Set email as the field used for authentication
    REQUIRED_FIELDS = ['first_name', 'last_name', 'created_by']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
                
    def set_password(self, raw_password):
        """
        Override set_password to encrypt password using AES encryption.
        Uses user's created_on timestamp as encryption key.
        """
        from encryption.encryption import encrypt_field
        import hashlib
        import json
        
        if raw_password is None:
            self.set_unusable_password()
            return
        
        from django.utils import timezone

        # Fetch the current time
        created_on = timezone.now()

        # Update the User model's created_on to this value
        self.created_on = created_on
        
        key_string = f"{created_on.strftime('%Y%m%d%H%M%S')}"
        hash_object = hashlib.sha256(key_string.encode())
        encryption_key = int(hash_object.hexdigest()[:8], 16)
        
        # Encrypt the password
        encrypted_password = encrypt_field(raw_password, encryption_key)
        
        # Store as JSON string in password field
        self.password = json.dumps(encrypted_password)
    
    def check_password(self, raw_password):
        """
        Override check_password to decrypt and compare passwords.
        Uses users's created_on timestamp for decryption.
        """
        from encryption.encryption import decrypt_field
        import hashlib
        import json
        
        if self.password.startswith('!'):
            return False
        
        try:
            
            
            key_string = f"{self.created_on.strftime('%Y%m%d%H%M%S')}"
            hash_object = hashlib.sha256(key_string.encode())
            encryption_key = int(hash_object.hexdigest()[:8], 16)
            
            # Load encrypted password from JSON
            encrypted_data = json.loads(self.password)
            
            # Decrypt the password
            decrypted_password = decrypt_field(
                encrypted_data=encrypted_data[0],
                cmp_id=encryption_key,
                nonce=encrypted_data[1],
                tag=encrypted_data[2],
                salt=encrypted_data[3],
                original_type=encrypted_data[4],
                iterations=encrypted_data[5]
            )
            return decrypted_password == raw_password
        except Exception as e:
            print(f"Error checking password: {str(e)}")
            return False
    
    
    class Meta:
        db_table = 'user'


class Customer(models.Model):
    """Model representing customers."""
    
    cust_id = models.CharField(max_length=10, verbose_name='Customer ID')
    name = models.CharField(max_length=100, verbose_name='Customer Name')
    street1 = models.CharField(max_length=100, verbose_name='Street 1')
    street2 = models.CharField(max_length=100, blank=True, null=True, verbose_name='Street 2')
    city = models.CharField(max_length=100, verbose_name='City')
    region = models.CharField(max_length=100, verbose_name='Region')
    country = models.ForeignKey(Country, on_delete=models.PROTECT, verbose_name='Country')
    phone = models.CharField(max_length=20, verbose_name='Phone')
    cust_db = models.CharField(max_length=10, unique=True, verbose_name='Customer Database')
    created_by = models.CharField(max_length=50, verbose_name='Created By')
    created_on = models.DateTimeField(default=timezone.now, verbose_name='Created On')
    modified_on = models.DateTimeField(auto_now=True, verbose_name='Modified On')
    modified_by = models.CharField(max_length=50, blank=True, null=True, verbose_name='Modified By')
    active = models.BooleanField(default=True, verbose_name='Active')
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Override save method to handle ID generation."""
        # If this is a new customer (no cust_id yet)
        if not self.cust_id:
            # Generate cust_id in the format C00001, C00002, etc.
            next_id = self.get_next_customer_id()
            self.cust_id = f"C{next_id:05d}"
            # Set cust_db to be the same as cust_id
            self.cust_db = self.cust_id
        
        # Call the parent save method
        super().save(*args, **kwargs)
    
    def get_next_customer_id(self):
        """Get the next available customer ID."""
        try:
            # Get all existing cust_ids and extract the numeric part
            existing_customers = Customer.objects.values_list('cust_id', flat=True)
            
            if not existing_customers:
                return 1
            
            # Extract numeric parts from existing cust_ids (e.g., "C00001" -> 1)
            numeric_ids = []
            for cust_id in existing_customers:
                if cust_id and cust_id.startswith('C'):
                    try:
                        numeric_part = int(cust_id[1:])  # Remove 'C' prefix and convert to int
                        numeric_ids.append(numeric_part)
                    except ValueError:
                        continue
            
            # If no valid numeric IDs found, start with 1
            if not numeric_ids:
                return 1
            
            # Return the highest numeric ID + 1
            return max(numeric_ids) + 1
            
        except Exception as e:
            # Fallback to 1 if there's an error
            print(f"Error getting next customer ID: {str(e)}")
            return 1
    
    def create_customer_database(self):
        """Create a new database for the customer."""
        import psycopg2
        from django.conf import settings
        
        database_created = False
        conn = None
        cursor = None
        
        try:
            # Connect to PostgreSQL server using the 'postgres' database to create new databases
            # Use a completely separate connection to avoid transaction conflicts
            conn = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD'],
                database='postgres'  # Connect to default postgres database to create new databases
            )
            conn.autocommit = True  # Enable autocommit to avoid transaction issues
            cursor = conn.cursor()
            
            # Check if database already exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s;", 
                (self.cust_db,)
            )
            
            if cursor.fetchone():
                print(f"Database {self.cust_db} already exists")
            else:
                # Create the database
                cursor.execute(f'CREATE DATABASE "{self.cust_db}";')
                print(f"Created database: {self.cust_db}")
                database_created = True
                
                try:
                    # Create schemas in the new database
                    self.create_customer_schemas()
                except Exception as schema_error:
                    # If schema creation fails, drop the database to maintain consistency
                    print(f"Schema creation failed, rolling back database creation for {self.cust_db}")
                    cursor.execute(f'DROP DATABASE IF EXISTS "{self.cust_db}";')
                    raise schema_error
            
        except Exception as e:
            print(f"Error creating database {self.cust_db}: {str(e)}")
            raise Exception(f"Failed to create customer database: {str(e)}")
        
        finally:
            # Ensure connections are always closed
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def create_customer_schemas(self):
        """Create schemas in the customer's database."""
        import psycopg2
        from django.conf import settings
        
        conn = None
        cursor = None
        
        try:
            # Connect to the customer's new database
            conn = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD'],
                database=self.cust_db
            )
            conn.autocommit = True  # Enable autocommit to avoid transaction issues
            cursor = conn.cursor()
            
            # Create main schema for customer data
            main_schema = "GENERAL"
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{main_schema}";')
            
            # Create Source table in the GENERAL schema
            source_table_sql = f'''
            CREATE TABLE IF NOT EXISTS "{main_schema}".source (
                id SERIAL PRIMARY KEY,
                src_name VARCHAR(255),
                src_config TEXT,
                created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            );
            '''
            cursor.execute(source_table_sql)
            
            # Create Destination table in the GENERAL schema
            destination_table_sql = f'''
            CREATE TABLE IF NOT EXISTS "{main_schema}".destination (
                id SERIAL PRIMARY KEY,
                dest_name VARCHAR(255),
                dest_config TEXT,
                created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            );
            '''
            cursor.execute(destination_table_sql)

            sequence_table_sql = f'''
            CREATE TABLE IF NOT EXISTS "{main_schema}".tbl_col_seq (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100),
                table_name VARCHAR(100),
                sequence VARCHAR(400),
                seq_name VARCHAR(100),
                scope VARCHAR(10) CHECK (scope IN ('G', 'L'))
            );
            '''
            cursor.execute(sequence_table_sql)
            
            print(f"Created schemas and tables in database {self.cust_db}: {main_schema}")
            
        except Exception as e:
            print(f"Error creating schemas in database {self.cust_db}: {str(e)}")
            raise Exception(f"Failed to create schemas in customer database: {str(e)}")
        
        finally:
            # Ensure connections are always closed
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    class Meta:
        db_table = 'customer'

class ObjectMap(models.Model):
    object_id = models.CharField(max_length=100)
    tecname = models.CharField(max_length=100)
    object_nme = models.CharField(max_length=100)
    tname = models.CharField(max_length=100) 

    class Meta:
        db_table = 'objectmap'


class ValidationRules(models.Model):
    question = models.CharField(max_length=200)
    expression = models.CharField(max_length=200)
    category = models.CharField(max_length=100,null=True)

    class Meta:
        db_table = 'validationrules'


    

