# VEDA WMTS Tools for ArcGIS Pro

## Overview

The VEDA WMTS Tools provide a streamlined workflow to access NASA VEDA STAC data through WMTS (Web Map Tile Service) connections in ArcGIS Pro. This toolbox generates properly formatted WMTS URLs from VEDA's STAC catalog and organizes them in a table for easy access.

## Toolbox Workflow

### Step 1: Browse STAC Collections
- **Purpose**: Select a collection from VEDA's STAC catalog
- **Input**: STAC API URL (Development or Production)
- **Process**: Tool queries the API and displays all available collections
- **Output**: Table containing selected collection information

### Step 2: Browse Collection Items
- **Purpose**: Find specific items (datasets) within the selected collection
- **Input**: Collection table from Step 1
- **Process**: Tool queries items and extracts metadata (datetime, bbox, assets)
- **Output**: Table containing item details for all available datasets

### Step 3: Create WMTS Connection
- **Purpose**: Generate WMTS Capabilities URLs for selected items
- **Input**: Items table from Step 2, asset type, tile format
- **Process**: Tool builds properly formatted WMTS URLs with all parameters
- **Output**: Table with WMTS URLs that appears in Contents pane under Standalone Tables

---

## Complete Step-by-Step Instructions

After running the toolbox (Steps 1-3), follow these instructions to add WMTS layers to your map:

### Part A: Accessing the WMTS URLs

1. **Locate the Table in Contents Pane**
   - Look in the **Contents** pane (left side of ArcGIS Pro)
   - Scroll down to the **"Standalone Tables"** section
   - Find your output table (e.g., `wmts_urls_table`)

2. **Open the Table**
   - **Right-click** on the table name
   - Select **"Open"** from the context menu
   - The attribute table opens showing all fields

3. **Copy a WMTS URL**
   - Locate the **`wmts_url`** column in the table
   - **Click** on a cell in the `wmts_url` column to select it
   - The full URL should be highlighted
   - **Right-click** the selected cell
   - Choose **"Copy"** from the menu
   - Alternatively, press **Ctrl+C** (Windows) or **Cmd+C** (Mac)

### Part B: Creating the WMTS Server Connection

4. **Open the Add WMTS Server Dialog**
   - Switch to the **Catalog** pane (right side of ArcGIS Pro)
   - Expand the **"Servers"** folder
   - **Right-click** on **"Servers"**
   - Select **"New WMTS Server"** from the menu

5. **Paste the WMTS URL**
   - A dialog box titled "Add WMTS Server Connection" appears
   - In the **"Server URL"** field, **paste** the WMTS URL you copied
   - The URL should look like:
     ```
     https://dev.openveda.cloud/api/raster/collections/geoglam/WebMercatorQuad/WMTSCapabilities.xml?tile_format=png&tile_scale=1&use_epsg=true&ids=CropMonitor_202502&bbox=-180.0,-90.0,180.0,90.0&datetime=2025-02-01T00:00:00Z&assets=cog_default
     ```
   - Optionally, give the connection a descriptive name in the **"Name"** field
   - Click **"OK"**

6. **Wait for Connection**
   - ArcGIS Pro will connect to the WMTS server
   - This may take a few seconds
   - A new server connection (`.wmts` file) appears under "Servers" in Catalog

### Part C: Adding Layers to Your Map

7. **Expand the WMTS Connection**
   - In the **Catalog** pane, locate the new WMTS server connection
   - It will be under **"Servers"** with a globe icon
   - **Click the arrow** next to the connection to expand it

8. **Browse Available Layers**
   - You'll see one or more layers listed under the connection
   - These represent the actual data layers available
   - Hover over layer names to see details

9. **Add Layer to Map**
   - **Drag and drop** a layer from the Catalog pane to your map
   - OR **Right-click** the layer → **"Add to Current Map"**
   - The layer appears in the **Contents** pane under your map layers
   - The data begins loading and rendering on your map

### Part D: Applying Color Scales (IMPORTANT)

**⚠ Important Note**: WMTS layers from VEDA often load without color scales applied by default, appearing as grayscale or with no symbology.

10. **Open Layer Properties**
    - In the **Contents** pane, locate your newly added WMTS layer
    - **Right-click** the layer name
    - Select **"Properties"**

11. **Access Symbology Settings**
    - In the Layer Properties window, click the **"Symbology"** tab on the left

12. **Choose Symbology Method**
    - At the top of the Symbology pane, select a method:
      - **Stretch**: For continuous data (elevation, temperature, vegetation indices)
      - **Classify**: For discrete value ranges
      - **Unique Values**: For categorical data
    - **Recommended**: Start with **"Stretch"** for most VEDA datasets

13. **Apply Color Scheme**
    - **Primary Symbology**: Ensure "Stretch" is selected
    - **Color Scheme**: Click the color ramp dropdown
    - Choose an appropriate color scheme:
      - **Elevation 1**: Good for terrain/bathymetry
      - **Temperature**: Red to blue scales
      - **Precipitation**: Blue/green scales
      - **Yellow-Green-Blue**: For vegetation/NDVI data
      - **Red-Yellow-Green**: Alternative vegetation scale
    - **Stretch Type**: Try different options:
      - **Standard Deviation**: Good for data with outliers
      - **Min-Max**: Uses full data range
      - **Percent Clip**: Clips extreme values (2% is default)

14. **Adjust Statistics**
    - Click **"Compute Statistics"** button if needed
    - This recalculates min/max values from the data
    - Adjust **Gamma** slider to enhance contrast if needed

15. **Apply Changes**
    - Click **"Apply"** to preview changes
    - Click **"OK"** when satisfied with the symbology

### Part E: Additional Symbology Options

16. **Alternative: Use Layer Symbology Pane**
    - Select your layer in Contents pane
    - Go to **"Appearance"** tab in the ribbon
    - Click **"Symbology"** button
    - The Symbology pane opens on the right
    - Make adjustments as described above

17. **Fine-Tune Transparency**
    - In the **Appearance** tab, use the **Transparency** slider
    - Useful for overlaying multiple WMTS layers
    - Typically 0-30% transparency works well

18. **Adjust Layer Order**
    - **Drag layers** up/down in Contents pane to change draw order
    - Basemaps should be at the bottom
    - WMTS data layers above basemaps

### Part F: Working with Multiple Items

19. **Repeat for Additional Items**
    - Return to your WMTS URLs table (Standalone Tables section)
    - Copy another URL from a different row
    - Follow steps 4-9 to create another WMTS connection
    - Each item gets its own server connection
    - You can have multiple WMTS layers in your map simultaneously

20. **Organize Connections**
    - Rename WMTS connections in Catalog for clarity
    - **Right-click** connection → **"Rename"**
    - Use descriptive names like "GeoGLAM_Feb2025" or "CropMonitor_Jan2025"

---

## Tips and Troubleshooting

### Connection Issues
- **Error connecting to server**: Verify URL is complete and correct
- **No layers appear**: The item may not have valid data for the specified parameters
- **Slow loading**: Large datasets take time; check your internet speed

### Symbology Issues
- **Layer appears blank**: Apply a color scheme (see Part D)
- **Colors look wrong**: Try different stretch types or color schemes
- **Too bright/dark**: Adjust gamma or use Standard Deviation stretch
- **Data seems clipped**: Change from Percent Clip to Min-Max stretch

### Performance Tips
- Use **JPG** instead of PNG for faster loading (change in Step 3)
- Reduce **transparency** if layers render slowly
- Close unused WMTS connections when not needed
- Zoom to a smaller area before adding new layers

### Data Quality
- Check the **datetime** field in the table to ensure you're using recent data
- Some items may have limited spatial coverage (check **bbox** values)
- Verify the **status** column shows "URL Generated" for all items

---

## Understanding the WMTS URL Components

Each WMTS URL contains several important parameters:

```
https://dev.openveda.cloud/api/raster/collections/{collection}/
WebMercatorQuad/WMTSCapabilities.xml?
tile_format=png&
tile_scale=1&
use_epsg=true&
ids={item_id}&
bbox={minx,miny,maxx,maxy}&
datetime={timestamp}&
assets={asset_type}
```

- **collection**: STAC collection identifier (e.g., `geoglam`)
- **item_id**: Specific dataset identifier (e.g., `CropMonitor_202502`)
- **tile_format**: Image format - `png` (quality) or `jpg` (speed)
- **bbox**: Bounding box coordinates for the data extent
- **datetime**: Temporal information for the dataset
- **assets**: Asset type, typically `cog_default`

---

## Common VEDA Collections

### GeoGLAM Crop Monitor
- **Collection ID**: `geoglam`
- **Data Type**: Crop condition monitoring
- **Temporal Resolution**: Monthly
- **Recommended Color Scheme**: Unique Values or Classification

### Other Collections
Explore additional collections in Step 1 by browsing the STAC API. Popular collections include:
- Environmental monitoring datasets
- Land cover classifications
- Vegetation indices
- Climate variables

---

## Advantages of WMTS Access

✅ **No AWS Credentials Required** - Works without S3 access setup
✅ **No Downloads** - Stream data directly to ArcGIS Pro
✅ **Always Current** - Access latest data from VEDA servers
✅ **Multi-Scale** - Tiles optimize for different zoom levels
✅ **Shareable** - URLs can be shared with colleagues

## Limitations

⚠ **Read-Only** - Cannot download full resolution data
⚠ **Internet Required** - Must be connected to VEDA servers
⚠ **Tile Resolution** - Limited by `tile_scale` parameter
⚠ **Manual Symbology** - Color schemes must be applied manually

---

## Comparison with S3 Tools

| Feature | VEDA_S3_STAC_Tools | VEDA_WMTS_Tools |
|---------|-------------------|-----------------|
| Setup | AWS credentials required | No credentials needed |
| Access Method | Direct S3 file access | Web tile service |
| Data Format | Full resolution COGs | Pre-rendered tiles |
| Offline Use | Yes (after download) | No |
| Speed | Depends on S3 connection | Optimized tiles |
| Best For | Analysis, downloads | Quick visualization |

---

## Additional Resources

- **VEDA STAC API**: https://dev.openveda.cloud/api/stac
- **VEDA Documentation**: https://www.earthdata.nasa.gov/veda
- **ArcGIS Pro WMTS Documentation**: Search ArcGIS Pro help for "WMTS"
- **STAC Specification**: https://stacspec.org/

---

## Troubleshooting Checklist

Before seeking help, verify:

- [ ] WMTS URL was copied completely from the table
- [ ] URL was pasted into "Server URL" field (not layer name field)
- [ ] You're connected to the internet
- [ ] The WMTS URL is valid (test in web browser - should return XML)
- [ ] You've applied a color scheme to the layer (Part D)
- [ ] Layer symbology is set to "Stretch" or appropriate method
- [ ] Layer is not hidden or below other opaque layers
- [ ] Zoom level is appropriate for viewing the data

---

## Support

For issues specific to:
- **VEDA data access**: Contact NASA VEDA team
- **ArcGIS Pro functionality**: Contact Esri support
- **This toolbox**: Check the GitHub repository issues

---

## Version Information

**Toolbox Version**: 1.0
**Compatible with**: ArcGIS Pro 2.8 or later
**VEDA API**: Development and Production environments
**Last Updated**: November 2025

---

## Quick Reference Card

### Essential Workflow
1. **Run Step 1** → Select collection
2. **Run Step 2** → Browse items
3. **Run Step 3** → Generate URLs
4. **Open table** → Copy URL
5. **Catalog pane** → New WMTS Server
6. **Paste URL** → Connect
7. **Drag layer** → Add to map
8. **Apply symbology** → Choose color scheme
9. **Adjust stretch** → Enhance visualization
10. **Save project** → Preserve connections

### Key Shortcuts
- **Ctrl+C** / **Cmd+C**: Copy URL from table
- **Ctrl+V** / **Cmd+V**: Paste URL in dialog
- **F2**: Rename connections in Catalog
- **Right-click layer** → Properties → Symbology

---

## License

See main repository LICENSE file for licensing information.
