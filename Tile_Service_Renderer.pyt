import arcpy
import os
import requests
import json
from urllib.parse import quote

class Toolbox(object):
    def __init__(self):
        """Dynamic Tile Rendering (No Download)"""
        self.label = "Tile Service Renderer"
        self.alias = "tile_renderer"
        self.tools = [AddTileService]

class AddTileService(object):
    def __init__(self):
        self.label = "Add STAC Item as Tile Service"
        self.description = """Render STAC items using dynamic tile services - no download required!
        
        This uses server-side rendering to display data without egress costs."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # STAC API
        params.append(arcpy.Parameter(
            displayName="STAC API",
            name="stac_api",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[0].filter.type = "ValueList"
        params[0].filter.list = [
            "https://dev.openveda.cloud/api/stac",
            "https://openveda.cloud/api/stac"
        ]
        params[0].value = "https://dev.openveda.cloud/api/stac"
        
        # Collection
        params.append(arcpy.Parameter(
            displayName="Collection ID",
            name="collection",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[1].value = "sentinel-1-all-vars-subdaily"
        
        # Rendering service
        params.append(arcpy.Parameter(
            displayName="Tile Service",
            name="tile_service",
            datatype="GPString",
            parameterType="Required",
            direction="Input"))
        params[2].filter.type = "ValueList"
        params[2].filter.list = [
            "VEDA TiTiler (https://dev.openveda.cloud/api/raster)",
            "NASA GIBS WMTS",
            "Planet Basemaps",
            "Custom TiTiler URL"
        ]
        params[2].value = "VEDA TiTiler (https://dev.openveda.cloud/api/raster)"
        
        return params

    def execute(self, parameters, messages):
        stac_api = parameters[0].valueAsText
        collection = parameters[1].valueAsText
        tile_service = parameters[2].valueAsText
        
        messages.addMessage("=== Dynamic Tile Rendering ===")
        
        try:
            # Query STAC for latest item
            messages.addMessage(f"\nQuerying STAC collection: {collection}")
            items_url = f"{stac_api}/collections/{collection}/items?limit=1"
            response = requests.get(items_url)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"STAC query failed: {response.status_code}")
                return
                
            data = response.json()
            features = data.get('features', [])
            
            if not features:
                messages.addMessage("No items found")
                return
                
            item = features[0]
            item_id = item.get('id')
            
            messages.addMessage(f"Found item: {item_id}")
            
            # Check for COG assets
            assets = item.get('assets', {})
            cog_asset = None
            
            for asset_name, asset_info in assets.items():
                if asset_info.get('type', '').startswith('image/tiff'):
                    href = asset_info.get('href', '')
                    # Check if it's in nasa-disasters bucket
                    if 's3://nasa-disasters/' in href:
                        cog_asset = {
                            'name': asset_name,
                            'href': href,
                            'info': asset_info
                        }
                        messages.addMessage(f"  Found COG asset: {asset_name}")
                        break
            
            if not cog_asset:
                messages.addMessage("No suitable COG assets found")
                return
            
            # Option 1: TiTiler dynamic tiles
            if "TiTiler" in tile_service:
                messages.addMessage("\n=== Using TiTiler Dynamic Rendering ===")
                
                # Base URL for TiTiler
                if "dev.openveda" in tile_service:
                    titiler_base = "https://dev.openveda.cloud/api/raster"
                else:
                    titiler_base = "https://openveda.cloud/api/raster"
                
                # Create XYZ tile URL template
                # TiTiler can render from STAC items directly
                stac_url = f"{stac_api}/collections/{collection}/items/{item_id}"
                
                # Build TiTiler URL
                xyz_url = f"{titiler_base}/stac/tiles/{{z}}/{{x}}/{{y}}"
                xyz_url += f"?url={quote(stac_url)}"
                xyz_url += f"&assets={cog_asset['name']}"
                
                messages.addMessage("\nTile URL Template:")
                messages.addMessage(xyz_url)
                
                # Create a tile layer URL for ArcGIS
                # Format for ArcGIS Pro raster tile layer
                service_url = f"{titiler_base}/stac/WMTSCapabilities.xml?url={quote(stac_url)}"
                
                messages.addMessage("\nAdding as web layer...")
                messages.addMessage("Note: This displays data dynamically without downloading!")
                
                # Add to map as web imagery layer
                try:
                    aprx = arcpy.mp.ArcGISProject("CURRENT")
                    active_map = aprx.activeMap
                    
                    # Try adding as raster tile layer
                    # Note: This is a workaround - proper implementation would create a .lyrx file
                    messages.addMessage("\nTo add this layer manually:")
                    messages.addMessage("1. Insert → Data From Path")
                    messages.addMessage("2. Enter this URL:")
                    messages.addMessage(xyz_url.replace("{z}", "${level}").replace("{x}", "${col}").replace("{y}", "${row}"))
                    messages.addMessage("3. Set as 'Raster Tile Layer'")
                    
                except Exception as e:
                    messages.addMessage(f"Auto-add failed: {str(e)}")
                
            # Option 2: Direct S3 HTTP endpoints (if public)
            elif tile_service == "NASA GIBS WMTS":
                messages.addMessage("\n=== Checking NASA GIBS ===")
                messages.addMessage("NASA GIBS provides pre-rendered tiles for many datasets")
                messages.addMessage("Check: https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/wmts.cgi")
                
            # Option 3: Create a proxy service
            messages.addMessage("\n=== Alternative: Proxy Service ===")
            messages.addMessage("For authenticated access without downloads:")
            messages.addMessage("1. Set up a Lambda function that:")
            messages.addMessage("   - Accepts tile requests")
            messages.addMessage("   - Uses your temp credentials to fetch tiles from S3")
            messages.addMessage("   - Returns tiles to ArcGIS")
            messages.addMessage("2. Add Lambda URL as tile service")
            
            # Option 4: Partial downloads
            messages.addMessage("\n=== Alternative: Smart Caching ===")
            messages.addMessage("Download only viewed extents:")
            messages.addMessage("- Use the 'Current Map Extent' option in COG tools")
            messages.addMessage("- Cache tiles locally")
            messages.addMessage("- Reuse cached data")
            
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
        
        return
