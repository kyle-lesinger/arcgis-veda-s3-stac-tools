import arcpy
import os
import json
import base64
import requests

class CreateACSWithSessionToken(object):
    """Create ACS files with proper session token support"""
    
    def __init__(self):
        self.label = "Step 2B: Create ACS with Session Token"
        self.description = """Creates AWS S3 connection files (.acs) with full session token support.
        
        This tool properly handles temporary credentials with session tokens."""
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
        
        # S3 Bucket
        param2 = arcpy.Parameter(
            displayName="S3 Bucket",
            name="bucket",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        param2.filter.list = [
            "veda-data-store-dev",
            "veda-data-store",
            "veda-data-store-staging",
            "nasa-disasters"
        ]
        param2.value = "veda-data-store-dev"
        params.append(param2)
        
        # Connection name
        param3 = arcpy.Parameter(
            displayName="Connection Name",
            name="connection_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.value = "veda-dev-temp"
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
            name="region",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param5.value = "us-west-2"
        params.append(param5)
        
        return params

    def execute(self, parameters, messages):
        api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        bucket = parameters[2].valueAsText
        conn_name = parameters[3].valueAsText
        output_folder = parameters[4].valueAsText
        region = parameters[5].valueAsText
        
        messages.addMessage("=== Creating ACS with Session Token Support ===")
        
        # Get credentials from API
        messages.addMessage(f"Fetching credentials from API...")
        try:
            headers = {"api-key": api_key}
            response = requests.get(api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"API request failed: {response.status_code}")
                return
                
            creds = response.json()
            access_key = creds.get('AccessKeyId')
            secret_key = creds.get('SecretAccessKey')
            session_token = creds.get('SessionToken')
            expiration = creds.get('Expiration', 'Unknown')
            
            if not all([access_key, secret_key, session_token]):
                messages.addErrorMessage("Missing required credential components")
                messages.addMessage(f"Has AccessKey: {access_key is not None}")
                messages.addMessage(f"Has SecretKey: {secret_key is not None}")
                messages.addMessage(f"Has SessionToken: {session_token is not None}")
                return
                
            messages.addMessage("[+] Retrieved temporary credentials with session token")
            messages.addMessage(f"Expires: {expiration}")
            
            # Method 1: Try standard ArcGIS method with environment variable
            acs_path = os.path.join(output_folder, f"{conn_name}.acs")
            
            try:
                messages.addMessage("\nMethod 1: Using environment variable for session token...")
                
                # Set environment variable for session token
                os.environ['AWS_SESSION_TOKEN'] = session_token
                
                # Create connection with environment variable set
                arcpy.management.CreateCloudStorageConnectionFile(
                    output_folder,
                    conn_name,
                    "AMAZON",
                    bucket,
                    access_key,
                    secret_key,
                    region
                )
                
                # Clear environment variable
                del os.environ['AWS_SESSION_TOKEN']
                
                messages.addMessage("[+] Created ACS file with environment variable method")
                
            except Exception as e1:
                messages.addMessage(f"[-] Method 1 failed: {str(e1)}")
                
                # Method 2: Create ACS file manually
                messages.addMessage("\nMethod 2: Creating ACS file manually...")
                
                try:
                    # ArcGIS Pro ACS file format
                    acs_content = f"""{{
    "version": "1.0",
    "type": "cloudStore",
    "cloudStoreType": "amazon",
    "connectionString": "REGION={region};BUCKET={bucket};ACCESS_KEY_ID={access_key};SECRET_ACCESS_KEY={secret_key};SESSION_TOKEN={session_token}",
    "friendlyName": "{conn_name}",
    "nodeId": "/"
}}"""
                    
                    with open(acs_path, 'w', encoding='utf-8') as f:
                        f.write(acs_content)
                    
                    messages.addMessage("[+] Created manual ACS file format 1")
                    
                except Exception as e2:
                    messages.addMessage(f"[-] Method 2 failed: {str(e2)}")
                    
                    # Method 3: Alternative ACS format
                    messages.addMessage("\nMethod 3: Alternative ACS format...")
                    
                    try:
                        # Alternative format that some versions use
                        connection_props = {
                            "bucketName": bucket,
                            "region": region,
                            "accessKey": access_key,
                            "secretKey": secret_key,
                            "sessionToken": session_token,
                            "authentication": "TEMPORARY"
                        }
                        
                        acs_data = {
                            "cloudStoreType": "AMAZON",
                            "connectionProperties": connection_props,
                            "name": conn_name
                        }
                        
                        with open(acs_path, 'w', encoding='utf-8') as f:
                            json.dump(acs_data, f, indent=2)
                        
                        messages.addMessage("[+] Created manual ACS file format 2")
                        
                    except Exception as e3:
                        messages.addMessage(f"[-] Method 3 failed: {str(e3)}")
            
            # Verify file was created
            if os.path.exists(acs_path):
                messages.addMessage(f"\n[+] ACS file created: {acs_path}")
                messages.addMessage(f"Size: {os.path.getsize(acs_path)} bytes")
                
                # Test the connection
                messages.addMessage("\nTesting connection...")
                test_key = "test-file.txt"  # A simple test
                test_path = acs_path + "\\" + test_key
                
                try:
                    if arcpy.Exists(test_path):
                        messages.addMessage("[+] Connection test passed - can list objects")
                    else:
                        messages.addMessage("[?] Connection created but couldn't verify access")
                except:
                    messages.addMessage("[?] Connection created but test inconclusive")
                    
                messages.addMessage("\n" + "="*50)
                messages.addMessage("ACS file created with session token support")
                messages.addMessage(f"Credentials expire: {expiration}")
                messages.addMessage("\nNOTE: If this still doesn't work, the issue may be:")
                messages.addMessage("- ArcGIS Pro version doesn't support session tokens in ACS files")
                messages.addMessage("- Cross-account bucket policies preventing access")
                messages.addMessage("- Need to use STS AssumeRole directly instead of basic session tokens")
            else:
                messages.addErrorMessage("Failed to create ACS file")
                
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
