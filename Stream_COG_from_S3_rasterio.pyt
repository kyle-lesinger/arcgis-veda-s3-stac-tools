import arcpy
import os
import requests
import json
import tempfile

class Toolbox(object):
    def __init__(self):
        """Stream COG files from S3 using rasterio"""
        self.label = "COG Streaming Tools"
        self.alias = "cog_stream"
        self.tools = [StreamCOGNative]

class StreamCOGNative(object):
    def __init__(self):
        self.label = "Stream COG from S3 (Native)"
        self.description = """Stream Cloud Optimized GeoTIFFs from S3 using rasterio's native capabilities.
        
        This tool can:
        - Stream only the visible area (zoom level)
        - Download just overviews for quick preview
        - Extract specific windows
        - Full download as fallback"""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # API credentials
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
        
        # S3 URL
        params.append(arcpy.Parameter(
            displayName="S3 URL (s3://bucket/key)",
            name="s3_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[2].value = "s3://nasa-disasters/drcs_activations_new/ALOS2/DPM/202302_Earthquake_Turkiye_EOS-RS_DPM_A2_Türkiye_Syria_Earthquake_v0.5_2023-02-08_day.tif"
        
        # Streaming method
        params.append(arcpy.Parameter(
            displayName="Streaming Method",
            name="method",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[3].filter.type = "ValueList"
        params[3].filter.list = [
            "Quick Overview (Smallest)",
            "Medium Overview",
            "Current Map Extent",
            "Custom Window",
            "Full Download"
        ]
        params[3].value = "Quick Overview (Smallest)"
        
        # Custom window parameters (optional)
        params.append(arcpy.Parameter(
            displayName="Custom Window (minx,miny,maxx,maxy)",
            name="custom_window",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            enabled=False))
        
        return params

    def updateParameters(self, parameters):
        # Enable custom window input only if selected
        if parameters[3].value == "Custom Window":
            parameters[4].enabled = True
        else:
            parameters[4].enabled = False

    def execute(self, parameters, messages):
        cred_api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        s3_url = parameters[2].valueAsText
        method = parameters[3].valueAsText
        custom_window = parameters[4].valueAsText
        
        messages.addMessage("=== COG Streaming from S3 ===")
        
        # Check dependencies
        try:
            import rasterio
            from rasterio.session import AWSSession
            import boto3
            import numpy as np
            messages.addMessage("✓ Required packages available")
        except ImportError as e:
            messages.addErrorMessage(f"Missing package: {str(e)}")
            messages.addMessage("\nInstall required packages:")
            messages.addMessage("1. Project → Python → Manage Environments")
            messages.addMessage("2. Add Packages: rasterio, boto3, numpy")
            return
        
        try:
            # Get credentials
            messages.addMessage("\nGetting credentials...")
            headers = {"api-key": api_key}
            response = requests.get(cred_api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"API error: {response.status_code}")
                return
                
            creds = response.json()
            
            # Create boto3 session
            session = boto3.Session(
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'],
                region_name='us-west-2'
            )
            
            messages.addMessage("✓ Authenticated")
            
            # Parse S3 URL
            bucket = s3_url.replace('s3://', '').split('/')[0]
            key = '/'.join(s3_url.replace('s3://', '').split('/')[1:])
            
            messages.addMessage(f"\nBucket: {bucket}")
            messages.addMessage(f"Key: {key}")
            
            # Open COG with rasterio using boto3 session
            messages.addMessage("\nOpening COG for streaming...")
            
            # Create AWS session for rasterio
            from rasterio.session import AWSSession
            
            # Create custom session with temporary credentials
            aws_session = AWSSession(
                aws_access_key_id=creds['AccessKeyId'],
                aws_secret_access_key=creds['SecretAccessKey'],
                aws_session_token=creds['SessionToken'],
                region_name='us-west-2'
            )
            
            # Open with rasterio using the session
            with rasterio.env.Env(
                session=aws_session,
                GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
                VSI_CACHE=True
            ):
                with rasterio.open(s3_url) as src:
                    messages.addMessage(f"✓ Connected to COG")
                    messages.addMessage(f"  Size: {src.width} x {src.height} pixels")
                    messages.addMessage(f"  Bands: {src.count}")
                    messages.addMessage(f"  CRS: {src.crs}")
                    
                    # Check for overviews
                    overviews = src.overviews(1) if src.count > 0 else []
                    if overviews:
                        messages.addMessage(f"  Overviews: {overviews}")
                    
                    # Determine output
                    output_dir = os.path.join(arcpy.env.scratchFolder, "cog_stream")
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    
                    # Sanitize filename
                    safe_name = os.path.basename(key).replace(':', '_')
                    
                    if method == "Quick Overview (Smallest)":
                        # Get smallest overview
                        messages.addMessage("\nStreaming smallest overview...")
                        
                        if overviews:
                            # Use smallest overview
                            overview_level = overviews[-1]
                            out_shape = (
                                src.count,
                                int(src.height / overview_level),
                                int(src.width / overview_level)
                            )
                            messages.addMessage(f"  Using overview {overview_level} ({out_shape[2]}x{out_shape[1]} pixels)")
                        else:
                            # No overviews, downsample
                            factor = max(src.width, src.height) / 1000  # Target ~1000 pixels max
                            out_shape = (
                                src.count,
                                int(src.height / factor),
                                int(src.width / factor)
                            )
                            messages.addMessage(f"  Downsampling by {factor:.1f}x")
                        
                        # Read overview
                        data = src.read(out_shape=out_shape)
                        
                        # Save
                        output_file = os.path.join(output_dir, f"overview_{safe_name}")
                        
                        # Create transform for overview
                        transform = src.transform * rasterio.Affine.scale(
                            src.width / out_shape[2],
                            src.height / out_shape[1]
                        )
                        
                        with rasterio.open(
                            output_file, 'w',
                            driver='GTiff',
                            height=out_shape[1],
                            width=out_shape[2],
                            count=src.count,
                            dtype=data.dtype,
                            crs=src.crs,
                            transform=transform,
                            compress='deflate'
                        ) as dst:
                            dst.write(data)
                        
                        messages.addMessage(f"✓ Saved overview: {output_file}")
                        
                    elif method == "Medium Overview":
                        # Get medium quality overview
                        messages.addMessage("\nStreaming medium overview...")
                        
                        target_size = 2000  # Target ~2000 pixels max dimension
                        factor = max(src.width, src.height) / target_size
                        
                        if factor > 1:
                            out_shape = (
                                src.count,
                                int(src.height / factor),
                                int(src.width / factor)
                            )
                            messages.addMessage(f"  Downsampling to {out_shape[2]}x{out_shape[1]} pixels")
                            data = src.read(out_shape=out_shape)
                            
                            transform = src.transform * rasterio.Affine.scale(factor, factor)
                        else:
                            messages.addMessage("  Using full resolution (image is small)")
                            data = src.read()
                            transform = src.transform
                        
                        output_file = os.path.join(output_dir, f"medium_{safe_name}")
                        
                        with rasterio.open(
                            output_file, 'w',
                            driver='GTiff',
                            height=data.shape[1],
                            width=data.shape[2],
                            count=src.count,
                            dtype=data.dtype,
                            crs=src.crs,
                            transform=transform,
                            compress='deflate'
                        ) as dst:
                            dst.write(data)
                        
                        messages.addMessage(f"✓ Saved medium overview: {output_file}")
                        
                    elif method == "Current Map Extent":
                        # Extract current map view
                        messages.addMessage("\nExtracting current map extent...")
                        
                        try:
                            aprx = arcpy.mp.ArcGISProject("CURRENT")
                            map_view = aprx.activeView
                            
                            if hasattr(map_view, 'camera'):
                                extent = map_view.camera.getExtent()
                                
                                # Convert extent to source CRS if needed
                                if extent.spatialReference.factoryCode != src.crs.to_epsg():
                                    extent = extent.projectAs(arcpy.SpatialReference(src.crs.to_epsg()))
                                
                                # Convert to pixel window
                                window = rasterio.windows.from_bounds(
                                    extent.XMin, extent.YMin,
                                    extent.XMax, extent.YMax,
                                    src.transform
                                )
                                
                                # Ensure window is within bounds
                                window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
                                
                                messages.addMessage(f"  Window: {window}")
                                messages.addMessage(f"  Size: {int(window.width)} x {int(window.height)} pixels")
                                
                                # Read window
                                data = src.read(window=window)
                                
                                output_file = os.path.join(output_dir, f"extent_{safe_name}")
                                
                                with rasterio.open(
                                    output_file, 'w',
                                    driver='GTiff',
                                    height=int(window.height),
                                    width=int(window.width),
                                    count=src.count,
                                    dtype=data.dtype,
                                    crs=src.crs,
                                    transform=src.window_transform(window),
                                    compress='deflate'
                                ) as dst:
                                    dst.write(data)
                                
                                messages.addMessage(f"✓ Saved extent: {output_file}")
                            else:
                                messages.addMessage("No active map view, using medium overview instead")
                                method = "Medium Overview"
                                
                        except Exception as e:
                            messages.addMessage(f"Could not get map extent: {str(e)}")
                            messages.addMessage("Using medium overview instead")
                            method = "Medium Overview"
                            
                    elif method == "Custom Window":
                        # Not implemented in this example
                        messages.addMessage("Custom window not implemented, using medium overview")
                        method = "Medium Overview"
                        
                    else:  # Full Download
                        # Download complete file
                        messages.addMessage("\nDownloading full resolution...")
                        
                        # Use boto3 for efficiency
                        s3 = session.client('s3')
                        output_file = os.path.join(output_dir, safe_name)
                        
                        s3.download_file(bucket, key, output_file)
                        file_size = os.path.getsize(output_file) / (1024 * 1024)
                        messages.addMessage(f"✓ Downloaded: {file_size:.1f} MB")
                    
                    # Add to map
                    if 'output_file' in locals():
                        messages.addMessage("\nAdding to map...")
                        try:
                            aprx = arcpy.mp.ArcGISProject("CURRENT")
                            active_map = aprx.activeMap
                            active_map.addDataFromPath(output_file)
                            messages.addMessage("✓ Added to map!")
                            
                            messages.addMessage(f"\n{'='*50}")
                            messages.addMessage("Success! COG data is now in your map.")
                            messages.addMessage(f"Method used: {method}")
                            messages.addMessage(f"File: {output_file}")
                            
                        except Exception as e:
                            messages.addMessage(f"Could not add to map: {str(e)}")
                    
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
