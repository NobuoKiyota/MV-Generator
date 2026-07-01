import os
import sys
import subprocess
import argparse

def run_command(args, shell=False):
    """Run command and stream output in real-time"""
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=shell)
    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())
    rc = process.poll()
    return rc

def main():
    parser = argparse.ArgumentParser(description="Launcher for Desktop GUI with automatic venv and dependency management.")
    parser.add_argument("--app", default="xlsx_generator_gui.py", help="Desktop GUI app script to run")
    args = parser.parse_args()

    app_path = args.app
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(base_dir, "venv")
    
    print("===================================================")
    print(f" Starting Desktop App: {app_path}")
    print("===================================================")
    print()

    # 1. Check and create virtual environment
    if not os.path.exists(venv_dir):
        print(f"[INFO] Virtual environment 'venv' not found. Creating at: {venv_dir}")
        rc = subprocess.call([sys.executable, "-m", "venv", venv_dir])
        if rc != 0:
            print("[ERROR] Failed to create virtual environment. Please ensure Python is installed and added to PATH.")
            sys.exit(1)
        print("[INFO] Virtual environment created successfully.")

    # Virtual environment execution paths (Windows)
    venv_python = os.path.join(venv_dir, "Scripts", "python.exe")

    if not os.path.exists(venv_python):
        print("[ERROR] Virtual environment python.exe not found. Virtual environment might be corrupted.")
        sys.exit(1)

    # 2. Check dependencies
    print("[INFO] Checking dependencies in virtual environment...")
    check_code = "import openpyxl, librosa, google.generativeai, dotenv, mido"
    rc = subprocess.call([venv_python, "-c", check_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3. Install dependencies if missing
    if rc != 0:
        print("[INFO] Some dependencies are missing. Installing packages from requirements.txt...")
        req_file = os.path.join(base_dir, "requirements.txt")
        if not os.path.exists(req_file):
            print(f"[ERROR] requirements.txt not found at: {req_file}")
            sys.exit(1)
            
        print("[INFO] Upgrading pip...")
        subprocess.call([venv_python, "-m", "pip", "install", "--upgrade", "pip"])
        
        rc_install = run_command([venv_python, "-m", "pip", "install", "-r", req_file])
        if rc_install != 0:
            print("[ERROR] Failed to install dependencies.")
            sys.exit(1)
        print("[INFO] Dependencies installed successfully.")
    else:
        print("[INFO] All dependencies are satisfied.")

    # 4. Start application
    print(f"[INFO] Launching Desktop GUI...")
    try:
        cmd = [venv_python, app_path]
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[INFO] Application stopped by user.")
    except Exception as e:
        print(f"[ERROR] Failed to start GUI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
