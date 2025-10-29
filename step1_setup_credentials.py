import arcpy
import os
import requests
import json
from datetime import datetime

class SetupAWSCredentials(object):
    """Step 1: Setup AWS Credentials by calling API and updating credentials file"""
    
    def __init__(self):
        self.label = "Step 1: Setup AWS Credentials"
        self.description = """Calls the API to get temporary credentials and updates ~/.aws/credentials
        
        This mimics what the creds-installer.py does but with manual input."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # API URL
        param0 = arcpy.Parameter(
            displayName="API URL",
            name="api_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.value = "https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds"
        params.append(param0)
        
        # API Key
        param1 = arcpy.Parameter(
            displayName="API Key",
            name="api_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        params.append(param1)
        
        # AWS Region
        param2 = arcpy.Parameter(
            displayName="AWS Region",
            name="aws_region",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.value = "us-west-2"
        params.append(param2)
        
        # Profile Name
        param3 = arcpy.Parameter(
            displayName="AWS Profile Name",
            name="profile_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.value = "nasa-disasters-temp-creds"
        params.append(param3)
        
        return params

    def execute(self, parameters, messages):
        api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        aws_region = parameters[2].valueAsText
        profile_name = parameters[3].valueAsText
        
        messages.addMessage("=== Step 1: Setup AWS Credentials ===")
        messages.addMessage(f"API URL: {api_url}")
        messages.addMessage(f"Profile: {profile_name}")
        messages.addMessage(f"Region: {aws_region}")
        
        # Show what the working script uses
        messages.addMessage("\nINFO: Your working get_temp_creds.py uses:")
        messages.addMessage('   headers={"api-key": API_KEY}')
        messages.addMessage("   Note: 'api-key' NOT 'x-api-key'!")
        
        # Step 1: Test API call
        messages.addMessage("\nTesting API connection...")
        try:
            # Try different authentication methods
            # CRITICAL: "api-key" must be first - this is what works!
            auth_methods = [
                ("api-key", {'api-key': api_key}),  # <-- THIS IS THE ONE THAT WORKS!
                ("x-api-key", {'x-api-key': api_key}),
                ("X-API-Key", {'X-API-Key': api_key}),
                ("X-Api-Key", {'X-Api-Key': api_key}),
                ("Authorization Bearer", {'Authorization': f'Bearer {api_key}'}),
                ("Authorization apikey", {'Authorization': f'apikey {api_key}'})
            ]
            
            messages.addMessage(f"\nWill test {len(auth_methods)} authentication methods:")
            
            response = None
            working_method = None
            
            for i, (method_name, headers) in enumerate(auth_methods, 1):
                try:
                    messages.addMessage(f"\n[{i}/{len(auth_methods)}] Testing: {method_name}")
                    messages.addMessage(f"     Headers: {headers}")
                    
                    response = requests.get(api_url, headers=headers, timeout=10)
                    messages.addMessage(f"     Response: {response.status_code}")
                    
                    if response.status_code == 200:
                        working_method = method_name
                        messages.addMessage(f"     SUCCESS with {method_name}!")
                        break
                    else:
                        messages.addMessage(f"     [-] Failed: {response.text[:100]}")
                except Exception as e:
                    messages.addMessage(f"     [-] Error: {str(e)}")
            
            if not working_method:
                messages.addErrorMessage("\nERROR: Could not authenticate with API")
                messages.addMessage("\nDEBUGGING INFO:")
                messages.addMessage("1. Your working script uses: headers={'api-key': API_KEY}")
                messages.addMessage("2. Make sure API key is correct")
                messages.addMessage("3. Try running this PowerShell test:")
                messages.addMessage('   $h = @{"api-key"="YOUR_API_KEY"}')
                messages.addMessage('   Invoke-RestMethod -Uri "YOUR_API_URL" -Headers $h')
                return
                
            # Parse response
            creds = response.json()
            messages.addMessage(f"\nRetrieved credentials successfully using: {working_method}")
            messages.addMessage(f"Credential fields: {list(creds.keys())}")
            if 'Expiration' in creds:
                messages.addMessage(f"Expires: {creds['Expiration']}")
            
            # Step 2: Create get_temp_creds.py script
            aws_dir = os.path.join(os.path.expanduser("~"), ".aws")
            if not os.path.exists(aws_dir):
                os.makedirs(aws_dir)
                messages.addMessage(f"\nCreated directory: {aws_dir}")
            
            script_path = os.path.join(aws_dir, f"get_temp_creds_{profile_name}.py")
            
            # Create script content that matches the working version with caching
            script_content = f'''#!/usr/bin/env python3
import os
import json
import requests
from datetime import datetime, timezone, timedelta

CACHE_FILE = os.path.expanduser("~/.aws/credentials_cache_{profile_name}.json")
API_URL = "{api_url}"
API_KEY = "{api_key}"
EXPIRATION_THRESHOLD = timedelta(minutes=5)  # Refresh if expiring within 5 min

def get_cached_credentials():
    """Reads cached credentials if they exist and are valid."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        expiration_time = datetime.fromisoformat(data.get("Expiration")).replace(tzinfo=timezone.utc)
        current_time = datetime.now(timezone.utc)  # Ensure UTC comparison
        if current_time < (expiration_time - EXPIRATION_THRESHOLD):
            return data  # Return valid cached credentials
        return None  # Expired or invalid credentials
    except:
        return None

def fetch_new_credentials():
    """Fetches new credentials from the API and saves them to cache."""
    try:
        # USING THE WORKING HEADER: {working_method}
        response = requests.get(API_URL, headers={{"{working_method}": API_KEY}}, timeout=5)
        response.raise_for_status()
        credentials = response.json()
        
        # Ensure Version field exists (required by AWS)
        if 'Version' not in credentials:
            credentials['Version'] = 1
            
        # Ensure Expiration is stored as a proper UTC timestamp
        if 'Expiration' in credentials:
            credentials["Expiration"] = datetime.fromisoformat(credentials["Expiration"]).replace(tzinfo=timezone.utc).isoformat()
            
        # Save to cache
        with open(CACHE_FILE, "w") as f:
            json.dump(credentials, f)
        return credentials
    except requests.RequestException as e:
        print(json.dumps({{"error": f"Failed to fetch credentials: {{str(e)}}"}}))
        exit(1)

if __name__ == "__main__":
    credentials = get_cached_credentials() or fetch_new_credentials()
    print(json.dumps(credentials))  # AWS CLI reads this output
'''
            
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            messages.addMessage(f"\n[+] Created script: {script_path}")
            messages.addMessage(f"  - Uses header: {working_method}")
            messages.addMessage("  - Includes credential caching")
            messages.addMessage("  - Auto-refreshes before expiration")
            
            # Step 3: Update ~/.aws/credentials
            creds_path = os.path.join(aws_dir, "credentials")
            
            # Read existing credentials
            existing_creds = ""
            if os.path.exists(creds_path):
                with open(creds_path, 'r', encoding='utf-8') as f:
                    existing_creds = f.read()
                messages.addMessage(f"\nFound existing credentials file with {len(existing_creds.split('[')) - 1} profiles")
            
            # Remove existing profile if present
            if f"[{profile_name}]" in existing_creds:
                messages.addMessage(f"Removing existing [{profile_name}] profile...")
                lines = existing_creds.split('\n')
                new_lines = []
                skip = False
                for line in lines:
                    if line.strip() == f"[{profile_name}]":
                        skip = True
                    elif skip and line.strip().startswith('['):
                        skip = False
                    if not skip:
                        new_lines.append(line)
                existing_creds = '\n'.join(new_lines)
                
                # Clean up extra blank lines
                while '\n\n\n' in existing_creds:
                    existing_creds = existing_creds.replace('\n\n\n', '\n\n')
            
            # Add new profile
            if not existing_creds.endswith('\n'):
                existing_creds += '\n'
            new_profile = f"\n[{profile_name}]\ncredential_process = python \"{script_path}\"\nregion = {aws_region}\n"
            
            with open(creds_path, 'w', encoding='utf-8') as f:
                f.write(existing_creds + new_profile)
            
            messages.addMessage(f"\n[+] Updated credentials file: {creds_path}")
            messages.addMessage(f"[+] Added profile: [{profile_name}]")
            
            # Save configuration for Step 2
            config_path = os.path.join(aws_dir, f"{profile_name}_config.json")
            config = {
                "profile_name": profile_name,
                "region": aws_region,
                "api_url": api_url,
                "api_key": api_key[:10] + "..." if len(api_key) > 10 else api_key,
                "created": datetime.now().isoformat(),
                "script_path": script_path,
                "auth_method": working_method,
                "auth_header_key": list(auth_methods[0][1].keys())[0]  # Store the exact header key
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            messages.addMessage(f"\n[+] Saved configuration: {config_path}")
            
            # Test the script
            messages.addMessage("\n" + "="*50)
            messages.addMessage("Testing the credential script...")
            try:
                import subprocess
                
                # Try to find python executable
                python_cmds = ["python", "python3", "py"]
                python_exe = None
                
                for cmd in python_cmds:
                    try:
                        result = subprocess.run([cmd, "--version"], capture_output=True, text=True)
                        if result.returncode == 0:
                            python_exe = cmd
                            messages.addMessage(f"Found Python: {cmd} ({result.stdout.strip()})")
                            break
                    except:
                        continue
                
                if not python_exe:
                    messages.addMessage("WARNING: Could not find Python executable")
                    return
                
                result = subprocess.run(
                    [python_exe, script_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    test_creds = json.loads(result.stdout)
                    messages.addMessage("Script test successful!")
                    messages.addMessage(f"  - AccessKeyId: {test_creds.get('AccessKeyId', 'N/A')[:10]}...")
                    messages.addMessage(f"  - Expires: {test_creds.get('Expiration', 'N/A')}")
                else:
                    messages.addMessage("WARNING: Script test failed")
                    messages.addMessage(f"Error: {result.stderr}")
                    messages.addMessage("The script was created but may need manual testing")
            except Exception as e:
                messages.addMessage(f"WARNING: Could not test script: {str(e)}")
            
            messages.addMessage("\n" + "="*50)
            messages.addMessage("[+] Setup complete! Now run Step 2 to create ACS files.")
            messages.addMessage(f"\nProfile created: {profile_name}")
            messages.addMessage(f"Script location: {script_path}")
            messages.addMessage("\nNote: Credentials are cached and auto-refresh before expiration.")
            
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage("\nFull error trace:")
            messages.addMessage(traceback.format_exc())
        
        return