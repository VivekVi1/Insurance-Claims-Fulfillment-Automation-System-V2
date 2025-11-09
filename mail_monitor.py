"""
Mail Monitor for Insurance Claim Automation System
================================================

This system monitors email inboxes and intelligently filters emails using LLM (Large Language Model)
to identify insurance-related communications. Only relevant insurance emails are processed for claims
assessment and fulfillment processing.

Features:
- LLM-based intelligent email filtering (using AWS Bedrock)
- User registration validation via FastAPI
- Fulfillment assessment using LLM
- Attachment processing and storage
- MongoDB integration for data persistence
- Comprehensive logging and monitoring

LLM Filtering:
The system uses an LLM to analyze email content, subject, and sender to determine if an email
is insurance-related. This provides much more accurate classification than keyword-based methods.
"""

import os
import imaplib
import email
import ssl
import time
import uuid
import requests
from datetime import datetime
from queue import Queue
from threading import Lock
from email.header import decode_header
from dotenv import load_dotenv
import fulfillment_processor
import mongodb_manager

load_dotenv()

# Global configuration
USERNAME = os.getenv("EMAIL_USERNAME")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
FASTAPI_BASE_URL = os.getenv('FASTAPI_BASE_URL', 'http://localhost:8000')
MAIL_SERVICE_URL = os.getenv('MAIL_SERVICE_URL', 'http://localhost:8001')
PROMPTS_FOLDER = os.path.join(os.path.dirname(__file__), 'prompts')

# Global state
mail_connection = None
email_queue = Queue()
queue_lock = Lock()
        
def load_prompt_file(filename):
    """Load content from prompt file"""
    try:
        file_path = os.path.join(PROMPTS_FOLDER, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"❌ Error loading prompt file {filename}: {e}")
        return None
        

def connect_to_database():
    """Connect to MongoDB database"""
    try:
        if mongodb_manager.connect():
            mongodb_manager.initialize_collections()
            print("✅ MongoDB connection established")
            return True
        else:
            print("❌ MongoDB connection failed")
            return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    

def connect_to_mail_server():
    """Connect to Gmail IMAP server"""
    global mail_connection
    try:
        context = ssl.create_default_context()
        mail_connection = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, ssl_context=context)
        mail_connection.login(USERNAME, APP_PASSWORD)
            
        status, messages = mail_connection.select("inbox")
        if status != 'OK':
            print("❌ Failed to select inbox")
            return False
            
        print("✅ Mail server connection established")
        return True
    except Exception as e:
        print(f"❌ Mail server connection failed: {e}")
        return False
    

def check_user_registration(email_address):
    """Check if user is registered using FastAPI endpoint"""
    try:
        print(f"🔍 Checking user registration for: {email_address}")
        
        # Call FastAPI endpoint
        response = requests.get(f"{FASTAPI_BASE_URL}/user/{email_address}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                user_data = data.get('user', {})
                print(f"✅ User registered - ID: {user_data.get('_id')}, Policy: {user_data.get('policy_type')}")
                return True, user_data
            else:
                print(f"❌ User not registered: {data.get('message', 'User not found')}")
                return False, None
        else:
            print(f"❌ API call failed with status {response.status_code}")
            return False, None
                
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling user registration API: {e}")
        return False, None
    except Exception as e:
        print(f"❌ Unexpected error during user check: {e}")
        return False, None
    

def send_unregistered_user_email_via_service(to_email, claim_id):
    """Send email to unregistered user via mail service"""
    try:
        # Load email template from file
        email_template = load_prompt_file('user_not_found_email.txt')
        
        if not email_template:
            # Try fallback template
            email_template = load_prompt_file('user_not_found_fallback.txt')
        
        if email_template:
            # Parse subject and content from template
            lines = email_template.split('\n')
            subject = lines[0].replace('Subject: ', '') if lines[0].startswith('Subject: ') else "Insurance Claim - Registration Required"
            
            # Get content after subject line and empty line
            content_start = 2 if len(lines) > 1 and lines[1] == '' else 1
            email_content = '\n'.join(lines[content_start:])
            
            # Format template with variables
            email_content = email_content.format(claim_id=claim_id, user_email=to_email)
        else:
            # Last resort: minimal fallback
            subject = "Insurance Claim - Registration Required"
            email_content = f"Dear Customer,\n\nYour email {to_email} is not registered in our system.\n\nClaim Reference: {claim_id}\n\nPlease contact customer service.\n\nBest regards,\nInsurance Claims Team"
        
        print(f"📧 Sending unregistered user email via mail service to: {to_email}")
        
        mail_request = {
            "mail_id": to_email,
            "subject": subject,
            "mail_content": email_content
        }
        
        response = requests.post(
            f"{MAIL_SERVICE_URL}/send-mail",
            json=mail_request,
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Unregistered user notification sent via mail service to {to_email}")
            return True
        else:
            print(f"❌ Mail service failed with status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling mail service: {e}")
        return False
    except Exception as e:
        print(f"❌ Error sending unregistered user email: {e}")
        return False
    
def get_current_mail_count():
    """Get current mail count from mail server"""
    global mail_connection
    try:
        status, messages = mail_connection.select("inbox")
        if status == 'OK':
            mail_count = int(messages[0])
            print(f"📧 Current mail count: {mail_count}")
            return mail_count
        return 0
    except Exception as e:
        print(f"❌ Error getting mail count: {e}")
        return 0
    
def get_stored_mail_details():
    """Get last mail count and connection time from database"""
    try:
        result = mongodb_manager.get_last_mail_details()
        
        if result:
            print(f"📊 Stored mail details - Count: {result['mail_count']}, Last connection: {result['last_connection_time']}")
            return result['mail_count'], result['last_connection_time']
        else:
            print("📊 No previous mail details found in database")
            return 0, None
    except Exception as e:
        print(f"❌ Error getting stored mail details: {e}")
        return 0, None
    
def update_mail_details(mail_count):
    """Update mail count and connection time in database"""
    try:
        current_time = datetime.now()
        success = mongodb_manager.update_mail_tracking(mail_count, current_time)
        
        if success:
            print(f"✅ Updated database - Mail count: {mail_count}, Time: {current_time}")
            return True
        else:
            print(f"❌ Failed to update mail details in MongoDB")
            return False
    except Exception as e:
        print(f"❌ Error updating mail details: {e}")
        return False
    
def process_email_attachments(msg, claim_id):
        """Extract and save email attachments"""
        attachment_paths = []
        save_path = os.getenv('LOCAL_ATTACHMENTS_FOLDER', 'attachments')
        
        # Create claim-specific folder
        claim_folder = os.path.join(save_path, claim_id)
        if not os.path.exists(claim_folder):
            os.makedirs(claim_folder)
            print(f"📁 Created folder: {claim_folder}")
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get('Content-Disposition'))
                
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        try:
                            # Decode filename if encoded
                            decoded_filename, charset = decode_header(filename)[0]
                            if charset:
                                filename = decoded_filename.decode(charset)
                            else:
                                filename = str(decoded_filename)
                            
                            # Create unique filename with timestamp
                            timestamp = str(int(time.time() * 1000))
                            unique_filename = f"{timestamp}_{filename}"
                            file_path = os.path.join(claim_folder, unique_filename)
                            
                            # Save attachment
                            with open(file_path, "wb") as f:
                                f.write(part.get_payload(decode=True))
                            
                            attachment_paths.append(file_path)
                            print(f"📎 Saved attachment: {unique_filename}")
                            
                        except Exception as e:
                            print(f"❌ Error saving attachment {filename}: {e}")
        
        return attachment_paths
    
def extract_email_content(msg):
        """Extract email content from message"""
        email_content = "No content found"
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition'))
                
                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        email_content = payload.decode('utf-8', errors='ignore')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                email_content = payload.decode('utf-8', errors='ignore')
        
        return email_content
    
def fetch_new_mails_to_queue(stored_count, current_count):
    """Fetch new emails from mail server and add to queue with LLM filtering"""
    global mail_connection, email_queue, queue_lock
    
    try:
        # Calculate how many new emails to fetch
        num_new_emails = current_count - stored_count
        print(f"📥 Fetching {num_new_emails} new emails...")
        
        # Fetch email IDs starting from the stored count + 1
        start_index = stored_count + 1
        end_index = current_count
        
        emails_added = 0
        emails_filtered = 0
        
        # Fetch each new email
        for i in range(start_index, end_index + 1):
            try:
                # Fetch the email by ID
                status, data = mail_connection.fetch(str(i), '(RFC822)')
                
                if status != 'OK':
                    print(f"❌ Failed to fetch email {i}")
                    continue
                
                # Parse the email
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Extract email details
                subject = msg.get('Subject', 'No Subject')
                if subject:
                    subject = str(email.header.make_header(email.header.decode_header(subject)))
                
                sender = msg.get('From', 'Unknown')
                if sender:
                    # Extract just the email address
                    from email.utils import parseaddr
                    _, sender_email = parseaddr(sender)
                else:
                    sender_email = 'unknown@email.com'
                
                # Extract email content
                email_content = extract_email_content(msg)
                
                # Generate claim ID
                claim_id = f"CLAIM_{uuid.uuid4().hex[:8].upper()}"
                
                # Process attachments
                attachment_paths = process_email_attachments(msg, claim_id)
                
                # Prepare email data
                email_data = {
                    'email_id': str(i),
                    'sender_email': sender_email,
                    'subject': subject,
                    'content': email_content,
                    'claim_id': claim_id,
                    'attachment_count': len(attachment_paths),
                    'attachment_paths': attachment_paths
                }
                
                # Apply LLM filtering
                print(f"\n🤖 Applying LLM filter to email from: {sender_email}")
                llm_result = fulfillment_processor.filter_email_with_llm(email_data)
                
                if llm_result and llm_result.get('is_insurance', False):
                    # Add LLM results to email data
                    email_data['llm_filter_result'] = llm_result
                    
                    # Add to queue
                    with queue_lock:
                        email_queue.put(email_data)
                        emails_added += 1
                    
                    print(f"✅ Email {i} added to queue - {llm_result.get('category', 'unknown')} (confidence: {llm_result.get('confidence', 0)}%)")
                else:
                    emails_filtered += 1
                    confidence = llm_result.get('confidence', 0) if llm_result else 0
                    reason = llm_result.get('reasoning', 'Not insurance related') if llm_result else 'LLM filter failed'
                    print(f"❌ Email {i} filtered out - {reason} (confidence: {confidence}%)")
                    
                    # Clean up attachments for filtered emails
                    if attachment_paths:
                        for path in attachment_paths:
                            try:
                                if os.path.exists(path):
                                    os.remove(path)
                            except:
                                pass
                        # Remove empty claim folder
                        try:
                            claim_folder = os.path.dirname(attachment_paths[0])
                            if os.path.exists(claim_folder) and not os.listdir(claim_folder):
                                os.rmdir(claim_folder)
                        except:
                            pass
                
            except Exception as e:
                print(f"❌ Error processing email {i}: {e}")
                continue
        
        print(f"\n📊 Email Filtering Summary:")
        print(f"✅ Added to queue: {emails_added} insurance-related emails")
        print(f"❌ Filtered out: {emails_filtered} non-insurance emails")
        print(f"📧 Total processed: {emails_added + emails_filtered} emails")
        
        return emails_added
        
    except Exception as e:
        print(f"❌ Error fetching new emails: {e}")
        return 0

def process_email_queue():
    """Process emails from queue with user validation and fulfillment processor"""
    global email_queue, queue_lock
    processed_count = 0
    
    print(f"📋 Starting queue processing - Queue Size: {email_queue.qsize()}")
    
    while not email_queue.empty():
        try:
            with queue_lock:
                email_data = email_queue.get_nowait()
                remaining_queue_size = email_queue.qsize()
            
            print("\n" + "="*60)
            print(f"🔄 PROCESSING EMAIL #{processed_count + 1} | Remaining in Queue: {remaining_queue_size}")
            print("="*60)
            print(f"📧 Email ID: {email_data['email_id']}")
            print(f"📧 Sender Email: {email_data['sender_email']}")
            print(f"📧 Subject: {email_data['subject']}")
            print(f"📧 Claim ID: {email_data['claim_id']}")
            print(f"📧 Attachment Count: {email_data['attachment_count']}")
            
            # Display LLM analysis results if available
            if 'llm_filter_result' in email_data:
                llm_result = email_data['llm_filter_result']
                confidence = llm_result.get('confidence', 0)
                category = llm_result.get('category', 'unknown')
                reasoning = llm_result.get('reasoning', 'No reasoning provided')
                print(f"🤖 LLM Analysis - Category: {category}, Confidence: {confidence}%")
                print(f"🤖 LLM Reasoning: {reasoning}")
            
            print("="*60)
            
            # Step 1: Check user registration via FastAPI
            is_registered, user_data = check_user_registration(email_data['sender_email'])
            
            if not is_registered:
                print(f"❌ User not registered - sending rejection email via mail service")
                
                # Send unregistered user email via mail service
                email_sent = send_unregistered_user_email_via_service(
                    email_data['sender_email'], 
                    email_data['claim_id']
                )
                
                if email_sent:
                    print(f"✅ Rejection email sent to unregistered user: {email_data['sender_email']}")
                    processed_count += 1
                else:
                    print(f"❌ Failed to send rejection email to {email_data['sender_email']}")
                
                # Skip LLM processing for unregistered users
                continue
            
            # Step 2: User is registered - proceed with LLM fulfillment processing
            print(f"✅ User registered - proceeding with fulfillment assessment")
            print(f"📋 User Info: {user_data.get('policy_type', 'N/A')} policy issued on {user_data.get('policy_issued_date', 'N/A')}")
            
            success = fulfillment_processor.process_email_fulfillment(email_data)
            
            if success:
                print(f"✅ Email {processed_count + 1} processed successfully through fulfillment assessment")
            else:
                print(f"❌ Failed to process email {processed_count + 1} in fulfillment assessment")
            
            processed_count += 1
            
            # Add delay between processing
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error processing email from queue: {e}")
            break
    
    final_queue_size = email_queue.qsize()
    if processed_count > 0:
        print(f"\n✅ Processed {processed_count} emails with user validation and fulfillment assessment | Final Queue Size: {final_queue_size}")
    else:
        print(f"\n📧 No emails to process in queue | Queue Size: {final_queue_size}")
    
def monitor_mails():
    """Main monitoring loop"""
    global mail_connection, email_queue
    
    print("🚀 Starting Mail Monitor with User Validation + Fulfillment Assessment")
    print("="*70)
    
    # Connect to database and mail server
    if not connect_to_database():
        return False
    
    if not connect_to_mail_server():
        return False
    
    try:
        while True:
            print(f"\n🔍 Checking for new mails at {datetime.now()} | Current Queue Size: {email_queue.qsize()}")
            
            # Get current mail count from server
            current_mail_count = get_current_mail_count()
            
            # Get stored mail count from database
            stored_mail_count, last_connection_time = get_stored_mail_details()
            
            print(f"📊 Comparison - Stored: {stored_mail_count}, Current: {current_mail_count}")
            
            # Check if this is the first run (database is empty)
            if last_connection_time is None:
                print("🆕 First run detected - initializing mail count without processing existing emails")
                update_mail_details(current_mail_count)
                print(f"✅ Initialized database with current mail count: {current_mail_count}")
                print("📧 Will start monitoring for new emails from next check onwards")
                
            # Check if there are new mails
            elif current_mail_count > stored_mail_count:
                print(f"🆕 Found {current_mail_count - stored_mail_count} new mails!")
                
                # Fetch new mails and add to queue with LLM filtering
                emails_added = fetch_new_mails_to_queue(stored_mail_count, current_mail_count)
                
                # Update the database with new mail count
                update_mail_details(current_mail_count)
                
                # Process emails from queue with user validation + fulfillment assessment
                if emails_added > 0:
                    print(f"🔄 Starting user validation and fulfillment assessment for {email_queue.qsize()} emails")
                    process_email_queue()
                else:
                    print("📧 No insurance-related emails found in new mails")
            
            else:
                print("📧 No new mails found")
            
            print(f"⏰ Waiting 30 seconds before next check...")
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n🛑 Mail monitoring stopped by user")
        return True
    except Exception as e:
        print(f"❌ Monitoring error: {e}")
        return False
    finally:
        # Close connections
        if mail_connection:
            try:
                mail_connection.close()
                mail_connection.logout()
            except:
                pass
        
        # Disconnect from MongoDB
        mongodb_manager.disconnect()
        
        print("🔒 All connections closed")

if __name__ == "__main__":
    monitor_mails() 