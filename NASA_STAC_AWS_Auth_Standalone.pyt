import arcpy
import os
import requests
import json
import tempfile
import hashlib
import hmac
from datetime import datetime, timezone
import urllib.parse

class Toolbox(object):
    def __init__(self):
        """NASA Disasters STAC Browser with AWS Authentication"""
        self.label = "NASA Disasters STAC AWS Auth"
        self.alias = "nasa_stac_aws"
        self.tools = [BrowseSTACWithAWSAuth]

class BrowseSTACWithAWSAuth(object):
    """Browse STAC and download using AWS signature authentication"""
    
    def __init__(self):
        self.label = "Browse STAC with AWS Auth"
        self.description = """Browse STAC catalogs and download files using AWS temporary credentials.
        
        This tool properly handles session tokens and signs S3 requests."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # Credential API
        param0 = arcpy.Parameter(
            displayName="Credential API URL",
            name="cred_api_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.value = "https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds"
        params.append(param0)
        
        param1 = arcpy.Parameter(
            displayName="API Key",
            name="api_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        params.append(param1)
        
        # STAC settings
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
        
        param3 = arcpy.Parameter(
            displayName="Collection ID",
            name="collection",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.value = "usda_cattle_large_AFOs_2017"
        params.append(param3)
        
        param4 = arcpy.Parameter(
            displayName="Number of Items",
            name="limit",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        param4.value = 1
        params.append(param4)
        
        # Output option
        param5 = arcpy.Parameter(
            displayName="Add to Map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        param5.value = True
        params.append(param5)
        
        return params

    def sign_request_v4(self, method, url, headers, payload, access_key, secret_key, session_token, region, service):
        """Manually implement AWS Signature V4"""
        
        # Parse URL
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc
        path = parsed.path or '/'
        
        # Calculate payload hash
        payload_hash = hashlib.sha256(payload.encode() if payload else b'').hexdigest()
        
        # Create timestamp
        now = datetime.now(timezone.utc)
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')
        
        # Create canonical headers (must be sorted)
        canonical_headers = f"host:{host}\n"
        canonical_headers += f"x-amz-content-sha256:{payload_hash}\n"
        canonical_headers += f"x-amz-date:{amz_date}\n"
        if session_token:
            canonical_headers += f"x-amz-security-token:{session_token}\n"
        
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        if session_token:
            signed_headers += ";x-amz-security-token"
        
        canonical_request = f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        
        # Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        
        # Calculate signature
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        k_date = sign(f"AWS4{secret_key}".encode('utf-8'), date_stamp)
        k_region = sign(k_date, region)
        k_service = sign(k_region, service)
        k_signing = sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # Create authorization header
        authorization = f"{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        # Build final headers
        final_headers = {
            'Host': host,
            'X-Amz-Date': amz_date,
            'X-Amz-Content-SHA256': payload_hash,
            'Authorization': authorization
        }
        
        if session_token:
            final_headers['X-Amz-Security-Token'] = session_token
            
        return final_headers

    def execute(self, parameters, messages):
        cred_api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        stac_url = parameters[2].valueAsText
        collection = parameters[3].valueAsText
        limit = parameters[4].value
        add_to_map = parameters[5].value
        
        messages.addMessage("=== STAC Browser with AWS Authentication ===")
        
        try:
            # Get credentials
            messages.addMessage("Fetching temporary credentials...")
            headers = {"api-key": api_key}
            response = requests.get(cred_api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"Failed to get credentials: {response.status_code}")
                return
                
            creds = response.json()
            access_key = creds.get('AccessKeyId')
            secret_key = creds.get('SecretAccessKey') 
            session_token = creds.get('SessionToken')
            
            if not all([access_key, secret_key, session_token]):
                messages.addErrorMessage("Missing credential components")
                return
                
            messages.addMessage("[+] Retrieved temporary credentials with session token")
            
            # Query STAC
            messages.addMessage(f"\nQuerying collection: {collection}")
            items_url = f"{stac_url}/collections/{collection}/items?limit={limit}"
            response = requests.get(items_url)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"STAC query failed: {response.status_code}")
                return
                
            data = response.json()
            features = data.get('features', [])
            messages.addMessage(f"Found {len(features)} items")
            
            # Create temp directory
            temp_dir = tempfile.mkdtemp()
            downloaded_files = []
            
            # Process each item
            for feature in features:
                item_id = feature.get('id')
                assets = feature.get('assets', {})
                
                messages.addMessage(f"\nProcessing: {item_id}")
                
                for asset_name, asset_info in assets.items():
                    href = asset_info.get('href', '')
                    asset_type = asset_info.get('type', '')
                    
                    if href.startswith('s3://') and 'image' in asset_type:
                        # Parse S3 URL
                        bucket = href.replace('s3://', '').split('/')[0]
                        key = '/'.join(href.replace('s3://', '').split('/')[1:])
                        
                        messages.addMessage(f"  Asset: {asset_name}")
                        messages.addMessage(f"  S3: {href}")
                        
                        # Build S3 REST API URL
                        s3_url = f"https://{bucket}.s3.us-west-2.amazonaws.com/{key}"
                        
                        # Sign the request
                        messages.addMessage("  Signing request...")
                        signed_headers = self.sign_request_v4(
                            method="GET",
                            url=s3_url,
                            headers={},
                            payload="",
                            access_key=access_key,
                            secret_key=secret_key,
                            session_token=session_token,
                            region="us-west-2",
                            service="s3"
                        )
                        
                        # Download with signed request
                        messages.addMessage("  Downloading...")
                        response = requests.get(s3_url, headers=signed_headers, stream=True)
                        
                        if response.status_code == 200:
                            # Save to temp file
                            local_file = os.path.join(temp_dir, os.path.basename(key))
                            with open(local_file, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                                    
                            file_size = os.path.getsize(local_file) / (1024 * 1024)  # MB
                            messages.addMessage(f"  [+] Downloaded: {file_size:.1f} MB")
                            downloaded_files.append(local_file)
                            
                            # Add to map
                            if add_to_map:
                                try:
                                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                                    active_map = aprx.activeMap
                                    active_map.addDataFromPath(local_file)
                                    messages.addMessage(f"  [+] Added to map!")
                                except Exception as e:
                                    messages.addMessage(f"  [-] Failed to add to map: {str(e)}")
                        else:
                            messages.addMessage(f"  [-] Download failed: {response.status_code}")
                            messages.addMessage(f"  Response: {response.text[:200]}")
            
            # Summary
            messages.addMessage(f"\n" + "="*50)
            messages.addMessage(f"Downloaded {len(downloaded_files)} files")
            messages.addMessage(f"Temp location: {temp_dir}")
            messages.addMessage("Files will remain until ArcGIS Pro is closed")
                    
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
