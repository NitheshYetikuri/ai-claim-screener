import os
import imaplib
import email
import ssl
import time
import mysql.connector
from mysql.connector import Error
import uuid
import json # Added for storing attachment paths
from datetime import datetime
# from queue import Queue  <- No longer needed
# from threading import Lock <- No longer needed
from email.header import decode_header
from dotenv import load_dotenv
# from fulfillment_processor import FulfillmentProcessor <- No longer needed

load_dotenv()

class MailMonitor:
    def __init__(self):
        self.username = os.getenv("EMAIL_USERNAME")
        self.app_password = os.getenv("EMAIL_APP_PASSWORD")
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        self.mail_connection = None
        self.db_connection = None
        # self.email_queue = Queue() <- REPLACED with mail_jobs table
        # self.queue_lock = Lock() <- REPLACED with DB transactions
        # self.fulfillment_processor = FulfillmentProcessor() <- MOVED to worker.py
        
        # API endpoints
        # self.fastapi_base_url = os.getenv('FASTAPI_BASE_URL', 'http://localhost:8000') <- MOVED to worker.py
        # self.mail_service_url = os.getenv('MAIL_SERVICE_URL', 'http://localhost:8001') <- MOVED to worker.py
        
        # Prompts folder
        self.prompts_folder = os.path.join(os.path.dirname(__file__), 'prompts')
        
    def load_prompt_file(self, filename):
        """Load content from prompt file"""
        # ... existing code ...
        try:
            file_path = os.path.join(self.prompts_folder, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[ERROR] Error loading prompt file {filename}: {e}")
            return None
            
    def connect_to_database(self):
        """Connect to MySQL database using mysql.connector"""
        try:
            # Updated to use your environment variables
            self.db_connection = mysql.connector.connect(
                host=os.getenv('mysql_host'),
                port=int(os.getenv('mysql_port', 3306)),
                user=os.getenv('mysql_user'),
                password=os.getenv('mysql_password'),
                database=os.getenv('mysql_db')
            )
            
            if self.db_connection.is_connected():
                print("[OK] Database connection established")
                return True
            else:
                print("[ERROR] Database connection failed")
                return False
                
        except Error as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False
    
    def connect_to_mail_server(self):
        """Connect to Gmail IMAP server"""
        # ... existing code ...
        try:
            context = ssl.create_default_context()
            self.mail_connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, ssl_context=context)
            self.mail_connection.login(self.username, self.app_password)
            
            status, messages = self.mail_connection.select("inbox")
            if status != 'OK':
                print("[ERROR] Failed to select inbox")
                return False
            
            print("[OK] Mail server connection established")
            return True
        except Exception as e:
            print(f"[ERROR] Mail server connection failed: {e}")
            return False
    
    # --- REMOVED check_user_registration ---
    # --- REMOVED send_unregistered_user_email_via_service ---
    # (This logic is now in worker.py)

    def get_current_mail_count(self):
        """Get current mail count from mail server"""
        # ... existing code ...
        try:
            status, messages = self.mail_connection.select("inbox")
            if status == 'OK':
                mail_count = int(messages[0])
                print(f"[EMAIL] Current mail count: {mail_count}")
                return mail_count
            return 0
        except Exception as e:
            print(f"[ERROR] Error getting mail count: {e}")
            return 0
    
    def get_stored_mail_details(self):
        """Get last mail count and connection time from database"""
        # ... existing code ...
        try:
            # Use dictionary=True to get dict results
            with self.db_connection.cursor(dictionary=True) as cursor:
                # Fixed table name to 'last_mail_details_vv' to match schema
                cursor.execute("SELECT mail_count, last_connection_time FROM last_mail_details ORDER BY id DESC LIMIT 1")
                result = cursor.fetchone()
                
                if result:
                    print(f"[DATA] Stored mail details - Count: {result['mail_count']}, Last connection: {result['last_connection_time']}")
                    return result['mail_count'], result['last_connection_time']
                else:
                    print("[DATA] No previous mail details found in database")
                    return 0, None
        except Exception as e:
            print(f"[ERROR] Error getting stored mail details: {e}")
            return 0, None
    
    def update_mail_details(self, mail_count):
        """Update mail count and connection time in database"""
        # ... existing code ...
        try:
            current_time = datetime.now()
            # Use dictionary=True for cursor
            with self.db_connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "INSERT INTO last_mail_details (mail_count, last_connection_time) VALUES (%s, %s)",
                    (mail_count, current_time)
                )
                self.db_connection.commit()
                print(f"[OK] Updated database - Mail count: {mail_count}, Time: {current_time}")
                return True
        except Exception as e:
            print(f"[ERROR] Error updating mail details: {e}")
            return False
    
    def process_email_attachments(self, msg, claim_id):
        """Extract and save email attachments"""
        # ... existing code ...
        attachment_paths = []
        save_path = os.getenv('LOCAL_ATTACHMENTS_FOLDER', 'attachments')
        
        # Create claim-specific folder
        claim_folder = os.path.join(save_path, claim_id)
        if not os.path.exists(claim_folder):
            os.makedirs(claim_folder)
            print(f"[FILE] Created folder: {claim_folder}")
        
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
                            print(f"[FILE] Saved attachment: {unique_filename}")
                            
                        except Exception as e:
                            print(f"[ERROR] Error saving attachment {filename}: {e}")
        
        return attachment_paths
    
    def extract_email_content(self, msg):
        """Extract email content from message"""
        # ... existing code ...
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
    
    def fetch_new_mails_to_db(self, stored_count, current_count):
        """Fetch new mails and add to mail_jobs database table"""
        try:
            new_mail_count = current_count - stored_count
            print(f"[EMAIL] Processing {new_mail_count} new mails")
            
            # ... existing code to get new_mail_ids ...
            status, email_ids = self.mail_connection.search(None, "ALL")
            if status != 'OK':
                print("[ERROR] Failed to search emails")
                return False
            
            email_id_list = email_ids[0].split() if email_ids[0] else []
            new_mail_ids = email_id_list[-new_mail_count:] if new_mail_count > 0 else []
            
            jobs_added = 0
            for email_id_bytes in new_mail_ids:
                email_id_str = email_id_bytes.decode('utf-8')
                
                try:
                    # ... existing code to fetch email and parse details ...
                    status, data = self.mail_connection.fetch(email_id_str, "(RFC822)")
                    if status != 'OK':
                        continue
                    
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    subject_header = msg.get("Subject", "No Subject")
                    subject, _ = decode_header(subject_header)[0]
                    subject = subject.decode('utf-8', errors='ignore') if isinstance(subject, bytes) else str(subject)
                    
                    from_header = msg.get("From", "Unknown Sender")
                    sender, _ = decode_header(from_header)[0]
                    sender = sender.decode('utf-8', errors='ignore') if isinstance(sender, bytes) else str(sender)
                    sender_email = email.utils.parseaddr(sender)[1]
                    
                    unique_id = str(uuid.uuid4()).replace('-', '').upper()[:8]
                    date_str = datetime.now().strftime("%Y%m%d")
                    claim_id = f"CLAIM_{unique_id}_{date_str}"
                    
                    email_content = self.extract_email_content(msg)
                    attachment_paths = self.process_email_attachments(msg, claim_id)
                    
                    # --- NEW DATABASE INSERT LOGIC ---
                    with self.db_connection.cursor() as cursor:
                        insert_query = """
                        INSERT INTO mail_jobs 
                        (claim_id, sender_email, subject, content, local_attachment_paths, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, 'PENDING', %s)
                        """
                        cursor.execute(insert_query, (
                            claim_id,
                            sender_email,
                            subject,
                            email_content,
                            json.dumps(attachment_paths), # Store paths as JSON string
                            datetime.now()
                        ))
                        self.db_connection.commit()
                        jobs_added += 1
                        print(f"[QUEUE] Added job to DB for {sender_email}. Claim ID: {claim_id}")

                except Exception as e:
                    print(f"[ERROR] Error processing email {email_id_str}: {e}")
            
            print(f"[OK] Added {jobs_added} new jobs to mail_jobs table")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error fetching new mails: {e}")
            return False
    
    # --- REMOVED process_email_queue ---
    # (This logic is now in worker.py)
    
    def monitor_mails(self):
        """Main monitoring loop (Producer)"""
        print("[START] Starting Mail Monitor (Producer)")
        print("="*70)
        
        # Connect to database and mail server
        if not self.connect_to_database():
            return False
        
        if not self.connect_to_mail_server():
            return False
        
        try:
            while True:
                print(f"\n[CHECK] Checking for new mails at {datetime.now()}")
                
                # Get current mail count from server
                current_mail_count = self.get_current_mail_count()
                
                # Get stored mail count from database
                stored_mail_count, last_connection_time = self.get_stored_mail_details()
                
                print(f"[DATA] Comparison - Stored: {stored_mail_count}, Current: {current_mail_count}")
                
                # Check if this is the first run (database is empty)
                if last_connection_time is None:
                    print("[NEW] First run detected - initializing mail count without processing existing emails")
                    self.update_mail_details(current_mail_count)
                    print(f"[OK] Initialized database with current mail count: {current_mail_count}")
                    print("[EMAIL] Will start monitoring for new emails from next check onwards")
                    
                # Check if there are new mails
                elif current_mail_count > stored_mail_count:
                    print(f"[NEW] Found {current_mail_count - stored_mail_count} new mails!")
                    
                    # Fetch new mails and add to DB queue
                    if self.fetch_new_mails_to_db(stored_mail_count, current_mail_count):
                        # Update database with new count
                        self.update_mail_details(current_mail_count)
                        
                        # --- REMOVED call to process_email_queue ---
                        print(f"[PRODUCER] New jobs added to database. Worker will process them.")
                    
                else:
                    print("[EMAIL] No new mails found")
                
                print("[WAIT] Waiting 30 seconds before next check...")
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n[STOP] Mail monitoring stopped by user")
            return True
        except Exception as e:
            print(f"[ERROR] Monitoring error: {e}")
            return False
        finally:
            # Close connections
            if self.mail_connection:
                try:
                    self.mail_connection.close()
                    self.mail_connection.logout()
                except:
                    pass
            
            if self.db_connection and self.db_connection.is_connected():
                self.db_connection.close()
            
            print("[CLOSE] All connections closed")

if __name__ == "__main__":
    monitor = MailMonitor()
    monitor.monitor_mails()
