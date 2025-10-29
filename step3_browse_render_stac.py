import arcpy
import os
import requests
import json
from datetime import datetime, timedelta

class BrowseAndRenderSTAC(object):
    """Step 3: Browse and Render STAC Items"""
    
    def __init__(self):
        self.label = "Step 3: Browse and Render STAC Items"
        self.description = """Browse STAC catalogs and add items to the map.
        
        This tool queries STAC APIs to find available data and adds them
        to your map using the ACS connection created in Step 2."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # STAC API selection
        param0 = arcpy.Parameter(
            displayName="STAC API URL",
            name="stac_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.filter.type = "ValueList"
        param0.filter.list = [
            "https://dev.openveda.cloud/api/stac",
            "https://openveda.cloud/api/stac",
            "https://earth.gov/ghgcenter/api/stac",
            "https://cmr.earthdata.nasa.gov/stac/POCLOUD",
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            "Custom URL"
        ]
        param0.value = "https://dev.openveda.cloud/api/stac"
        params.append(param0)
        
        # Custom STAC URL (if Custom selected)
        param1 = arcpy.Parameter(
            displayName="Custom STAC URL",
            name="custom_stac_url",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            enabled=False)
        params.append(param1)
        
        # Collection dropdown - populated dynamically
        param2 = arcpy.Parameter(
            displayName="Collection",
            name="collection",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        param2.filter.list = ["Select STAC API first..."]
        params.append(param2)
        
        # Date range filter
        param3 = arcpy.Parameter(
            displayName="Start Date (optional)",
            name="start_date",
            datatype="GPDate",
            parameterType="Optional",
            direction="Input")
        # Default to 30 days ago
        param3.value = datetime.now() - timedelta(days=30)
        params.append(param3)
        
        param4 = arcpy.Parameter(
            displayName="End Date (optional)",
            name="end_date",
            datatype="GPDate",
            parameterType="Optional",
            direction="Input")
        param4.value = datetime.now()
        params.append(param4)
        
        # Number of items
        param5 = arcpy.Parameter(
            displayName="Number of Items to Retrieve",
            name="limit",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        param5.value = 10
        params.append(param5)
        
        # Bounding box filter (optional)
        param6 = arcpy.Parameter(
            displayName="Filter by Current Map Extent",
            name="use_map_extent",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param6.value = False
        params.append(param6)
        
        # ACS Connection selection
        param7 = arcpy.Parameter(
            displayName="ACS Connection File",
            name="acs_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input")
        param7.filter.list = ["acs"]
        # Try to find ACS files in project folder
        try:
            project_folder = arcpy.mp.ArcGISProject("CURRENT").homeFolder
            acs_files = [f for f in os.listdir(project_folder) if f.endswith('.acs')]
            if acs_files:
                param7.value = os.path.join(project_folder, acs_files[0])
        except:
            pass
        params.append(param7)
        
        # Add to map option
        param8 = arcpy.Parameter(
            displayName="Add to Map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        param8.value = True
        params.append(param8)
        
        # Output table (optional)
        param9 = arcpy.Parameter(
            displayName="Output Table (optional)",
            name="output_table",
            datatype="DETable",
            parameterType="Optional",
            direction="Output")
        params.append(param9)
        
        return params

    def updateParameters(self, parameters):
        # Enable custom URL if "Custom URL" selected
        if parameters[0].value == "Custom URL":
            parameters[1].enabled = True
        else:
            parameters[1].enabled = False
            
        # Populate collections when STAC API changes
        if parameters[0].altered and not parameters[0].hasBeenValidated:
            stac_url = parameters[0].value
            if stac_url and stac_url != "Custom URL":
                self.populate_collections(parameters, stac_url)
        
        # Also populate if custom URL changes
        if parameters[1].altered and parameters[0].value == "Custom URL":
            custom_url = parameters[1].value
            if custom_url:
                self.populate_collections(parameters, custom_url)
    
    def populate_collections(self, parameters, stac_url):
        """Fetch and populate available collections from STAC API"""
        parameters[2].filter.list = ["Loading collections..."]
        
        try:
            # Fetch collections
            all_collections = []
            next_url = f"{stac_url}/collections?limit=50"
            page_count = 0
            
            while next_url and page_count < 10:  # Limit pages for performance
                response = requests.get(next_url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    collections = data.get('collections', [])
                    all_collections.extend(collections)
                    
                    # Look for next page
                    next_url = None
                    links = data.get('links', [])
                    for link in links:
                        if link.get('rel') == 'next':
                            next_url = link.get('href')
                            if next_url and not next_url.startswith('http'):
                                next_url = stac_url.rstrip('/') + '/' + next_url.lstrip('/')
                            break
                    page_count += 1
                else:
                    break
            
            # Create display list
            collection_list = []
            for coll in all_collections:
                coll_id = coll.get('id', '')
                title = coll.get('title', coll_id)
                
                # Look for keywords that might indicate disaster relevance
                description = coll.get('description', '').lower()
                keywords = coll.get('keywords', [])
                
                disaster_related = any(term in description or term in str(keywords).lower() 
                                     for term in ['disaster', 'flood', 'fire', 'hurricane', 
                                               'earthquake', 'landslide', 'drought', 'volcano'])
                
                # Format display
                if title and title != coll_id:
                    display = f"{coll_id} - {title[:60]}"
                else:
                    display = coll_id
                    
                # Add indicator for disaster-related collections
                if disaster_related:
                    display = f"[DISASTER] {display}"
                    
                collection_list.append(display)
            
            if collection_list:
                # Sort with disaster collections first
                disaster_cols = [c for c in collection_list if c.startswith("[DISASTER]")]
                other_cols = [c for c in collection_list if not c.startswith("[DISASTER]")]
                parameters[2].filter.list = sorted(disaster_cols) + sorted(other_cols)
                if disaster_cols:
                    parameters[2].value = disaster_cols[0]
                else:
                    parameters[2].value = collection_list[0]
            else:
                parameters[2].filter.list = ["No collections found"]
                
        except Exception as e:
            parameters[2].filter.list = [f"Error: {str(e)[:50]}"]

    def execute(self, parameters, messages):
        """Browse STAC and add items to map"""
        # Get parameters
        stac_url = parameters[0].valueAsText
        if stac_url == "Custom URL":
            stac_url = parameters[1].valueAsText
        collection_display = parameters[2].valueAsText
        start_date = parameters[3].value
        end_date = parameters[4].value
        limit = parameters[5].value
        use_extent = parameters[6].value
        acs_file = parameters[7].valueAsText
        add_to_map = parameters[8].value
        output_table = parameters[9].valueAsText
        
        messages.addMessage("=== Step 3: Browse and Render STAC Items ===")
        
        # Extract collection ID from display
        collection = collection_display.replace("[DISASTER] ", "").split(" - ")[0]
        
        # Extract bucket name from ACS file
        acs_name = os.path.basename(acs_file).replace('.acs', '')
        messages.addMessage(f"\nUsing ACS connection: {acs_name}")
        messages.addMessage(f"Collection: {collection}")
        
        try:
            # Build query parameters
            query_params = {"limit": limit}
            
            # Add date filter if provided
            if start_date or end_date:
                datetime_filter = []
                if start_date:
                    datetime_filter.append(start_date.strftime('%Y-%m-%dT%H:%M:%S') + 'Z')
                else:
                    datetime_filter.append('..')
                datetime_filter.append('/')
                if end_date:
                    datetime_filter.append(end_date.strftime('%Y-%m-%dT%H:%M:%S') + 'Z')
                else:
                    datetime_filter.append('..')
                query_params['datetime'] = ''.join(datetime_filter)
            
            # Add bbox filter if using map extent
            if use_extent:
                try:
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    map_view = aprx.activeView
                    if hasattr(map_view, 'camera'):
                        extent = map_view.camera.getExtent()
                        # Convert to WGS84 if needed
                        if extent.spatialReference.factoryCode != 4326:
                            extent = extent.projectAs(arcpy.SpatialReference(4326))
                        bbox = f"{extent.XMin},{extent.YMin},{extent.XMax},{extent.YMax}"
                        query_params['bbox'] = bbox
                        messages.addMessage(f"Using map extent: {bbox}")
                except:
                    messages.addMessage("Could not get map extent, proceeding without spatial filter")
            
            # Query STAC API
            items_url = f"{stac_url}/collections/{collection}/items"
            messages.addMessage(f"\nQuerying: {items_url}")
            
            response = requests.get(items_url, params=query_params, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"STAC query failed: {response.status_code}")
                messages.addMessage(response.text)
                return
            
            data = response.json()
            features = data.get('features', [])
            messages.addMessage(f"\nFound {len(features)} items")
            
            if not features:
                messages.addMessage("No items found for the specified criteria")
                return
            
            # Process items
            items_added = 0
            s3_paths = []
            
            for i, feature in enumerate(features):
                item_id = feature.get('id', f'item_{i}')
                properties = feature.get('properties', {})
                assets = feature.get('assets', {})
                
                # Show item info
                messages.addMessage(f"\n[{i+1}/{len(features)}] Item: {item_id}")
                if 'datetime' in properties:
                    messages.addMessage(f"  Date: {properties['datetime']}")
                
                # Look for COG assets
                cog_assets = []
                for asset_name, asset_info in assets.items():
                    href = asset_info.get('href', '')
                    asset_type = asset_info.get('type', '')
                    
                    # Check if it's a COG or raster
                    if ('image/tiff' in asset_type or 
                        'cloud-optimized' in str(asset_info) or 
                        href.endswith(('.tif', '.tiff', '.TIF', '.TIFF'))):
                        
                        # Store both S3 and HTTP URLs
                        http_href = href
                        s3_path = None
                        
                        # Convert URLs to S3 paths if possible
                        if href.startswith('s3://'):
                            s3_path = href
                        elif 'amazonaws.com' in href:
                            # Try to extract S3 path from HTTP URL
                            parts = href.split('/')
                            if '.s3.' in href or '.s3-' in href:
                                bucket_part = parts[2].split('.')[0]
                                key_part = '/'.join(parts[3:])
                                s3_path = f"s3://{bucket_part}/{key_part}"
                        
                        if s3_path:
                            cog_assets.append((asset_name, s3_path, asset_info, http_href))
                        elif href.startswith('http'):
                            # Even without S3, we might be able to use HTTP
                            cog_assets.append((asset_name, None, asset_info, http_href))
                
                # Add COG assets to map
                if cog_assets and add_to_map:
                    for asset_name, s3_path, asset_info, http_href in cog_assets:
                        if s3_path:
                            # Try S3 access first
                            # Extract bucket and key from S3 path
                            bucket = s3_path.replace('s3://', '').split('/')[0]
                            key = '/'.join(s3_path.replace('s3://', '').split('/')[1:])
                            
                            # Build full path with ACS connection
                            key_windows = key.replace('/', '\\')
                            full_path = acs_file + "\\" + key_windows
                            
                            messages.addMessage(f"  Asset: {asset_name}")
                            messages.addMessage(f"  S3: {s3_path}")
                            messages.addMessage(f"  ACS path: {full_path}")
                            
                            if add_to_map:
                                try:
                                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                                    active_map = aprx.activeMap
                                    
                                    # Create a unique layer name
                                    layer_name = f"{collection}_{item_id}_{asset_name}"[:100]
                                    
                                    # Add to map
                                    active_map.addDataFromPath(full_path)
                                    messages.addMessage(f"  [+] Added to map: {layer_name}")
                                    items_added += 1
                                    
                                except Exception as e:
                                    messages.addMessage(f"  [-] S3 access failed: {str(e)}")
                                    
                                    # Try HTTP URL as fallback
                                    if http_href and http_href.startswith('http'):
                                        messages.addMessage(f"  Trying HTTP access: {http_href}")
                                        try:
                                            active_map.addDataFromPath(http_href)
                                            messages.addMessage(f"  [+] Added via HTTP!")
                                            items_added += 1
                                        except Exception as e2:
                                            messages.addMessage(f"  [-] HTTP also failed: {str(e2)}")
                                            messages.addMessage("  LIKELY ISSUE: Your credentials are for upload-only")
                                            messages.addMessage("  The API 'get-s3-upload-creds' provides WRITE access to nasa-disasters")
                                            messages.addMessage("  But not READ access to veda-data-store-dev")
                        
                        elif http_href and http_href.startswith('http'):
                            # No S3 path, try HTTP directly
                            messages.addMessage(f"  Asset: {asset_name}")
                            messages.addMessage(f"  HTTP: {http_href}")
                            
                            try:
                                aprx = arcpy.mp.ArcGISProject("CURRENT")
                                active_map = aprx.activeMap
                                active_map.addDataFromPath(http_href)
                                messages.addMessage(f"  [+] Added via HTTP!")
                                items_added += 1
                            except Exception as e:
                                messages.addMessage(f"  [-] Failed: {str(e)}")

                        
                        s3_paths.append({
                            'item_id': item_id,
                            'asset': asset_name,
                            's3_path': s3_path,
                            'full_path': full_path,
                            'datetime': properties.get('datetime', '')
                        })
            
            # Create output table if requested
            if output_table and s3_paths:
                messages.addMessage(f"\nCreating output table...")
                
                # Create table
                arcpy.management.CreateTable(os.path.dirname(output_table), 
                                           os.path.basename(output_table))
                
                # Add fields
                arcpy.management.AddField(output_table, "item_id", "TEXT", field_length=100)
                arcpy.management.AddField(output_table, "asset_name", "TEXT", field_length=50)
                arcpy.management.AddField(output_table, "s3_path", "TEXT", field_length=500)
                arcpy.management.AddField(output_table, "full_path", "TEXT", field_length=500)
                arcpy.management.AddField(output_table, "datetime", "TEXT", field_length=30)
                
                # Insert rows
                with arcpy.da.InsertCursor(output_table, 
                    ["item_id", "asset_name", "s3_path", "full_path", "datetime"]) as cursor:
                    for item in s3_paths:
                        cursor.insertRow([
                            item['item_id'],
                            item['asset'],
                            item['s3_path'],
                            item['full_path'],
                            item['datetime']
                        ])
                
                messages.addMessage(f"Created table with {len(s3_paths)} records")
            
            # Summary
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"Browsed {len(features)} STAC items")
            if add_to_map:
                messages.addMessage(f"Added {items_added} rasters to map")
            messages.addMessage("\nNote: Some items may take time to render if they're large")
            
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
