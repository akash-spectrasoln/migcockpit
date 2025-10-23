"""
Pydantic models for MIGDATA HANA Import API - Simplified
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Base Response Model
class BaseResponse(BaseModel):
    success: bool = True
    message: str = "Operation completed successfully"

# PROJECT Table Models (Customer database GENERAL schema)
class PROJECT_Response(BaseModel):
    PROJECT_ID: int
    SYS_ID: str
    MT_ID: str
    COBJ_IDENT: str
    CREATED_BY: str
    CREATED_ON: datetime
    MODIFIED_ON: datetime
    MODIFIED_BY: Optional[str]
    ACTIVE: bool

# STAGE_TBLE Table Models (Project schema: SYS_ID + MT_ID)
class STAGE_TBLE_Response(BaseModel):
    SYS_ID: str
    MT_ID: str
    COBJ_IDENT: str
    STRUCT_IDENT: str
    STAGING_TAB: str
    CREATED_ON: datetime
    MODIFIED_ON: datetime

# HANA Integration Models
class HANA_CONFIG(BaseModel):
    host: str = Field(..., description="HANA server host")
    port: int = Field(..., description="HANA server port")
    user: str = Field(..., description="HANA username")
    password: str = Field(..., description="HANA password")
    database: str = Field(..., description="HANA database name")
    schema_name: str = Field(default="MIG_COCKPIT", description="HANA schema name", alias="schema")
    table_name: str = Field(default="/1LT/DS_MAPPING", description="HANA table name")
    customer_db: str = Field(default="C00001", description="Customer database name to create")

class HANA_CONNECTION_TEST(BaseModel):
    success: bool
    message: str
    schemas: Optional[List[str]] = None
    tables_count: Optional[int] = None