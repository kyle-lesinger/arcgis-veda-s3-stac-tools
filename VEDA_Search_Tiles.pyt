import arcpy
import os
import requests
import json
from datetime import datetime, timedelta

class Toolbox(object):
    def __init__(self):
        """VEDA Explorer-Style Tile Rendering"""
        self.label = "VEDA Search Tiles"
        self.alias = "veda_search_tiles"
        self.tools = [VEDASearchTiles]

class VEDASearchTiles(object):
    def __init__(self):
        self.label = "Create VEDA Search Tiles"
        self.description = """Create tile services using VEDA's search API - same method as VEDA Explorer.
        
        This creates a search registration that can be used for tile rendering."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # Collection
        params.append(arcpy.Parameter(
            displayName="Collection ID",
            name="collection",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[0].filter.type = "ValueList"
        params[0].filter.list = [
            "lis-global-da-evap",
            "no2-monthly",
            "co2-monthly", 
            "bangladesh-landcover-2001-2020",
            "lst-monthly",
            "worldpop-mosaic-2020",
            "sentinel-1-all-vars-subdaily",
            "landsat-all-vars-daily"
        ]
        params[0].value = "lis-global-da-evap"
        
        # Date
        params.append(arcpy.Parameter(
            displayName="Date (YYYY-MM-DD)",
            name="date",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[1].value = "2021-12-01"
        
        # API endpoint
        params.append(arcpy.Parameter(
            displayName="API Endpoint",
            name="api_endpoint",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[2].filter.type = "ValueList"
        params[2].filter.list = [
            "https://dev.openveda.cloud/api/raster",
            "https://openveda.cloud/api/raster"
        ]
        params[2].value = "https://dev.openveda.cloud/api/raster"
        
        # Visualization parameters
        params.append(arcpy.Parameter(
            displayName="Color Map",
            name="colormap",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[3].filter.type = "ValueList"
        params[3].filter.list = [
            "viridis", "plasma", "inferno", "magma",
            "rdbu_r", "rdylgn_r", "hot_r", "coolwarm"
        ]
        params[3].value = "viridis"
        
        params.append(arcpy.Parameter(
            displayName="Rescale Min",
            name="rescale_min",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input"))
        params[4].value = 0
        
        params.append(arcpy.Parameter(
            displayName="Rescale Max",
            name="rescale_max",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input"))
        params[5].value = 0.0001
        
        return params

    def execute(self, parameters, messages):
        collection = parameters[0].valueAsText
        date_str = parameters[1].valueAsText
        api_endpoint = parameters[2].valueAsText
        colormap = parameters[3].valueAsText
        rescale_min = parameters[4].value
        rescale_max = parameters[5].value
        
        messages.addMessage("=== VEDA Search-Based Tile Rendering ===")
        
        try:
            # Step 1: Create search registration
            messages.addMessage("\nStep 1: Creating search registration...")
            
            # Build datetime range for the date
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            start_dt = date_obj.isoformat() + "Z"
            end_dt = (date_obj + timedelta(days=1) - timedelta(seconds=1)).isoformat() + "Z"
            
            search_data = {
                "collections": [collection],
                "datetime": f"{start_dt}/{end_dt}",
                "limit": 10  # Get multiple items if available
            }
            
            # Register the search
            register_url = f"{api_endpoint}/searches/register"
            messages.addMessage(f"Registering search: {register_url}")
            messages.addMessage(f"Search parameters: {json.dumps(search_data, indent=2)}")
            
            response = requests.post(
                register_url,
                json=search_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                messages.addErrorMessage(f"Search registration failed: {response.status_code}")
                messages.addMessage(f"Response: {response.text}")
                
                # Try alternative - direct STAC query
                messages.addMessage("\nTrying direct STAC approach...")
                stac_url = api_endpoint.replace('/raster', '/stac')
                items_url = f"{stac_url}/collections/{collection}/items?datetime={date_str}&limit=1"
                
                stac_response = requests.get(items_url)
                if stac_response.status_code == 200:
                    items = stac_response.json().get('features', [])
                    if items:
                        item_id = items[0]['id']
                        messages.addMessage(f"Found item: {item_id}")
                        
                        # Try direct tile URL
                        tile_url = f"{api_endpoint}/stac/tiles/{{z}}/{{x}}/{{y}}"
                        tile_url += f"?url={stac_url}/collections/{collection}/items/{item_id}"
                        tile_url += f"&assets=cog_default"
                        tile_url += f"&rescale={rescale_min},{rescale_max}"
                        tile_url += f"&colormap_name={colormap}"
                        
                        messages.addMessage("\nDirect tile URL:")
                        messages.addMessage(tile_url)
                return
            
            # Parse search response
            search_result = response.json()
            search_id = search_result.get('id') or search_result.get('search_id')
            
            if not search_id:
                messages.addErrorMessage("No search ID in response")
                messages.addMessage(f"Response: {json.dumps(search_result, indent=2)}")
                return
                
            messages.addMessage(f"✓ Search registered: {search_id}")
            
            # Step 2: Build tile URL
            messages.addMessage("\nStep 2: Building tile service URL...")
            
            # Tile URL template
            tile_url = f"{api_endpoint}/searches/{search_id}/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}"
            
            # Add rendering parameters
            params = []
            params.append(f"rescale={rescale_min},{rescale_max}")
            params.append(f"colormap_name={colormap}")
            params.append("assets=cog_default")
            params.append("resampling=bilinear")
            
            full_tile_url = tile_url + "?" + "&".join(params)
            
            messages.addMessage("\n✓ Tile Service URL:")
            messages.addMessage(full_tile_url)
            
            # Step 3: Test preview
            messages.addMessage("\nStep 3: Testing preview...")
            preview_url = f"{api_endpoint}/searches/{search_id}/preview.png"
            preview_url += "?" + "&".join(params) + "&max_size=512"
            
            messages.addMessage(f"Preview URL: {preview_url}")
            
            # Test the preview
            preview_response = requests.head(preview_url)
            if preview_response.status_code == 200:
                messages.addMessage("✓ Preview is accessible!")
            else:
                messages.addMessage(f"Preview status: {preview_response.status_code}")
            
            # Step 4: Instructions for ArcGIS Pro
            messages.addMessage("\n" + "="*60)
            messages.addMessage("TO ADD TO ARCGIS PRO:")
            messages.addMessage("\nMethod 1: XYZ Tiles")
            messages.addMessage("1. Map tab → Add Data → XYZ Tiles")
            messages.addMessage("2. Enter this URL (replace {z}{x}{y} with ${level}${col}${row}):")
            
            arcgis_url = full_tile_url.replace("{z}", "${level}").replace("{x}", "${col}").replace("{y}", "${row}")
            messages.addMessage(arcgis_url)
            
            messages.addMessage("\nMethod 2: Create Connection File")
            messages.addMessage("Save this as a .json file and add to project")
            
            connection_json = {
                "type": "XYZ",
                "url": arcgis_url,
                "name": f"VEDA {collection} {date_str}",
                "spatialReference": {"wkid": 3857}
            }
            
            messages.addMessage(json.dumps(connection_json, indent=2))
            
            # Try to save connection file
            try:
                output_dir = arcpy.env.scratchFolder
                json_file = os.path.join(output_dir, f"veda_{collection}_{search_id}.json")
                
                with open(json_file, 'w') as f:
                    json.dump(connection_json, f, indent=2)
                    
                messages.addMessage(f"\nConnection file saved: {json_file}")
            except Exception as e:
                messages.addMessage(f"\nCould not save file: {str(e)}")
                
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
