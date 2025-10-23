import arcpy
import os
import configparser
import requests
import json

class Toolbox(object):
    def __init__(self):
        """VEDA S3 STAC Tools - Access NASA VEDA STAC data through S3"""
        self.label = "VEDA S3 STAC Tools"
        self.alias = "veda_s3_stac"
        # Tools ordered by typical workflow
        self.tools = [
            Step1_CreateVEDAConnection,
            Step2_BrowseSTACCollection, 
            Step3_AddS3ToMap,
            Alternative_DownloadSTACItem
        ]

class Step1_CreateVEDAConnection(object):
    def __init__(self):
        self.label = "Step 1: Create VEDA S3 Connection"
        self.description = """Creates AWS S3 connection files (.acs) for accessing VEDA data.
        
        This tool reads your AWS credentials from ~/.aws/credentials and creates 
        ArcGIS Cloud Storage connection files that allow you to access S3 data
        directly without downloading.
        
        Prerequisites:
        - AWS credentials configured in C:\\Users\\[username]\\.aws\\credentials
        - Valid AWS profile with access to VEDA buckets"""
        self.canRunInBackground = False

    def getParameterInfo(self):
        # Environment selection
        param0 = arcpy.Parameter(
            displayName="VEDA Environment",
            name="environment",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.filter.type = "ValueList"
        param0.filter.list = [
            "All Environments (Recommended)",
            "Production (veda-data-store)", 
            "Development (veda-data-store-dev)", 
            "Staging (veda-data-store-staging)"
        ]
        param0.value = "All Environments (Recommended)"
        
        # AWS Profile - defaults to common VEDA profile names
        param1 = arcpy.Parameter(
            displayName="AWS Profile Name (from ~/.aws/credentials)",
            name="profile_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.value = "uah-veda"  # Common VEDA profile name
        
        # Connection name prefix
        param2 = arcpy.Parameter(
            displayName="Connection Name Prefix",
            name="connection_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.value = "veda"
        
        # Output folder - defaults to project folder
        param3 = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        param3.value = arcpy.mp.ArcGISProject("CURRENT").homeFolder
        
        return [param0, param1, param2, param3]

    def execute(self, parameters, messages):
        """Create ACS connection files for selected VEDA environments"""
        env = parameters[0].valueAsText
        profile = parameters[1].valueAsText
        conn_name = parameters[2].valueAsText
        output_folder = parameters[3].valueAsText
        
        messages.addMessage("=== Creating VEDA S3 Connections ===")
        
        # Determine which buckets to create based on selection
        if env == "All Environments (Recommended)":
            # Create connections for all three environments
            buckets = [
                ("veda-data-store", f"{conn_name}-prod"),
                ("veda-data-store-dev", f"{conn_name}-dev"),
                ("veda-data-store-staging", f"{conn_name}-staging")
            ]
            messages.addMessage("Creating connections for all VEDA environments...")
        else:
            # Single bucket based on selection
            bucket_map = {
                "Production (veda-data-store)": ("veda-data-store", f"{conn_name}-prod"),
                "Development (veda-data-store-dev)": ("veda-data-store-dev", f"{conn_name}-dev"),
                "Staging (veda-data-store-staging)": ("veda-data-store-staging", f"{conn_name}-staging")
            }
            buckets = [bucket_map[env]]
        
        # Read AWS credentials from Windows location
        creds_path = os.path.join(os.path.expanduser("~"), ".aws", "credentials")
        if not os.path.exists(creds_path):
            messages.addErrorMessage(f"AWS credentials file not found: {creds_path}")
            messages.addMessage("\nTo fix this:")
            messages.addMessage("1. Create the folder: C:\\Users\\[username]\\.aws")
            messages.addMessage("2. Create a file named 'credentials' (no extension)")
            messages.addMessage("3. Add your AWS credentials in this format:")
            messages.addMessage("[profile-name]")
            messages.addMessage("aws_access_key_id = YOUR_ACCESS_KEY")
            messages.addMessage("aws_secret_access_key = YOUR_SECRET_KEY")
            return
        
        # Parse credentials file
        creds = configparser.ConfigParser()
        creds.read(creds_path)
        
        # Check if requested profile exists
        if profile not in creds:
            messages.addErrorMessage(f"Profile '{profile}' not found in credentials file")
            messages.addMessage(f"\nAvailable profiles: {', '.join(creds.sections())}")
            messages.addMessage("\nMake sure your profile name matches exactly")
            return
        
        # Create ACS file for each bucket
        messages.addMessage(f"\nUsing AWS profile: {profile}")
        created_count = 0
        
        for bucket, name in buckets:
            try:
                # Create the cloud storage connection
                arcpy.management.CreateCloudStorageConnectionFile(
                    output_folder,
                    name,
                    "AMAZON",
                    bucket,
                    creds[profile]['aws_access_key_id'],
                    creds[profile]['aws_secret_access_key'],
                    "us-west-2"  # VEDA buckets are in us-west-2
                )
                
                acs_path = os.path.join(output_folder, f"{name}.acs")
                messages.addMessage(f"\n✓ Created: {name}.acs")
                messages.addMessage(f"  Bucket: {bucket}")
                messages.addMessage(f"  Path: {acs_path}")
                created_count += 1
                
            except Exception as e:
                messages.addErrorMessage(f"\n✗ Failed for {bucket}: {str(e)}")
        
        # Summary
        messages.addMessage(f"\n{'='*50}")
        messages.addMessage(f"Successfully created {created_count} connection(s)")
        messages.addMessage("\nNext step: Use 'Step 2: Browse STAC Collection' to find data")
        
        return

class Step2_BrowseSTACCollection(object):
    def __init__(self):
        self.label = "Step 2: Browse STAC Collection"
        self.description = """Browse VEDA STAC catalogs to find available data.
        
        This tool queries VEDA's STAC API to list available collections and items,
        creating a table of S3 paths that can be used in Step 3.
        
        STAC APIs:
        - Production: https://openveda.cloud/api/stac
        - Development: https://dev.openveda.cloud/api/stac"""
        self.canRunInBackground = False

    def getParameterInfo(self):
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
            "https://openveda.cloud/api/stac"
        ]
        param0.value = "https://dev.openveda.cloud/api/stac"
        
        # Collection dropdown - populated dynamically
        param1 = arcpy.Parameter(
            displayName="Collection (select STAC API first)",
            name="collection",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.filter.type = "ValueList"
        param1.filter.list = ["Select STAC API first..."]
        
        # Number of items to retrieve
        param2 = arcpy.Parameter(
            displayName="Number of Items to Retrieve",
            name="limit",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        param2.value = 10
        
        # Output table to store results
        param3 = arcpy.Parameter(
            displayName="Output Table (stores S3 paths)",
            name="output_table",
            datatype="DETable",
            parameterType="Required",
            direction="Output")
        
        return [param0, param1, param2, param3]

    def updateParameters(self, parameters):
        """Dynamically populate collections when STAC API is selected"""
        # When STAC URL changes, fetch all available collections
        if parameters[0].altered and not parameters[0].hasBeenValidated:
            stac_url = parameters[0].value
            if stac_url:
                parameters[1].filter.list = ["Loading collections..."]
                
                try:
                    # Fetch all collections with pagination support
                    all_collections = []
                    next_url = f"{stac_url}/collections?limit=50"
                    page_count = 0
                    
                    # Paginate through all collections (max 20 pages for safety)
                    while next_url and page_count < 20:
                        response = requests.get(next_url, timeout=10)
                        
                        if response.status_code == 200:
                            data = response.json()
                            collections = data.get('collections', [])
                            all_collections.extend(collections)
                            
                            # Check for next page link
                            next_url = None
                            links = data.get('links', [])
                            for link in links:
                                if link.get('rel') == 'next':
                                    next_url = link.get('href')
                                    # Ensure full URL
                                    if next_url and not next_url.startswith('http'):
                                        next_url = stac_url.rstrip('/') + '/' + next_url.lstrip('/')
                                    break
                            
                            page_count += 1
                        else:
                            break
                    
                    # Create user-friendly collection list
                    collection_list = []
                    for coll in all_collections:
                        coll_id = coll.get('id', '')
                        title = coll.get('title', coll_id)
                        
                        # Include title if different from ID
                        if title and title != coll_id:
                            display = f"{coll_id} - {title[:60]}"  # Limit title length
                        else:
                            display = coll_id
                            
                        collection_list.append(display)
                    
                    if collection_list:
                        parameters[1].filter.list = sorted(collection_list)
                        parameters[1].value = collection_list[0]
                    else:
                        parameters[1].filter.list = ["No collections found"]
                        
                except Exception as e:
                    parameters[1].filter.list = [f"Error loading: {str(e)[:30]}..."]
                    
        return

    def execute(self, parameters, messages):
        """Query STAC collection and create table of available S3 paths"""
        stac_url = parameters[0].valueAsText
        collection_value = parameters[1].valueAsText
        limit = parameters[2].value
        output_table = parameters[3].valueAsText
        
        messages.addMessage("=== Browsing STAC Collection ===")
        
        # Extract collection ID from display value
        collection = collection_value.split(" - ")[0]
        
        try:
            # Query STAC for items in the collection
            items_url = f"{stac_url}/collections/{collection}/items?limit={limit}"
            messages.addMessage(f"\nQuerying collection: {collection}")
            messages.addMessage(f"API URL: {items_url}")
            
            response = requests.get(items_url)
            if response.status_code != 200:
                messages.addErrorMessage(f"STAC query failed: HTTP {response.status_code}")
                return
            
            items = response.json()
            total_items = items.get('numberMatched', len(items.get('features', [])))
            messages.addMessage(f"\nTotal items in collection: {total_items}")
            messages.addMessage(f"Retrieving first {limit} items...")
            
            # Create output table to store results
            messages.addMessage("\nCreating output table...")
            arcpy.management.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))
            
            # Add fields to store STAC information
            fields = [
                ("item_id", "TEXT", 100, "STAC Item ID"),
                ("datetime", "TEXT", 30, "Acquisition Date/Time"),
                ("s3_href", "TEXT", 500, "S3 URL"),
                ("asset_type", "TEXT", 50, "Asset Type (e.g., cog_default)"),
                ("collection", "TEXT", 100, "Collection Name"),
                ("bucket", "TEXT", 50, "S3 Bucket Name")
            ]
            
            for field_name, field_type, field_length, alias in fields:
                arcpy.management.AddField(output_table, field_name, field_type, 
                                        field_length=field_length, field_alias=alias)
            
            # Process items and extract S3 paths
            messages.addMessage("\nProcessing items...")
            cursor = arcpy.da.InsertCursor(output_table, [f[0] for f in fields])
            
            s3_count = 0
            item_count = 0
            
            for feature in items.get('features', []):
                item_id = feature['id']
                datetime_val = feature['properties'].get('datetime', '')
                item_count += 1
                
                # Look for S3 assets in each item
                for asset_name, asset in feature.get('assets', {}).items():
                    href = asset.get('href', '')
                    if 's3://' in href:
                        # Extract bucket name from S3 URL
                        bucket = href.split('/')[2] if href.startswith('s3://') else ''
                        
                        cursor.insertRow([item_id, datetime_val, href, asset_name, collection, bucket])
                        s3_count += 1
            
            del cursor
            
            # Summary
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"✓ Processed {item_count} items")
            messages.addMessage(f"✓ Found {s3_count} S3 assets")
            messages.addMessage(f"✓ Results saved to: {output_table}")
            
            if s3_count > 0:
                messages.addMessage("\nNext step: Use 'Step 3: Add S3 Raster to Map' to visualize the data")
                messages.addMessage("Select 'From Browse Results' and choose this table")
            else:
                messages.addWarningMessage("\nNo S3 assets found in this collection")
                messages.addMessage("Try a different collection or use the Download tool")
            
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
        
        return

class Step3_AddS3ToMap(object):
    def __init__(self):
        self.label = "Step 3: Add S3 Raster to Map"
        self.description = """Add S3 rasters to your map using ACS connections.
        
        This tool uses the browse results from Step 2 and the ACS connections
        from Step 1 to add rasters directly from S3 to your map.
        
        Options:
        - Stream directly from S3 (requires good internet)
        - Copy to local first (more stable, uses disk space)"""
        self.canRunInBackground = False

    def getParameterInfo(self):
        # Input method
        param0 = arcpy.Parameter(
            displayName="Input Method",
            name="input_method",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.filter.type = "ValueList"
        param0.filter.list = ["From Browse Results", "Manual S3 URL", "Manual ACS Path"]
        param0.value = "From Browse Results"
        
        # Browse results table from Step 2
        param1 = arcpy.Parameter(
            displayName="Browse Results Table (from Step 2)",
            name="browse_table",
            datatype="GPTableView",
            parameterType="Optional",
            direction="Input")
        
        # S3 Path dropdown - populated from browse results
        param2 = arcpy.Parameter(
            displayName="Select S3 Path",
            name="s3_path",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        
        # Manual path input (for manual methods)
        param3 = arcpy.Parameter(
            displayName="Manual Path",
            name="manual_path",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        param3.enabled = False
        
        # Copy locally option
        param4 = arcpy.Parameter(
            displayName="Copy to Local (recommended for stability)",
            name="copy_local",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")
        param4.value = False
        
        return [param0, param1, param2, param3, param4]

    def updateParameters(self, parameters):
        """Handle parameter interactions and populate S3 paths"""
        # Handle input method changes
        if parameters[0].altered:
            if parameters[0].value == "From Browse Results":
                parameters[1].enabled = True
                parameters[2].enabled = True
                parameters[3].enabled = False
            else:
                parameters[1].enabled = False
                parameters[2].enabled = False
                parameters[3].enabled = True
                
                # Provide example for manual entry
                if parameters[0].value == "Manual S3 URL":
                    parameters[3].value = "s3://veda-data-store-dev/path/to/file.tif"
                else:
                    parameters[3].value = "C:\\path\\to\\connection.acs\\path\\to\\file.tif"
                
        # When browse table is selected, populate S3 paths dropdown
        if parameters[1].value and parameters[1].altered:
            try:
                table = parameters[1].valueAsText
                
                if arcpy.Exists(table):
                    # Read S3 paths from the browse results table
                    s3_items = []
                    with arcpy.da.SearchCursor(table, ["item_id", "s3_href", "asset_type"]) as cursor:
                        for row in cursor:
                            # Create descriptive label for dropdown
                            label = f"{row[0]} - {row[2]}"  # item_id - asset_type
                            s3_items.append(label)
                    
                    if s3_items:
                        parameters[2].filter.list = s3_items
                        parameters[2].value = s3_items[0]
                    else:
                        parameters[2].filter.list = ["No S3 paths found in table"]
                else:
                    parameters[2].filter.list = ["Table not found"]
                    
            except Exception as e:
                parameters[2].filter.list = [f"Error: {str(e)[:30]}"]
                
        return

    def execute(self, parameters, messages):
        """Add selected S3 raster to the current map"""
        input_method = parameters[0].valueAsText
        copy_local = parameters[4].value
        
        messages.addMessage("=== Adding S3 Raster to Map ===")
        
        # Get the S3 path based on input method
        if input_method == "From Browse Results":
            # Get path from browse results table
            table = parameters[1].valueAsText
            selected_item = parameters[2].valueAsText
            
            # Parse the selected item (format: "item_id - asset_type")
            parts = selected_item.split(" - ")
            if len(parts) >= 2:
                item_id = parts[0]
                asset_type = parts[1]
                
                # Look up the actual S3 href in the table
                s3_path = None
                with arcpy.da.SearchCursor(table, ["item_id", "asset_type", "s3_href"]) as cursor:
                    for row in cursor:
                        if row[0] == item_id and row[1] == asset_type:
                            s3_path = row[2]
                            break
                
                if not s3_path:
                    messages.addErrorMessage(f"Could not find S3 path for: {selected_item}")
                    return
            else:
                messages.addErrorMessage("Invalid selection format")
                return
                
            messages.addMessage(f"\nSelected item: {selected_item}")
            messages.addMessage(f"S3 path: {s3_path}")
            
            # Convert S3 URL to ACS path if needed
            full_path = s3_path  # Default to S3 path
            
            if s3_path.startswith("s3://"):
                # Extract bucket and relative path from S3 URL
                s3_parts = s3_path.replace("s3://", "").split("/", 1)
                bucket = s3_parts[0]
                relative_path = s3_parts[1] if len(s3_parts) > 1 else ""
                
                messages.addMessage(f"\nS3 Bucket: {bucket}")
                
                # Find matching ACS file created in Step 1
                import glob
                project_folder = arcpy.mp.ArcGISProject("CURRENT").homeFolder
                acs_files = glob.glob(os.path.join(project_folder, "*.acs"))
                
                matching_acs = None
                for acs in acs_files:
                    # Match ACS file to bucket name
                    if bucket == "veda-data-store-dev" and "dev" in acs:
                        matching_acs = acs
                        break
                    elif bucket == "veda-data-store" and "prod" in acs:
                        matching_acs = acs
                        break
                    elif bucket == "veda-data-store-staging" and "staging" in acs:
                        matching_acs = acs
                        break
                
                if matching_acs:
                    # Build ACS path with proper Windows path separators
                    relative_path_windows = relative_path.replace('/', '\\')
                    full_path = matching_acs + "\\" + relative_path_windows
                    messages.addMessage(f"Using ACS connection: {os.path.basename(matching_acs)}")
                    
                    # Ensure AWS credentials are set for the session
                    creds_path = os.path.join(os.path.expanduser("~"), ".aws", "credentials")
                    if os.path.exists(creds_path):
                        creds = configparser.ConfigParser()
                        creds.read(creds_path)
                        
                        # Try to use the same profile used to create ACS
                        if 'uah-veda' in creds:
                            os.environ['AWS_ACCESS_KEY_ID'] = creds['uah-veda']['aws_access_key_id']
                            os.environ['AWS_SECRET_ACCESS_KEY'] = creds['uah-veda']['aws_secret_access_key']
                            os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
                            messages.addMessage("AWS credentials set from profile: uah-veda")
                else:
                    messages.addWarningMessage(f"No ACS connection found for bucket: {bucket}")
                    messages.addMessage("Make sure you ran Step 1 to create connections")
                    
        else:  # Manual methods
            full_path = parameters[3].valueAsText
            messages.addMessage(f"\nManual path: {full_path}")
        
        # Add to map
        messages.addMessage(f"\nPath to add: {full_path}")
        
        try:
            if copy_local:
                # Copy to local disk first (more stable)
                messages.addMessage("\nCopying to local disk first...")
                
                # Create safe filename
                filename = os.path.basename(full_path).replace('.', '_').replace(':', '_')
                local_path = os.path.join(arcpy.env.scratchFolder, f"{filename}.tif")
                
                # Perform the copy
                arcpy.management.CopyRaster(full_path, local_path)
                messages.addMessage(f"✓ Copied to: {local_path}")
                
                # Add local copy to map
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                map_obj = aprx.activeMap
                map_obj.addDataFromPath(local_path)
                messages.addMessage("✓ Successfully added to map!")
                
            else:
                # Add directly from S3 (requires stable connection)
                messages.addMessage("\nAdding directly from S3...")
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                map_obj = aprx.activeMap
                map_obj.addDataFromPath(full_path)
                messages.addMessage("✓ Successfully added to map!")
                
        except Exception as e:
            messages.addErrorMessage(f"\nFailed to add raster: {str(e)}")
            
            # Provide helpful error-specific suggestions
            if "does not exist" in str(e):
                messages.addMessage("\n⚠ The file may not exist in S3")
                messages.addMessage("Suggestions:")
                messages.addMessage("- Check if you're browsing the correct date range")
                messages.addMessage("- Some STAC items may reference files that were removed")
                messages.addMessage("- Try the 'Alternative: Download STAC Item' tool instead")
                
            elif "403" in str(e) or "credentials" in str(e).lower():
                messages.addMessage("\n⚠ AWS credentials issue detected")
                messages.addMessage("Suggestions:")
                messages.addMessage("- Run Step 1 again to recreate ACS connections")
                messages.addMessage("- Check if your AWS credentials have expired")
                messages.addMessage("- Enable 'Copy to Local' option")
                messages.addMessage("- Use 'Alternative: Download STAC Item' tool")
                
            elif "Failed to add data" in str(e):
                messages.addMessage("\n⚠ ArcGIS had trouble adding the data")
                messages.addMessage("Try enabling 'Copy to Local' option - it's more stable")
                
        return

class Alternative_DownloadSTACItem(object):
    def __init__(self):
        self.label = "Alternative: Download STAC Item via API"
        self.description = """Downloads STAC items using VEDA's REST API instead of S3.
        
        Use this tool when:
        - S3 access fails due to credentials
        - You want a permanent local copy
        - The file doesn't exist in S3 but is available through the API
        
        This method is slower but more reliable."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # API endpoint
        params.append(arcpy.Parameter(
            displayName="VEDA API URL",
            name="api_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[0].filter.type = "ValueList"
        params[0].filter.list = [
            "https://dev.openveda.cloud/api",
            "https://openveda.cloud/api"
        ]
        params[0].value = "https://dev.openveda.cloud/api"
        
        # Collection ID
        params.append(arcpy.Parameter(
            displayName="Collection ID",
            name="collection",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[1].value = "bangladesh-landcover-2001-2020"
        
        # Item ID
        params.append(arcpy.Parameter(
            displayName="Item ID (from STAC browse)",
            name="item_id",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[2].value = "MODIS_LC_2020_BD.cog"
        
        # Add to map option
        params.append(arcpy.Parameter(
            displayName="Add to Map after Download",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"))
        params[3].value = True
        
        return params

    def execute(self, parameters, messages):
        """Download item through VEDA API"""
        api_url = parameters[0].valueAsText
        collection = parameters[1].valueAsText
        item_id = parameters[2].valueAsText
        add_to_map = parameters[3].value
        
        messages.addMessage("=== Downloading STAC Item via API ===")
        
        try:
            # Build download URL for VEDA's COG API
            download_url = f"{api_url}/raster/cog/collections/{collection}/items/{item_id}?assets=cog_default"
            
            # Determine output location
            output_file = os.path.join(arcpy.env.scratchFolder, f"{item_id}.tif")
            
            messages.addMessage(f"\nCollection: {collection}")
            messages.addMessage(f"Item: {item_id}")
            messages.addMessage(f"API URL: {download_url}")
            messages.addMessage("\nDownloading... (this may take a moment)")
            
            # Download the file
            response = requests.get(download_url, stream=True)
            
            if response.status_code == 200:
                # Get file size if available
                total_size = int(response.headers.get('content-length', 0))
                
                # Write file with progress indication
                downloaded = 0
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Show progress every 10MB
                            if downloaded % (10 * 1024 * 1024) < 8192 and total_size > 0:
                                percent = (downloaded / total_size) * 100
                                messages.addMessage(f"Progress: {percent:.1f}%")
                
                messages.addMessage(f"\n✓ Downloaded to: {output_file}")
                messages.addMessage(f"File size: {downloaded / (1024*1024):.1f} MB")
                
                # Add to map if requested
                if add_to_map:
                    messages.addMessage("\nAdding to map...")
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    map_obj = aprx.activeMap
                    map_obj.addDataFromPath(output_file)
                    messages.addMessage("✓ Successfully added to map!")
                    
            else:
                messages.addErrorMessage(f"Download failed: HTTP {response.status_code}")
                
                # Common error explanations
                if response.status_code == 404:
                    messages.addMessage("\nItem not found. Check:")
                    messages.addMessage("- Collection ID is correct")
                    messages.addMessage("- Item ID is correct (case-sensitive)")
                elif response.status_code == 500:
                    messages.addMessage("\nServer error. The item might not be available through the API")
                    
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
        
        return