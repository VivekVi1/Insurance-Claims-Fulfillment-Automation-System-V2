"""
Test MongoDB connection for the insurance claim system
"""
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import mongodb_manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import mongodb_manager

load_dotenv()

def test_connection():
    print("🔍 Testing MongoDB Connection...")
    print("=" * 50)
    
    # Check environment variables
    connection_string = os.getenv('MONGODB_CONNECTION_STRING')
    database_name = os.getenv('MONGODB_DATABASE')
    
    print(f"📍 Connection String: {connection_string or 'Not set'}")
    print(f"📍 Database Name: {database_name or 'Not set'}")
    
    if not connection_string:
        print("\n❌ MONGODB_CONNECTION_STRING not found in .env file")
        print("Please add it to your .env file:")
        print("MONGODB_CONNECTION_STRING=mongodb://localhost:27017/")
        return False
    
    if not database_name:
        print("\n❌ MONGODB_DATABASE not found in .env file")
        print("Please add it to your .env file:")
        print("MONGODB_DATABASE=insurance_claims")
        return False
    
    # MongoDB functions are imported directly
    print("\n📦 Using MongoDB functions directly...")
    
    # Try to connect
    print("🔌 Attempting to connect...")
    if mongodb_manager.connect():
        print("✅ Successfully connected to MongoDB!")
        
        # Test database operations
        print("\n🧪 Testing database operations...")
        
        # Test 1: Create a test user
        print("   📝 Test 1: Creating test user...")
        test_user = {
            "mail_id": "test@example.com",
            "policy_issued_date": "2024-01-01",
            "policy_type": "TEST_POLICY"
        }
        
        if mongodb_manager.create_user(test_user):
            print("   ✅ Successfully created test user")
        else:
            print("   ❌ Failed to create test user")
            return False
        
        # Test 2: Retrieve the test user
        print("   📖 Test 2: Retrieving test user...")
        retrieved = mongodb_manager.get_user_by_email("test@example.com")
        if retrieved:
            print("   ✅ Successfully retrieved test user")
            print(f"      User data: {retrieved}")
        else:
            print("   ❌ Failed to retrieve test user")
            return False
        
        # Test 3: Test mail tracking
        print("   📧 Test 3: Testing mail tracking...")
        from datetime import datetime
        if mongodb_manager.update_mail_tracking(100, datetime.now()):
            print("   ✅ Successfully updated mail tracking")
        else:
            print("   ❌ Failed to update mail tracking")
            return False
        
        # Test 4: Test GridFS file upload
        print("   📁 Test 4: Testing GridFS file upload...")
        test_content = "This is a test file content for GridFS testing"
        test_metadata = {
            "test": True,
            "purpose": "connection_test"
        }
        
        file_id = mongodb_manager.upload_file(
            test_content.encode('utf-8'),
            "test_file.txt",
            test_metadata
        )
        
        if file_id:
            print("   ✅ Successfully uploaded test file to GridFS")
            
            # Test file retrieval
            file_data = mongodb_manager.download_file(file_id)
            if file_data and file_data.decode('utf-8') == test_content:
                print("   ✅ Successfully retrieved test file from GridFS")
            else:
                print("   ❌ Failed to retrieve test file from GridFS")
                return False
            
            # Clean up test file
            mongodb_manager.delete_file(file_id)
            print("   ✅ Cleaned up test file")
        else:
            print("   ❌ Failed to upload test file to GridFS")
            return False
        
        # Clean up test data
        print("\n🧹 Cleaning up test data...")
        mongodb_manager.db.users.delete_one({"mail_id": "test@example.com"})
        print("   ✅ Removed test user")
        
        # Disconnect
        mongodb_manager.disconnect()
        print("\n✅ All tests passed! MongoDB connection is working correctly.")
        return True
        
    else:
        print("\n❌ Failed to connect to MongoDB")
        print("\n🔧 Troubleshooting tips:")
        print("1. Check your MONGODB_CONNECTION_STRING in .env")
        print("2. For Atlas: Ensure your IP is whitelisted")
        print("3. For Atlas: Verify username and password")
        print("4. For local: Ensure MongoDB is running")
        print("5. Check network connectivity")
        print("\n📋 Common connection strings:")
        print("   Local: mongodb://localhost:27017/")
        print("   Atlas: mongodb+srv://user:pass@cluster.mongodb.net/")
        return False

def test_collections():
    """Test if collections are properly initialized"""
    print("\n📚 Testing collection initialization...")
    
    if mongodb_manager.connect():
        if mongodb_manager.initialize_collections():
            print("✅ Collections initialized successfully")
            mongodb_manager.disconnect()
            return True
        else:
            print("❌ Failed to initialize collections")
            mongodb_manager.disconnect()
            return False
    else:
        print("❌ Cannot test collections - connection failed")
        return False

if __name__ == "__main__":
    print("🚀 MongoDB Connection Test for Insurance Claim System")
    print("=" * 60)
    
    # Test basic connection and operations
    if test_connection():
        print("\n🎉 Connection test completed successfully!")
        
        # Test collection initialization
        if test_collections():
            print("🎉 Collection test completed successfully!")
            print("\n✅ Your MongoDB setup is ready to use!")
        else:
            print("⚠️  Collection initialization had issues")
    else:
        print("\n❌ Connection test failed. Please fix the issues above.")
        print("\n💡 Need help? Check the troubleshooting tips above.") 