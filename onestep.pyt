import arcpy
import os
import requests
import json
from datetime import datetime

class Toolbox(object):
    def __init__(self):
        """Landsat Data from NASA Disasters"""
        self.label = "Landsat NASA Disasters"
        self.alias = "landsat_disasters"
        self.tools = [GetLandsatData]

class GetLandsatData(object):
    def __init__(self):
        self.label = "Get Landsat Data from NASA Disasters"
        self.description = """Download Landsat data from nasa-disasters bucket via STAC API."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # API Key
        param0 = arcpy.Parameter(
            displayName="API Key",
            name="api_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        params.append(param0)
        
        # Number of items
        param1 = arcpy.Parameter(
            displayName="Number of Items",
            name="limit",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        param1.value = 1
        params.append(param1)
        
        # Add to map
        param2 = arcpy.Parameter(
            displayName="Add to Map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        param2.value = True
        params.append(param2)
        
        return params

    def execute(self, parameters, messages):
        api_key = parameters[0].valueAsText
        limit = parameters[1].value
        add_to_map = parameters[2].value
        
        # Fixed values
        API_URL = "https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds"
        STAC_URL = "https://dev.openveda.cloud/api/stac"
        COLLECTION = "landsat-all-vars-daily"
        
        messages.addMessage("=== Getting Landsat Data from NASA Disasters ===")
        
        # Check boto3
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            messages.addErrorMessage("boto3 not installed! Use ArcGIS Pro Package Manager to install.")
            return
        
        try:
            # Step 1: Get credentials
            messages.addMessage("\nStep 1: Getting credentials...")
            headers = {"api-key": api_key}
            response = requests.get(API_URL, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"API error: {response.status_code}")
                return
                
            creds = response.json()
            messages.addMessage("✓ Got credentials")
            
            # Step 2: Query STAC for landsat data
            messages.addMessage(f"\nStep 2: Querying STAC for Landsat data...")
            items_url = f"{STAC_URL}/collections/{COLLECTION}/items?limit={limit}"
            messages.addMessage(f"URL: {items_url}")
            
            response = requests.get(items_url)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"STAC query failed: {response.status_code}")
                return
                
            data = response.json()
            features = data.get('features', [])
            messages.addMessage(f"Found {len(features)} Landsat items")
            
            if not features:
                messages.addMessage("No items found in collection")
                return
            
            # Step 3: Create S3 client
            messages.addMessage("\nStep 3: Creating S3 client...")
            session = boto3.Session(
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'],
                region_name='us-west-2'
            )
            s3 = session.client('s3')
            messages.addMessage("✓ S3 client ready")
            
            # Step 4: Process items
            messages.addMessage("\nStep 4: Processing Landsat items...")
            output_dir = os.path.join(arcpy.env.scratchFolder, f"Landsat_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            downloaded = []
            
            for i, feature in enumerate(features):
                item_id = feature.get('id', f'item_{i}')
                messages.addMessage(f"\n[{i+1}/{len(features)}] Item: {item_id}")
                
                # Show item date if available
                props = feature.get('properties', {})
                if 'datetime' in props:
                    messages.addMessage(f"  Date: {props['datetime']}")
                
                # Look through assets
                assets = feature.get('assets', {})
                asset_count = 0
                
                for asset_name, asset_info in assets.items():
                    href = asset_info.get('href', '')
                    
                    # Only process S3 URLs in nasa-disasters bucket
                    if href.startswith('s3://nasa-disasters/'):
                        asset_count += 1
                        
                        # Parse S3 URL
                        bucket = href.replace('s3://', '').split('/')[0]
                        key = '/'.join(href.replace('s3://', '').split('/')[1:])
                        
                        messages.addMessage(f"\n  Asset: {asset_name}")
                        messages.addMessage(f"  S3: {href}")
                        
                        # Create local filename
                        local_file = os.path.join(output_dir, f"{item_id}_{asset_name}.tif")
                        
                        try:
                            # Download
                            s3.download_file(bucket, key, local_file)
                            file_size = os.path.getsize(local_file) / (1024 * 1024)
                            messages.addMessage(f"  ✓ Downloaded: {file_size:.1f} MB")
                            downloaded.append(local_file)
                            
                            # Add first asset to map
                            if add_to_map and asset_count == 1:  # Only add first asset per item
                                try:
                                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                                    active_map = aprx.activeMap
                                    active_map.addDataFromPath(local_file)
                                    messages.addMessage("  ✓ Added to map")
                                except Exception as e:
                                    messages.addMessage(f"  Could not add to map: {str(e)}")
                                    
                        except Exception as e:
                            messages.addErrorMessage(f"  ✗ Download failed: {str(e)}")
                            if "403" in str(e):
                                messages.addMessage("  Access denied - check if file exists in bucket")
                
                if asset_count == 0:
                    messages.addMessage("  No assets found in nasa-disasters bucket")
            
            # Summary
            messages.addMessage(f"\n{'='*60}")
            messages.addMessage(f"Downloaded {len(downloaded)} files")
            if downloaded:
                messages.addMessage(f"Location: {output_dir}")
            else:
                messages.addMessage("\nNo files were downloaded. Possible reasons:")
                messages.addMessage("- The landsat collection might not have data in nasa-disasters bucket")
                messages.addMessage("- Files might be in a different bucket")
                messages.addMessage("- Check the STAC response to see actual asset URLs")
                
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
