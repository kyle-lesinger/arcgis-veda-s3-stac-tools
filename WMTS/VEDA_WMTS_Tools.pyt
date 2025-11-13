import arcpy
import os
import requests

class Toolbox(object):
    def __init__(self):
        """VEDA WMTS Tools - Access NASA VEDA STAC data through WMTS services"""
        self.label = "VEDA WMTS Tools"
        self.alias = "veda_wmts"
        # Tools ordered by typical workflow
        self.tools = [
            Step1_BrowseSTACCollections,
            Step2_BrowseCollectionItems,
            Step3_CreateWMTSConnection
        ]

class Step1_BrowseSTACCollections(object):
    def __init__(self):
        self.label = "Step 1: Browse STAC Collections"
        self.description = """Browse VEDA STAC catalogs to find available collections.

        This tool queries VEDA's STAC API to list all available collections
        that can be accessed via WMTS services.

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

        # Output table to store selected collection info
        param2 = arcpy.Parameter(
            displayName="Output Table (stores collection info)",
            name="output_table",
            datatype="DETable",
            parameterType="Required",
            direction="Output")

        return [param0, param1, param2]

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
        """Store selected collection information for use in Step 2"""
        stac_url = parameters[0].valueAsText
        collection_value = parameters[1].valueAsText
        output_table = parameters[2].valueAsText

        messages.addMessage("=== Browsing STAC Collections ===")

        # Extract collection ID and title from display value
        parts = collection_value.split(" - ")
        collection_id = parts[0]
        title = parts[1] if len(parts) > 1 else collection_id

        messages.addMessage(f"\nSelected collection: {collection_id}")
        messages.addMessage(f"Title: {title}")

        try:
            # Create output table to store collection info
            messages.addMessage("\nCreating output table...")
            arcpy.management.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))

            # Add fields to store collection information
            fields = [
                ("collection_id", "TEXT", 100, "Collection ID"),
                ("title", "TEXT", 200, "Collection Title"),
                ("stac_url", "TEXT", 200, "STAC API URL")
            ]

            for field_name, field_type, field_length, alias in fields:
                arcpy.management.AddField(output_table, field_name, field_type,
                                        field_length=field_length, field_alias=alias)

            # Insert collection data
            cursor = arcpy.da.InsertCursor(output_table, [f[0] for f in fields])
            cursor.insertRow([
                collection_id,
                title,
                stac_url
            ])
            del cursor

            # Summary
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"✓ Collection information saved")
            messages.addMessage(f"  Collection: {collection_id}")
            messages.addMessage(f"  Output: {output_table}")
            messages.addMessage(f"\nNext step: Use 'Step 2: Browse Collection Items' to find items")
            messages.addMessage("Select this table as input")

        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")

        return


class Step2_BrowseCollectionItems(object):
    def __init__(self):
        self.label = "Step 2: Browse Collection Items"
        self.description = """Browse items in selected STAC collection.

        This tool queries items from the collection selected in Step 1,
        extracting bbox, datetime, and available assets for WMTS access."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        # Input table from Step 1
        param0 = arcpy.Parameter(
            displayName="Collection Table (from Step 1)",
            name="collection_table",
            datatype="GPTableView",
            parameterType="Required",
            direction="Input")

        # Number of items to retrieve
        param1 = arcpy.Parameter(
            displayName="Number of Items to Retrieve",
            name="limit",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        param1.value = 10

        # Output table to store item results
        param2 = arcpy.Parameter(
            displayName="Output Table (stores item details)",
            name="output_table",
            datatype="DETable",
            parameterType="Required",
            direction="Output")

        return [param0, param1, param2]

    def execute(self, parameters, messages):
        """Query collection items and extract bbox, datetime, assets"""
        collection_table = parameters[0].valueAsText
        limit = parameters[1].value
        output_table = parameters[2].valueAsText

        messages.addMessage("=== Browsing Collection Items ===")

        try:
            # Read collection info from Step 1 table
            with arcpy.da.SearchCursor(collection_table, ["collection_id", "stac_url"]) as cursor:
                row = next(cursor)
                collection_id = row[0]
                stac_url = row[1]

            messages.addMessage(f"\nCollection: {collection_id}")

            # Query items from STAC
            items_url = f"{stac_url}/collections/{collection_id}/items?limit={limit}"
            messages.addMessage(f"API URL: {items_url}")

            response = requests.get(items_url)
            if response.status_code != 200:
                messages.addErrorMessage(f"STAC query failed: HTTP {response.status_code}")
                return

            items = response.json()
            total_items = items.get('numberMatched', len(items.get('features', [])))
            messages.addMessage(f"\nTotal items in collection: {total_items}")
            messages.addMessage(f"Retrieving first {limit} items...")

            # Create output table
            messages.addMessage("\nCreating output table...")
            arcpy.management.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))

            # Add fields to store item information
            fields = [
                ("item_id", "TEXT", 100, "Item ID"),
                ("datetime", "TEXT", 50, "Date/Time"),
                ("bbox", "TEXT", 200, "Bounding Box"),
                ("assets", "TEXT", 500, "Available Assets"),
                ("collection_id", "TEXT", 100, "Collection ID"),
                ("stac_url", "TEXT", 200, "STAC API URL")
            ]

            for field_name, field_type, field_length, alias in fields:
                arcpy.management.AddField(output_table, field_name, field_type,
                                        field_length=field_length, field_alias=alias)

            # Process items
            messages.addMessage("\nProcessing items...")
            cursor = arcpy.da.InsertCursor(output_table, [f[0] for f in fields])

            item_count = 0

            for feature in items.get('features', []):
                item_id = feature['id']

                # Extract datetime
                datetime_val = feature['properties'].get('datetime', '')
                if not datetime_val:
                    # Try start_datetime if datetime not present
                    datetime_val = feature['properties'].get('start_datetime', '')

                # Extract bbox
                bbox = feature.get('bbox', [])
                bbox_str = ','.join(map(str, bbox)) if bbox else ''

                # Extract available assets
                assets = list(feature.get('assets', {}).keys())
                assets_str = ','.join(assets)

                # Insert row
                cursor.insertRow([
                    item_id,
                    datetime_val,
                    bbox_str,
                    assets_str,
                    collection_id,
                    stac_url
                ])

                item_count += 1

                # Show sample
                if item_count <= 3:
                    messages.addMessage(f"\nItem {item_count}: {item_id}")
                    messages.addMessage(f"  DateTime: {datetime_val}")
                    messages.addMessage(f"  BBox: {bbox_str}")
                    messages.addMessage(f"  Assets: {assets_str}")

            del cursor

            # Summary
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"✓ Processed {item_count} items")
            messages.addMessage(f"✓ Results saved to: {output_table}")
            messages.addMessage("\nNext step: Use 'Step 3: Create WMTS Connection'")
            messages.addMessage("Select this table and choose items to visualize")

        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")

        return


class Step3_CreateWMTSConnection(object):
    def __init__(self):
        self.label = "Step 3: Create WMTS Connection"
        self.description = """Create WMTS connections for selected items.

        This tool builds WMTS Capabilities URLs and creates connections
        in ArcGIS Pro to visualize the data through web services.

        For each selected item, a separate WMTS connection is created."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        # Input table from Step 2
        param0 = arcpy.Parameter(
            displayName="Items Table (from Step 2)",
            name="items_table",
            datatype="GPTableView",
            parameterType="Required",
            direction="Input")

        # Item selection dropdown
        param1 = arcpy.Parameter(
            displayName="Select Items (one or more)",
            name="selected_items",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param1.filter.type = "ValueList"

        # Asset selection
        param2 = arcpy.Parameter(
            displayName="Asset Type",
            name="asset_type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param2.filter.type = "ValueList"
        param2.filter.list = ["cog_default"]  # Will be updated dynamically
        param2.value = "cog_default"

        # Tile format
        param3 = arcpy.Parameter(
            displayName="Tile Format",
            name="tile_format",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.filter.type = "ValueList"
        param3.filter.list = ["png", "jpg"]
        param3.value = "png"

        # Output table for WMTS URLs
        param4 = arcpy.Parameter(
            displayName="Output Table (stores WMTS URLs)",
            name="output_table",
            datatype="DETable",
            parameterType="Required",
            direction="Output")

        return [param0, param1, param2, param3, param4]

    def updateParameters(self, parameters):
        """Dynamically populate items and assets from table"""
        # When items table is selected, populate dropdown
        if parameters[0].value and parameters[0].altered:
            try:
                table = parameters[0].valueAsText

                if arcpy.Exists(table):
                    # Read items from table
                    items = []
                    all_assets = set()

                    with arcpy.da.SearchCursor(table, ["item_id", "datetime", "assets"]) as cursor:
                        for row in cursor:
                            item_id = row[0]
                            datetime_val = row[1]
                            assets_str = row[2]

                            # Create descriptive label
                            label = f"{item_id} ({datetime_val[:10]})"
                            items.append(label)

                            # Collect all unique assets
                            if assets_str:
                                for asset in assets_str.split(','):
                                    all_assets.add(asset.strip())

                    if items:
                        parameters[1].filter.list = items
                    else:
                        parameters[1].filter.list = ["No items found"]

                    # Update asset dropdown
                    if all_assets:
                        parameters[2].filter.list = sorted(list(all_assets))
                        if "cog_default" in all_assets:
                            parameters[2].value = "cog_default"
                        else:
                            parameters[2].value = sorted(list(all_assets))[0]
                else:
                    parameters[1].filter.list = ["Table not found"]

            except Exception as e:
                parameters[1].filter.list = [f"Error: {str(e)[:30]}"]

        return

    def execute(self, parameters, messages):
        """Create WMTS URL table for selected items"""
        items_table = parameters[0].valueAsText
        selected_items = parameters[1].valueAsText.split(';')  # Multi-value parameter
        asset_type = parameters[2].valueAsText
        tile_format = parameters[3].valueAsText
        output_table = parameters[4].valueAsText

        messages.addMessage("=== Creating WMTS URLs ===")
        messages.addMessage(f"\nSelected {len(selected_items)} item(s)")
        messages.addMessage(f"Asset: {asset_type}")
        messages.addMessage(f"Tile format: {tile_format}")

        try:
            # Read item details from table
            item_data = {}
            with arcpy.da.SearchCursor(items_table,
                                      ["item_id", "datetime", "bbox", "collection_id", "stac_url"]) as cursor:
                for row in cursor:
                    item_data[row[0]] = {
                        'datetime': row[1],
                        'bbox': row[2],
                        'collection_id': row[3],
                        'stac_url': row[4]
                    }

            # Create output table
            messages.addMessage("\nCreating output table for WMTS URLs...")
            arcpy.management.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))

            # Add fields
            fields = [
                ("item_id", "TEXT", 100, "Item ID"),
                ("collection_id", "TEXT", 100, "Collection ID"),
                ("wmts_url", "TEXT", 1000, "WMTS URL"),
                ("layer_name", "TEXT", 200, "Layer Name"),
                ("status", "TEXT", 200, "Status")
            ]

            for field_name, field_type, field_length, alias in fields:
                arcpy.management.AddField(output_table, field_name, field_type,
                                        field_length=field_length, field_alias=alias)

            output_cursor = arcpy.da.InsertCursor(output_table, [f[0] for f in fields])

            # Process each selected item
            rows_written = 0

            messages.addMessage(f"\nProcessing {len(selected_items)} selected item(s)...")

            for selected in selected_items:
                # Parse selection (format: "item_id (date)")
                # Strip quotes and whitespace that may be added by ArcGIS
                selected = selected.strip().strip("'\"")

                # Extract item_id from format "item_id (date)"
                if " (" in selected:
                    item_id = selected.split(" (")[0]
                else:
                    item_id = selected

                if item_id not in item_data:
                    messages.addWarningMessage(f"\nSkipping {item_id}: not found in table")
                    messages.addMessage(f"  Available items: {', '.join(list(item_data.keys())[:5])}")
                    continue

                data = item_data[item_id]
                collection_id = data['collection_id']
                datetime_val = data['datetime']
                bbox_str = data['bbox']
                stac_url = data['stac_url']

                # Build base API URL (convert STAC URL to raster API)
                base_api = stac_url.replace('/stac', '')

                # Build WMTS Capabilities URL (no encoding for readability)
                wmts_url = (
                    f"{base_api}/raster/collections/{collection_id}/"
                    f"WebMercatorQuad/WMTSCapabilities.xml?"
                    f"tile_format={tile_format}&"
                    f"tile_scale=1&"
                    f"use_epsg=true&"
                    f"ids={item_id}&"
                    f"bbox={bbox_str}&"
                    f"datetime={datetime_val}&"
                    f"assets={asset_type}"
                )

                messages.addMessage(f"\n{'='*50}")
                messages.addMessage(f"Item: {item_id}")
                messages.addMessage(f"WMTS URL: {wmts_url}")

                layer_name = f"{collection_id}_{item_id}"
                status = "URL Generated"

                # Write to output table
                try:
                    row_data = [
                        item_id,
                        collection_id,
                        wmts_url,
                        layer_name,
                        status
                    ]

                    output_cursor.insertRow(row_data)
                    rows_written += 1
                    messages.addMessage(f"✓ Saved to table")
                except Exception as e:
                    messages.addErrorMessage(f"✗ Failed to write to table: {str(e)}")
                    messages.addMessage(f"  Item: {item_id}")

            # Close output cursor
            del output_cursor
            messages.addMessage(f"\n✓ Committed {rows_written} row(s) to table")

            # Verify data was written by reading it back
            messages.addMessage("\nVerifying table contents...")
            try:
                with arcpy.da.SearchCursor(output_table, ["item_id", "wmts_url"]) as verify_cursor:
                    verify_count = 0
                    for row in verify_cursor:
                        verify_count += 1
                        messages.addMessage(f"  Row {verify_count}: {row[0]} - URL present: {len(row[1]) if row[1] else 0} chars")
                    messages.addMessage(f"✓ Verified {verify_count} row(s) in table")
            except Exception as e:
                messages.addWarningMessage(f"⚠ Could not verify table: {str(e)}")

            # Add table to Contents pane as standalone table
            try:
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                map_obj = aprx.activeMap

                # Create Table object from path, then add to map
                table_obj = arcpy.mp.Table(output_table)
                map_obj.addTable(table_obj)

                messages.addMessage(f"\n✓ Table added to Contents pane!")
                messages.addMessage(f"  Look for '{os.path.basename(output_table)}' under Standalone Tables")
            except Exception as e:
                messages.addWarningMessage(f"⚠ Could not add table to Contents pane")
                messages.addMessage(f"  You can manually add it from: {output_table}")

            # Summary
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"✓ Successfully processed {rows_written} item(s)")
            messages.addMessage(f"✓ WMTS URLs saved to table: {os.path.basename(output_table)}")

            messages.addMessage("\n" + "="*50)
            messages.addMessage("NEXT STEPS - How to add WMTS layers to your map:")
            messages.addMessage("="*50)
            messages.addMessage("\n1. In Contents pane, find the table under 'Standalone Tables'")
            messages.addMessage("2. Right-click the table → Open")
            messages.addMessage("3. Copy a URL from the 'wmts_url' column")
            messages.addMessage("4. In Catalog pane, right-click 'Servers'")
            messages.addMessage("5. Select 'New WMTS Server'")
            messages.addMessage("6. Paste the WMTS URL in the URL field")
            messages.addMessage("7. Click OK - server connection is created")
            messages.addMessage("8. Expand the connection and drag layers to your map!")
            messages.addMessage("\n✓ WMTS layers will appear in Contents pane")

        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")

        return
