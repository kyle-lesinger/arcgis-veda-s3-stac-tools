import arcpy
import os
import requests
import json
from datetime import datetime

class Toolbox(object):
    def __init__(self):
        """Direct API Credential Tool"""
        self.label = "Direct API Credential Tool"
        self.alias = "direct_api_creds"
        self.tools = [CreateACSDirectAPI]

class CreateACSDirectAPI(object):
    def __init__(self):
        self.label = "Create ACS with Direct API Call"
        self.description = """Creates AWS S3 connection files (.acs) by calling the API directly.
        
        This avoids Python environment conflicts by making the API call within ArcGIS."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # Read API details from get_temp_creds.py if it exists
        default_url = ""
        default_key = ""
        script_path = os.path.join(os.path.expanduser("~"), ".aws", "get_temp_creds.py")
        
        if os.path.exists(script_path):
            try:
                with open(script_path, 'r') as f:
                    content = f.read()
                    # Try to extract URL and key from the script
                    if 'API_URL =' in content:
                        url_line = [line for line in content.split('\n') if 'API_URL =' in line][0]
                        default_url = url_line.split('=', 1)[1].strip().strip('"\'')
                    if 'API_KEY =' in content:
                        key_line = [line for line in content.split('\n') if 'API_KEY =' in line][0]
                        default_key = key_line.split('=', 1)[1].strip().strip('"\'')
            except:
                pass
        
        # API URL
        param0 = arcpy.Parameter(
            displayName="API URL (from get_temp_creds.py)",
            name="api_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.value = default_url or "https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds"
        params.append(param0)
        
        # API Key
        param1 = arcpy.Parameter(
            displayName="API Key (from get_temp_creds.py)",
            name="api_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.value = default_key or ""
        params.append(param1)
        
        # Environment selection
        param2 = arcpy.Parameter(
            displayName="S3 Bucket",
            name="environment",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        param2.filter.list = [
            "NASA Disasters (nasa-disasters)",
            "VEDA Production (veda-data-store)",
            "VEDA Development (veda-data-store-dev)",
            "VEDA Staging (veda-data-store-staging)",
            "All VEDA Environments",
            "Custom Bucket"
        ]
        param2.value = "NASA Disasters (nasa-disasters)"
        params.append(param2)
        
        # Custom bucket
        param3 = arcpy.Parameter(
            displayName="Custom Bucket Name",
            name="custom_bucket",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            enabled=False)
        params.append(param3)
        
        # AWS Region
        param4 = arcpy.Parameter(
            displayName="AWS Region",
            name="aws_region",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param4.value = "us-west-2"
        params.append(param4)
        
        # Connection name prefix
        param5 = arcpy.Parameter(
            displayName="Connection Name Prefix",
            name="connection_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param5.value = "nasa-disasters"
        params.append(param5)
        
        # Output folder
        param6 = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        param6.value = arcpy.mp.ArcGISProject("CURRENT").homeFolder
        params.append(param6)
        
        return params

    def updateParameters(self, parameters):
        # Enable/disable custom bucket parameter
        if parameters[2].value == "Custom Bucket":
            parameters[3].enabled = True
        else:
            parameters[3].enabled = False

    def execute(self, parameters, messages):
        api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        env = parameters[2].valueAsText
        custom_bucket = parameters[3].valueAsText
        aws_region = parameters[4].valueAsText
        conn_name = parameters[5].valueAsText
        output_folder = parameters[6].valueAsText
        
        messages.addMessage("=== Direct API Credential Retrieval ===")
        messages.addMessage(f"API URL: {api_url}")
        messages.addMessage(f"API Key: {api_key[:10]}..." if len(api_key) > 10 else f"API Key: {api_key}")
        
        # Make direct API call
        messages.addMessage("\nCalling API for temporary credentials...")
        try:
            headers = {
                'x-api-key': api_key,
                'Accept': 'application/json'
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"API request failed with status: {response.status_code}")
                messages.addErrorMessage(f"Response: {response.text}")
                return
                
            # Parse credentials
            creds = response.json()
            
            # Extract fields - try different naming conventions
            access_key = (creds.get('AccessKeyId') or 
                         creds.get('access_key_id') or 
                         creds.get('accessKeyId'))
                         
            secret_key = (creds.get('SecretAccessKey') or 
                         creds.get('secret_access_key') or 
                         creds.get('secretAccessKey'))
                         
            session_token = (creds.get('SessionToken') or 
                            creds.get('session_token') or 
                            creds.get('sessionToken'))
                            
            expiration = (creds.get('Expiration') or 
                         creds.get('expiration') or 
                         creds.get('expires_at'))
            
            if not access_key or not secret_key:
                messages.addErrorMessage("Failed to extract credentials from response")
                messages.addMessage(f"Response keys: {list(creds.keys())}")
                return
                
            messages.addMessage("✓ Successfully retrieved temporary credentials")
            if expiration:
                messages.addMessage(f"Expires: {expiration}")
            
            # Determine buckets
            bucket_map = {
                "NASA Disasters (nasa-disasters)": [("nasa-disasters", conn_name)],
                "VEDA Production (veda-data-store)": [("veda-data-store", f"{conn_name}-prod")],
                "VEDA Development (veda-data-store-dev)": [("veda-data-store-dev", f"{conn_name}-dev")],
                "VEDA Staging (veda-data-store-staging)": [("veda-data-store-staging", f"{conn_name}-staging")],
                "All VEDA Environments": [
                    ("veda-data-store", f"{conn_name}-prod"),
                    ("veda-data-store-dev", f"{conn_name}-dev"),
                    ("veda-data-store-staging", f"{conn_name}-staging")
                ],
                "Custom Bucket": [(custom_bucket, f"{conn_name}-custom")] if custom_bucket else []
            }
            
            buckets = bucket_map.get(env, [])
            
            # Create ACS files
            messages.addMessage(f"\nCreating {len(buckets)} connection file(s)...")
            created_count = 0
            
            for bucket, name in buckets:
                try:
                    messages.addMessage(f"\nCreating connection for bucket: {bucket}")
                    
                    # Create connection - handle session token carefully
                    if session_token:
                        # Session tokens require special handling
                        messages.addMessage("Including session token...")
                        try:
                            # Try the newer syntax first
                            arcpy.management.CreateCloudStorageConnectionFile(
                                output_folder,
                                name,
                                "AMAZON",
                                bucket,
                                access_key,
                                secret_key,
                                aws_region,
                                authentication_type="IAM_ROLE",
                                session_token=session_token
                            )
                        except:
                            # Fall back to standard method
                            messages.addWarning("Session token may not be supported, creating without it")
                            arcpy.management.CreateCloudStorageConnectionFile(
                                output_folder,
                                name,
                                "AMAZON",
                                bucket,
                                access_key,
                                secret_key,
                                aws_region
                            )
                    else:
                        arcpy.management.CreateCloudStorageConnectionFile(
                            output_folder,
                            name,
                            "AMAZON",
                            bucket,
                            access_key,
                            secret_key,
                            aws_region
                        )
                    
                    acs_path = os.path.join(output_folder, f"{name}.acs")
                    messages.addMessage(f"✓ Created: {acs_path}")
                    created_count += 1
                    
                except Exception as e:
                    messages.addErrorMessage(f"Failed for {bucket}: {str(e)}")
                    # Provide helpful guidance
                    if "session" in str(e).lower():
                        messages.addMessage("Note: Session tokens may require ArcGIS Pro 3.0 or newer")
            
            # Summary
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"Created {created_count} connection(s)")
            if expiration:
                messages.addMessage(f"\n⚠ Credentials expire: {expiration}")
                messages.addMessage("Re-run this tool when they expire")
                
        except requests.exceptions.RequestException as e:
            messages.addErrorMessage(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            messages.addErrorMessage(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            messages.addErrorMessage(f"Unexpected error: {str(e)}")
        
        return
