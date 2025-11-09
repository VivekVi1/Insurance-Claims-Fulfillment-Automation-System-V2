import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import mongodb_manager
import uvicorn

load_dotenv()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not mongodb_manager.connect():
        print("⚠️ Failed to connect to MongoDB")
    yield
    # Shutdown
    mongodb_manager.disconnect()

app = FastAPI(lifespan=lifespan)

def get_user_by_email(email: str):
    """Get user details by email from MongoDB"""
    try:
        user = mongodb_manager.get_user_by_email(email)
        
        if user and 'policy_issued_date' in user:
            # Convert date to string format if it's a datetime object
            if hasattr(user['policy_issued_date'], 'strftime'):
                user['policy_issued_date'] = user['policy_issued_date'].strftime('%Y-%m-%d')
        
        return user
        
    except Exception as e:
        raise e

@app.get("/user/{user_email}")
def get_user_details(user_email: str):
    """Get user details by email ID"""
    try:
        user = get_user_by_email(user_email)
        
        if user:
            return JSONResponse(
                content={
                    "status": "success",
                    "user": user
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "message": f"User with email {user_email} not found"
                }
            )
    except Exception as e:
        print(f"Error getting user details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "user_validator", "database": "mongodb"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 