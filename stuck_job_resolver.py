import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

def connect_to_database():
    """Connect to MySQL database using mysql.connector."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('mysql_host'),
            port=int(os.getenv('mysql_port', 3306)),
            user=os.getenv('mysql_user'),
            password=os.getenv('mysql_password'),
            database=os.getenv('mysql_db')
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"[ERROR] Database connection failed: {e}")
        return None

def reset_stuck_jobs():
    """
    Resets jobs that have been in the 'FLYING' state for too long
    (e.g., > 300 seconds) back to 'PENDING'.
    """
    connection = connect_to_database()
    if not connection:
        print("[ERROR] Janitor could not connect to database.")
        return

    print(f"\n[JANITOR] Running cleanup at {datetime.now()}")
    
    # Get timeout from env or default to 300 seconds (5 minutes)
    timeout_seconds = int(os.getenv('JOB_TIMEOUT_SECONDS', 300))
    
    try:
        with connection.cursor(dictionary=True) as cursor:
            # Find jobs that are 'FLYING' and older than the timeout
            query = """
                UPDATE mail_jobs
                SET 
                    status = 'PENDING', 
                    error_message = 'Reset by Janitor (stuck FLYING job)',
                    last_processed_at = %s
                WHERE 
                    status = 'FLYING' 
                    AND last_processed_at < NOW() - INTERVAL %s SECOND
            """
            cursor.execute(query, (datetime.now(), timeout_seconds))
            affected_rows = cursor.rowcount
            
            connection.commit()
            
            if affected_rows > 0:
                print(f"[OK] Found and reset {affected_rows} stuck 'FLYING' jobs.")
            else:
                print("[OK] No stuck jobs found.")
                
    except Error as e:
        print(f"[ERROR] Error during janitor run: {e}")
        connection.rollback()
    finally:
        if connection.is_connected():
            connection.close()
            print("[JANITOR] Cleanup finished. Connection closed.")

if __name__ == "__main__":
    while True:
        reset_stuck_jobs()
        # Run the janitor every 5 minutes
        print("[WAIT] Janitor sleeping for 300 seconds...")
        time.sleep(300)
