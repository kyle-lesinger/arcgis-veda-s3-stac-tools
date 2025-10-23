\# VEDA S3 STAC Tools for ArcGIS Pro



A Python toolbox for ArcGIS Pro that enables direct access to NASA VEDA (Visualization, Exploration, and Data Analysis) STAC data through S3, eliminating the need to download large raster datasets.



\## Overview



This toolbox provides a streamlined workflow for:

\- Creating AWS S3 connections to VEDA data buckets

\- Browsing VEDA STAC collections and items

\- Adding cloud-optimized GeoTIFFs (COGs) directly to ArcGIS Pro maps

\- Downloading data through VEDA's API when S3 access fails



\## Features



\- \*\*Direct S3 Access\*\*: Stream rasters directly from S3 without downloading

\- \*\*STAC Integration\*\*: Browse and search VEDA's STAC catalogs

\- \*\*Multiple Environments\*\*: Support for production, development, and staging VEDA environments

\- \*\*Credential Management\*\*: Automated AWS credential handling

\- \*\*Error Recovery\*\*: Alternative download method via VEDA API

\- \*\*User-Friendly\*\*: Step-by-step workflow with helpful error messages



\## Prerequisites



1\. \*\*ArcGIS Pro\*\* (version 3.0 or higher recommended)

2\. \*\*AWS Credentials\*\* with access to VEDA buckets

3\. \*\*Python packages\*\* (included with ArcGIS Pro):

&nbsp;  - arcpy

&nbsp;  - requests

&nbsp;  - configparser



\## Installation



1\. Download `VEDA\_S3\_STAC\_Tools.pyt` from this repository

2\. In ArcGIS Pro:

&nbsp;  - Open the Catalog pane

&nbsp;  - Right-click on \*\*Toolboxes\*\*

&nbsp;  - Select \*\*Add Toolbox\*\*

&nbsp;  - Browse to and select `VEDA\_S3\_STAC\_Tools.pyt`



\## AWS Credential Setup



Before using the toolbox, configure your AWS credentials:



1\. Create the AWS directory:

```

&nbsp;  C:\\Users\\\[your-username]\\.aws\\

```



2\. Create a file named `credentials` (no extension) with:

```ini

&nbsp;  \[default]

&nbsp;  aws\_access\_key\_id = YOUR\_ACCESS\_KEY

&nbsp;  aws\_secret\_access\_key = YOUR\_SECRET\_KEY



&nbsp;  \[uah-veda]

&nbsp;  aws\_access\_key\_id = YOUR\_VEDA\_ACCESS\_KEY

&nbsp;  aws\_secret\_access\_key = YOUR\_VEDA\_SECRET\_KEY

```



3\. Create a file named `config` with:

```ini

&nbsp;  \[default]

&nbsp;  region = us-west-2



&nbsp;  \[profile uah-veda]

&nbsp;  region = us-west-2

```



\## Usage



The toolbox follows a three-step workflow:



\### Step 1: Create VEDA S3 Connection

Creates ACS (ArcGIS Cloud Storage) connection files for accessing S3 buckets.



\- Select environment(s): Production, Development, Staging, or All

\- Specify your AWS profile name

\- Choose output folder for .acs files



\### Step 2: Browse STAC Collection

Queries VEDA STAC API to discover available data.



\- Select STAC API URL (production or development)

\- Choose a collection from the dropdown

\- Specify number of items to retrieve

\- Creates a table with S3 paths



\### Step 3: Add S3 Raster to Map

Adds selected rasters to your current map.



\- Select "From Browse Results" and choose your table from Step 2

\- Pick an item from the dropdown

\- Optional: Enable "Copy to Local" for more stable access

\- Click OK to add to map



\### Alternative: Download STAC Item via API

Use when S3 access fails or you need a permanent local copy.



\- Enter collection ID and item ID

\- Downloads through VEDA's REST API

\- Automatically adds to map



\## Common Issues and Solutions



\### "Failed to add data. Possible credentials issue"

\- Ensure your AWS credentials are correctly configured

\- Try enabling "Copy to Local" option

\- Verify your account has access to the VEDA bucket



\### "Dataset does not exist or is not supported"

\- The file may not exist in S3 (check date ranges)

\- Some STAC items reference removed files

\- Use the Alternative Download tool



\### "No ACS file found for bucket"

\- Run Step 1 to create ACS connections

\- Ensure you selected the correct environment



\### Performance Issues

\- Enable "Copy to Local" for large files

\- Check your internet connection speed

\- Consider downloading frequently-used data



\## VEDA Environments



\- \*\*Production\*\*: https://openveda.cloud/api/stac

\- \*\*Development\*\*: https://dev.openveda.cloud/api/stac

\- \*\*S3 Buckets\*\*:

&nbsp; - Production: `veda-data-store`

&nbsp; - Development: `veda-data-store-dev`

&nbsp; - Staging: `veda-data-store-staging`



\## Technical Details



The toolbox uses:

\- \*\*ArcGIS Cloud Storage (.acs)\*\* files for S3 authentication

\- \*\*STAC API\*\* for data discovery

\- \*\*GDAL/VSICURL\*\* for cloud-optimized GeoTIFF access

\- \*\*AWS Signature Version 4\*\* for S3 authentication



\## Limitations



\- Direct S3 streaming requires stable internet connection

\- Some older ArcGIS Pro versions may have S3 compatibility issues

\- Cross-account S3 access can be problematic with assumed roles

\- Large rasters may be slow to display when streaming



\## Contributing



Issues and pull requests are welcome. Please test any changes with multiple VEDA collections before submitting.



\## License



This toolbox is provided as-is for accessing public NASA VEDA data. Users are responsible for complying with VEDA's data use policies and AWS terms of service.



\## Acknowledgments



Developed for use with NASA's VEDA (Visualization, Exploration, and Data Analysis) platform. Special thanks to the VEDA team for providing STAC-compliant data access.



\## Support



For VEDA data questions: https://www.earthdata.nasa.gov/esds/veda  

For toolbox issues: Submit an issue on this GitHub repository

