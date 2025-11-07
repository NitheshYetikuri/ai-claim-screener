import subprocess
import time
import sys
import os

# --- Configuration ---

# List of scripts to launch in order.
# APIs must start first so the workers can connect to them.
SCRIPTS_TO_RUN = [
    # 1. Microservices (FastAPI)
    "apis/user_validator.py",
    "apis/mail_service.py",
    "apis/fulfillment_api.py",
    
    # 2. Background Workers
    "mail_monitor.py",
    "worker.py",
    "stuck_job_resolver.py"
]

# Path to the Python executable in your virtual environment.
# This ensures the correct interpreter and packages are used.
PYTHON_EXECUTABLE = sys.executable

# --- NEW: Central log file ---
LOG_FILE = "app.log"
# -----------------------------


def run_all_services():
    """
    Launches all specified Python scripts as independent processes.
    All output will be redirected to the LOG_FILE.
    """
    print("=" * 70)
    print(f"Starting all services using Python: {PYTHON_EXECUTABLE}")
    print(f"Redirecting all output to: {LOG_FILE}")
    print("=" * 70)
    
    processes = []
    
    # Open the log file in append mode with line buffering
    try:
        log_file_handle = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    except Exception as e:
        print(f"[CRITICAL] Failed to open log file {LOG_FILE}: {e}")
        return
    
    try:
        for script in SCRIPTS_TO_RUN:
            if not os.path.exists(script):
                print(f"[ERROR] Script not found: {script}. Skipping.")
                continue
                
            print(f"[LAUNCH] Starting {script}...")
            
            try:
                # MODIFIED:
                # - Added "-u" for unbuffered python output, critical for live logs
                # - Redirected stdout to our log file
                # - Redirected stderr to stdout (so errors go to the same log file)
                process = subprocess.Popen(
                    [PYTHON_EXECUTABLE, "-u", script],
                    stdout=log_file_handle,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8"
                )
                processes.append((script, process))
                print(f"[OK] Launched {script} (PID: {process.pid})")
                
                time.sleep(2) # Give the service time to start
                
            except Exception as e:
                print(f"[ERROR] Failed to launch {script}: {e}")

        print("\n" + "=" * 70)
        print("✅ All services are now running in the background.")
        print("View live logs in 'app.log' or on the Streamlit dashboard.")
        print("Press Ctrl+C in this terminal to shut down all services.")
        print("=" * 70)

        # Keep this main script alive.
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[STOP] KeyboardInterrupt received. Shutting down all services...")
        
    except Exception as e:
        print(f"\n[CRITICAL] Main runner failed: {e}. Shutting down...")

    finally:
        print("[CLEANUP] Terminating all child processes...")
        for script_name, process in processes:
            try:
                process.terminate()
                print(f"[STOPPED] {script_name} (PID: {process.pid})")
            except Exception as e:
                print(f"[ERROR] Could not terminate {script_name}: {e}")
        
        # Close the main log file handle
        if log_file_handle:
            log_file_handle.close()
            print(f"[CLEANUP] Log file {LOG_FILE} closed.")
                
        print("=" * 70)
        print("All services have been shut down.")
        print("=" * 70)


if __name__ == "__main__":
    # Clear the log file on each new run
    if os.path.exists(LOG_FILE):
        open(LOG_FILE, "w").close()
        
    run_all_services()