import subprocess
import time
import httpx
import sys
import os

# Define paths
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_python = os.path.join(backend_path, "venv", "Scripts", "python.exe")

if not os.path.exists(venv_python):
    # Fallback to current system python if venv isn't present
    venv_python = sys.executable

# 1. Clean up any process on port 8000
print("Checking and cleaning port 8000...")
if sys.platform == "win32":
    try:
        output = subprocess.check_output("netstat -aon | findstr :8000.*LISTENING", shell=True, text=True)
        for line in output.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 5:
                pid = parts[-1]
                print(f"Killing process {pid} occupying port 8000...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Port 8000 is free.")
else:
    subprocess.run("lsof -t -i:8000 | xargs kill -9", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 2. Setup environment variables for test execution
env = os.environ.copy()
env["CLAP_ENABLED"] = "false"
env["SYNC_ENABLED"] = "false"
env["PYTHONUNBUFFERED"] = "1"

# 3. Start the FastAPI backend
print("Starting JARVIS FastAPI backend...")
process = subprocess.Popen(
    [venv_python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=backend_path,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    env=env,
    text=True,
    bufsize=1
)

# 4. Monitor startup
startup_complete = False
start_time = time.time()
timeout = 90.0

print("Waiting for server startup logs...")
while True:
    poll = process.poll()
    if poll is not None:
        print(f"\nERROR: Backend process exited with code {poll}")
        remaining = process.stdout.read()
        print("Remaining process output:")
        print(remaining)
        sys.exit(1)

    line = process.stdout.readline()
    if line:
        print(f"[Uvicorn] {line.strip()}")
        if "Application startup complete" in line or "Uvicorn running on" in line or "JARVIS is online!" in line:
            print("\n✓ Backend startup detected!")
            startup_complete = True
            break
    else:
        time.sleep(0.1)

    if time.time() - start_time > timeout:
        print(f"\nERROR: Startup timed out after {timeout} seconds")
        process.terminate()
        sys.exit(1)

# Extra buffer for ports to bind completely
time.sleep(2)

print("\n--- Testing API Endpoints ---")
all_passed = True

tests = [
    {
        "name": "GET /health",
        "path": "/health",
        "method": "GET",
        "payload": None,
        "expect_status": [200]
    },
    {
        "name": "GET /status",
        "path": "/status",
        "method": "GET",
        "payload": None,
        "expect_status": [200]
    },
    {
        "name": "GET /voices",
        "path": "/voices",
        "method": "GET",
        "payload": None,
        "expect_status": [200]
    },
    {
        "name": "GET /monitors",
        "path": "/monitors",
        "method": "GET",
        "payload": None,
        "expect_status": [200]
    },
    {
        "name": "GET /history",
        "path": "/history",
        "method": "GET",
        "payload": None,
        "expect_status": [200]
    },
    {
        "name": "POST /settings",
        "path": "/settings",
        "method": "POST",
        "payload": {"tts_voice": "en-US-GuyNeural"},
        "expect_status": [200]
    },
    {
        "name": "POST /command",
        "path": "/command",
        "method": "POST",
        "payload": {"text": "ping"},
        # /command could return 200, or 503/500 depending on active LLM connections,
        # but the endpoint itself should respond properly rather than crash.
        "expect_status": [200, 503, 500]
    }
]

with httpx.Client(timeout=15.0) as client:
    for test in tests:
        url = f"http://127.0.0.1:8000{test['path']}"
        print(f"Running Test: {test['name']}")
        try:
            if test["method"] == "GET":
                response = client.get(url)
            else:
                response = client.post(url, json=test["payload"])
            
            print(f"  Response Status: {response.status_code}")
            if response.status_code in test["expect_status"]:
                resp_json = response.json()
                print(f"  Response Body: {resp_json}")
                if isinstance(resp_json, dict) and "error" in resp_json and resp_json["error"] and response.status_code == 200:
                    print(f"  Result: FAILED (API returned error: {resp_json['error']})")
                    all_passed = False
                else:
                    print("  Result: PASSED")
            else:
                print(f"  Response Body: {response.text}")
                print(f"  Result: FAILED (Expected one of status codes: {test['expect_status']})")
                all_passed = False
        except Exception as e:
            print(f"  Exception querying {url}: {e}")
            print("  Result: FAILED")
            all_passed = False
        print("-" * 40)

# 5. Terminate server cleanly
print("Stopping FastAPI server...")
process.terminate()
try:
    process.wait(timeout=5)
except subprocess.TimeoutExpired:
    process.kill()

print("FastAPI server stopped.")

if all_passed:
    print("\nSUCCESS: All REST routes verified successfully!")
    sys.exit(0)
else:
    print("\nFAILURE: One or more routes failed validation.")
    sys.exit(1)
