import arcpy
import os

class Toolbox(object):
    def __init__(self):
        """Debug S3 Access"""
        self.label = "Debug S3 Access"
        self.alias = "debug_s3"
        self.tools = [TestS3Access]

class TestS3Access(object):
    def __init__(self):
        self.label = "Test S3 Access"
        self.description = "Test if ACS connection can access S3 data"
        self.canRunInBackground = False

    def getParameterInfo(self):
        # ACS File
        param0 = arcpy.Parameter(
            displayName="ACS Connection File",
            name="acs_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["acs"]
        
        # Test path
        param1 = arcpy.Parameter(
            displayName="S3 Key Path (without bucket)",
            name="s3_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.value = "cattle-heat-story/pasture-grassland-CONUS/usda_cattle_large_AFOs_2017_cog.tif"
        
        return [param0, param1]

    def execute(self, parameters, messages):
        acs_file = parameters[0].valueAsText
        s3_key = parameters[1].valueAsText
        
        messages.addMessage("=== Testing S3 Access ===")
        messages.addMessage(f"ACS File: {acs_file}")
        messages.addMessage(f"S3 Key: {s3_key}")
        
        # Test different path formats
        test_paths = [
            # Format 1: ACS + key with forward slashes
            acs_file + "/" + s3_key,
            
            # Format 2: ACS + key with backslashes
            acs_file + "\\" + s3_key.replace('/', '\\'),
            
            # Format 3: Using os.path.join
            os.path.join(acs_file, s3_key.replace('/', os.sep)),
            
            # Format 4: Just in case - with bucket name
            os.path.join(acs_file, "veda-data-store-dev", s3_key.replace('/', os.sep))
        ]
        
        messages.addMessage("\nTesting different path formats:")
        
        for i, test_path in enumerate(test_paths, 1):
            messages.addMessage(f"\n[Test {i}] Path: {test_path}")
            
            try:
                # Test if path exists
                if arcpy.Exists(test_path):
                    messages.addMessage("  [+] Path exists!")
                    
                    # Try to describe the raster
                    desc = arcpy.Describe(test_path)
                    messages.addMessage(f"  [+] Data type: {desc.dataType}")
                    messages.addMessage(f"  [+] Format: {desc.format}")
                    
                    # Try to add to map
                    try:
                        aprx = arcpy.mp.ArcGISProject("CURRENT")
                        active_map = aprx.activeMap
                        active_map.addDataFromPath(test_path)
                        messages.addMessage("  [+] Successfully added to map!")
                        return  # Success, stop testing
                    except Exception as e:
                        messages.addMessage(f"  [-] Add to map failed: {str(e)}")
                else:
                    messages.addMessage("  [-] Path does not exist")
                    
            except Exception as e:
                messages.addMessage(f"  [-] Error: {str(e)}")
        
        # Additional debugging
        messages.addMessage("\n=== Additional Debugging ===")
        
        # Check if ACS file exists
        if os.path.exists(acs_file):
            messages.addMessage(f"[+] ACS file exists: {acs_file}")
            messages.addMessage(f"    Size: {os.path.getsize(acs_file)} bytes")
        else:
            messages.addMessage(f"[-] ACS file not found!")
            
        # Try to list what's accessible through the ACS
        messages.addMessage("\nTrying to explore ACS contents...")
        try:
            # This might work to show what's accessible
            workspace = acs_file
            arcpy.env.workspace = workspace
            rasters = arcpy.ListRasters()
            if rasters:
                messages.addMessage(f"Found {len(rasters)} rasters:")
                for r in rasters[:5]:  # Show first 5
                    messages.addMessage(f"  - {r}")
            else:
                messages.addMessage("No rasters found through ACS connection")
        except Exception as e:
            messages.addMessage(f"Could not list contents: {str(e)}")
        
        return
