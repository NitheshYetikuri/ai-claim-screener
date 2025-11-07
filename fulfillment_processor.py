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
from s3_uploader import S3Uploader

load_dotenv()

class FulfillmentProcessor:
    def __init__(self):
        # ... (all existing __init__ code is unchanged) ...
        # AWS Bedrock configuration
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        _bedrock_token = os.getenv("BEDROCK_API")
        if _bedrock_token:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = _bedrock_token
        
        self.bedrock_client = boto3.client(service_name="bedrock-runtime", region_name=self.aws_region)
        self.llm = ChatBedrockConverse(
            model_id=os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
            temperature=float(os.getenv("BEDROCK_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("BEDROCK_MAX_TOKENS", "1500")),
            client=self.bedrock_client,
        )
        
        # Mail service configuration
        self.mail_service_url = os.getenv('MAIL_SERVICE_URL', 'http://localhost:8001')
        
        # Fulfillment API configuration
        self.fulfillment_api_url = os.getenv('FULFILLMENT_API_URL', 'http://localhost:8002')
        
        # S3 Uploader for completed fulfillments
        self.s3_uploader = S3Uploader()
        
        # Load prompts from files
        self.prompts_folder = os.path.join(os.path.dirname(__file__), 'prompts')
    
    def load_prompt_file(self, filename):
        # ... (all existing load_prompt_file code is unchanged) ...
        """Load content from prompt file"""
        try:
            file_path = os.path.join(self.prompts_folder, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[ERROR] Error loading prompt file {filename}: {e}")
            return None
    
    def encode_image(self, image_path):
        # ... (all existing encode_image code is unchanged) ...
        """Encode image file to base64"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"[ERROR] Error encoding image {image_path}: {e}")
            return None
    
    def send_mail_via_service(self, to_email: str, subject: str, content: str):
        """Send email via mail service API"""
        # This function now raises an exception on failure instead of returning False
        try:
            print(f"[EMAIL] Sending email via mail service to: {to_email}")
            
            mail_request = {
                "mail_id": to_email,
                "subject": subject,
                "mail_content": content
            }
            
            response = requests.post(
                f"{self.mail_service_url}/send-mail",
                json=mail_request,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"[OK] Email sent successfully via mail service to {to_email}")
                return True
            else:
                # Raise an error with the details
                raise Exception(f"Mail service failed with status {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            # Raise the error for the worker to catch
            raise Exception(f"Error calling mail service: {e}")
        except Exception as e:
            raise e # Re-raise any other unexpected error
    
    def assess_fulfillment_with_llm(self, email_data):
        """
        Use LLM to assess if customer has provided all required fulfillment details.
        Raises Exception on failure.
        """
        # This function is unchanged, it already raises exceptions on failure
        # (e.g., if self.llm.invoke fails)
        try:
            # ... (all existing code from assess_fulfillment_with_llm) ...
            # Load system prompt from file
            system_prompt_content = self.load_prompt_file('fulfillment_system_prompt.txt')
            if not system_prompt_content:
                raise Exception("Failed to load system prompt")
            
            system_prompt = SystemMessage(content=system_prompt_content)
            
            # ... (rest of the function is unchanged) ...
            
            # Prepare content for LLM
            user_content_parts = [
                {
                    "type": "text",
                    "text": (
                        f"CLAIM FULFILLMENT ASSESSMENT\n\n"
                        f"CUSTOMER DETAILS:\n"
                        f"Email: {email_data['sender_email']}\n"
                        f"Subject: {email_data['subject']}\n"
                        f"Claim ID: {email_data['claim_id']}\n\n"
                        
                        f"EMAIL CONTENT TO ANALYZE:\n"
                        f"{email_data['content']}\n\n"
                        
                        f"ATTACHMENTS PROVIDED ({email_data['attachment_count']}):\n"
                    )
                }
            ]
            
            # Add detailed attachment information
            if email_data['attachment_paths']:
                attachment_details = []
                for i, path in enumerate(email_data['attachment_paths'], 1):
                    filename = os.path.basename(path)
                    file_size = os.path.getsize(path) if os.path.exists(path) else 0
                    file_ext = os.path.splitext(filename)[1].lower()
                    attachment_details.append(f"{i}. {filename} ({file_ext}, {file_size} bytes)")
                
                user_content_parts[0]["text"] += "\n".join(attachment_details)
            else:
                user_content_parts[0]["text"] += "No attachments provided"
            
            user_content_parts[0]["text"] += (
                f"\n\nPLEASE ASSESS:\n"
                f"- REASON FOR CLAIM: Is there a clear description of what happened?\n"
                f"- CLAIM AMOUNT: Look carefully for ANY monetary amount in the email content. Accept formats like:\n"
                f"   - 'claim amount: 3,00,000' (Indian format)\n"
                f"   - 'amount: 250000' or '$2500' or 'Rs 25000'\n"
                f"   - 'cost: 25000', 'damage: 2,50,000', 'total: 300000'\n"
                f"   - ANY clear monetary value or number that represents money\n"
                f"   If you find ANY monetary reference, consider CLAIM AMOUNT as PROVIDED!\n"
                f"- SUPPORTING PROOFS: Do the attachments support the claim (bills, photos, reports)?\n"
            )
            
            # Add images to LLM analysis for visual proof validation
            for attachment_path in email_data['attachment_paths']:
                if attachment_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    encoded_image = self.encode_image(attachment_path)
                    if encoded_image:
                        user_content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded_image}"
                            }
                        })
                        print(f"[IMAGE] Added image for analysis: {os.path.basename(attachment_path)}")
            
            user_prompt = HumanMessage(content=user_content_parts)
            
            # Invoke LLM
            print(f"[AI] Analyzing fulfillment requirements for {email_data['claim_id']}...")
            response = self.llm.invoke([system_prompt, user_prompt])
            
            print(f"[AI] LLM Fulfillment Assessment:")
            print(response.content)
            print("-" * 60)
            
            return response.content
            
        except Exception as e:
            # Re-raise the exception for the worker to catch
            raise Exception(f"Error in LLM fulfillment assessment: {e}")
    
    def identify_satisfied_requirements(self, email_data, missing_items_text):
        # ... (all existing identify_satisfied_requirements code is unchanged) ...
        """Identify which requirements have been satisfied based on email data and LLM response"""
        satisfied = []
        
        # User email is always satisfied (they sent the email)
        satisfied.append("- User email address provided")
        
        # Check if requirements are NOT mentioned in missing items
        missing_lower = missing_items_text.lower()
        
        # Check for reason/description
        reason_keywords = ["reason", "description", "what happened", "incident", "cause", "explain"]
        if not any(keyword in missing_lower for keyword in reason_keywords):
            satisfied.append("- Reason for claim provided")
            
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
            satisfied.append("- Claim amount specified")
            
        # Check for supporting proofs/attachments
        proof_keywords = ["proof", "document", "attachment", "evidence", "support", "bill", "receipt", "photo", "police report", "medical"]
        if email_data['attachment_count'] > 0:
            if not any(keyword in missing_lower for keyword in proof_keywords):
                satisfied.append(f"- Supporting documents provided ({email_data['attachment_count']} attachments)")
            else:
                # They have attachments but LLM says they need more/different ones
                satisfied.append(f"- Some documents provided ({email_data['attachment_count']} attachments, additional may be needed)")
        
        return satisfied
    
    def parse_fulfillment_response(self, llm_response, email_data):
        # ... (all existing parse_fulfillment_response code is unchanged) ...
        """Parse LLM response to extract fulfillment status and details"""
        try:
            import re
            
            print(f"[AI] Raw LLM Response:")
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
                satisfied_items = self.identify_satisfied_requirements(email_data, missing_items)
                
                # FAILSAFE: If all requirements are satisfied but LLM still says PENDING, override to COMPLETED
                if len(satisfied_items) >= 4 and (not missing_items or missing_items.strip() == "" or missing_items == "- Required fulfillment items missing"):
                    print("[PROCESS] FAILSAFE ACTIVATED: All requirements satisfied, overriding PENDING to COMPLETED")
                    status = "COMPLETED"
                    missing_items = ""
                    satisfied_items = []
            else:
                # For COMPLETED status, still identify what was satisfied for logging
                satisfied_items = [
                    "- User email address provided",
                    "- Reason for claim provided", 
                    "- Claim amount specified",
                    f"- Supporting documents provided ({email_data['attachment_count']} attachments)"
                ]
            
            # Generate email content if status is PENDING
            email_content = ""
            if status == "PENDING":
                # Always use our template to ensure consistent formatting with both satisfied and missing items
                email_template = self.load_prompt_file('fulfillment_pending_email.txt')
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
                    satisfied_items_text = ", ".join([item.replace("- ", "") for item in satisfied_items]) if satisfied_items else "None"
                    email_content = (
                        "Dear Customer,\n\n"
                        "Thank you for submitting your insurance claim. We have reviewed your submission:\n\n"
                        f"REQUIREMENTS SATISFIED: {satisfied_items_text}\n\n"
                        f"MISSING REQUIREMENTS: {missing_items}\n\n"
                        "Please reply with the missing information and supporting documents.\n\n"
                        "Best regards,\n"
                        "Insurance Claims Team"
                    )
            
            print(f"[DATA] Final Assessment: {status}")
            if satisfied_items:
                print(f"[OK] Satisfied: {len(satisfied_items)} requirements")
            if missing_items:
                print(f"[ERROR] Missing: {missing_items}")
            
            return {
                'status': status,
                'missing_items': missing_items,
                'satisfied_items': satisfied_items,
                'email_content': email_content
            }
            
        except Exception as e:
            print(f"[ERROR] Error parsing fulfillment response: {e}")
            return None
    
    def save_to_fulfillment_table(self, email_data, status, missing_items="", s3_result=None):
        """Save fulfillment details via API call. Raises Exception on failure."""
        try:
            # ... (all existing code from save_to_fulfillment_table) ...
            
            # Prepare data based on status and S3 upload result
            if s3_result and status == "completed":
                # For completed fulfillments with S3 upload
                mail_content_s3_url = s3_result['mail_content']['url']
                attachment_urls = [att['url'] for att in s3_result['attachments']]
                attachment_count = len(attachment_urls)
                s3_upload_timestamp = datetime.now().isoformat()
                
                # Store original mail content (first 1000 chars for reference)
                mail_content = f"Subject: {email_data['subject']}\nContent: {email_data['content'][:800]}"
                
                # Store local attachment paths for reference
                local_paths = [os.path.basename(path) for path in email_data.get('attachment_paths', [])]
                
                print(f"[SAVE] Preparing S3 data for API call")
                print(f"[FILE] Mail content S3 URL: {mail_content_s3_url[:50]}...")
                print(f"[FILE] {attachment_count} attachment URLs")
                
            else:
                # For pending fulfillments - no S3 upload yet
                mail_content_s3_url = None
                attachment_urls = []
                attachment_count = len(email_data.get('attachment_paths', []))
                s3_upload_timestamp = None
                
                # Store full mail content
                mail_content = f"Subject: {email_data['subject']}\nContent: {email_data['content']}"
                mail_content = mail_content[:1000]  # Limit length
                
                # Store local attachment paths
                local_paths = [os.path.basename(path) for path in email_data.get('attachment_paths', [])]
                
                print(f"[SAVE] Preparing pending fulfillment for API call")
            
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
            
            print(f"[PROCESS] Calling fulfillment API...")
            
            # Make API call
            response = requests.post(
                f"{self.fulfillment_api_url}/add-fulfillment",
                json=api_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                fulfillment_id = result.get('fulfillment_id')
                
                if s3_result:
                    print(f"[OK] Saved completed fulfillment via API: {fulfillment_id}")
                    print(f"[DATA] Record includes: Mail S3 URL + {attachment_count} attachment URLs")
                else:
                    print(f"[OK] Saved pending fulfillment via API: {fulfillment_id}")
                    print(f"[DATA] Record includes: Local content + {attachment_count} local attachments")
                    
                return fulfillment_id
            else:
                # Raise an error with the details
                raise Exception(f"Fulfillment API call failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            # Re-raise the exception for the worker to catch
            raise Exception(f"Error calling fulfillment API: {e}")
    
    # --- The main 'process_email_fulfillment' function is REMOVED ---
    # The worker will call the functions above directly.

    def upload_to_s3_for_completed_fulfillment(self, email_data):
        """
        Upload mail content and attachments to S3. Raises Exception on failure.
        """
        # This function is unchanged, it already raises exceptions on failure
        # (e.g., if s3_uploader.authenticate... fails)
        try:
            # ... (all existing code from upload_to_s3_for_completed_fulfillment) ...
            print(f"[CLOUD] Starting S3 upload for completed claim: {email_data['claim_id']}")
            
            # Get AWS credentials from environment or prompt user
            aws_credentials_json = os.getenv('AWS_CREDENTIALS_JSON')
            
            if aws_credentials_json:
                # Parse credentials from environment variable
                try:
                    aws_credentials = json.loads(aws_credentials_json)
                    print(f"[KEY] Using AWS credentials from environment variable")
                except json.JSONDecodeError:
                    print(f"[ERROR] Invalid AWS credentials JSON in environment variable")
                    aws_credentials = None
            else:
                # Prompt for credentials at runtime
                print(f"[KEY] AWS credentials not found in environment. Please provide them:")
                print(f"Enter AWS credentials JSON:")
                aws_creds_input = input().strip()
                
                if aws_creds_input:
                    try:
                        aws_credentials = json.loads(aws_creds_input)
                        print(f"[OK] AWS credentials provided via input")
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Invalid AWS credentials JSON format: {e}")
                        raise Exception(f"Invalid AWS credentials JSON format: {e}")
                else:
                    print(f"[ERROR] No AWS credentials provided")
                    raise Exception("No AWS credentials provided")
            
            # Authenticate S3 uploader
            if not self.s3_uploader.authenticate_aws_session(aws_credentials):
                print(f"[ERROR] S3 authentication failed")
                raise Exception("S3 authentication failed")
            
            # Upload complete email to S3
            s3_result = self.s3_uploader.upload_complete_email(email_data, email_data['claim_id'])
            
            if s3_result:
                print(f"[OK] S3 upload completed successfully")
                print(f"[FILE] Mail content URL: {s3_result['mail_content']['url']}")
                print(f"[FILE] Uploaded {s3_result['total_attachments']} attachments to S3")
                return s3_result
            else:
                print(f"[ERROR] S3 upload failed")
                raise Exception("S3 upload failed (upload_complete_email returned None)")
                
        except Exception as e:
            # Re-raise the exception for the worker to catch
            raise Exception(f"Error during S3 upload: {e}")
    
    def cleanup_local_files_after_s3_upload(self, email_data):
        # ... (all existing cleanup_local_files_after_s3_upload code is unchanged) ...
        """Delete local attachment files and claim folder after successful S3 upload"""
        try:
            print(f"[CLEANUP] Starting cleanup of local files for claim: {email_data['claim_id']}")
            
            deleted_files = 0
            failed_deletions = 0
            
            # Delete individual attachment files
            if email_data.get('attachment_paths'):
                for attachment_path in email_data['attachment_paths']:
                    try:
                        if os.path.exists(attachment_path):
                            os.remove(attachment_path)
                            deleted_files += 1
                            print(f"[DELETE] Deleted: {os.path.basename(attachment_path)}")
                        else:
                            print(f"[WARN] File not found (already deleted?): {os.path.basename(attachment_path)}")
                    except Exception as e:
                        failed_deletions += 1
                        print(f"[ERROR] Failed to delete {os.path.basename(attachment_path)}: {e}")
            
            # Try to delete the claim folder if it's empty
            try:
                # Extract the claim folder path from the first attachment
                if email_data.get('attachment_paths') and len(email_data['attachment_paths']) > 0:
                    first_attachment = email_data['attachment_paths'][0]
                    claim_folder = os.path.dirname(first_attachment)
                    
                    # Check if folder exists and is empty
                    if os.path.exists(claim_folder) and not os.listdir(claim_folder):
                        os.rmdir(claim_folder)
                        print(f"[FOLDER] Deleted empty claim folder: {os.path.basename(claim_folder)}")
                    elif os.path.exists(claim_folder):
                        remaining_files = os.listdir(claim_folder)
                        print(f"[FOLDER] Claim folder not deleted (contains {len(remaining_files)} files): {remaining_files}")
                    else:
                        print(f"[FOLDER] Claim folder already deleted: {claim_folder}")
                        
            except Exception as e:
                print(f"[ERROR] Error deleting claim folder: {e}")
            
            # Summary
            if deleted_files > 0:
                print(f"[OK] Cleanup completed: {deleted_files} files deleted")
            if failed_deletions > 0:
                print(f"[WARN] Cleanup issues: {failed_deletions} files failed to delete")
            
            if deleted_files > 0 and failed_deletions == 0:
                print(f"[OK] All local files successfully cleaned up - space saved!")
                
        except Exception as e:
            print(f"[ERROR] Error during local file cleanup: {e}")
    
