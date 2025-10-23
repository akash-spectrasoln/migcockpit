"""
Simple FastAPI application with ONE endpoint for HANA import
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn

# Import our modules
from hana_service import HanaService
from models import HANA_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="MIGDATA HANA Import API",
    description="Single endpoint for complete HANA import process",
    version="1.0.0",
    docs_url="/docs"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single endpoint for complete HANA import process
@app.post("/import-hana", status_code=status.HTTP_200_OK)
async def import_hana_data(hana_config: HANA_CONFIG):
    """
    Single endpoint that receives HANA connection details and executes complete import process synchronously.
    
    This endpoint:
    1. Receives HANA connection details as input
    2. Connects to HANA database
    3. Creates C00001 database (if not exists)
    4. Creates GENERAL schema with PROJECT and TESTDATA tables
    5. Extracts projects from HANA MIG_COCKPIT."/1LT/DS_MAPPING"
    6. Extracts testdata from HANA SAPHANADB.DMC_MT_HEADER and DMC_COBJ
    7. Creates project schemas ({SYS_ID}_{MT_ID})
    8. Creates STAGE_TBLE tables
    9. Imports all staging table data and testdata
    10. Returns comprehensive results
    
    Input: HANA_CONFIG with connection details
    Output: Complete import results with success/failure details
    """
    try:
        logger.info("🚀 Starting complete HANA import process...")
        logger.info(f"📡 HANA Config: {hana_config.host}:{hana_config.port}")
        
        # Create service instance with customer database name
        service = HanaService(customer_db=hana_config.customer_db)
        
        # Execute complete import process synchronously
        result = service.complete_import_process(hana_config.dict())
        
        logger.info("✅ Complete HANA import process finished successfully")
        return result
        
    except Exception as e:
        logger.error(f"❌ Complete HANA import process failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"HANA import process failed: {str(e)}"
        )

# Health check endpoint (optional)
@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"message": "MIGDATA HANA Import API is running", "status": "healthy"}

# Test HANA connection endpoint
@app.post("/test-hana-connection")
async def test_hana_connection(hana_config: HANA_CONFIG):
    """
    Test HANA connection without running the full import process.
    This endpoint only tests if the HANA connection is working.
    """
    try:
        logger.info("🧪 Testing HANA connection...")
        logger.info(f"📡 HANA Config: {hana_config.host}:{hana_config.port}")
        
        # Create service instance
        service = HanaService(customer_db=hana_config.customer_db)
        
        # Test only the HANA connection
        result = service.test_hana_connection(hana_config.dict())
        
        logger.info(f"✅ HANA connection test completed: {result['success']}")
        return result
        
    except Exception as e:
        logger.error(f"❌ HANA connection test failed: {e}")
        return {
            "success": False,
            "message": f"HANA connection test failed: {str(e)}",
            "error": str(e)
        }

# Test PostgreSQL connection endpoint
@app.get("/test-postgres-connection")
async def test_postgres_connection():
    """
    Test PostgreSQL connection without running the full import process.
    This endpoint only tests if the PostgreSQL connection is working.
    """
    try:
        logger.info("🧪 Testing PostgreSQL connection...")
        
        # Create service instance
        service = HanaService()
        
        # Test only the PostgreSQL connection
        result = service.test_postgres_connection()
        
        logger.info(f"✅ PostgreSQL connection test completed: {result['success']}")
        return result
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection test failed: {e}")
        return {
            "success": False,
            "message": f"PostgreSQL connection test failed: {str(e)}",
            "error": str(e)
        }

# Test both connections endpoint
@app.post("/test-both-connections")
async def test_both_connections(hana_config: HANA_CONFIG):
    """
    Test both HANA and PostgreSQL connections.
    This endpoint tests if both database connections are working.
    """
    try:
        logger.info("🧪 Testing both HANA and PostgreSQL connections...")
        logger.info(f"📡 HANA Config: {hana_config.host}:{hana_config.port}")
        
        # Create service instance
        service = HanaService(customer_db=hana_config.customer_db)
        
        # Test both connections
        result = service.test_both_connections(hana_config.dict())
        
        logger.info(f"✅ Both connections test completed: {result['success']}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Both connections test failed: {e}")
        return {
            "success": False,
            "message": f"Both connections test failed: {str(e)}",
            "error": str(e)
        }

# Test testdata query endpoint
@app.post("/test-testdata-query")
async def test_testdata_query(hana_config: HANA_CONFIG):
    """
    Test the testdata query specifically.
    This endpoint tests if the HANA testdata query is working and returns sample data.
    """
    try:
        logger.info("🧪 Testing testdata query...")
        logger.info(f"📡 HANA Config: {hana_config.host}:{hana_config.port}")
        
        # Create service instance
        service = HanaService(customer_db=hana_config.customer_db)
        
        # Test testdata query
        result = service.test_testdata_query(hana_config.dict())
        
        logger.info(f"✅ Testdata query test completed: {result['success']}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Testdata query test failed: {e}")
        return {
            "success": False,
            "message": f"Testdata query test failed: {str(e)}",
            "error": str(e)
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
