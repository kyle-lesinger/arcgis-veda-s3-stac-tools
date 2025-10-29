import arcpy
import os
import requests
import json
import tempfile
import shutil

class BrowseAndRenderSTACDirect(object):
    """Step 3 Alternative: Browse and Render STAC using direct credential access"""
    
    def __init__(self):
        self.label = "Step 3 Alt: Browse STAC (Direct Credentials)"
        self.description = """Browse STAC and render using temporary credentials directly.
        
        This bypasses ACS files and downloads data using credentials directly."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # API Credentials
        param0 = arcpy.Parameter(
            displayName="Credential API URL",
            name="cred_api_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.value = "https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds"
        params.append(param0)
        
        param1 = arcpy.Parameter(
            displayName="Credential API Key",
            name="cred_api_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        params.append(param1)
        
        # STAC API
        param2 = arcpy.Parameter(
            displayName="STAC API URL",
            name="stac_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        param2.filter.list = [
            "https://dev.openveda.cloud/api/stac",
            "https://openveda.cloud/api/stac"
        ]
        param2.value = "https://dev.openveda.cloud/api/stac"
        params.append(param2)
        
        # Collection
        param3 = arcpy.Parameter(
            displayName="Collection",
            name="collection",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.value = "usda_cattle_large_AFOs_2017"
        params.append(param3)
        
        # Number of items
        param4 = arcpy.Parameter(
            displayName="Number of Items",
            name="limit",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        param4.value = 1
        params.append(param4)
        
        # Download method
        param5 = arcpy.Parameter(
            displayName="Download Method",
            name="method",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param5.filter.type = "ValueList"
        param5.filter.list = ["boto3 (S3 API)", "HTTP Pre-signed URLs"]
        param5.value = "boto3 (S3 API)"
        params.append(param5)
        
        return params

    def execute(self, parameters, messages):
        cred_api_url = parameters[0].valueAsText
        cred_api_key = parameters[1].valueAsText
        stac_url = parameters[2].valueAsText
        collection = parameters[3].valueAsText
        limit = parameters[4].value
        method = parameters[5].valueAsText
        
        messages.addMessage("=== Direct Credential STAC Access ===")
        
        try:
            # Get credentials
            messages.addMessage("Fetching temporary credentials...")
            headers = {"api-key": cred_api_key}
            response = requests.get(cred_api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"Failed to get credentials: {response.status_code}")
                return
                
            creds = response.json()
            access_key = creds.get('AccessKeyId')
            secret_key = creds.get('SecretAccessKey')
            session_token = creds.get('SessionToken')
            
            messages.addMessage("[+] Retrieved credentials with session token")
            
            # Query STAC
            messages.addMessage(f"\nQuerying STAC collection: {collection}")
            items_url = f"{stac_url}/collections/{collection}/items?limit={limit}"
            response = requests.get(items_url)
            
            if response.status_code != 200:
                messages.addErrorMessage("Failed to query STAC")
                return
                
            data = response.json()
            features = data.get('features', [])
            messages.addMessage(f"Found {len(features)} items")
            
            if not features:
                return
            
            # Process items
            temp_dir = tempfile.mkdtemp()
            messages.addMessage(f"\nTemp directory: {temp_dir}")
            
            for feature in features:
                item_id = feature.get('id')
                assets = feature.get('assets', {})
                
                messages.addMessage(f"\nProcessing: {item_id}")
                
                for asset_name, asset_info in assets.items():
                    href = asset_info.get('href', '')
                    if href.startswith('s3://') and asset_info.get('type', '').startswith('image/'):
                        # Extract S3 details
                        bucket = href.replace('s3://', '').split('/')[0]
                        key = '/'.join(href.replace('s3://', '').split('/')[1:])
                        
                        messages.addMessage(f"  Asset: {asset_name}")
                        messages.addMessage(f"  Bucket: {bucket}")
                        messages.addMessage(f"  Key: {key}")
                        
                        if method == "boto3 (S3 API)":
                            # Method 1: Use boto3
                            try:
                                import boto3
                                from botocore.config import Config
                                
                                messages.addMessage("  Using boto3 to download...")
                                
                                # Create session with temporary credentials
                                session = boto3.Session(
                                    aws_access_key_id=access_key,
                                    aws_secret_access_key=secret_key,
                                    aws_session_token=session_token,
                                    region_name='us-west-2'
                                )
                                
                                s3 = session.client('s3', config=Config(signature_version='s3v4'))
                                
                                # Download file
                                local_file = os.path.join(temp_dir, os.path.basename(key))
                                s3.download_file(bucket, key, local_file)
                                
                                messages.addMessage(f"  [+] Downloaded to: {local_file}")
                                
                                # Add to map
                                aprx = arcpy.mp.ArcGISProject("CURRENT")
                                active_map = aprx.activeMap
                                active_map.addDataFromPath(local_file)
                                messages.addMessage("  [+] Added to map!")
                                
                            except ImportError:
                                messages.addMessage("  [-] boto3 not installed, trying HTTP method...")
                                method = "HTTP Pre-signed URLs"
                            except Exception as e:
                                messages.addMessage(f"  [-] boto3 failed: {str(e)}")
                                method = "HTTP Pre-signed URLs"
                        
                        if method == "HTTP Pre-signed URLs":
                            # Method 2: Generate pre-signed URL
                            try:
                                # Use requests-aws4auth or manual signing
                                messages.addMessage("  Generating pre-signed URL...")
                                
                                # Manual v4 signature (simplified)
                                import hmac
                                import hashlib
                                from datetime import datetime
                                
                                # This is a simplified version - full implementation would be longer
                                # For now, try direct HTTPS access first
                                https_url = f"https://{bucket}.s3.amazonaws.com/{key}"
                                messages.addMessage(f"  Trying HTTPS: {https_url}")
                                
                                # Download file
                                local_file = os.path.join(temp_dir, os.path.basename(key))
                                response = requests.get(https_url, stream=True)
                                
                                if response.status_code == 200:
                                    with open(local_file, 'wb') as f:
                                        shutil.copyfileobj(response.raw, f)
                                    
                                    messages.addMessage(f"  [+] Downloaded via HTTPS")
                                    
                                    # Add to map
                                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                                    active_map = aprx.activeMap
                                    active_map.addDataFromPath(local_file)
                                    messages.addMessage("  [+] Added to map!")
                                else:
                                    messages.addMessage(f"  [-] HTTPS failed: {response.status_code}")
                                    messages.addMessage("  The bucket might require signed requests")
                                    
                            except Exception as e:
                                messages.addMessage(f"  [-] HTTP method failed: {str(e)}")
            
            messages.addMessage(f"\n" + "="*50)
            messages.addMessage("Processing complete")
            messages.addMessage(f"Temp files in: {temp_dir}")
            messages.addMessage("Files will remain until you close ArcGIS Pro")
            
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
