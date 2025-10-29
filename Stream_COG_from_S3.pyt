import arcpy
import os
import requests
import json
import subprocess
import sys

class Toolbox(object):
    def __init__(self):
        """Stream COG data from S3 with temporary credentials"""
        self.label = "Stream COG from S3"
        self.alias = "stream_cog_s3"
        self.tools = [InstallRasterio, StreamCOGFromS3]

class InstallRasterio(object):
    def __init__(self):
        self.label = "Install rasterio (for streaming)"
        self.description = "Installs rasterio package for COG streaming support"
        self.canRunInBackground = False

    def getParameterInfo(self):
        return []

    def execute(self, parameters, messages):
        messages.addMessage("=== Installing rasterio for COG streaming ===")
        
        python_exe = sys.executable
        
        try:
            import rasterio
            messages.addMessage(f"✓ rasterio already installed: {rasterio.__version__}")
            return
        except ImportError:
            messages.addMessage("Installing rasterio...")
        
        # Try conda first (recommended for rasterio)
        try:
            conda_exe = os.path.join(os.path.dirname(python_exe), "Scripts", "conda.exe")
            if not os.path.exists(conda_exe):
                conda_exe = os.path.join(os.path.dirname(os.path.dirname(python_exe)), "Scripts", "conda.exe")
            
            if os.path.exists(conda_exe):
                messages.addMessage("Installing via conda (recommended)...")
                result = subprocess.run(
                    [conda_exe, "install", "-y", "-c", "conda-forge", "rasterio", "boto3"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    messages.addMessage("✓ Successfully installed rasterio and boto3")
                else:
                    messages.addMessage("conda failed, trying pip...")
                    result = subprocess.run(
                        [python_exe, "-m", "pip", "install", "rasterio", "boto3"],
                        capture_output=True,
                        text=True
                    )
        except Exception as e:
            messages.addErrorMessage(f"Installation error: {str(e)}")
            
        return

class StreamCOGFromS3(object):
    def __init__(self):
        self.label = "Stream COG from S3"
        self.description = """Stream Cloud Optimized GeoTIFFs directly from S3 without downloading.
        
        Only downloads the parts of the image needed for display."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # Credentials
        params.append(arcpy.Parameter(
            displayName="Credential API URL",
            name="cred_api_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[0].value = "https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds"
        
        params.append(arcpy.Parameter(
            displayName="API Key",
            name="api_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[1].value = "BjIti74LmYBtcjvaZIej8xRLSmmN1GP3ZEJ"
        
        # S3 URL
        params.append(arcpy.Parameter(
            displayName="S3 URL (s3://bucket/key)",
            name="s3_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[2].value = "s3://nasa-disasters/drcs_activations_new/ALOS2/DPM/202302_Earthquake_Turkiye_EOS-RS_DPM_A2_Türkiye_Syria_Earthquake_v0.5_2023-02-08_day.tif"
        
        # Options
        params.append(arcpy.Parameter(
            displayName="Operation",
            name="operation",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[3].filter.type = "ValueList"
        params[3].filter.list = [
            "Add to Map (via VRT)",
            "Extract Current View",
            "Get Overview",
            "Full Download"
        ]
        params[3].value = "Add to Map (via VRT)"
        
        return params

    def execute(self, parameters, messages):
        cred_api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        s3_url = parameters[2].valueAsText
        operation = parameters[3].valueAsText
        
        messages.addMessage("=== Streaming COG from S3 ===")
        
        try:
            import rasterio
            from rasterio.session import AWSSession
            import boto3
            messages.addMessage("✓ rasterio available")
        except ImportError:
            messages.addErrorMessage("rasterio not installed! Run install tool first.")
            return
            
        try:
            # Get credentials
            headers = {"api-key": api_key}
            response = requests.get(cred_api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"Failed to get credentials: {response.status_code}")
                return
                
            creds = response.json()
            
            # Create boto3 session
            session = boto3.Session(
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'],
                region_name='us-west-2'
            )
            
            messages.addMessage("✓ Authenticated with temporary credentials")
            
            # Parse S3 URL
            bucket = s3_url.replace('s3://', '').split('/')[0]
            key = '/'.join(s3_url.replace('s3://', '').split('/')[1:])
            
            messages.addMessage(f"\nBucket: {bucket}")
            messages.addMessage(f"Key: {key}")
            
            if operation == "Add to Map (via VRT)":
                # Create a VRT that references the S3 file
                messages.addMessage("\nCreating Virtual Raster (VRT) for streaming...")
                
                # Build GDAL VRT that points to S3
                vrt_file = os.path.join(arcpy.env.scratchFolder, "stream_cog.vrt")
                
                # Use GDAL virtual file system with credentials
                aws_env = {
                    'AWS_ACCESS_KEY_ID': creds['AccessKeyId'],
                    'AWS_SECRET_ACCESS_KEY': creds['SecretAccessKey'],
                    'AWS_SESSION_TOKEN': creds['SessionToken'],
                    'AWS_REGION': 'us-west-2'
                }
                
                # Update environment
                for k, v in aws_env.items():
                    os.environ[k] = v
                
                # Build VRT using GDAL
                gdal_path = f"/vsis3/{bucket}/{key}"
                
                import subprocess
                result = subprocess.run([
                    "gdal_translate",
                    "-of", "VRT",
                    gdal_path,
                    vrt_file
                ], capture_output=True, text=True, env=os.environ)
                
                if os.path.exists(vrt_file):
                    messages.addMessage("✓ Created VRT for streaming")
                    messages.addMessage(f"VRT: {vrt_file}")
                    
                    # Add VRT to map
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    active_map = aprx.activeMap
                    active_map.addDataFromPath(vrt_file)
                    messages.addMessage("✓ Added to map - data streams on demand!")
                else:
                    messages.addMessage("VRT creation failed, trying direct rasterio...")
                    
            elif operation == "Extract Current View":
                # Stream only the current map extent
                messages.addMessage("\nExtracting current view extent...")
                
                with rasterio.env.Env(AWSSession(session)):
                    with rasterio.open(s3_url) as src:
                        messages.addMessage(f"COG dimensions: {src.width} x {src.height}")
                        messages.addMessage(f"Bands: {src.count}")
                        
                        # Get current map extent
                        aprx = arcpy.mp.ArcGISProject("CURRENT")
                        map_view = aprx.activeView
                        
                        if hasattr(map_view, 'camera'):
                            extent = map_view.camera.getExtent()
                            
                            # Convert extent to pixel window
                            window = rasterio.windows.from_bounds(
                                extent.XMin, extent.YMin, 
                                extent.XMax, extent.YMax,
                                src.transform
                            )
                            
                            # Read only the window
                            data = src.read(window=window)
                            
                            messages.addMessage(f"✓ Streamed window: {window.width} x {window.height} pixels")
                            
                            # Save extract
                            out_file = os.path.join(arcpy.env.scratchFolder, "view_extract.tif")
                            
                            # Write with same CRS and transform adjusted for window
                            with rasterio.open(
                                out_file, 'w',
                                driver='GTiff',
                                height=window.height,
                                width=window.width,
                                count=src.count,
                                dtype=data.dtype,
                                crs=src.crs,
                                transform=src.window_transform(window)
                            ) as dst:
                                dst.write(data)
                            
                            # Add to map
                            active_map = aprx.activeMap
                            active_map.addDataFromPath(out_file)
                            messages.addMessage("✓ Added view extract to map")
                        else:
                            messages.addMessage("No active map view")
                            
            elif operation == "Get Overview":
                # Stream lowest resolution overview
                messages.addMessage("\nGetting overview (fastest)...")
                
                with rasterio.env.Env(AWSSession(session)):
                    with rasterio.open(s3_url) as src:
                        # Use the smallest overview
                        overviews = src.overviews(1)
                        if overviews:
                            overview_level = overviews[-1]  # Smallest
                            messages.addMessage(f"Using overview level {overview_level}")
                            
                            # Read overview
                            data = src.read(
                                out_shape=(
                                    src.count,
                                    int(src.height / overview_level),
                                    int(src.width / overview_level)
                                )
                            )
                            
                            messages.addMessage(f"✓ Streamed overview: {data.shape[2]} x {data.shape[1]} pixels")
                            
                            # Save overview
                            out_file = os.path.join(arcpy.env.scratchFolder, "overview.tif")
                            
                            # Create transform for overview
                            transform = src.transform * rasterio.Affine.scale(overview_level)
                            
                            with rasterio.open(
                                out_file, 'w',
                                driver='GTiff',
                                height=data.shape[1],
                                width=data.shape[2],
                                count=src.count,
                                dtype=data.dtype,
                                crs=src.crs,
                                transform=transform
                            ) as dst:
                                dst.write(data)
                            
                            # Add to map
                            aprx = arcpy.mp.ArcGISProject("CURRENT")
                            active_map = aprx.activeMap
                            active_map.addDataFromPath(out_file)
                            messages.addMessage("✓ Added overview to map")
                        else:
                            messages.addMessage("No overviews available")
                            
            elif operation == "Full Download":
                # Traditional full download
                messages.addMessage("\nDownloading full file...")
                
                # Use boto3 for full download
                s3 = session.client('s3')
                out_file = os.path.join(arcpy.env.scratchFolder, os.path.basename(key))
                
                s3.download_file(bucket, key, out_file)
                
                file_size = os.path.getsize(out_file) / (1024 * 1024)
                messages.addMessage(f"✓ Downloaded: {file_size:.1f} MB")
                
                # Add to map
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                active_map = aprx.activeMap
                active_map.addDataFromPath(out_file)
                messages.addMessage("✓ Added to map")
                
            # Clean environment
            for k in aws_env.keys():
                if k in os.environ:
                    del os.environ[k]
                    
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
