import arcpy
import os
import requests
import json
import subprocess
import sys

class Toolbox(object):
    def __init__(self):
        """STAC Browser with boto3 for Temporary Credentials"""
        self.label = "STAC Browser with boto3"
        self.alias = "stac_boto3"
        self.tools = [InstallBoto3, BrowseSTACWithBoto3]

class InstallBoto3(object):
    """Install boto3 in ArcGIS Pro environment"""
    
    def __init__(self):
        self.label = "Step 1: Install boto3"
        self.description = "Installs boto3 package in ArcGIS Pro's Python environment"
        self.canRunInBackground = False

    def getParameterInfo(self):
        return []

    def execute(self, parameters, messages):
        messages.addMessage("=== Installing boto3 ===")
        
        # Get ArcGIS Pro's Python executable
        python_exe = sys.executable
        messages.addMessage(f"Python: {python_exe}")
        
        # Check if boto3 already installed
        try:
            import boto3
            messages.addMessage(f"✓ boto3 already installed: {boto3.__version__}")
            messages.addMessage("You can proceed to Step 2!")
            return
        except ImportError:
            messages.addMessage("boto3 not found, installing...")
        
        # Try pip install
        try:
            messages.addMessage("\nInstalling via pip...")
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "boto3"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                messages.addMessage("✓ Successfully installed boto3")
                # Test import
                try:
                    import boto3
                    messages.addMessage(f"✓ Verified: boto3 {boto3.__version__} is ready!")
                except:
                    messages.addMessage("⚠ Installed but can't import yet - restart ArcGIS Pro")
            else:
                messages.addErrorMessage("Failed to install via pip")
                messages.addMessage(result.stderr)
                
                # Try conda
                messages.addMessage("\nTrying conda instead...")
                conda_exe = os.path.join(os.path.dirname(python_exe), "Scripts", "conda.exe")
                if not os.path.exists(conda_exe):
                    conda_exe = os.path.join(os.path.dirname(os.path.dirname(python_exe)), "Scripts", "conda.exe")
                
                if os.path.exists(conda_exe):
                    result = subprocess.run(
                        [conda_exe, "install", "-y", "boto3"],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        messages.addMessage("✓ Successfully installed via conda")
                    else:
                        messages.addMessage("Failed with conda too")
                        messages.addMessage("\nManual installation required:")
                        messages.addMessage("1. Open ArcGIS Pro Python Command Prompt as Administrator")
                        messages.addMessage("2. Run: conda install boto3")
                else:
                    messages.addMessage("conda not found")
                    messages.addMessage("\nTry running ArcGIS Pro as Administrator")
                    
        except Exception as e:
            messages.addErrorMessage(f"Installation error: {str(e)}")
        
        return

class BrowseSTACWithBoto3(object):
    """Browse STAC and download using boto3 with temporary credentials"""
    
    def __init__(self):
        self.label = "Step 2: Browse STAC with boto3"
        self.description = """Browse STAC catalogs and download files using boto3.
        
        This properly handles AWS temporary credentials with session tokens."""
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
        param1.value = "BjIti74LmYBtcjvaZIej8xRLSmmN1GP3ZEJ"
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
        param3.value = "landsat-all-vars-daily"
        params.append(param3)
        
        param4 = arcpy.Parameter(
            displayName="Number of Items",
            name="limit",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        param4.value = 1
        params.append(param4)
        
        param5 = arcpy.Parameter(
            displayName="Add to Map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        param5.value = True
        params.append(param5)
        
        return params

    def execute(self, parameters, messages):
        cred_api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        stac_url = parameters[2].valueAsText
        collection = parameters[3].valueAsText
        limit = parameters[4].value
        add_to_map = parameters[5].value
        
        messages.addMessage("=== STAC Browser with boto3 ===")
        
        # Check if boto3 is installed
        try:
            import boto3
            from botocore.config import Config
            messages.addMessage("✓ boto3 is available")
        except ImportError:
            messages.addErrorMessage("boto3 not installed! Run Step 1 first.")
            return
        
        try:
            # Get temporary credentials
            messages.addMessage("\nFetching temporary credentials...")
            headers = {"api-key": api_key}
            response = requests.get(cred_api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"Failed to get credentials: {response.status_code}")
                messages.addMessage(f"Response: {response.text}")
                return
                
            creds = response.json()
            access_key = creds.get('AccessKeyId')
            secret_key = creds.get('SecretAccessKey') 
            session_token = creds.get('SessionToken')
            
            if not all([access_key, secret_key, session_token]):
                messages.addErrorMessage("Missing credential components")
                return
                
            messages.addMessage("✓ Retrieved credentials with session token")
            messages.addMessage(f"  Expires: {creds.get('Expiration', 'Unknown')}")
            
            # Create boto3 session with temporary credentials
            messages.addMessage("\nCreating boto3 session...")
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name='us-west-2'
            )
            
            # Create S3 client
            s3 = session.client('s3', config=Config(signature_version='s3v4'))
            messages.addMessage("✓ boto3 S3 client ready")
            
            # Query STAC
            messages.addMessage(f"\nQuerying STAC collection: {collection}")
            items_url = f"{stac_url}/collections/{collection}/items?limit={limit}"
            response = requests.get(items_url)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"STAC query failed: {response.status_code}")
                return
                
            data = response.json()
            features = data.get('features', [])
            messages.addMessage(f"Found {len(features)} items")
            
            # Create temp directory for downloads
            download_dir = os.path.join(arcpy.env.scratchFolder, "stac_downloads")
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            
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
                        messages.addMessage(f"  Bucket: {bucket}")
                        messages.addMessage(f"  Key: {key}")
                        
                        # Download using boto3
                        # Sanitize filename for Windows
                        filename = os.path.basename(key)
                        # Replace invalid Windows filename characters
                        invalid_chars = '<>:"|?*'
                        for char in invalid_chars:
                            filename = filename.replace(char, '_')
                        
                        local_file = os.path.join(download_dir, filename)
                        messages.addMessage(f"  Downloading with boto3...")
                        
                        try:
                            # Download file
                            s3.download_file(bucket, key, local_file)
                            
                            file_size = os.path.getsize(local_file) / (1024 * 1024)  # MB
                            messages.addMessage(f"  ✓ Downloaded: {file_size:.1f} MB")
                            downloaded_files.append(local_file)
                            
                            # Add to map
                            if add_to_map:
                                try:
                                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                                    active_map = aprx.activeMap
                                    active_map.addDataFromPath(local_file)
                                    messages.addMessage("  ✓ Added to map!")
                                except Exception as e:
                                    messages.addMessage(f"  ⚠ Failed to add to map: {str(e)}")
                                    
                        except Exception as e:
                            messages.addErrorMessage(f"  ✗ Download failed: {str(e)}")
                            
                            # Check specific error types
                            if "AccessDenied" in str(e):
                                messages.addMessage("  → Access denied. Your credentials may not have read permissions.")
                                messages.addMessage("    Check if the IAM role includes this bucket")
                            elif "NoSuchBucket" in str(e):
                                messages.addMessage("  → Bucket not found")
                            elif "NoSuchKey" in str(e):
                                messages.addMessage("  → File not found in bucket")
            
            # Summary
            messages.addMessage(f"\n{'='*60}")
            messages.addMessage(f"Successfully downloaded {len(downloaded_files)} files")
            if downloaded_files:
                messages.addMessage(f"Location: {download_dir}")
                messages.addMessage("\nNext steps:")
                messages.addMessage("- Files are now local and can be used offline")
                messages.addMessage("- They'll remain available after credentials expire")
                    
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
