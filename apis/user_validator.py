import os
import mysql.connector  # Changed from pymysql
from mysql.connector import Error
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

class UserCreateRequest(BaseModel):
    mail_id: EmailStr
    policy_type: str
    policy_issued_date: date

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

def get_user_by_email(email: str):
    """Get user details by email from user_details table"""
    connection = None
    try:
        connection = get_database_connection()
        if connection is None:
            raise Exception("Database connection failed")
            
        # Use dictionary=True for dict-like results
        with connection.cursor(dictionary=True) as cursor:
            query = "SELECT id, mail_id, policy_issued_date, policy_type FROM user_details WHERE mail_id = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            
            # Convert date to string for JSON serialization
            if result and 'policy_issued_date' in result:
                result['policy_issued_date'] = result['policy_issued_date'].strftime('%Y-%m-%d')
            
            return result
            
    except Exception as e:
        raise e
    finally:
        if connection and connection.is_connected():
            connection.close()

def create_user(user_data: UserCreateRequest):
    """Create a new user in the database"""
    connection = None
    try:
        connection = get_database_connection()
        if connection is None:
            raise Exception("Database connection failed")
        
        with connection.cursor(dictionary=True) as cursor:
            # Check if user already exists
            check_query = "SELECT id FROM user_details WHERE mail_id = %s"
            cursor.execute(check_query, (user_data.mail_id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                raise HTTPException(status_code=400, detail="User already exists")
            
            # Insert new user
            insert_query = """
                INSERT INTO user_details (mail_id, policy_type, policy_issued_date)
                VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (
                user_data.mail_id,
                user_data.policy_type,
                user_data.policy_issued_date
            ))
            
            # Get the created user ID
            user_id = cursor.lastrowid
            
            connection.commit()
            
            return {
                "id": user_id,
                "mail_id": user_data.mail_id,
                "policy_type": user_data.policy_type,
                "policy_issued_date": user_data.policy_issued_date.strftime('%Y-%m-%d')
            }
            
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if connection and connection.is_connected():
            connection.close()

@app.get("/")
def read_root():
    return {"status": "User Validator API is running"}

@app.get("/user/{user_email}")
def get_user_details(user_email: str):
    """Get user details by email ID"""
    try:
        if not user_email or "@" not in user_email:
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        user_details = get_user_by_email(user_email)
        
        if not user_details:
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "message": "User not found"
                }
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": user_details
            }
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/user")
def add_user(user_data: UserCreateRequest):
    """Add a new user to the database"""
    try:
        created_user = create_user(user_data)
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "User created successfully",
                "data": created_user
            }
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    uvicorn.run("user_validator:app", host="0.0.0.0", port=8000, reload=True)

