import os
import boto3
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class S3Uploader:
    def __init__(self):
        self.config = {
            'bucket_name': os.getenv('S3_BUCKET_NAME', 'aig-vibecoding'),
            'region': os.getenv('AWS_REGION', 'us-east-1'),
            's3_prefix': os.getenv('S3_PREFIX', 'AI_insurance_claim'),
            'url_expiry': int(os.getenv('S3_URL_EXPIRY_SECONDS', 3600))
        }
        self.s3_client = None
        
    def authenticate_aws_session(self, aws_credentials=None):
        try:
            if aws_credentials is None:
                access_key = os.getenv('AWS_ACCESS_KEY_ID')
                secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
                session_token = os.getenv('AWS_SESSION_TOKEN')
                
                if access_key and secret_key:
                    self.s3_client = boto3.client(
                        's3',
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key,
                        aws_session_token=session_token,
                        region_name=self.config['region']
                    )
                else:
                    cred_input = input("Enter AWS credentials JSON: ").strip()
                    if not cred_input:
                        self.s3_client = boto3.client('s3', region_name=self.config['region'])
                    else:
                        credentials = json.loads(cred_input)
                        if "AccessKeyId" in credentials:
                            self.s3_client = boto3.client(
                                's3',
                                aws_access_key_id=credentials["AccessKeyId"],
                                aws_secret_access_key=credentials["SecretAccessKey"],
                                aws_session_token=credentials["SessionToken"],
                                region_name=self.config['region']
                            )
                        else:
                            return False
            else:
                if isinstance(aws_credentials, str):
                    credentials = json.loads(aws_credentials)
                else:
                    credentials = aws_credentials
                
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                    region_name=self.config['region']
                )
            
            self.s3_client.head_bucket(Bucket=self.config['bucket_name'])
            return True
            
        except Exception as e:
            self.s3_client = None
            return False

    def generate_claim_id(self):
        unique_id = str(uuid.uuid4()).replace('-', '').upper()[:8]
        date_str = datetime.now().strftime("%Y%m%d")
        return f"CLAIM_{unique_id}_{date_str}"

    def upload_mail_content(self, user_email, claim_id, mail_content):
        if not self.s3_client:
            return None
            
        try:
            s3_key = f"{self.config['s3_prefix']}/{user_email}/claims/{claim_id}/mail_content.txt"
            
            self.s3_client.put_object(
                Bucket=self.config['bucket_name'],
                Key=s3_key,
                Body=mail_content.encode('utf-8'),
                ContentType='text/plain'
            )
            
            signed_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.config['bucket_name'], 'Key': s3_key},
                ExpiresIn=self.config['url_expiry']
            )
            
            return {
                'url': signed_url,
                's3_key': s3_key,
                'bucket': self.config['bucket_name']
            }
            
        except Exception as e:
            return None

    def upload_attachment(self, user_email, claim_id, attachment_path):
        """Upload single attachment to S3 and return signed URL"""
        if not self.s3_client:
            print("[ERROR] S3 client not initialized. Please authenticate first.")
            return None
            
        try:
            if not os.path.exists(attachment_path):
                print(f"[ERROR] Attachment file not found: {attachment_path}")
                return None
                
            filename = os.path.basename(attachment_path)
            s3_key = f"{self.config['s3_prefix']}/{user_email}/claims/{claim_id}/attachments/{filename}"
            
            # Get file info
            file_size = os.path.getsize(attachment_path)
            file_ext = os.path.splitext(filename)[1].lower()
            
            # Determine content type
            content_type_map = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.txt': 'text/plain',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            content_type = content_type_map.get(file_ext, 'application/octet-stream')
            
            # Upload attachment
            self.s3_client.upload_file(
                attachment_path, 
                self.config['bucket_name'], 
                s3_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'Metadata': {
                        'claim_id': claim_id,
                        'user_email': user_email,
                        'original_filename': filename,
                        'file_size': str(file_size),
                        'upload_timestamp': datetime.now().isoformat()
                    }
                }
            )
            
            # Generate signed URL
            signed_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.config['bucket_name'], 'Key': s3_key},
                ExpiresIn=self.config['url_expiry']
            )
            
            print(f"[OK] Attachment uploaded: {filename} ({file_size} bytes)")
            return {
                'url': signed_url,
                's3_key': s3_key,
                'bucket': self.config['bucket_name'],
                'filename': filename,
                'file_size': file_size,
                'content_type': content_type,
                'expires_in': self.config['url_expiry']
            }
            
        except Exception as e:
            print(f"[ERROR] Error uploading attachment {attachment_path}: {e}")
            return None

    def upload_attachments(self, user_email, claim_id, attachment_paths):
        """Upload multiple attachments to S3 and return list of signed URLs"""
        if not attachment_paths:
            return []
            
        uploaded_attachments = []
        
        for attachment_path in attachment_paths:
            result = self.upload_attachment(user_email, claim_id, attachment_path)
            if result:
                uploaded_attachments.append(result)
        
        print(f"[OK] Uploaded {len(uploaded_attachments)} out of {len(attachment_paths)} attachments")
        return uploaded_attachments

    def upload_complete_email(self, email_data, claim_id=None):
        """Upload complete email (content + attachments) and return all URLs"""
        if not self.s3_client:
            if not self.authenticate_aws_session():
                return None
        
        try:
            # Generate claim ID if not provided
            if not claim_id:
                claim_id = self.generate_claim_id()
            
            user_email = email_data['sender_email']
            
            # Prepare mail content
            mail_content = f"""Subject: {email_data['subject']}
From: {email_data['sender_email']}
Timestamp: {email_data.get('timestamp', datetime.now())}
Claim ID: {claim_id}

Content:
{email_data['content']}
"""
            
            # Upload mail content
            mail_result = self.upload_mail_content(user_email, claim_id, mail_content)
            if not mail_result:
                print("[ERROR] Failed to upload mail content")
                return None
            
            # Upload attachments
            attachment_results = []
            if email_data.get('attachment_paths'):
                attachment_results = self.upload_attachments(
                    user_email, 
                    claim_id, 
                    email_data['attachment_paths']
                )
            
            # Return complete upload results
            return {
                'claim_id': claim_id,
                'user_email': user_email,
                'mail_content': mail_result,
                'attachments': attachment_results,
                'total_attachments': len(attachment_results),
                'upload_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"[ERROR] Error uploading complete email: {e}")
            return None

    def get_file_info(self, s3_key):
        """Get file information from S3"""
        if not self.s3_client:
            return None
            
        try:
            response = self.s3_client.head_object(
                Bucket=self.config['bucket_name'], 
                Key=s3_key
            )
            
            return {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'content_type': response.get('ContentType', 'unknown'),
                'metadata': response.get('Metadata', {})
            }
            
        except Exception as e:
            print(f"[ERROR] Error getting file info: {e}")
            return None

    def generate_download_url(self, s3_key, expires_in=None):
        """Generate a new signed URL for existing S3 object"""
        if not self.s3_client:
            return None
            
        try:
            expiry = expires_in or self.config['url_expiry']
            
            signed_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.config['bucket_name'], 'Key': s3_key},
                ExpiresIn=expiry
            )
            
            return signed_url
            
        except Exception as e:
            print(f"[ERROR] Error generating download URL: {e}")
            return None


def test_s3_uploader():
    """Test function for S3 uploader"""
    uploader = S3Uploader()
    
    # Test authentication
    if not uploader.authenticate_aws_session():
        print("[ERROR] Authentication failed")
        return
    
    # Test data
    test_email = {
        'sender_email': 'test@example.com',
        'subject': 'Test Claim',
        'content': 'This is a test claim submission.',
        'attachment_paths': [],  # Add real file paths for testing
        'timestamp': datetime.now()
    }
    
    # Test upload
    result = uploader.upload_complete_email(test_email)
    if result:
        print("[OK] Test upload successful:")
        print(json.dumps(result, indent=2, default=str))
    else:
        print("[ERROR] Test upload failed")


if __name__ == "__main__":
    print("S3 Uploader Module")
    print("Run test_s3_uploader() to test functionality")
    
    # Uncomment to run test
    test_s3_uploader() 