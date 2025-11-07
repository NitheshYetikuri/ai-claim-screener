import os
import json
import uuid
import mysql.connector  # Changed from pymysql
from mysql.connector import Error
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

def get_database_connection():
    """Get database connection using mysql.connector"""
    # Updated to use your environment variables
    try:
        connection = mysql.connector.connect(
            host=os.getenv('mysql_host'),
            port=int(os.getenv('mysql_port', 3306)),
            user=os.getenv('mysql_user'),
            password=os.getenv('mysql_password'),
            database=os.getenv('mysql_db')
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

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

@app.get("/")
def test_database_connection():
    """Test database connection"""
    try:
        connection = get_database_connection()
        if connection is None:
            raise Exception("Database connection failed to initialize")
        
        # Use dictionary=True for dict-like results
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        connection.close()
        
        return {
            "status": "success",
            "database_connection": "successful",
            "message": "Database connection working"
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "database_connection": "failed",
            "error": str(e),
            "message": "Database connection failed"
       }

@app.post("/add-fulfillment")
def add_fulfillment(data: FulfillmentRequest):
    """Add fulfillment data to database"""
    try:
        connection = get_database_connection()
        if connection is None:
            raise Exception("Database connection failed")
            
        fulfillment_id = f"FULFILL_{str(uuid.uuid4()).replace('-', '').upper()[:8]}"
        
        # Convert string timestamp to datetime if provided
        s3_timestamp = None
        if data.s3_upload_timestamp:
            try:
                s3_timestamp = datetime.fromisoformat(data.s3_upload_timestamp.replace('Z', '+00:00'))
            except:
                s3_timestamp = datetime.now()
        
        # Use dictionary=True for dict-like results
        with connection.cursor(dictionary=True) as cursor:
            insert_query = """
            INSERT INTO fulfillment (
                fulfillment_id, user_mail, claim_id, mail_content, 
                mail_content_s3_url, attachment_count, attachment_s3_urls, 
                local_attachment_paths, fulfillment_status, missing_items,
                s3_upload_timestamp, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                fulfillment_id,
                data.user_mail,
                data.claim_id,
                data.mail_content,
                data.mail_content_s3_url,
                data.attachment_count,
                json.dumps(data.attachment_s3_urls) if data.attachment_s3_urls else None,
                json.dumps(data.local_attachment_paths) if data.local_attachment_paths else None,
                data.fulfillment_status,
                data.missing_items,
                s3_timestamp,
                datetime.now()
            ))
            
            connection.commit()
        
        connection.close()
        
        return {
            "success": True,
            "fulfillment_id": fulfillment_id,
            "message": "Fulfillment data saved successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("fulfillment_api:app", host="0.0.0.0", port=8002, reload=True)

