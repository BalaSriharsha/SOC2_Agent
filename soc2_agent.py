import sys
import time
import os
import json
import requests
import re
import tempfile
import subprocess
import argparse
from playwright.sync_api import sync_playwright
import boto3

# Define a system prompt that instructs the LLM to generate Python code
system_prompt = """
You are an AI assistant that helps collect SOC 2 evidence in AWS. Generate precise Python code based on the user's request.

DECISION FRAMEWORK:
1. For data that can be directly queried via AWS APIs → Use boto3
2. For visual evidence or data only available in the AWS Console UI → Use Playwright

BOTO3 APPROACH (AWS API):
- Import boto3 and set up appropriate clients
- Use list_*, describe_*, get_* methods to query AWS resources
- Process and format the returned JSON data
- Write results to a timestamped file under evidences/
- Example services: IAM, CloudTrail, S3, CloudWatch, Config, KMS, etc.
- Code template:
  ```python
  import boto3
  import json
  import time
  import os
  
  def collect_evidence():
      # Initialize AWS clients
      client = boto3.client('service_name')
      
      # Make API calls
      response = client.describe_resource()
      
      # Process results
      # ...
      
      # Save evidence
      timestamp = int(time.time())
      evidence_dir = f"evidences/{timestamp}"
      os.makedirs(evidence_dir, exist_ok=True)
      output_file = os.path.join(evidence_dir, "evidence.json")
      
      with open(output_file, "w") as f:
          json.dump(response, f, indent=2, default=str)
          
      return os.path.abspath(output_file)
  
  # Execute and print result path
  print(collect_evidence())
  ```

PLAYWRIGHT APPROACH (Browser Automation):
- Import Playwright and load AWS session from aws_session.json
- Navigate to specific AWS Console URLs
- Use robust waiting strategies and avoid hardcoded selectors
- Take screenshots or extract text/data from the UI
- Save evidence to timestamped directory
- Code template:
  ```python
  from playwright.sync_api import sync_playwright
  import json
  import time
  import os
  
  def collect_evidence():
      evidence_dir = f"evidences/{int(time.time())}"
      os.makedirs(evidence_dir, exist_ok=True)
      
      with sync_playwright() as p:
          # Launch browser with increased timeouts
          browser = p.chromium.launch(headless=True)
          
          try:
              # Load AWS session
              with open("aws_session.json", "r") as f:
                  storage = json.load(f)
                  
              # Create context with longer timeout
              context = browser.new_context(
                  storage_state=storage,
                  viewport={"width": 1280, "height": 720}
              )
              
              # Set generous timeouts for the AWS Console which can be slow
              page = context.new_page()
              page.set_default_timeout(60000)  # 60 seconds for all operations
              
              # Navigate and wait for page to be fully loaded
              page.goto("https://console.aws.amazon.com/specific-service")
              
              # Wait for network to be idle and page content to stabilize
              page.wait_for_load_state("networkidle")
              page.wait_for_load_state("domcontentloaded")
              
              # Wait for any content to appear rather than specific selectors
              # Look for common AWS console elements instead of specific tables
              page.wait_for_selector("main", timeout=60000)
              
              # Additional safety - wait a bit for any animations/loading
              page.wait_for_timeout(2000)
              
              # Capture evidence
              screenshot_path = os.path.join(evidence_dir, "screenshot.png")
              page.screenshot(path=screenshot_path)
              
              return os.path.abspath(screenshot_path)
          except Exception as e:
              # Log error and save error screenshot if possible
              error_path = os.path.join(evidence_dir, "error.txt")
              with open(error_path, "w") as f:
                  f.write(f"Error: {str(e)}")
              
              try:
                  # Try to capture screenshot even if there was an error
                  page.screenshot(path=os.path.join(evidence_dir, "error_state.png"))
              except:
                  pass
                  
              return os.path.abspath(error_path)
          finally:
              browser.close()
  
  # Execute and print result path
  print(collect_evidence())
  ```

IMPORTANT REQUIREMENTS:
1. Create complete, standalone code that's ready to execute
2. Include ALL necessary imports and error handling
3. Save evidence files with descriptive names in timestamped directories
4. THE FINAL LINE MUST PRINT THE ABSOLUTE PATH to the evidence file/directory
5. DO NOT include any explanations, comments or markdown formatting

Return ONLY executable Python code.
"""

def execute_in_sandbox(code: str) -> str:
    """Execute code in a sandbox and return the result."""
    # Create a temporary directory and file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, "task.py")
        with open(temp_file, "w") as f:
            f.write(code)
        
        # Execute the code in a subprocess
        try:
            # Make sure the current directory is available to the subprocess
            # so it can access aws_session.json
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),  # Run in the current directory
                timeout=300  # 5 minute timeout
            )
            if result.returncode != 0:
                return f"Error executing code: {result.stderr}"
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Execution timed out after 5 minutes"
        except Exception as e:
            return f"Error executing code: {str(e)}"

def ask_permission(code: str) -> bool:
    """Ask user for permission to execute the generated code."""
    print("\n===== GENERATED CODE =====")
    print(code)
    print("=========================\n")
    response = input("Do you want to execute this code? (yes/no): ").lower()
    return response in ["yes", "y"]

# Query the LLM (Ollama with llama3.1)
def query_llm(prompt: str) -> str:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

# Extract Python code from LLM response
def extract_code(response: str) -> str:
    """Extract Python code from LLM response."""
    # Try to find code blocks with ```python ... ``` format
    match = re.search(r'```python\s*(.*?)\s*```', response, re.DOTALL)
    if match:
        return match.group(1)
    
    # If no python code blocks, try to find any code blocks
    match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
    if match:
        return match.group(1)
    
    # Look for common Python patterns if no code blocks are found
    if re.search(r'import\s+[a-zA-Z0-9_]+', response) and re.search(r'def\s+[a-zA-Z0-9_]+\(', response):
        # This looks like Python code without code blocks
        return response
    
    # If no code blocks, assume the entire response is code
    return response

# Main logic
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="SOC 2 Evidence Collection Agent")
    parser.add_argument("prompt", help="The SOC 2-related prompt for evidence collection")
    parser.add_argument("--sandbox", action="store_true", default=False, 
                        help="Run in sandbox mode without asking for permission")
    parser.add_argument("--ask-permission", action="store_true", default=True,
                        help="Always ask for permission before executing code")
    args = parser.parse_args()
    
    # Ensure evidences directory exists
    os.makedirs("evidences", exist_ok=True)
    
    user_prompt = args.prompt
    full_prompt = system_prompt + "\n\nUser request: " + user_prompt
    print(f"Processing prompt: {user_prompt}")
    
    print("Generating code for your request...")
    llm_response = query_llm(full_prompt)
    
    # Extract code from LLM response
    code = extract_code(llm_response)
    
    # Execute code based on permission settings
    if args.sandbox:
        print("Executing code in sandbox environment...")
        result = execute_in_sandbox(code)
        print(f"Evidence collected: {result}")
    elif args.ask_permission:
        if ask_permission(code):
            print("Executing code...")
            result = execute_in_sandbox(code)
            print(f"Evidence collected: {result}")
        else:
            print("Code execution cancelled by user.")
    else:
        print("Executing code...")
        result = execute_in_sandbox(code)
        print(f"Evidence collected: {result}")