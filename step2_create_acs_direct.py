import arcpy
import os
import requests
import json

class CreateACSFromProfileDirect(object):
    """Step 2 Alternative: Create ACS files by calling API directly"""
    
    def __init__(self):
        self.label = "Step 2 Direct: Create ACS (Direct API)"
        self.description = """Creates AWS S3 connection files (.acs) by calling the API directly.
        
        This avoids Python environment issues by not using subprocess."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # Profile Name
        param0 = arcpy.Parameter(
            displayName="AWS Profile",
            name="profile_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.value = "nasa-disasters-temp-creds"
        params.append(param0)
        
        # S3 Bucket selection
        param1 = arcpy.Parameter(
            displayName="S3 Bucket",
            name="bucket_selection",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.filter.type = "ValueList"
        param1.filter.list = [
            "NASA Disasters (nasa-disasters)",
            "VEDA Production (veda-data-store)",
            "VEDA Development (veda-data-store-dev)",
            "VEDA Staging (veda-data-store-staging)",
            "All VEDA Buckets",
            "Custom"
        ]
        param1.value = "NASA Disasters (nasa-disasters)"
        params.append(param1)
        
        # Custom bucket name
        param2 = arcpy.Parameter(
            displayName="Custom Bucket Name",
            name="custom_bucket",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            enabled=False)
        params.append(param2)
        
        # Connection name prefix
        param3 = arcpy.Parameter(
            displayName="Connection Name Prefix",
            name="connection_prefix",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.value = "nasa-disasters"
        params.append(param3)
        
        # Output folder
        param4 = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        param4.value = arcpy.mp.ArcGISProject("CURRENT").homeFolder
        params.append(param4)
        
        # AWS Region
        param5 = arcpy.Parameter(
            displayName="AWS Region",
            name="aws_region",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param5.value = "us-west-2"
        params.append(param5)
        
        return params

    def updateParameters(self, parameters):
        # Enable custom bucket field if Custom selected
        if parameters[1].value == "Custom":
            parameters[2].enabled = True
        else:
            parameters[2].enabled = False
            
        # Try to read config from profile
        profile_name = parameters[0].value
        if profile_name:
            config_path = os.path.join(os.path.expanduser("~"), ".aws", f"{profile_name}_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        if 'region' in config:
                            parameters[5].value = config['region']
                except:
                    pass

    def execute(self, parameters, messages):
        profile_name = parameters[0].valueAsText
        bucket_selection = parameters[1].valueAsText
        custom_bucket = parameters[2].valueAsText
        connection_prefix = parameters[3].valueAsText
        output_folder = parameters[4].valueAsText
        aws_region = parameters[5].valueAsText
        
        messages.addMessage("=== Step 2 Direct: Create ACS using Direct API ===")
        messages.addMessage(f"Profile: {profile_name}")
        messages.addMessage(f"Region: {aws_region}")
        
        # Read config file to get API details
        config_path = os.path.join(os.path.expanduser("~"), ".aws", f"{profile_name}_config.json")
        if not os.path.exists(config_path):
            # Try to extract from the script file
            script_path = os.path.join(os.path.expanduser("~"), ".aws", f"get_temp_creds_{profile_name}.py")
            if os.path.exists(script_path):
                messages.addMessage(f"\nReading API details from script: {script_path}")
                with open(script_path, 'r') as f:
                    script_content = f.read()
                    # Extract API URL and key
                    import re
                    url_match = re.search(r'API_URL\s*=\s*["\']([^"\']+)["\']', script_content)
                    key_match = re.search(r'API_KEY\s*=\s*["\']([^"\']+)["\']', script_content)
                    
                    if url_match and key_match:
                        api_url = url_match.group(1)
                        api_key = key_match.group(1)
                        messages.addMessage("Extracted API details from script")
                    else:
                        messages.addErrorMessage("Could not extract API details from script")
                        return
            else:
                messages.addErrorMessage(f"Config file not found: {config_path}")
                messages.addMessage("Please run Step 1 first")
                return
        else:
            # Read from config
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    
                # Try to get full API key from script
                script_path = config.get('script_path', f"~/.aws/get_temp_creds_{profile_name}.py")
                script_path = os.path.expanduser(script_path)
                
                if os.path.exists(script_path):
                    with open(script_path, 'r') as f:
                        script_content = f.read()
                        import re
                        url_match = re.search(r'API_URL\s*=\s*["\']([^"\']+)["\']', script_content)
                        key_match = re.search(r'API_KEY\s*=\s*["\']([^"\']+)["\']', script_content)
                        if url_match and key_match:
                            api_url = url_match.group(1)
                            api_key = key_match.group(1)
                        else:
                            messages.addErrorMessage("Could not extract API details")
                            return
                else:
                    messages.addErrorMessage("Script file not found")
                    return
            except Exception as e:
                messages.addErrorMessage(f"Error reading config: {str(e)}")
                return
        
        # Call API directly
        messages.addMessage(f"\nCalling API directly...")
        messages.addMessage(f"API URL: {api_url}")
        
        try:
            # Use the correct header
            headers = {"api-key": api_key}
            response = requests.get(api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"API request failed: {response.status_code}")
                messages.addMessage(f"Response: {response.text}")
                return
                
            # Parse credentials
            creds = response.json()
            
            access_key = creds.get('AccessKeyId')
            secret_key = creds.get('SecretAccessKey')
            session_token = creds.get('SessionToken')
            expiration = creds.get('Expiration', 'Unknown')
            
            if not access_key or not secret_key:
                messages.addErrorMessage("Invalid credentials returned")
                return
                
            messages.addMessage("[+] Retrieved temporary credentials")
            messages.addMessage(f"Expires: {expiration}")
            
            # Determine buckets to create
            bucket_map = {
                "NASA Disasters (nasa-disasters)": [("nasa-disasters", connection_prefix)],
                "VEDA Production (veda-data-store)": [("veda-data-store", f"{connection_prefix}-prod")],
                "VEDA Development (veda-data-store-dev)": [("veda-data-store-dev", f"{connection_prefix}-dev")],
                "VEDA Staging (veda-data-store-staging)": [("veda-data-store-staging", f"{connection_prefix}-staging")],
                "All VEDA Buckets": [
                    ("veda-data-store", f"{connection_prefix}-prod"),
                    ("veda-data-store-dev", f"{connection_prefix}-dev"),
                    ("veda-data-store-staging", f"{connection_prefix}-staging")
                ],
                "Custom": [(custom_bucket, f"{connection_prefix}-custom")] if custom_bucket else []
            }
            
            buckets = bucket_map.get(bucket_selection, [])
            
            # Create ACS files
            messages.addMessage(f"\nCreating {len(buckets)} ACS file(s)...")
            created = 0
            
            for bucket_name, conn_name in buckets:
                try:
                    messages.addMessage(f"\nCreating connection for: {bucket_name}")
                    
                    # Create the ACS file
                    # Note: Session tokens require special handling in ArcGIS Pro
                    if session_token:
                        try:
                            messages.addMessage("Including session token...")
                            # Method 1: Try with additional_options parameter
                            arcpy.management.CreateCloudStorageConnectionFile(
                                output_folder,
                                conn_name,
                                "AMAZON",
                                bucket_name,
                                access_key,
                                secret_key,
                                aws_region,
                                additional_options=f"AWS_SESSION_TOKEN={session_token}"
                            )
                            messages.addMessage("[+] Created with session token (method 1)")
                        except:
                            try:
                                # Method 2: Try embedding in secret key (some versions)
                                messages.addMessage("Trying alternate session token method...")
                                combined_secret = f"{secret_key}:{session_token}"
                                arcpy.management.CreateCloudStorageConnectionFile(
                                    output_folder,
                                    conn_name,
                                    "AMAZON",
                                    bucket_name,
                                    access_key,
                                    combined_secret,
                                    aws_region
                                )
                                messages.addMessage("[+] Created with session token (method 2)")
                            except:
                                # Method 3: Create ACS file manually
                                messages.addMessage("Creating ACS file manually with session token...")
                                acs_content = {
                                    "cloudName": "AMAZON",
                                    "connectionProperties": {
                                        "bucketName": bucket_name,
                                        "region": aws_region,
                                        "accessKeyId": access_key,
                                        "secretAccessKey": secret_key,
                                        "sessionToken": session_token
                                    },
                                    "name": conn_name
                                }
                                
                                acs_path = os.path.join(output_folder, f"{conn_name}.acs")
                                with open(acs_path, 'w') as f:
                                    json.dump(acs_content, f)
                                messages.addMessage("[+] Created manual ACS file with session token")
                    else:
                        arcpy.management.CreateCloudStorageConnectionFile(
                            output_folder,
                            conn_name,
                            "AMAZON",
                            bucket_name,
                            access_key,
                            secret_key,
                            aws_region
                        )
                        messages.addMessage("[+] Created without session token")
                    
                    acs_path = os.path.join(output_folder, f"{conn_name}.acs")
                    messages.addMessage(f"[+] Created: {acs_path}")
                    created += 1
                    
                except Exception as e:
                    messages.addErrorMessage(f"Failed for {bucket_name}: {str(e)}")
            
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"Successfully created {created} connection(s)")
            if expiration != 'Unknown':
                messages.addMessage(f"\nIMPORTANT: Credentials expire at {expiration}")
                messages.addMessage("You will need to recreate the ACS files before then")
                
        except requests.exceptions.RequestException as e:
            messages.addErrorMessage(f"Network error: {str(e)}")
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
            
        return
