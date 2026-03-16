"""
Expression and column-related API views.
Handles column filtering, statistics, and sequence management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from api.authentications import JWTCookieAuthentication
from api.utils.helpers import ensure_user_has_customer
from django.conf import settings
from api.models import Customer, User
import logging
import json
import psycopg2
try:
    import pandas as pd
except ImportError:
    pd = None
try:
    import pycountry
except ImportError:
    pycountry = None
try:
    import pgeocode
except ImportError:
    pgeocode = None
try:
    import country_converter as cc
except ImportError:
    cc = None
try:
    import pint
except ImportError:
    pint = None

logger = logging.getLogger(__name__)

class FilterColumnValuesView(APIView):
    """
    API endpoint for filtering column values.
    """
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]



# Helper functions for column statistics
def get_column_info(column_name):
    """
    Get column information from column_categories.json
    """
    with open('column_categories.json', 'r') as f:
        column_categories = json.load(f)
        for category, value in column_categories.items():
            if isinstance(value,list) and column_name in value:
                return category
            elif isinstance(value,dict) and "columns" in value and column_name in value["columns"]:
                return category
    return None
 

 # Helper function for column statistics
def get_category_columns(column_name):
    """
    Get category columns from column_categories.json
    """
    with open('column_categories.json', 'r') as f:
        column_categories = json.load(f)
        return column_categories.get(column_name, None)

# hepler function for column statistics
def check_columns_in_table(cursor, schema, table_name, category_columns):
    """
    Check if any columns from category_columns exist in the table
    """
    if not category_columns:
        return []
    
    # Create placeholders for the IN clause
    placeholders = ','.join(['%s'] * len(category_columns))
    
    query = f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = %s 
        AND table_name = %s 
        AND column_name IN ({placeholders})
    """
    
    cursor.execute(query, [schema, table_name] + category_columns)
    existing_columns = [row[0] for row in cursor.fetchall()]

    if len(existing_columns) > 0:
        return existing_columns[0]
    return None

class ColumnStatisticsView(APIView):
    """
    API endpoint for getting column statistics.
    """
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        column_name = request.data.get('column_name')
        table_name = request.data.get('table_name')
        schema = request.data.get('schema')
        # user_email = request.data.get('user')

        if not column_name or not table_name or not schema:
            return Response(
                {"error": "Column name, table name and schema are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        column_category = get_column_info(column_name)

        if not column_category:
            return Response(
                {"error": "Column category not found."},
                status=status.HTTP_400_BAD_REQUEST
            )
        user = request.user
        # user=User.objects.get(email=user_email)
        customer = user.cust_id
        if not customer:
            return Response(
                {"error": "User is not associated with any customer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if pd is None:
            return Response(
                {
                    "error": "pandas is not available. Column statistics for date/country/units require pandas. "
                    "Fix with: pip uninstall -y pandas && pip install \"pandas==2.2.3\""
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        if column_category in ("country_code", "currency_code", "subdivision_code") and pycountry is None:
            return Response(
                {"error": "pycountry is not available. Install with: pip install pycountry"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if column_category == "postal_code" and (pgeocode is None or pycountry is None):
            return Response(
                {"error": "pgeocode/pycountry not available (pandas may be broken). Fix with: pip uninstall -y pandas && pip install \"pandas==2.2.3\""},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if column_category == "subdivision_code" and cc is None:
            return Response(
                {"error": "country_converter is not available. Install with: pip install country_converter"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if column_category == "units" and pint is None:
            return Response(
                {"error": "pint is not available. Install with: pip install pint"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            connection = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD'],
                database=customer.cust_db
            )
            with connection.cursor() as cursor:

                if column_category == 'numerical':
                    cursor.execute(f"""
                        SELECT 
                            MIN("{column_name}"), 
                            MAX("{column_name}"), 
                            COUNT(*),
                            COUNT(CASE WHEN "{column_name}" = 0 THEN 1 END) as zero_count,
                            COUNT(CASE WHEN "{column_name}" IS NULL THEN 1 END) as null_count
                        FROM "{schema}"."{table_name}"
                    """)
                    
                    result = cursor.fetchone()
                    min_val, max_val, total_count, zero_count, null_count = result
                    
                    return Response({
                        "column_name": column_name,
                        "column_category": column_category,
                        "statistics": {
                            "min_value": min_val,
                            "max_value": max_val,
                            "total_count": total_count,
                            "zero_count": zero_count,
                            "null_count": null_count
                        }
                    })

                elif column_category == 'string':
                    # Get basic statistics
                    cursor.execute(f"""
                        SELECT 
                            COUNT(*) as total_count,
                            COUNT(CASE WHEN "{column_name}" IS NULL THEN 1 END) as null_count
                        FROM "{schema}"."{table_name}"
                    """)
                    
                    result = cursor.fetchone()
                    total_count, null_count = result
                    
                    # Get distinct values and their counts
                    cursor.execute(f"""
                        SELECT 
                            "{column_name}" as value,
                            COUNT(*) as count
                        FROM "{schema}"."{table_name}"
                        WHERE "{column_name}" IS NOT NULL
                        GROUP BY "{column_name}"
                        ORDER BY "{column_name}" ASC
                    """)
                    
                    distinct_values = cursor.fetchall()
                    return Response({
                        "column_name": column_name,
                        "column_category": column_category,
                        "statistics": {
                            "total_count": total_count,
                            "null_count": null_count,
                            "distinct_values": [
                                {"value": row[0], "count": row[1]} 
                                for row in distinct_values
                            ]
                        }
                    })

                elif column_category == 'date':
                    # Load data using pandas for better date analysis
                    cursor.execute(f"""
                        SELECT "{column_name}"
                        FROM "{schema}"."{table_name}"
                    """)

                    
                    # Fetch all data and create DataFrame
                    data = cursor.fetchall()
                    df = pd.DataFrame(data, columns=[column_name])
                    
                    # Basic statistics
                    total_count = len(df)
                    null_count = df[column_name].isnull().sum()
                    non_null_count = df[column_name].notna().sum()
                    
                    # Count invalid dates and get min/max dates using pandas
                    non_null_data = df[column_name].dropna()
                    invalid_dates = []
                    invalid_date_count = 0
                    min_date = None
                    max_date = None
                    
                    if len(non_null_data) > 0:
                        # Convert to datetime with errors='coerce' - invalid dates become NaT
                        converted_dates = pd.to_datetime(non_null_data, errors='coerce')
                        
                        # Find invalid dates (where conversion resulted in NaT)
                        invalid_mask = converted_dates.isnull()
                        invalid_date_count = invalid_mask.sum()
                        
                        # Get valid dates (non-NaT)
                        valid_dates = converted_dates.dropna()
                        
                        if len(valid_dates) > 0:
                            min_date = str(valid_dates.min())
                            max_date = str(valid_dates.max())
                        
                    # Get the actual invalid date values for display
                    if invalid_date_count > 0:
                        invalid_dates = non_null_data[invalid_mask].tolist()
                        # Convert to string and remove duplicates
                        invalid_dates = list(set([str(date) for date in invalid_dates]))
                    
                    return Response({
                        "column_name": column_name,
                        "column_category": column_category,
                        "statistics": {
                            "total_count": int(total_count),
                            "null_count": int(null_count),
                            "non_null_count": int(non_null_count),
                            "min_date": min_date,
                            "max_date": max_date,
                            "invalid_date_count": int(invalid_date_count),
                            "invalid_dates": invalid_dates
                        }
                    })

                elif column_category == 'country_code':
                    # Load data using pandas for better country code analysis
                    cursor.execute(f"""
                        SELECT "{column_name}"
                        FROM "{schema}"."{table_name}"
                    """)
                    
                    # Fetch all data and create DataFrame
                    data = cursor.fetchall()
                    df = pd.DataFrame(data, columns=[column_name])
                    # Check if maximum character length in this column is more than three
                    max_char_len = df[column_name].dropna().astype(str).apply(len).max() if not df.empty else 0

                    if max_char_len > 3:
                        return Response(
                            {"error": "Maximum character length in this column is less than three."},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                      
                    # Basic statistics - null count and invalid country codes
                    null_count = df[column_name].isnull().sum()
                    
                    # Get distinct country codes with counts
                    distinct_countries = []
                    # Get distinct country codes and their counts
                    country_counts = df[column_name].dropna().astype(str).str.strip().str.upper().value_counts()
                    distinct_countries = [
                        {"value": code, "count": int(count)}
                        for code, count in country_counts.items()
                    ]
                    
                    # Validate country codes (ISO 3166-1 Alpha-3)
                    non_null_data = df[column_name].dropna()
                    invalid_country_codes = []
                    invalid_country_code_count = 0
                    
                    if len(non_null_data) > 0:
                        # Get all valid ISO 3166-1 Alpha-3 country codes
                        valid_country_codes = {country.alpha_2 for country in pycountry.countries} | {country.alpha_3 for country in pycountry.countries}

                        # Convert to string and strip whitespace, then to uppercase
                        non_null_data_str = non_null_data.astype(str).str.strip().str.upper()
                        
                        # Check length and validity
                        length_invalid_mask = non_null_data_str.str.len() > 3
                        not_in_valid_mask = ~non_null_data_str.isin(valid_country_codes)

                        # Combine masks using OR operator to find invalid entries
                        invalid_mask = length_invalid_mask | not_in_valid_mask

                        # Extract unique invalid country codes
                        invalid_country_codes = non_null_data_str[invalid_mask].unique().tolist()
                        invalid_country_code_count = len(invalid_country_codes)

                   
                     
                    return Response({
                        "column_name": column_name,
                        "column_category": column_category,
                        "statistics": {
                            "null_count": int(null_count),
                            "invalid_country_code_count": int(invalid_country_code_count),
                            "invalid_country_codes": invalid_country_codes,
                            "distinct_countries": distinct_countries
                        }
                        # "mismatched_country_codes": mismatched_country_codes 
                    })

                elif column_category == 'currency_code':
                    # Load data using pandas for better currency code analysis
                    cursor.execute(f"""
                        SELECT "{column_name}"
                        FROM "{schema}"."{table_name}"
                    """)
                    
                    # Fetch all data and create DataFrame
                    data = cursor.fetchall()
                    df = pd.DataFrame(data, columns=[column_name])
                    
                    # Basic statistics - null count
                    null_count = df[column_name].isnull().sum()
                    
                    # Get distinct currency codes and their counts
                    currency_counts = df[column_name].dropna().astype(str).str.strip().value_counts()
                    distinct_currencies = [
                        {"value": code, "count": int(count)}
                        for code, count in currency_counts.items()
                    ]
                    
                    # Validate currency codes
                    non_null_data = df[column_name].dropna()
                    invalid_currency_codes = []
                    invalid_currency_code_count = 0
                    
                    if len(non_null_data) > 0:
                        # Get all valid currency codes from pycountry
                        valid_currencies = {currency.alpha_3 for currency in pycountry.currencies}

                        
                        # Convert to string and strip whitespace, then to uppercase
                        non_null_data_str = non_null_data.astype(str).str.strip().str.upper()
                        
                        # Check validity of currency codes
                        not_in_valid_mask = ~non_null_data_str.isin(valid_currencies)
                        
                        # Extract unique invalid currency codes (original values as fetched from DB)
                        invalid_currency_codes = non_null_data[not_in_valid_mask].unique().tolist()
                        invalid_currency_code_count = len(invalid_currency_codes)
                        
    
                    return Response({
                        "column_name": column_name,
                        "column_category": column_category,
                        "statistics": {
                            "null_count": int(null_count),
                            "invalid_currency_code_count": int(invalid_currency_code_count),
                            "invalid_currency_codes": invalid_currency_codes,
                            "distinct_currencies": distinct_currencies
                        }
                    })
                elif column_category == 'region_category':
                    # First check if country_column_in_table exists
                    country_columns = get_category_columns('country_code')
                    country_column_in_table = None
                    if country_columns:
                        country_column_in_table = check_columns_in_table(cursor, schema, table_name, country_columns)
                    
                    # Only proceed with validation if country_column_in_table exists
                    if country_column_in_table:
                        # Load data using pandas for better region code analysis
                        cursor.execute(f"""
                            SELECT "{country_column_in_table}", "{column_name}"
                            FROM "{schema}"."{table_name}"
                        """)
                        # Fetch all data and create DataFrame
                        data = cursor.fetchall()
                        df = pd.DataFrame(data, columns=[country_column_in_table, column_name])

                        # Basic statistics - null count
                        null_count = df[column_name].isnull().sum()
                        
                        # Validate region codes
                        non_null_data = df[column_name].dropna()
                        invalid_region_codes = []
                        invalid_region_code_count = 0
                        mismatched_region_codes = []
                        mismatched_region_code_count = 0

                        if len(non_null_data) > 0:
                            # Get all valid subdivision codes from pycountry
                            valid_subdivisions = set()
                            for subdivision in pycountry.subdivisions:
                                if hasattr(subdivision, 'code'):
                                    valid_subdivisions.add(subdivision.code.upper().split('-')[-1])

                            # Convert to string and strip whitespace, then to uppercase
                            non_null_data_str = non_null_data.astype(str).str.strip().str.upper()
                            
                            # Check validity of region codes
                            not_in_valid_mask = ~non_null_data_str.isin(valid_subdivisions)
                            
                            # Extract unique invalid region codes (original values as fetched from DB)
                            invalid_region_codes = non_null_data[not_in_valid_mask].unique().tolist()
                            invalid_region_code_count = len(invalid_region_codes)
                            
                            # Check for region-country code mismatches
                            try:
                                # Get data for both region and country columns where both are not null
                                cursor.execute(f"""
                                    SELECT "{country_column_in_table}", "{column_name}"
                                    FROM "{schema}"."{table_name}"
                                    WHERE "{column_name}" IS NOT NULL AND "{country_column_in_table}" IS NOT NULL
                                """)
                                region_country_data = cursor.fetchall()
                                
                                if region_country_data:
                                    df_region_country = pd.DataFrame(region_country_data, columns=[country_column_in_table, column_name])
                                    
                                    # Create mapping from country code to valid region codes
                                    country_to_regions = {}
                                    for subdivision in pycountry.subdivisions:
                                        if hasattr(subdivision, 'country_code') and hasattr(subdivision, 'code'):
                                            country_code = subdivision.country_code.upper()
                                            region_code = subdivision.code.upper().split('-')[-1]
                                            if country_code not in country_to_regions:
                                                country_to_regions[country_code] = set()
                                            country_to_regions[country_code].add(region_code)
                                    
                                    # Process data for mismatch checking
                                    non_null_region_country = df_region_country.dropna()
                                    
                                    if len(non_null_region_country) > 0:
                                        # Convert country values to alpha_2 codes using bulk conversion
                                        country_values = non_null_region_country[country_column_in_table].astype(str).str.strip()
                                        country_values_list = country_values.tolist()
                                        # Bulk convert using country_converter
                                        country_codes_alpha2 = cc.convert(country_values_list, to='ISO2', not_found=None)
                                        country_codes_alpha2 = pd.Series(country_codes_alpha2)
                                        
                                        # Convert to uppercase for comparison
                                        country_codes_upper = country_codes_alpha2.astype(str).str.upper()
                                        region_codes_upper = non_null_region_country[column_name].astype(str).str.strip().str.upper()
                                        
                                        # Find mismatches where region code doesn't belong to the country
                                        mismatch_records = []
                                        for idx, row in non_null_region_country.iterrows():
                                            country_code = country_codes_upper.iloc[idx]
                                            region_code = region_codes_upper.iloc[idx]
                                            
                                            # Skip if country conversion failed (None or 'NONE')
                                            if country_code and country_code != 'NONE' and country_code in country_to_regions:
                                                if region_code not in country_to_regions[country_code]:
                                                    mismatch_records.append({
                                                        column_name: row[column_name],
                                                        country_column_in_table: row[country_column_in_table]
                                                    })
                                        
                                        # Get unique mismatched combinations
                                        if mismatch_records:
                                            df_mismatches = pd.DataFrame(mismatch_records)
                                            mismatched_region_codes = (
                                                df_mismatches
                                                .drop_duplicates()
                                                .to_dict('records')
                                            )
                                            mismatched_region_code_count = len(mismatched_region_codes)
                                        
                            except Exception as e:
                                # If there's an error in mismatch checking, set defaults
                                mismatched_region_codes = []
                                mismatched_region_code_count = 0
                            
                            # Get distinct regions grouped by country
                            regions_counts = df.groupby([country_column_in_table, column_name]).size()
                            distinct_regions = [
                                {
                                    "value": {
                                        country_column_in_table: str(country_val),
                                        column_name: str(region_val)
                                    },
                                    "count": int(count)
                                }
                                for (country_val, region_val), count in regions_counts.items()
                            ]

                        return Response({
                            "column_name": column_name,
                            "column_category": column_category,
                            "column_in_table": country_column_in_table,
                            "statistics": {
                                "null_count": int(null_count),
                                "total_count": len(df),
                                "distinct_regions": distinct_regions,
                                "invalid_region_category_count": invalid_region_code_count,
                                "invalid_region_categories": invalid_region_codes,
                                "mismatched_region_category_count": int(mismatched_region_code_count),
                                "mismatched_region_categories": mismatched_region_codes
                            }
                        })
                    else:
                        # If country_column_in_table doesn't exist, return response indicating it's required
                        return Response({
                            "column_name": column_name,
                            "column_category": column_category,
                            "column_in_table": None,
                            "error": "country_column_in_table is required for region_category validation"
                        }, status=400)

                elif column_category == 'postal_code':
                    # First check if country_code column exists in the table
                    country_columns = get_category_columns('country_code')
                    country_column_in_table = None
                    if country_columns:
                        country_column_in_table = check_columns_in_table(cursor, schema, table_name, country_columns)
                    
                    # Check if country column exists
                    if country_column_in_table:
                        # Load both country_code and postal_code columns together
                        print(country_column_in_table, column_name)
                        cursor.execute(f"""
                            SELECT "{country_column_in_table}", "{column_name}"
                            FROM "{schema}"."{table_name}"
                        """)
                        data = cursor.fetchall()
                        df = pd.DataFrame(data, columns=[country_column_in_table, column_name])

                        # # Check if maximum character length in postal_code column is more than three
                        # max_char_len = df[country_column_in_table].dropna().astype(str).apply(len).max() if not df.empty else 0

                        # if max_char_len > 3:
                        #     return Response(
                        #         {"error": "Maximum character length in this column is less than three."},
                        #         status=status.HTTP_400_BAD_REQUEST
                        #     )
                        
                        # Basic statistics
                        null_count = df[column_name].isnull().sum()
                        non_null_count = df[column_name].notna().sum()
                        total_count = len(df)

                        df_postal_country = df.dropna(subset=[country_column_in_table, column_name]).copy()
                        if len(df_postal_country) > 0:
                            postal_counts = df_postal_country.groupby([country_column_in_table, column_name]).size()
                            distinct_postal_codes = [
                                {
                                    "value": {
                                        country_column_in_table: str(country_val),
                                        column_name: str(postal_val)
                                    },
                                    "count": int(count)
                                }
                                for (country_val, postal_val), count in postal_counts.items()
                            ]
            
                        
                        # Get non-null data for validation - both postal_code and country must be present
                        df_validation = df.dropna(subset=[column_name, country_column_in_table]).copy()
                        
                        if len(df_validation) > 0:
                            # Cache for Nominatim objects
                            nomi_cache = {}

                            def get_alpha2_country(country):
                                """Convert country name or code to ISO alpha-2 code."""
                                if not country:
                                    return None
                                country = country.strip()
                                # If already 2 letters, assume it's alpha-2
                                if len(country) == 2:
                                    return country.upper()
                                try:
                                    return pycountry.countries.lookup(country).alpha_2
                                except LookupError:
                                    return None

                            def is_valid_postal(country_input, postal_code):
                                try:
                                    if postal_code is None or str(postal_code).strip() == "":
                                        return False
                                    
                                    country_code = get_alpha2_country(country_input)
                                    if not country_code:
                                        return False
                                    
                                    # Use cached Nominatim object
                                    if country_code not in nomi_cache:
                                        nomi_cache[country_code] = pgeocode.Nominatim(country_code)
                                    
                                    nomi = nomi_cache[country_code]
                                    loc = nomi.query_postal_code(str(postal_code))
                                    return not pd.isna(loc.get('country_code'))
                                except:
                                    return False
                            df_validation['is_valid'] = df_validation.apply(lambda row: is_valid_postal(row[country_column_in_table], row[column_name]), axis=1)

                            # Step 5: Extract all mismatched records (invalid postal codes)
                            df_mismatched = df_validation[~df_validation['is_valid']].copy()
                            
                            if len(df_mismatched) > 0:
                                # Get unique mismatched postal codes with their country codes
                                df_mismatched_unique = df_mismatched[[country_column_in_table, column_name]].drop_duplicates()
                                mismatched_postal_codes = df_mismatched_unique.to_dict('records')
                                mismatched_postal_code_count = len(mismatched_postal_codes)
                            else:
                                mismatched_postal_codes = []
                                mismatched_postal_code_count = 0
                        else:
                            # No non-null data to validate
                            mismatched_postal_codes = []
                            mismatched_postal_code_count = 0

                    
                    else:
                        # No country_code column exists - cannot validate without country
                        return Response({
                            "error": "country_code column required for postal_code validation"
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    return Response({
                        "column_name": column_name,
                        "column_category": column_category,
                        "column_in_table": country_column_in_table,
                        "statistics": {
                            "null_count": int(null_count),
                            "non_null_count": int(non_null_count),
                            "total_count": int(total_count),
                            "distinct_postal_codes": distinct_postal_codes,
                            "mismatched_postal_code_count": int(mismatched_postal_code_count),
                            "mismatched_postal_codes": mismatched_postal_codes
                        }
                    })

                elif column_category == 'units':
                    # Load data using pandas for better unit analysis
                    cursor.execute(f"""
                        SELECT "{column_name}"
                        FROM "{schema}"."{table_name}"
                    """)
                    
                    # Fetch all data and create DataFrame
                    data = cursor.fetchall()
                    df = pd.DataFrame(data, columns=[column_name])
                    
                    # Basic statistics
                    null_count = df[column_name].isnull().sum()
                    
                    # Get distinct units and their counts
                    unit_counts = df[column_name].dropna().astype(str).str.strip().value_counts()
                    distinct_values = [
                        {"value": str(unit), "count": int(count)}
                        for unit, count in unit_counts.items()
                    ]
                    
                    # Validate units using pint
                    invalid_units = []
                    
                    non_null_data = df[column_name].dropna()
                    if len(non_null_data) > 0:
                        # Create UnitRegistry instance
                        ureg = pint.UnitRegistry()
                        
                        # Convert to string and strip whitespace
                        non_null_data_str = non_null_data.astype(str).str.strip()
                        
                        # Function to validate a unit string (case-insensitive)
                        def is_valid_unit(unit_str):
                            """Validate if a unit string is a valid pint unit expression"""
                            try:
                                # Try to parse the expression in lowercase for validation
                                ureg.parse_expression(unit_str.lower())
                                return True
                            except Exception:
                                return False
                        
                        # Apply validation to each unit
                        is_valid_mask = non_null_data_str.apply(is_valid_unit)
                        
                        # Get invalid units (preserve original case)
                        invalid_mask = ~is_valid_mask
                        invalid_units = non_null_data_str[invalid_mask].unique().tolist()
                    
                    return Response({
                        "column_name": column_name,
                        "column_category": column_category,
                        "statistics": {
                            "null_count": int(null_count),
                            "distinct_values": distinct_values,
                            "invalid_units": invalid_units
                        }
                    })
                # else:
                #     cursor.execute(f"""
                #         SELECT "{column_name}"
                #         FROM "{schema}"."{table_name}"
                #     """)
                    
                #     # Fetch all data and create DataFrame
                #     data = cursor.fetchall()
                #     df = pd.DataFrame(data, columns=[column_name])
                    
                #     # Basic statistics
                #     null_count = df[column_name].isnull().sum() 
                #     category = get_column_info(column_name)   

        except Exception as e:
            return Response({
                "error": f"error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ColumnSequenceListView(APIView):
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            table_name = request.query_params.get('table_name')
            user = request.user
            customer = user.cust_id
            if not customer:
                return Response(
                    {"error": "User is not associated with any customer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not table_name:
                return Response(
                    {"error": "table_name is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            customer_connection = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                database=customer.cust_db,
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD']
            )
            customer_connection.autocommit = True
            with customer_connection.cursor() as cursor:
                sql = """
                    SELECT seq_name, username, scope
                    FROM "GENERAL"."tbl_col_seq"
                    WHERE table_name = %s
                    AND (
                        username = %s
                        OR scope = 'G'
                    )
                    ORDER BY seq_name
                """
                cursor.execute(sql, (table_name, user.email))
                rows = cursor.fetchall()
                result = [
                    {
                        "seq_name": row[0],
                        "username": row[1],
                        "scope": row[2],
                        "is_owner": row[1] == user.email or row[2] == 'G'  # Global sequences can be edited by anyone
                    }
                    for row in rows
                ]
            customer_connection.close()
            return Response({"sequences": result})
        except Exception as e:
            return Response({
                "error": f"error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ColumnSequenceView(APIView):
    authentication_classes = [JWTCookieAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            table_name = request.query_params.get('table_name')
            user = request.user
            customer = user.cust_id
            if not customer:
                return Response(
                    {"error": "User is not associated with any customer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not table_name:
                return Response(
                    {"error": "table_name and schema are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            customer_connection = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                database=customer.cust_db,
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD']
            )
            customer_connection.autocommit = True
            with customer_connection.cursor() as cursor:
                # Fetch user-specific sequences and global ones for table
                sql = f"""
                    SELECT seq_name, sequence
                    FROM "GENERAL"."tbl_col_seq"
                    WHERE table_name = %s
                    AND (
                        username = %s
                        OR scope = 'G'
                    )
                    ORDER BY 
                        seq_name
                """
                cursor.execute(sql, (table_name, user.email))
                rows = cursor.fetchall()
                result = [
                    {
                        "seq_name": row[0],
                        "sequence": row[1],
                    }
                    for row in rows
                ]
            customer_connection.close()
            return Response({"sequences": result})
        except Exception as e:
            return Response({
                "error": f"error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Create a new column sequence"""
        try:
            table_name = request.data.get('table_name')
            sequence = request.data.get('sequence')
            seq_name = request.data.get('seq_name')
            scope = request.data.get('scope', 'L')  # Default to Local scope
            user = request.user
            customer = user.cust_id
            
            if not customer:
                return Response(
                    {"error": "User is not associated with any customer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not table_name or not sequence or not seq_name:
                return Response(
                    {"error": "table_name, sequence, and seq_name are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            customer_connection = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                database=customer.cust_db,
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD']  
            )
            customer_connection.autocommit = True
            
            with customer_connection.cursor() as cursor:
                # Check if sequence name already exists for this table and user
                check_sql = """
                    SELECT seq_name FROM "GENERAL"."tbl_col_seq"
                    WHERE table_name = %s AND seq_name = %s AND username = %s
                """
                cursor.execute(check_sql, (table_name, seq_name, user.email))
                existing = cursor.fetchone()
                
                if existing:
                    customer_connection.close()
                    return Response(
                        {"error": f"Sequence name '{seq_name}' already exists for this table."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Insert new sequence
                sql = """
                    INSERT INTO "GENERAL"."tbl_col_seq" (username, table_name, sequence, seq_name, scope)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (user.email, table_name, sequence, seq_name, scope))
            
            customer_connection.close()
            return Response({"message": f"Sequence '{seq_name}' created successfully"})
        except Exception as e:
            return Response({
                "error": f"Failed to create sequence: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        """Update an existing column sequence"""
        try:
            table_name = request.data.get('table_name')
            sequence = request.data.get('sequence')
            seq_name = request.data.get('seq_name')
            old_seq_name = request.data.get('old_seq_name')  # For renaming
            scope = request.data.get('scope', 'L')
            user = request.user
            customer = user.cust_id
            
            if not customer:
                return Response(
                    {"error": "User is not associated with any customer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not table_name or not sequence or not seq_name:
                return Response(
                    {"error": "table_name, sequence, and seq_name are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            customer_connection = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                database=customer.cust_db,
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD']
            )
            customer_connection.autocommit = True
            
            with customer_connection.cursor() as cursor:
                # Use old_seq_name if provided (for renaming), otherwise use seq_name
                update_seq_name = old_seq_name if old_seq_name else seq_name
                
                # Check if user owns this sequence or if it's a global sequence
                check_sql = """
                    SELECT username, scope FROM "GENERAL"."tbl_col_seq"
                    WHERE table_name = %s AND seq_name = %s
                """
                cursor.execute(check_sql, (table_name, update_seq_name))
                result = cursor.fetchone()
                
                if not result:
                    customer_connection.close()
                    return Response(
                        {"error": f"Sequence '{update_seq_name}' not found."},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Allow editing if user owns the sequence OR if it's a global sequence
                if result[0] != user.email and result[1] != 'G':
                    customer_connection.close()
                    return Response(
                        {"error": "You don't have permission to edit this sequence."},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # If renaming, check if new name already exists
                if old_seq_name and old_seq_name != seq_name:
                    cursor.execute(check_sql, (table_name, seq_name))
                    if cursor.fetchone():
                        customer_connection.close()
                        return Response(
                            {"error": f"Sequence name '{seq_name}' already exists."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                # Update sequence (keep original username if updating global sequence)
                update_sql = """
                    UPDATE "GENERAL"."tbl_col_seq"
                    SET sequence = %s, seq_name = %s, scope = %s
                    WHERE table_name = %s AND seq_name = %s
                """
                cursor.execute(update_sql, (sequence, seq_name, scope, table_name, update_seq_name))
            
            customer_connection.close()
            return Response({"message": f"Sequence '{seq_name}' updated successfully"})
        except Exception as e:
            return Response({
                "error": f"Failed to update sequence: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request):
        """Delete a column sequence"""
        try:
            table_name = request.data.get('table_name')
            seq_name = request.data.get('seq_name')
            user = request.user
            customer = user.cust_id
            
            if not customer:
                return Response(
                    {"error": "User is not associated with any customer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not table_name or not seq_name:
                return Response(
                    {"error": "table_name and seq_name are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            customer_connection = psycopg2.connect(
                host=settings.DATABASES['default']['HOST'],
                port=settings.DATABASES['default']['PORT'],
                database=customer.cust_db,
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD']
            )
            customer_connection.autocommit = True
            
            with customer_connection.cursor() as cursor:
                # Check if user owns this sequence or if it's a global sequence
                check_sql = """
                    SELECT username, scope FROM "GENERAL"."tbl_col_seq"
                    WHERE table_name = %s AND seq_name = %s
                """
                cursor.execute(check_sql, (table_name, seq_name))
                result = cursor.fetchone()
                
                if not result:
                    customer_connection.close()
                    return Response(
                        {"error": f"Sequence '{seq_name}' not found."},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Allow deleting if user owns the sequence OR if it's a global sequence
                if result[0] != user.email and result[1] != 'G':
                    customer_connection.close()
                    return Response(
                        {"error": "You don't have permission to delete this sequence."},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Delete sequence
                delete_sql = """
                    DELETE FROM "GENERAL"."tbl_col_seq"
                    WHERE table_name = %s AND seq_name = %s
                """
                cursor.execute(delete_sql, (table_name, seq_name))
            
            customer_connection.close()
            return Response({"message": f"Sequence '{seq_name}' deleted successfully"})
        except Exception as e:
            return Response({
                "error": f"Failed to delete sequence: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

