import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import mongodb_manager
import uvicorn

load_dotenv()

app = FastAPI()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not mongodb_manager.connect():
        print("⚠️ Failed to connect to MongoDB")
    else:
        # Initialize collections with indexes
        mongodb_manager.initialize_collections()
    yield
    # Shutdown
    mongodb_manager.disconnect()

app = FastAPI(lifespan=lifespan)

class FulfillmentRequest(BaseModel):
    user_mail: EmailStr
    claim_id: str
    mail_content: str
    mail_content_s3_url: Optional[str] = None
    attachment_count: int = 0
    attachment_s3_urls: Optional[List[str]] = None
    local_attachment_paths: Optional[List[str]] = None
    fulfillment_status: str  # "pending" or "completed"
    missing_items: Optional[str] = None
    s3_upload_timestamp: Optional[str] = None
    # MongoDB GridFS file IDs
    mail_content_file_id: Optional[str] = None
    attachment_file_ids: Optional[List[str]] = None

@app.get("/")
def test_database_connection():
    """Test database connection"""
    try:
        # Test MongoDB connection
        if mongodb_manager.client and mongodb_manager.client.server_info():
            return {
                "status": "success",
                "database_connection": "successful",
                "message": "MongoDB connection working",
                "database": mongodb_manager.database_name
            }
        else:
            return {
                "status": "error",
                "database_connection": "failed",
                "message": "MongoDB connection not established"
            }
        
    except Exception as e:
        return {
            "status": "error", 
            "database_connection": "failed",
            "error": str(e),
            "message": "MongoDB connection failed"
        }

@app.post("/add-fulfillment")
def add_fulfillment(data: FulfillmentRequest):
    """Add fulfillment data to MongoDB"""
    try:
        # Create fulfillment request data
        request_data = {
            "user_mail": data.user_mail,
            "claim_id": data.claim_id,
            "mail_content": data.mail_content,
            "mail_content_file_id": data.mail_content_file_id,  # Use provided file ID
            "attachment_count": data.attachment_count,
            "attachment_file_ids": data.attachment_file_ids or [],  # Use provided file IDs
            "local_attachment_paths": data.local_attachment_paths,
            "fulfillment_status": data.fulfillment_status,
            "missing_items": data.missing_items,
            "s3_upload_timestamp": data.s3_upload_timestamp  # Legacy field kept for compatibility
        }
        
        # If mail_content_s3_url is provided, store it as legacy reference
        if data.mail_content_s3_url:
            request_data["mail_content_s3_url"] = data.mail_content_s3_url
        
        # If attachment_s3_urls are provided, store them as legacy reference
        if data.attachment_s3_urls:
            request_data["attachment_s3_urls"] = data.attachment_s3_urls
        
        # Create fulfillment request in MongoDB
        fulfillment_id = mongodb_manager.create_fulfillment_request(request_data)
        
        if fulfillment_id:
            return {
                "success": True,
                "fulfillment_id": fulfillment_id,
                "message": "Fulfillment data saved successfully in MongoDB"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save fulfillment data")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/fulfillment/{claim_id}")
def get_fulfillment(claim_id: str):
    """Get fulfillment request by claim ID"""
    try:
        fulfillment = mongodb_manager.get_fulfillment_request(claim_id)
        
        if fulfillment:
            return {
                "success": True,
                "data": fulfillment
            }
        else:
            return {
                "success": False,
                "message": f"Fulfillment with claim_id {claim_id} not found"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.put("/fulfillment/{claim_id}/status")
def update_fulfillment_status(claim_id: str, status: str):
    """Update fulfillment status"""
    try:
        if status not in ["pending", "completed", "failed"]:
            raise HTTPException(status_code=400, detail="Invalid status. Must be 'pending', 'completed', or 'failed'")
        
        success = mongodb_manager.update_fulfillment_request(claim_id, {"fulfillment_status": status})
        
        if success:
            return {
                "success": True,
                "message": f"Fulfillment status updated to {status}"
            }
        else:
            return {
                "success": False,
                "message": f"Fulfillment with claim_id {claim_id} not found"
            }
            
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "fulfillment_api", "database": "mongodb"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002) 