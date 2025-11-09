import os
import boto3
import json
import base64
import uuid
import requests
import re
from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime
import mongodb_manager

load_dotenv()

# AWS Bedrock configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
_bedrock_token = os.getenv("BEDROCK_API")
if _bedrock_token:
    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = _bedrock_token

BEDROCK_CLIENT = boto3.client(service_name="bedrock-runtime", region_name=AWS_REGION)
LLM = ChatBedrockConverse(
    model_id=os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
    temperature=float(os.getenv("BEDROCK_TEMPERATURE", "0.3")),
    max_tokens=int(os.getenv("BEDROCK_MAX_TOKENS", "1500")),
    client=BEDROCK_CLIENT,
)

# Service configuration
MAIL_SERVICE_URL = os.getenv('MAIL_SERVICE_URL', 'http://localhost:8001')
FULFILLMENT_API_URL = os.getenv('FULFILLMENT_API_URL', 'http://localhost:8002')

# Prompts folder
PROMPTS_FOLDER = os.path.join(os.path.dirname(__file__), 'prompts')

# Initialize MongoDB connection
mongodb_manager.connect()

def load_prompt_file(filename):
    """Load content from prompt file"""
    try:
        file_path = os.path.join(PROMPTS_FOLDER, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"❌ Error loading prompt file {filename}: {e}")
        return None

def encode_image(image_path):
    """Encode image file to base64"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"❌ Error encoding image {image_path}: {e}")
        return None

def send_mail_via_service(to_email: str, subject: str, content: str):
    """Send email via mail service API"""
    try:
        print(f"📧 Sending email via mail service to: {to_email}")
        
        mail_request = {
            "mail_id": to_email,
            "subject": subject,
            "mail_content": content
        }
        
        response = requests.post(
            f"{MAIL_SERVICE_URL}/send-mail",
            json=mail_request,
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Email sent successfully via mail service to {to_email}")
            return True
        else:
            print(f"❌ Mail service failed with status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling mail service: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error sending mail: {e}")
        return False

def assess_fulfillment_with_llm(email_data):
    """Use LLM to assess if customer has provided all required fulfillment details"""
    try:
        # Load system prompt from file
        system_prompt_content = load_prompt_file('fulfillment_system_prompt.txt')
        if not system_prompt_content:
            print("❌ Failed to load system prompt")
            return None
        
        # Load fulfillment requirements from file
        requirements_content = load_prompt_file('fulfillment_requirements.txt')
        if not requirements_content:
            print("❌ Failed to load fulfillment requirements")
            # Use default requirements
            requirements_content = """
            1. User email address
            2. Reason for claim
            3. Claim amount
            4. Supporting proofs (attachments)
            """
        
        # Create system message
        system_message = SystemMessage(content=system_prompt_content)
        
        # Create human message with email data
        human_message_content = f"""
        Please assess if this insurance claim email contains all required information for fulfillment.
        
        Required Information:
        {requirements_content}
        
        Email Details:
        - From: {email_data.get('sender_email', 'Unknown')}
        - Subject: {email_data.get('subject', 'No Subject')}
        - Content: {email_data.get('content', 'No Content')}
        - Attachments: {email_data.get('attachment_count', 0)} files
        
        Instructions:
        1. Check if ALL required information is provided
        2. If all requirements are met, respond with: FULFILLMENT_STATUS: COMPLETED
        3. If any requirements are missing, respond with:
           FULFILLMENT_STATUS: PENDING
           MISSING_ITEMS:
           - List each missing item
        
        Example response for complete fulfillment:
        FULFILLMENT_STATUS: COMPLETED
        
        Example response for pending fulfillment:
        FULFILLMENT_STATUS: PENDING
        MISSING_ITEMS:
        - Specific claim amount not provided
        - Supporting documents/bills missing
        """
        
        human_message = HumanMessage(content=human_message_content)
        
        # Get LLM response
        response = LLM.invoke([system_message, human_message])
        
        # Return the raw response content for parsing
        return response.content
            
    except Exception as e:
        print(f"❌ Error in LLM fulfillment assessment: {e}")
        return None

def filter_email_with_llm(email_data):
    """Use LLM to determine if an email is insurance-related"""
    try:
        print(f"🤖 Using LLM to filter email: {email_data.get('subject', 'No Subject')[:50]}...")
        
        # Create a focused system prompt for email filtering
        system_prompt = """You are an expert insurance email classifier. Your job is to determine if an email is related to insurance matters.

Insurance-related emails include:
- Insurance claims (auto, home, health, life, etc.)
- Policy inquiries and renewals
- Coverage questions and changes
- Premium payments and billing
- Claims status updates
- Insurance company communications
- Agent/broker communications

Non-insurance emails include:
- Marketing emails
- Personal communications
- Business communications unrelated to insurance
- Spam or promotional content

Analyze the email content carefully and respond with a JSON object containing:
- "is_insurance": true/false
- "confidence": 0-100 (confidence level)
- "reasoning": brief explanation of your decision
- "category": specific insurance category if applicable

Be conservative - when in doubt, classify as insurance-related to avoid missing important claims."""
        
        # Create system message
        system_message = SystemMessage(content=system_prompt)
        
        # Create human message with email data
        human_message_content = f"""
        Please classify this email as insurance-related or not:
        
        From: {email_data.get('sender_email', 'Unknown')}
        Subject: {email_data.get('subject', 'No Subject')}
        Content: {email_data.get('content', 'No Content')}
        Attachments: {email_data.get('attachment_count', 0)} files
        
        Respond with JSON only:
        {{
            "is_insurance": true/false,
            "confidence": 0-100,
            "reasoning": "explanation",
            "category": "category_name"
        }}
        """
        
        human_message = HumanMessage(content=human_message_content)
        
        # Get LLM response
        response = LLM.invoke([system_message, human_message])
        
        # Parse response
        try:
            response_content = response.content
            if isinstance(response_content, str):
                # Try to extract JSON from the response
                json_start = response_content.find('{')
                json_end = response_content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_content[json_start:json_end]
                    result = json.loads(json_str)
                else:
                    result = _parse_llm_response_fallback(response_content)
            else:
                result = _parse_llm_response_fallback(str(response_content))
            
            print(f"🤖 LLM Email Filter Result: {result}")
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse LLM response as JSON: {e}")
            print(f"Raw response: {response.content}")
            return _fallback_insurance_check(email_data)
            
    except Exception as e:
        print(f"❌ Error in LLM email filtering: {e}")
        return _fallback_insurance_check(email_data)

def _parse_llm_response_fallback(response_content):
    """Fallback parsing for LLM response when JSON parsing fails"""
    try:
        # Try to extract key information from text response
        response_lower = response_content.lower()
        
        is_insurance = any(keyword in response_lower for keyword in ['true', 'yes', 'insurance', 'claim'])
        confidence = 50  # Default confidence for fallback
        
        # Extract reasoning
        reasoning = "LLM response parsing failed, using fallback analysis"
        
        # Determine category
        category = "unknown"
        if 'auto' in response_lower or 'car' in response_lower:
            category = "auto_claim"
        elif 'health' in response_lower or 'medical' in response_lower:
            category = "health_inquiry"
        elif 'home' in response_lower or 'property' in response_lower:
            category = "property_claim"
        
        return {
            "is_insurance": is_insurance,
            "confidence": confidence,
            "reasoning": reasoning,
            "category": category
        }
        
    except Exception as e:
        print(f"❌ Fallback parsing also failed: {e}")
        return {
            "is_insurance": True,  # Default to including email if all parsing fails
            "confidence": 0,
            "reasoning": "All parsing methods failed, defaulting to include",
            "category": "unknown"
        }

def _fallback_insurance_check(email_data):
    """Fallback insurance check using keyword-based method"""
    try:
        subject = email_data.get('subject', '').lower()
        content = email_data.get('content', '').lower()
        sender = email_data.get('sender_email', '').lower()
        
        # Simple keyword check
        insurance_keywords = ['claim', 'insurance', 'policy', 'coverage', 'damage', 'accident']
        keyword_count = sum(1 for keyword in insurance_keywords if keyword in subject or keyword in content)
        
        is_insurance = keyword_count >= 2
        
        return {
            "is_insurance": is_insurance,
            "confidence": 30,  # Low confidence for fallback method
            "reasoning": f"Fallback keyword check found {keyword_count} insurance keywords",
            "category": "fallback_analysis"
        }
        
    except Exception as e:
        print(f"❌ Fallback insurance check failed: {e}")
        return {
            "is_insurance": True,  # Default to including email
            "confidence": 0,
            "reasoning": "Fallback check failed, defaulting to include",
            "category": "unknown"
        }

def identify_satisfied_requirements(email_data, missing_items_text):
    """Identify which requirements have been satisfied based on email data and LLM response"""
    satisfied = []
    
    # User email is always satisfied (they sent the email)
    satisfied.append("✓ User email address provided")
    
    # Check if requirements are NOT mentioned in missing items
    missing_lower = missing_items_text.lower()
    
    # Check for reason/description
    reason_keywords = ["reason", "description", "what happened", "incident", "cause", "explain"]
    if not any(keyword in missing_lower for keyword in reason_keywords):
        satisfied.append("✓ Reason for claim provided")
        
    # Check for claim amount (enhanced detection)
    amount_keywords = ["amount", "dollar", "cost", "money", "price", "value", "sum", "total", "claim", "damage", "bill", "specific claim amount", "currency"]
    
    # Also check if email content contains monetary values
    email_content = email_data.get('content', '').lower()
    has_monetary_value = False
    
    # Look for common monetary patterns
    monetary_patterns = [
        r'\$\s*[\d,]+',  # $2500, $2,500
        r'rs\.?\s*[\d,]+',  # Rs 25000, Rs. 2,50,000
        r'inr\s*[\d,]+',  # INR 25000
        r'usd\s*[\d,]+',  # USD 2500
        r'amount:?\s*[\d,]+',  # amount: 25000
        r'cost:?\s*[\d,]+',  # cost: 25000
        r'claim:?\s*[\d,]+',  # claim: 25000
        r'damage:?\s*[\d,]+',  # damage: 25000
        r'total:?\s*[\d,]+',  # total: 25000
        r'[\d,]{3,}',  # Any number with 3+ digits (with commas)
    ]
    
    for pattern in monetary_patterns:
        if re.search(pattern, email_content):
            has_monetary_value = True
            break
    
    # Only consider satisfied if LLM doesn't mention it as missing
    # Don't add to satisfied if amount keywords are found in missing items
    if not any(keyword in missing_lower for keyword in amount_keywords):
        satisfied.append("✓ Claim amount specified")
        
    # Check for supporting proofs/attachments
    proof_keywords = ["proof", "document", "attachment", "evidence", "support", "bill", "receipt", "photo", "police report", "medical"]
    if email_data['attachment_count'] > 0:
        if not any(keyword in missing_lower for keyword in proof_keywords):
            satisfied.append(f"✓ Supporting documents provided ({email_data['attachment_count']} attachments)")
        else:
            # They have attachments but LLM says they need more/different ones
            satisfied.append(f"✓ Some documents provided ({email_data['attachment_count']} attachments, additional may be needed)")
    
    return satisfied

def parse_fulfillment_response(llm_response, email_data):
    """Parse LLM response to extract fulfillment status and details"""
    try:
        import re
        
        print(f"🤖 Raw LLM Response:")
        print(f"{llm_response}")
        print("-" * 60)
        
        # Extract fulfillment status
        status_match = re.search(r'FULFILLMENT_STATUS:\s*(COMPLETED|PENDING)', llm_response)
        status = status_match.group(1) if status_match else "PENDING"
        
        # Extract missing items if status is PENDING
        missing_items = ""
        satisfied_items = []
        
        if status == "PENDING":
            # Updated regex to capture multi-line missing items
            # Look for MISSING_ITEMS: and capture everything until the next major section or end
            missing_match = re.search(r'MISSING_ITEMS:\s*(.*?)(?=\n\n|FULFILLMENT_STATUS:|$)', llm_response, re.DOTALL)
            if missing_match:
                missing_items = missing_match.group(1).strip()
                # Clean up the formatting - ensure each item starts with a bullet
                lines = missing_items.split('\n')
                formatted_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('-'):
                        line = '- ' + line
                    if line:
                        formatted_lines.append(line)
                missing_items = '\n'.join(formatted_lines)
            else:
                missing_items = "- Required fulfillment items missing"
            
            # Identify satisfied requirements
            satisfied_items = identify_satisfied_requirements(email_data, missing_items)
            
            # FAILSAFE: If all requirements are satisfied but LLM still says PENDING, override to COMPLETED
            if len(satisfied_items) >= 4 and (not missing_items or missing_items.strip() == "" or missing_items == "- Required fulfillment items missing"):
                print("🔄 FAILSAFE ACTIVATED: All requirements satisfied, overriding PENDING to COMPLETED")
                status = "COMPLETED"
                missing_items = ""
                satisfied_items = []
        else:
            # For COMPLETED status, still identify what was satisfied for logging
            satisfied_items = [
                "✓ User email address provided",
                "✓ Reason for claim provided", 
                "✓ Claim amount specified",
                f"✓ Supporting documents provided ({email_data['attachment_count']} attachments)"
            ]
        
        # Generate email content if status is PENDING
        email_content = ""
        if status == "PENDING":
            # Always use our template to ensure consistent formatting with both satisfied and missing items
            email_template = load_prompt_file('fulfillment_pending_email.txt')
            if email_template:
                # Parse subject and content from template
                lines = email_template.split('\n')
                subject = lines[0].replace('Subject: ', '') if lines[0].startswith('Subject: ') else "Insurance Claim - Additional Information Required"
                
                # Get content after subject line and empty line
                content_start = 2 if len(lines) > 1 and lines[1] == '' else 1
                template_content = '\n'.join(lines[content_start:])
                
                # Format template with satisfied and missing items
                satisfied_items_text = "\n".join(satisfied_items) if satisfied_items else "None identified"
                email_content = template_content.format(
                    satisfied_items=satisfied_items_text,
                    missing_items=missing_items
                )
            else:
                # Final fallback if template file is not available
                satisfied_items_text = ", ".join([item.replace("✓ ", "") for item in satisfied_items]) if satisfied_items else "None"
                email_content = (
                    "Dear Customer,\n\n"
                    "Thank you for submitting your insurance claim. We have reviewed your submission:\n\n"
                    f"REQUIREMENTS SATISFIED: {satisfied_items_text}\n\n"
                    f"MISSING REQUIREMENTS: {missing_items}\n\n"
                    "Please reply with the missing information and supporting documents.\n\n"
                    "Best regards,\n"
                    "Insurance Claims Team"
                )
        
        print(f"📊 Final Assessment: {status}")
        if satisfied_items:
            print(f"✅ Satisfied: {len(satisfied_items)} requirements")
        if missing_items:
            print(f"❌ Missing: {missing_items}")
        
        return {
            'status': status,
            'missing_items': missing_items,
            'satisfied_items': satisfied_items,
            'email_content': email_content
        }
        
    except Exception as e:
        print(f"❌ Error parsing fulfillment response: {e}")
        return None

def save_to_fulfillment_table(email_data, status, missing_items="", mongodb_result=None):
    """Save fulfillment details via API call"""
    try:
        # Prepare data based on status and MongoDB upload result
        if mongodb_result and status == "completed":
            # For completed fulfillments with MongoDB upload
            mail_content_file_id = mongodb_result['mail_content']['file_id'] if mongodb_result.get('mail_content') else None
            attachment_file_ids = [att['file_id'] for att in mongodb_result.get('attachments', [])]
            attachment_count = len(attachment_file_ids)
            upload_timestamp = mongodb_result.get('upload_timestamp', datetime.now().isoformat())
            
            # Store original mail content (first 1000 chars for reference)
            mail_content = f"Subject: {email_data['subject']}\nContent: {email_data['content'][:800]}"
            
            # Store local attachment paths for reference
            local_paths = [os.path.basename(path) for path in email_data.get('attachment_paths', [])]
            
            print(f"💾 Preparing MongoDB data for API call")
            print(f"📄 Mail content file ID: {mail_content_file_id}")
            print(f"📎 {attachment_count} attachment file IDs")
            
            # For backward compatibility, we'll still use the s3_url fields but populate them with MongoDB info
            mail_content_s3_url = f"mongodb://gridfs/{mail_content_file_id}" if mail_content_file_id else None
            attachment_urls = [f"mongodb://gridfs/{file_id}" for file_id in attachment_file_ids]
            s3_upload_timestamp = upload_timestamp
            
        else:
            # For pending fulfillments - no MongoDB upload yet
            mail_content_s3_url = None
            attachment_urls = []
            attachment_count = len(email_data.get('attachment_paths', []))
            s3_upload_timestamp = None
            
            # Store full mail content
            mail_content = f"Subject: {email_data['subject']}\nContent: {email_data['content']}"
            mail_content = mail_content[:1000]  # Limit length
            
            # Store local attachment paths
            local_paths = [os.path.basename(path) for path in email_data.get('attachment_paths', [])]
            
            print(f"💾 Preparing pending fulfillment for API call")
        
        # Prepare API request data
        api_data = {
            "user_mail": email_data['sender_email'],
            "claim_id": email_data.get('claim_id', 'UNKNOWN'),
            "mail_content": mail_content,
            "mail_content_s3_url": mail_content_s3_url,
            "attachment_count": attachment_count,
            "attachment_s3_urls": attachment_urls if attachment_urls else None,
            "local_attachment_paths": local_paths if local_paths else None,
            "fulfillment_status": status,
            "missing_items": missing_items if missing_items else None,
            "s3_upload_timestamp": s3_upload_timestamp
        }
        
        # Add MongoDB file IDs if available
        if mongodb_result and status == "completed":
            api_data["mail_content_file_id"] = mail_content_file_id
            api_data["attachment_file_ids"] = attachment_file_ids
        
        print(f"🔄 Calling fulfillment API...")
        
        # Make API call
        response = requests.post(
            f"{FULFILLMENT_API_URL}/add-fulfillment",
            json=api_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            fulfillment_id = result.get('fulfillment_id')
            
            if mongodb_result:
                print(f"✅ Saved completed fulfillment via API: {fulfillment_id}")
                print(f"📊 Record includes: Mail MongoDB file ID + {attachment_count} attachment file IDs")
            else:
                print(f"✅ Saved pending fulfillment via API: {fulfillment_id}")
                print(f"📊 Record includes: Local content + {attachment_count} local attachments")
                
            return fulfillment_id
        else:
            print(f"❌ API call failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error calling fulfillment API: {e}")
        return None

def process_email_fulfillment(email_data):
    """Main function to process email fulfillment"""
    try:
        print(f"\n🔍 Assessing fulfillment requirements for: {email_data['sender_email']}")
        print(f"📋 Checking for: Reason for claim, Claim amount, Supporting proofs")
        
        # Use LLM to assess fulfillment
        llm_response = assess_fulfillment_with_llm(email_data)
        if not llm_response:
            print(f"❌ Failed to get LLM assessment")
            return False
        
        # Parse LLM response
        parsed_result = parse_fulfillment_response(llm_response, email_data)
        if not parsed_result:
            print(f"❌ Failed to parse LLM response")
            return False
        
        status = parsed_result['status']
        print(f"📊 Fulfillment Assessment Result: {status}")
        
        if status == "COMPLETED":
            print(f"🎉 All requirements fulfilled - proceeding with MongoDB upload")
            
            # Upload to MongoDB when fulfillment is completed
            mongodb_result = upload_to_mongodb_for_completed_fulfillment(email_data)
            
            if mongodb_result:
                # Save to fulfillment table with MongoDB file IDs
                success = save_to_fulfillment_table(email_data, "completed", mongodb_result=mongodb_result)
                if success:
                    print(f"✅ Completed fulfillment saved with MongoDB file IDs")
                    print(f"📋 Customer provided: User mail ✓, Reason ✓, Claim amount ✓, Supporting proofs ✓")
                    
                    # Clean up local files after successful MongoDB upload and API storage
                    cleanup_local_files_after_mongodb_upload(email_data)
                
                return success
            else:
                print(f"❌ MongoDB upload failed - saving fulfillment without file IDs")
                # Still save the fulfillment record even if MongoDB upload fails
                success = save_to_fulfillment_table(email_data, "completed")
                return success
            
        elif status == "PENDING":
            # Save to fulfillment table as pending
            missing_items = parsed_result['missing_items']
            success = save_to_fulfillment_table(email_data, "pending", missing_items)
            
            if success:
                # Show satisfied requirements
                satisfied_items = parsed_result.get('satisfied_items', [])
                if satisfied_items:
                    print(f"✅ Requirements satisfied: {', '.join([item.replace('✓ ', '') for item in satisfied_items])}")
                
                # Send email to customer for missing items via mail service
                email_sent = send_mail_via_service(
                    to_email=email_data['sender_email'],
                    subject="Insurance Claim - Additional Information Required",
                    content=parsed_result['email_content']
                )
                
                if email_sent:
                    print(f"✅ Fulfillment pending - email sent requesting missing information")
                    print(f"❌ Missing: {missing_items}")
                    return True
                else:
                    print(f"❌ Failed to send fulfillment email via mail service")
                    return False
            
            return success
        
    except Exception as e:
        print(f"❌ Error in fulfillment processing: {e}")
        return False

def upload_to_mongodb_for_completed_fulfillment(email_data):
    """Upload mail content and attachments to MongoDB GridFS for completed fulfillments"""
    try:
        print(f"☁️  Starting MongoDB upload for completed claim: {email_data['claim_id']}")
        
        # Check if MongoDB is connected
        if not mongodb_manager.client:
            print(f"⚠️  MongoDB not connected. Attempting to connect...")
            if not mongodb_manager.connect():
                print(f"❌ MongoDB connection failed")
                return None
        
        # Upload complete email to MongoDB GridFS
        mongodb_result = mongodb_manager.upload_complete_email(email_data, email_data['claim_id'])
        
        if mongodb_result:
            print(f"✅ MongoDB upload completed successfully")
            if mongodb_result['mail_content']:
                print(f"📄 Mail content uploaded: {mongodb_result['mail_content']['filename']}")
            print(f"📎 Uploaded {len(mongodb_result['attachments'])} attachments to MongoDB GridFS")
            print(f"☁️  All content uploaded to MongoDB GridFS for permanent storage")
            return mongodb_result
        else:
            print(f"❌ MongoDB upload failed")
            return None
            
    except Exception as e:
        print(f"❌ Error during MongoDB upload: {e}")
        return None

def cleanup_local_files_after_mongodb_upload(email_data):
    """Delete local attachment files and claim folder after successful MongoDB upload"""
    try:
        print(f"🧹 Starting cleanup of local files for claim: {email_data['claim_id']}")
        
        deleted_files = 0
        failed_deletions = 0
        
        # Delete individual attachment files
        if email_data.get('attachment_paths'):
            for attachment_path in email_data['attachment_paths']:
                try:
                    if os.path.exists(attachment_path):
                        os.remove(attachment_path)
                        deleted_files += 1
                        print(f"🗑️  Deleted: {os.path.basename(attachment_path)}")
                    else:
                        print(f"⚠️  File not found (already deleted?): {os.path.basename(attachment_path)}")
                except Exception as e:
                    failed_deletions += 1
                    print(f"❌ Failed to delete {os.path.basename(attachment_path)}: {e}")
        
        # Try to delete the claim folder if it's empty
        try:
            # Extract the claim folder path from the first attachment
            if email_data.get('attachment_paths') and len(email_data['attachment_paths']) > 0:
                first_attachment = email_data['attachment_paths'][0]
                claim_folder = os.path.dirname(first_attachment)
                
                # Check if folder exists and is empty
                if os.path.exists(claim_folder) and not os.listdir(claim_folder):
                    os.rmdir(claim_folder)
                    print(f"📁 Deleted empty claim folder: {os.path.basename(claim_folder)}")
                elif os.path.exists(claim_folder):
                    remaining_files = os.listdir(claim_folder)
                    print(f"📁 Claim folder not deleted (contains {len(remaining_files)} files): {remaining_files}")
                else:
                    print(f"📁 Claim folder already deleted: {claim_folder}")
                    
        except Exception as e:
            print(f"❌ Error deleting claim folder: {e}")
        
        # Summary
        if deleted_files > 0:
            print(f"✅ Cleanup completed: {deleted_files} files deleted")
        if failed_deletions > 0:
            print(f"⚠️  Cleanup issues: {failed_deletions} files failed to delete")
        
        if deleted_files > 0 and failed_deletions == 0:
            print(f"🎉 All local files successfully cleaned up - space saved!")
            
    except Exception as e:
        print(f"❌ Error during local file cleanup: {e}")

def cleanup_all_local_attachments(older_than_hours=24):
    """Clean up all local attachment folders older than specified hours (maintenance function)"""
    try:
        print(f"🧹 Starting maintenance cleanup of attachments older than {older_than_hours} hours")
        
        attachments_folder = os.getenv('LOCAL_ATTACHMENTS_FOLDER', 'attachments')
        if not os.path.exists(attachments_folder):
            print(f"📁 Attachments folder not found: {attachments_folder}")
            return
        
        import time
        current_time = time.time()
        cutoff_time = current_time - (older_than_hours * 3600)  # Convert hours to seconds
        
        deleted_folders = 0
        deleted_files = 0
        
        for item in os.listdir(attachments_folder):
            item_path = os.path.join(attachments_folder, item)
            
            if os.path.isdir(item_path) and item.startswith('CLAIM_'):
                # Check folder creation time
                folder_mtime = os.path.getmtime(item_path)
                
                if folder_mtime < cutoff_time:
                    try:
                        # Delete all files in the folder
                        files_in_folder = 0
                        for file in os.listdir(item_path):
                            file_path = os.path.join(item_path, file)
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                files_in_folder += 1
                                deleted_files += 1
                            
                        # Delete the folder itself
                        os.rmdir(item_path)
                        deleted_folders += 1
                        print(f"🗑️  Deleted old claim folder: {item} ({files_in_folder} files)")
                        
                    except Exception as e:
                        print(f"❌ Failed to delete folder {item}: {e}")
        
        print(f"✅ Maintenance cleanup completed:")
        print(f"📁 Deleted folders: {deleted_folders}")
        print(f"📄 Deleted files: {deleted_files}")
        
    except Exception as e:
        print(f"❌ Error during maintenance cleanup: {e}") 