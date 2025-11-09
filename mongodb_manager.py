import os
import json
import uuid
import gridfs
from datetime import datetime
from typing import Optional, Dict, Any, List
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

# Global variables for MongoDB connection
connection_string = os.getenv('MONGODB_CONNECTION_STRING', 'mongodb://localhost:27017/')
database_name = os.getenv('MONGODB_DATABASE', 'insurance_claims')
client = None
db = None
fs = None

def connect():
    """Connect to MongoDB and initialize GridFS"""
    global client, db, fs
    try:
        # Add connection options for better reliability
        connection_options = {
            'serverSelectionTimeoutMS': 5000,
            'connectTimeoutMS': 10000,
            'socketTimeoutMS': 20000,
        }
        
        # For Atlas connections, add TLS options for Windows compatibility
        if 'mongodb+srv://' in connection_string:
            connection_options.update({
                'tls': True,
                'tlsAllowInvalidCertificates': True,
                'tlsAllowInvalidHostnames': True,
            })
        
        client = MongoClient(connection_string, **connection_options)
        db = client[database_name]
        fs = gridfs.GridFS(db)
        
        # Test connection
        client.server_info()
        print("✅ MongoDB connection established")
        return True
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False

def disconnect():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        print("✅ MongoDB connection closed")

# User Management Functions
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user details by email"""
    try:
        user = db.users.find_one({"mail_id": email})
        if user and "_id" in user:
            user["_id"] = str(user["_id"])
        return user
    except Exception as e:
        print(f"❌ Error getting user: {e}")
        return None

def create_user(user_data: Dict[str, Any]) -> bool:
    """Create a new user"""
    try:
        db.users.insert_one(user_data)
        return True
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False

# Fulfillment Request Functions
def create_fulfillment_request(request_data: Dict[str, Any]) -> Optional[str]:
    """Create a new fulfillment request"""
    try:
        request_data["created_at"] = datetime.now()
        request_data["updated_at"] = datetime.now()
        result = db.fulfillment.insert_one(request_data)
        return str(result.inserted_id)
    except Exception as e:
        print(f"❌ Error creating fulfillment request: {e}")
        return None

def get_fulfillment_request(claim_id: str) -> Optional[Dict[str, Any]]:
    """Get fulfillment request by claim ID"""
    try:
        request = db.fulfillment.find_one({"claim_id": claim_id})
        if request and "_id" in request:
            request["_id"] = str(request["_id"])
        return request
    except Exception as e:
        print(f"❌ Error getting fulfillment request: {e}")
        return None

def update_fulfillment_status(claim_id: str, status: str, s3_url: Optional[str] = None) -> bool:
    """Update fulfillment request status"""
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.now()
        }
        if s3_url:
            update_data["s3_url"] = s3_url
            
        result = db.fulfillment.update_one(
            {"claim_id": claim_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"❌ Error updating fulfillment status: {e}")
        return False

def update_fulfillment_request(claim_id: str, update_data: Dict[str, Any]) -> bool:
    """Update fulfillment request with any data"""
    try:
        update_data["updated_at"] = datetime.now()
        result = db.fulfillment.update_one(
            {"claim_id": claim_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"❌ Error updating fulfillment request: {e}")
        return False

# Mail Tracking Functions
def get_last_mail_details() -> Optional[Dict[str, Any]]:
    """Get last mail tracking details"""
    try:
        # Get the most recent record
        details = db.mail_tracking.find_one(
            {},
            sort=[("_id", -1)]
        )
        if details and "_id" in details:
            details["_id"] = str(details["_id"])
        return details
    except Exception as e:
        print(f"❌ Error getting last mail details: {e}")
        return None

def update_mail_tracking(mail_count: int, last_connection_time: datetime) -> bool:
    """Update mail tracking information"""
    try:
        db.mail_tracking.insert_one({
            "mail_count": mail_count,
            "last_connection_time": last_connection_time,
            "created_at": datetime.now()
        })
        return True
    except Exception as e:
        print(f"❌ Error updating mail tracking: {e}")
        return False

# GridFS File Storage Functions
def upload_file(file_data: bytes, filename: str, metadata: Dict[str, Any]) -> Optional[str]:
    """Upload file to GridFS and return file ID"""
    try:
        file_id = fs.put(
            file_data,
            filename=filename,
            metadata=metadata,
            upload_date=datetime.now()
        )
        return str(file_id)
    except Exception as e:
        print(f"❌ Error uploading file to GridFS: {e}")
        return None

def download_file(file_id: str) -> Optional[bytes]:
    """Download file from GridFS by file ID"""
    try:
        if isinstance(file_id, str):
            file_id = ObjectId(file_id)
        return fs.get(file_id).read()
    except Exception as e:
        print(f"❌ Error downloading file from GridFS: {e}")
        return None

def get_file_metadata(file_id: str) -> Optional[Dict[str, Any]]:
    """Get file metadata from GridFS"""
    try:
        if isinstance(file_id, str):
            file_id = ObjectId(file_id)
        file_doc = fs.get(file_id)
        return {
            "filename": file_doc.filename,
            "upload_date": file_doc.upload_date,
            "metadata": file_doc.metadata,
            "length": file_doc.length
        }
    except Exception as e:
        print(f"❌ Error getting file metadata: {e}")
        return None

def delete_file(file_id: str) -> bool:
    """Delete file from GridFS"""
    try:
        if isinstance(file_id, str):
            file_id = ObjectId(file_id)
        fs.delete(file_id)
        return True
    except Exception as e:
        print(f"❌ Error deleting file from GridFS: {e}")
        return False

def upload_mail_content(user_email: str, claim_id: str, mail_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Upload mail content to GridFS"""
    try:
        # Convert datetime objects to strings for JSON serialization
        serializable_content = {}
        for key, value in mail_content.items():
            if hasattr(value, 'isoformat'):  # datetime object
                serializable_content[key] = value.isoformat()
            else:
                serializable_content[key] = value
        
        # Convert mail content to JSON bytes
        mail_bytes = json.dumps(serializable_content, indent=2).encode('utf-8')
        filename = f"{claim_id}_mail_content.json"
        
        metadata = {
            "claim_id": claim_id,
            "user_email": user_email,
            "type": "mail_content",
            "timestamp": datetime.now().isoformat()
        }
        
        file_id = upload_file(mail_bytes, filename, metadata)
        
        if file_id:
            return {
                "file_id": file_id,
                "filename": filename,
                "size": len(mail_bytes),
                "metadata": metadata
            }
        return None
        
    except Exception as e:
        print(f"❌ Error uploading mail content: {e}")
        return None

def upload_attachment(user_email: str, claim_id: str, attachment_path: str) -> Optional[Dict[str, Any]]:
    """Upload attachment file to GridFS"""
    try:
        if not os.path.exists(attachment_path):
            print(f"❌ Attachment file not found: {attachment_path}")
            return None
        
        filename = os.path.basename(attachment_path)
        file_size = os.path.getsize(attachment_path)
        
        with open(attachment_path, 'rb') as f:
            file_data = f.read()
        
        metadata = {
            "claim_id": claim_id,
            "user_email": user_email,
            "type": "attachment",
            "original_filename": filename,
            "file_size": file_size,
            "timestamp": datetime.now().isoformat()
        }
        
        file_id = upload_file(file_data, filename, metadata)
        
        if file_id:
            return {
                "file_id": file_id,
                "filename": filename,
                "size": file_size,
                "metadata": metadata
            }
        return None
        
    except Exception as e:
        print(f"❌ Error uploading attachment: {e}")
        return None

def upload_complete_email(email_data: Dict[str, Any], claim_id: str) -> Optional[Dict[str, Any]]:
    """Upload complete email with attachments to GridFS"""
    try:
        user_email = email_data.get('sender_email') or email_data.get('from')
        print(f"📝 Starting GridFS upload for claim {claim_id}, user: {user_email}")
        print(f"   Email data keys: {list(email_data.keys())}")
        
        upload_result = {
            "claim_id": claim_id,
            "user_email": user_email,
            "upload_timestamp": datetime.now().isoformat(),
            "mail_content": None,
            "attachments": []
        }
        
        # Upload mail content
        mail_content_result = upload_mail_content(user_email, claim_id, email_data)
        if mail_content_result:
            upload_result["mail_content"] = mail_content_result
            print(f"✅ Mail content uploaded: {mail_content_result['filename']}")
        
        # Upload attachments
        if 'attachment_paths' in email_data and email_data['attachment_paths']:
            for attachment_path in email_data['attachment_paths']:
                if os.path.exists(attachment_path):
                    att_result = upload_attachment(user_email, claim_id, attachment_path)
                    if att_result:
                        upload_result["attachments"].append(att_result)
                        print(f"✅ Attachment uploaded: {att_result['filename']}")
        
        # Store upload summary in database (optional - can be removed if not needed)
        # db.upload_summaries.insert_one(upload_result)
        
        return upload_result
        
    except Exception as e:
        print(f"❌ Error uploading complete email: {e}")
        return None

# Initialize collections with indexes
def initialize_collections():
    """Create indexes for better performance"""
    try:
        # Users collection indexes
        db.users.create_index("mail_id", unique=True)
        
        # Fulfillment collection indexes
        db.fulfillment.create_index("claim_id", unique=True)
        db.fulfillment.create_index("user_mail")
        db.fulfillment.create_index("fulfillment_status")
        
        # Mail tracking indexes
        db.mail_tracking.create_index("created_at")
        
        print("✅ MongoDB collections and indexes initialized")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing collections: {e}")
        return False 