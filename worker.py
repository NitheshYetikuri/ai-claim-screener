import os
import mysql.connector
from mysql.connector import Error
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from fulfillment_processor import FulfillmentProcessor

# Load environment variables from .env file
load_dotenv()

class MailWorker:
    def __init__(self):
        """Initialize the worker, database connection, and fulfillment processor."""
        print("[START] Initializing Mail Worker (Consumer)")
        self.db_connection = self.connect_to_database()
        self.fulfillment_processor = FulfillmentProcessor()
        
        # API endpoints
        self.fastapi_base_url = os.getenv('FASTAPI_BASE_URL', 'http://localhost:8000')
        self.mail_service_url = os.getenv('MAIL_SERVICE_URL', 'http://localhost:8001')
        self.human_verifier_email = os.getenv('HUMAN_VERIFICATION_EMAIL_ID')
        
        if not self.human_verifier_email:
            print("[WARN] HUMAN_VERIFICATION_EMAIL_ID not set. Error notifications will not be sent.")

    def connect_to_database(self):
        # ... (all existing connect_to_database code is unchanged) ...
        """Connect to MySQL database using mysql.connector."""
        try:
            connection = mysql.connector.connect(
                host=os.getenv('mysql_host'),
                port=int(os.getenv('mysql_port', 3306)),
                user=os.getenv('mysql_user'),
                password=os.getenv('mysql_password'),
                database=os.getenv('mysql_db'),
                autocommit=False # We will manage transactions manually
            )
            if connection.is_connected():
                print("[OK] Worker database connection established")
                return connection
        except Error as e:
            print(f"[ERROR] Worker database connection failed: {e}")
            return None

    def get_next_pending_job(self):
        # ... (all existing get_next_pending_job code is unchanged) ...
        """Get the next 'PENDING' job from the queue and lock it."""
        if not self.db_connection or not self.db_connection.is_connected():
            self.db_connection = self.connect_to_database()
            if not self.db_connection:
                return None

        try:
            with self.db_connection.cursor(dictionary=True) as cursor:
                # Lock the next PENDING row so no other worker can grab it
                cursor.execute("""
                    SELECT * FROM mail_jobs 
                    WHERE status = 'PENDING' 
                    ORDER BY created_at ASC 
                    LIMIT 1 
                    FOR UPDATE SKIP LOCKED
                """)
                job = cursor.fetchone()
                
                if job:
                    # Immediately update status to 'FLYING' to "check it out"
                    cursor.execute("""
                        UPDATE mail_jobs 
                        SET status = 'FLYING', last_processed_at = %s 
                        WHERE id = %s
                    """, (datetime.now(), job['id']))
                    self.db_connection.commit()
                    return job
                
                self.db_connection.commit() # Release any locks
                return None
                
        except Error as e:
            print(f"[ERROR] Error getting next job: {e}")
            self.db_connection.rollback()
            return None

    def update_job_status(self, job_id, status, error_message=None):
        # ... (all existing update_job_status code is unchanged) ...
        """Update the status of a job in the mail_jobs table."""
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE mail_jobs 
                    SET status = %s, error_message = %s, last_processed_at = %s
                    WHERE id = %s
                """, (status, error_message, datetime.now(), job_id))
            self.db_connection.commit()
            print(f"[JOB] Updated job {job_id} to status: {status}")
        except Error as e:
            print(f"[ERROR] Error updating job status for {job_id}: {e}")
            self.db_connection.rollback()

    def add_to_human_fulfillment(self, job, error_message):
        # ... (all existing add_to_human_fulfillment code is unchanged) ...
        """Add a failed job to the human_fulfillment table for review."""
        try:
            with self.db_connection.cursor() as cursor:
                insert_query = """
                INSERT INTO human_fulfillment 
                (failed_job_id, claim_id, sender_email, error_message, full_job_data, status, created_at)
                VALUES (%s, %s, %s, %s, %s, 'NEEDS_REVIEW', %s)
                """
                # Store all job data for easier review
                full_job_data = json.dumps(job, default=str)
                
                cursor.execute(insert_query, (
                    job['id'],
                    job['claim_id'],
                    job['sender_email'],
                    error_message,
                    full_job_data,
                    datetime.now()
                ))
            self.db_connection.commit()
            print(f"[FAIL] Job {job['id']} logged to human_fulfillment table")
        except Error as e:
            print(f"[ERROR] Error logging job {job['id']} to human_fulfillment: {e}")
            self.db_connection.rollback()

    def send_email(self, to_email, subject, content):
        # ... (all existing send_email code is unchanged) ...
        """Send an email via the mail_service API."""
        try:
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
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Error calling mail service: {e}")
            return False

    def check_user_registration(self, email_address):
        # ... (all existing check_user_registration code is unchanged) ...
        """Check if user is registered using user_validator API."""
        try:
            response = requests.get(f"{self.fastapi_base_url}/user/{email_address}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') == True:
                    return True, data.get('data', {})
            return False, None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Error calling user registration API: {e}")
            return False, None

    def send_unregistered_user_email(self, job):
        # ... (all existing send_unregistered_user_email code is unchanged) ...
        """Send email to unregistered user."""
        subject = "Insurance Claim - Registration Required"
        content = f"Dear Customer,\n\nYour email {job['sender_email']} is not registered in our system.\n\nClaim Reference: {job['claim_id']}\n\nPlease contact customer service.\n\nBest regards,\nInsurance Claims Team"
        
        # Try to load from template (example of using processor's helper)
        try:
            template = self.fulfillment_processor.load_prompt_file('user_not_found_email.txt')
            if template:
                lines = template.split('\n')
                subject = lines[0].replace('Subject: ', '')
                content_start = 2 if len(lines) > 1 and lines[1] == '' else 1
                content = '\n'.join(lines[content_start:])
                content = content.format(claim_id=job['claim_id'], user_email=job['sender_email'])
        except Exception:
            pass # Fallback to default content

        return self.send_email(job['sender_email'], subject, content)

    def run_worker(self):
        """Main worker loop to process jobs from the queue."""
        print("[RUN] Mail Worker is running... Checking for jobs.")
        
        while True:
            job = None
            try:
                # -----------------------------------------------------------------
                # STAGE 0: GET JOB
                # -----------------------------------------------------------------
                job = self.get_next_pending_job()
                
                if not job:
                    # No jobs found, wait
                    time.sleep(5)
                    continue

                print("\n" + "="*60)
                print(f"[PROCESS] Processing Job ID: {job['id']} | Claim ID: {job['claim_id']}")
                print("="*60)

                # --- 1. Re-create the email_data dict for the processor ---
                try:
                    attachment_paths = json.loads(job['local_attachment_paths']) if job['local_attachment_paths'] else []
                except json.JSONDecodeError:
                    attachment_paths = []

                email_data = {
                    'email_id': job['id'], # Use job ID for reference
                    'sender_email': job['sender_email'],
                    'subject': job['subject'],
                    'content': job['content'],
                    'claim_id': job['claim_id'],
                    'attachment_paths': attachment_paths,
                    'attachment_count': len(attachment_paths),
                    'timestamp': job['created_at']
                }

                # -----------------------------------------------------------------
                # STAGE 1: USER VALIDATION
                # -----------------------------------------------------------------
                is_registered, user_data = self.check_user_registration(email_data['sender_email'])
                
                if not is_registered:
                    print(f"[REJECT] User {email_data['sender_email']} not registered.")
                    self.send_unregistered_user_email(job)
                    self.update_job_status(job['id'], 'REJECTED')
                    continue

                print(f"[OK] User {email_data['sender_email']} is registered. Starting fulfillment.")
                
                # -----------------------------------------------------------------
                # STAGE 2: LLM ASSESSMENT
                # -----------------------------------------------------------------
                try:
                    llm_response = self.fulfillment_processor.assess_fulfillment_with_llm(email_data)
                    if not llm_response:
                        raise Exception("LLM returned no response")
                except Exception as e:
                    raise Exception(f"STAGE_LLM_ASSESSMENT_FAILED: {e}")

                # -----------------------------------------------------------------
                # STAGE 3: PARSE LLM RESPONSE
                # -----------------------------------------------------------------
                try:
                    parsed_result = self.fulfillment_processor.parse_fulfillment_response(llm_response, email_data)
                    if not parsed_result:
                        raise Exception("Failed to parse LLM response")
                except Exception as e:
                    raise Exception(f"STAGE_LLM_PARSE_FAILED: {e}")

                status = parsed_result['status']

                # -----------------------------------------------------------------
                # STAGE 4: FULFILLMENT (COMPLETED or PENDING)
                # -----------------------------------------------------------------
                if status == "COMPLETED":
                    
                    s3_result = None # Initialize s3_result
                    # --- STAGE 4a (COMPLETED): S3 UPLOAD ---
                    try:
                        s3_result = self.fulfillment_processor.upload_to_s3_for_completed_fulfillment(email_data)
                        if not s3_result:
                            # We will allow this to fail "gracefully" for now, but log it
                            print("[WARN] S3 upload failed, but proceeding to save fulfillment record.")
                            # You could also raise an exception here if S3 is mandatory
                            # raise Exception("S3 Uploader returned no result")
                    except Exception as e:
                        # Raise a specific error for the safety net
                        raise Exception(f"STAGE_S3_UPLOAD_FAILED: {e}")

                    # --- STAGE 4b (COMPLETED): SAVE TO API ---
                    try:
                        fulfillment_id = self.fulfillment_processor.save_to_fulfillment_table(email_data, "completed", s3_result=s3_result)
                        if not fulfillment_id:
                            raise Exception("Fulfillment API call failed")
                        
                        # Clean up local files AFTER successful API save
                        self.fulfillment_processor.cleanup_local_files_after_s3_upload(email_data)

                    except Exception as e:
                        raise Exception(f"STAGE_FULFILLMENT_API_FAILED: {e}")

                elif status == "PENDING":
                    
                    missing_items = parsed_result['missing_items']
                    email_content = parsed_result['email_content']

                    # --- STAGE 4c (PENDING): SAVE TO API ---
                    try:
                        fulfillment_id = self.fulfillment_processor.save_to_fulfillment_table(email_data, "pending", missing_items)
                        if not fulfillment_id:
                            raise Exception("Fulfillment API call failed for PENDING")
                    except Exception as e:
                        raise Exception(f"STAGE_FULFILLMENT_API_FAILED: {e}")

                    # --- STAGE 4d (PENDING): SEND MAIL ---
                    try:
                        email_sent = self.fulfillment_processor.send_mail_via_service(
                            to_email=email_data['sender_email'],
                            subject="Insurance Claim - Additional Information Required",
                            content=email_content
                        )
                        if not email_sent:
                            raise Exception("Mail Service API call returned False")
                    except Exception as e:
                        raise Exception(f"STAGE_MAIL_SERVICE_FAILED: {e}")
                
                # --- STAGE 5: FINAL SUCCESS ---
                # If we get here, all steps for this path passed
                # We use a clear success status. 'COMPLETED' means the job is done,
                # whether it was a COMPLETED or PENDING_CUSTOMER fulfillment.
                self.update_job_status(job['id'], 'PROCESSED_SUCCESS')
                print(f"[OK] All stages passed for Job ID: {job['id']} (Final Status: {status})")


            except Exception as e:
                # -----------------------------------------------------------------
                # CATCH-ALL SAFETY NET
                # 'e' will now contain our specific error message, e.g., "STAGE_S3_UPLOAD_FAILED: ..."
                # -----------------------------------------------------------------
                error_message = str(e)
                print(f"[CRITICAL] Job {job['id'] if job else 'N/A'} failed. Error: {error_message}")
                
                if job:
                    # Log to human fulfillment table
                    self.add_to_human_fulfillment(job, error_message)
                    # Mark as FAILED to stop crash loop
                    self.update_job_status(job['id'], 'FAILED', error_message)
                    
                    # Notify human verifier
                    if self.human_verifier_email:
                        self.send_email(
                            self.human_verifier_email,
                            f"URGENT: Job Failed - {job['claim_id']}",
                            f"Job ID {job['id']} for Claim ID {job['claim_id']} failed with an unexpected error:\n\n{error_message}\n\nThe job has been logged to the human_fulfillment table for review."
                        )
                
                # Wait a moment before retrying to prevent rapid-fire DB errors
                time.sleep(2)
            
            finally:
                # This block ensures our database connection is stable
                try:
                    if not self.db_connection.is_connected():
                        print("[DB] Reconnecting to database...")
                        self.db_connection = self.connect_to_database()
                except Exception as db_e:
                    print(f"[CRITICAL] Database connection failed in finally block: {db_e}")
                    self.db_connection = self.connect_to_database()


if __name__ == "__main__":
    worker = MailWorker()
    worker.run_worker()

