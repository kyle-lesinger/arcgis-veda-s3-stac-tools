# VEDA STAC Data Access: Implementation Documentation

## Executive Summary

This document details the  implementation of two ArcGIS Pro Python toolboxes developed to access NASA VEDA (Visualization, Exploration, and Data Analysis) STAC collection data from non-public AWS S3 buckets. These solutions circumvent limitations in ArcGIS Pro's native STAC and Cloud Storage connection capabilities.

**Toolboxes:**
- **VEDA_S3_STAC_Tools.pyt** - For users with permanent AWS credentials
- **STAC_Browser_boto3.pyt** - For users given credential API token (no AWS account needed)

---

## 1. Introduction: The Challenge

### 1.1 Problem Statement

The goal was to enable ArcGIS Pro users to access and analyze VEDA STAC collection data stored in non-public AWS S3 buckets. While ArcGIS Pro provides built-in capabilities for both STAC connections and Cloud Storage connections, several critical limitations prevented their use:

1. **STAC Connection Limitations:**
   - ArcGIS Pro's STAC connection interface requires selecting "Microsoft Planetary Computer" as the connection type
   - According to [Esri's documentation](https://www.esri.com/arcgis-blog/products/arcgis-pro/imagery/looking-for-an-alternative-to-the-microsoft-planetary-computer-hub-2), this is an Azure-specific template designed for Microsoft's Planetary Computer platform
   - Current STAC connection support in ArcGIS Pro appears limited to publicly accessible data within the Microsoft Planetary Computer ecosystem
   - No native option exists for connecting to custom STAC APIs with authenticated S3 backends

2. **Cloud Store Connection Limitations:**
   - While ArcGIS can create Cloud Store connection files (.acs) for AWS S3 buckets with proper credentials, these .acs files cannot be integrated into ArcGIS STAC connections for authenticated data access
   - Attempting to add a Cloud Store connection to a VEDA STAC connection fails because VEDA STAC and S3 access is not within the Microsoft Planetary Computer scope
   - The authentication model for STAC connections does not support custom AWS credential-based access

3. **Authentication Mismatch:**
   - VEDA data resides in non-public S3 buckets requiring AWS authentication
   - ArcGIS Pro's STAC implementation expects public data or Azure-specific authentication
   - No mechanism exists to link AWS credentials to STAC item retrieval

### 1.2 Solution Overview

To overcome these limitations, two alternative approaches were developed that bypass ArcGIS Pro's native STAC connection interface:

1. **VEDA_S3_STAC_Tools.pyt**: Direct STAC API querying with .acs-based S3 access for permanent credentials
2. **STAC_Browser_boto3.pyt**: STAC API querying with boto3-based downloads for temporary SSO credentials

Both solutions query the VEDA STAC API directly via HTTP requests and handle S3 authentication independently from ArcGIS Pro's connection framework.

---

## 2. Solution 1: VEDA_S3_STAC_Tools.pyt

### 2.1 Overview

**Purpose:** Enable users with permanent AWS Access Key ID and Secret Access Key to browse VEDA STAC collections and access data through ArcGIS Cloud Storage connections.

**Target Users:** Developers, researchers, or organizations with permanent AWS IAM credentials for VEDA buckets.

**Limitation:** Becomes ineffective when organizations transition to AWS SSO (Single Sign-On) authentication, which only provides temporary credentials without permanent access keys.

### 2.2 Architecture

The toolbox implements a three-step workflow plus an alternative download method:

```
Step 1: Create VEDA S3 Connection
    ↓ (Creates .acs files)
Step 2: Browse STAC Collection
    ↓ (Queries STAC API, creates table)
Step 3: Add S3 Raster to Map
    ↓ (Uses .acs files to stream/copy data)

Alternative: Download STAC Item via API
    (Bypasses S3 entirely)
```

### 2.3 Technical Implementation

#### 2.3.1 Step 1: Create VEDA S3 Connection (`Step1_CreateVEDAConnection`)

**Purpose:** Generate ArcGIS Cloud Storage (.acs) connection files for VEDA S3 buckets.

**Process:**
1. Reads AWS credentials from `~/.aws/credentials` file (Windows: `C:\Users\[username]\.aws\credentials`)
2. Parses INI-formatted credentials using Python's `configparser` module
3. Validates that the specified AWS profile exists
4. Calls `arcpy.management.CreateCloudStorageConnectionFile()` for each selected environment
5. Creates .acs files with embedded credentials for specific STAC environments (dev, staging, or production)

**Key Technical Details:**
- **Region:** All VEDA buckets are in `us-west-2`
- **Provider:** Amazon S3 (`"AMAZON"` parameter)
- **Credentials Format:** Uses AWS Signature Version 4 authentication
- **Output:** `.acs` files stored in the project's home folder

**Code Flow:**
```python
# Read credentials from standard AWS location
creds_path = os.path.join(os.path.expanduser("~"), ".aws", "credentials")
creds = configparser.ConfigParser()
creds.read(creds_path)

# Create connection for each bucket
arcpy.management.CreateCloudStorageConnectionFile(
    output_folder,
    connection_name,
    "AMAZON",                                    # Provider
    bucket_name,                                 # e.g., "veda-data-store-dev"
    creds[profile]['aws_access_key_id'],        # From credentials file
    creds[profile]['aws_secret_access_key'],    # From credentials file
    "us-west-2"                                  # Region
)
```

#### 2.3.2 Step 2: Browse STAC Collection (`Step2_BrowseSTACCollection`)

**Purpose:** Query VEDA STAC API to discover available data and create a searchable table of S3 paths.

**Process:**
1. **Collection Discovery:**
   - Queries STAC API endpoint: `{stac_url}/collections?limit=50`
   - Implements pagination to retrieve all collections (up to 20 pages)
   - Follows STAC API `next` links in the response
   - Populates dropdown with collection IDs and titles

2. **Item Retrieval:**
   - Queries selected collection: `{stac_url}/collections/{collection}/items?limit={limit}`
   - Parses STAC GeoJSON response
   - Extracts S3 URLs from asset `href` fields

3. **Table Creation:**
   - Creates ArcGIS table using `arcpy.management.CreateTable()`
   - Adds fields for metadata storage:
     - `item_id`: STAC item identifier
     - `datetime`: Acquisition timestamp
     - `s3_href`: Full S3 URL (e.g., `s3://veda-data-store-dev/path/to/file.tif`)
     - `asset_type`: Asset name (e.g., `cog_default`)
     - `collection`: Collection identifier
     - `bucket`: Extracted S3 bucket name

4. **Data Population:**
   - Iterates through STAC features
   - Filters assets containing `s3://` URLs
   - Inserts rows using `arcpy.da.InsertCursor`

**STAC API Endpoints:**
- Production: `https://openveda.cloud/api/stac`
- Development: `https://dev.openveda.cloud/api/stac`

**Technical Notes:**
- Uses `requests` library for HTTP communication
- Implements error handling for network failures
- Supports STAC pagination via `rel=next` links
- Extracts bucket name by parsing S3 URL structure

#### 2.3.3 Step 3: Add S3 Raster to Map (`Step3_AddS3ToMap`)

**Purpose:** Add raster data from S3 to the active ArcGIS Pro map using .acs connections.

**Process:**
1. **Path Resolution:**
   - Retrieves selected item from browse results table
   - Extracts S3 URL (format: `s3://bucket-name/path/to/file.tif`)
   - Parses bucket and relative path components

2. **ACS File Matching:**
   - Scans project folder for `.acs` files created in Step 1
   - Matches bucket name to appropriate .acs file:
     - `veda-data-store-dev` → `*dev*.acs`
     - `veda-data-store` → `*prod*.acs`
     - `veda-data-store-staging` → `*staging*.acs`

3. **Path Construction:**
   - Converts S3 URL to ACS path format
   - Replaces forward slashes with Windows backslashes
   - Builds path: `C:\path\to\connection.acs\relative\path\to\file.tif`

4. **Environment Variable Setup:**
   - Sets AWS credentials in environment for GDAL/ArcGIS subsystems:
     ```python
     os.environ['AWS_ACCESS_KEY_ID'] = creds['uah-veda']['aws_access_key_id']
     os.environ['AWS_SECRET_ACCESS_KEY'] = creds['uah-veda']['aws_secret_access_key']
     os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
     ```

5. **Data Addition:**
   - **Direct Streaming:** Calls `map_obj.addDataFromPath(acs_path)` to stream from S3
   - **Local Copy Option:** Uses `arcpy.management.CopyRaster()` to download first, then adds local copy

**Authentication Model:**
- ACS files contain encrypted credential information
- ArcGIS Pro's raster subsystem uses these credentials for S3 access
- Environment variables provide backup authentication for GDAL operations
- Uses AWS Signature Version 4 for S3 request signing

**Error Handling:**
- **403/Credentials Error:** Suggests recreating .acs files or using local copy
- **404/Does Not Exist:** Indicates file may have been removed from S3
- **Failed to Add Data:** Recommends enabling "Copy to Local" option

#### 2.3.4 Alternative: Download STAC Item via API (`Alternative_DownloadSTACItem`)

**Purpose:** Download raster data through VEDA's Raster API when S3 access fails.

**Process:**
1. Constructs download URL using VEDA's COG (Cloud-Optimized GeoTIFF) API
2. URL format: `{api_url}/raster/cog/collections/{collection}/items/{item_id}?assets=cog_default`
3. Downloads via HTTP GET with streaming response
4. Saves to scratch folder: `arcpy.env.scratchFolder/{item_id}.tif`
5. Optionally adds downloaded file to map

**Use Cases:**
- S3 credentials are unavailable or expired
- .acs connection fails
- User needs permanent local copy
- STAC item references non-existent S3 file but API has cached version

**Technical Details:**
- Uses `requests.get(stream=True)` for memory-efficient downloads
- Implements chunked download (8KB chunks)
- Displays progress every 10MB
- Does not require AWS credentials (uses VEDA API authentication)

### 2.4 Limitations

1. **Permanent Credentials Required:**
   - Solution depends on permanent AWS Access Key ID and Secret Access Key
   - Does not support temporary credentials or session tokens
   - Incompatible with AWS SSO authentication workflows

2. **Credential Expiration:**
   - If credentials expire or are rotated, .acs files must be recreated
   - No automatic credential refresh mechanism

3. **Security Concerns:**
   - Credentials stored in plaintext in `~/.aws/credentials`
   - .acs files contain embedded credentials (Esri uses encryption, but files should be protected)

4. **Manual Workflow:**
   - Three-step process required for each data access operation
   - Browse results table becomes outdated as STAC catalog updates

---

## 3. Solution 2: STAC_Browser_boto3.pyt

### 3.1 Overview

**Purpose:** Enable users with AWS SSO temporary credentials to browse VEDA STAC collections and download data using boto3.

**Target Users:** Organizations using AWS SSO with temporary credential generation via Lambda functions.

**Key Advantage:** Handles temporary credentials with session tokens that expire after one hour.

### 3.2 Architecture

The toolbox implements a two-step workflow:

```
Step 1: Install boto3
    ↓ (Ensures boto3 package is available)
Step 2: Browse STAC with boto3
    ↓ (Retrieves temp credentials → Downloads via boto3)
```

### 3.3 Technical Implementation

#### 3.3.1 Step 1: Install boto3 (`InstallBoto3`)

**Purpose:** Ensure boto3 library is installed in ArcGIS Pro's Python environment.

**Process:**
1. Checks if boto3 is already available via `import boto3`
2. If not found, attempts installation via pip:
   ```python
   subprocess.run([python_exe, "-m", "pip", "install", "boto3"])
   ```
3. Falls back to conda if pip fails:
   ```python
   subprocess.run([conda_exe, "install", "-y", "boto3"])
   ```
4. Verifies installation by importing and checking version

**Why boto3 is Required:**
- ArcGIS Pro's default Python environment doesn't include boto3
- boto3 is AWS's official Python SDK for S3 operations
- Provides native support for temporary credentials with session tokens
- Handles AWS Signature Version 4 authentication automatically

**Technical Notes:**
- **Environment Cloning Required:** ArcGIS Pro's default Python environment is read-only and managed by Esri. To install boto3, the ArcGIS Pro Python environment must first be cloned to create a writable copy. This is done through ArcGIS Pro's Python Package Manager (Project → Python → Manage Environments → Clone Default).
- Runs in the cloned ArcGIS Pro Python environment (`sys.executable`)
- May require administrator privileges
- Users may need to restart ArcGIS Pro after installation

#### 3.3.2 Step 2: Browse STAC with boto3 (`BrowseSTACWithBoto3`)

**Purpose:** Query STAC API and download data using temporary AWS credentials retrieved from a Lambda function.

**Process:**

1. **Retrieve Temporary Credentials:**
   - Calls AWS Lambda API endpoint via HTTP GET
   - Endpoint: `https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds`
   - Includes API key in request headers: `{"api-key": api_key}`
   - Response contains temporary credentials:
     ```json
     {
       "AccessKeyId": "ASIA...",
       "SecretAccessKey": "...",
       "SessionToken": "...",
       "Expiration": "2025-11-10T15:30:00Z"
     }
     ```

2. **Create boto3 Session:**
   - Initializes boto3 session with all three credential components:
     ```python
     session = boto3.Session(
         aws_access_key_id=access_key,
         aws_secret_access_key=secret_key,
         aws_session_token=session_token,  # Required for temporary credentials
         region_name='us-west-2'
     )
     ```
   - Creates S3 client with Signature Version 4:
     ```python
     s3 = session.client('s3', config=Config(signature_version='s3v4'))
     ```

3. **Query STAC Collection:**
   - Queries STAC API identically to Solution 1
   - Endpoint: `{stac_url}/collections/{collection}/items?limit={limit}`
   - Parses STAC GeoJSON response
   - Extracts S3 URLs from assets

4. **Download Files via boto3:**
   - For each S3 asset (`s3://bucket/path/to/file.tif`):
     - Parses bucket name and key
     - Downloads using boto3:
       ```python
       s3.download_file(bucket, key, local_file)
       ```
     - Saves to: `arcpy.env.scratchFolder/stac_downloads/`
   - Sanitizes filenames for Windows (removes invalid characters: `<>:"|?*`)

5. **Add to Map:**
   - If "Add to Map" option is enabled
   - Adds downloaded local files via `map_obj.addDataFromPath(local_file)`

**Authentication Flow:**
```
Lambda API → Temporary Credentials (1 hour expiry)
    ↓
boto3 Session (with session token)
    ↓
S3 Client (Signature V4 signing)
    ↓
download_file() → Authenticated S3 GET request
```

### 3.4 Key Differences from Solution 1

| Aspect | Solution 1 (Permanent Creds) | Solution 2 (Temporary Creds) |
|--------|------------------------------|------------------------------|
| **Credential Source** | `~/.aws/credentials` file | Lambda API endpoint |
| **Credential Type** | Permanent access key/secret | Temporary with session token |
| **Session Token** | Not used | Required |
| **Credential Lifetime** | Permanent (until rotated) | ~1 hour |
| **S3 Access Method** | ArcGIS .acs files + streaming | boto3 direct download |
| **Data Location** | Can stream from S3 | Downloads to local disk |
| **ArcGIS Integration** | Native raster layer from S3 | Adds downloaded local files |
| **Credential Refresh** | Manual recreation | New API call per session |

### 3.5 Advantages

1. **SSO Compatibility:** Works with AWS SSO temporary credential workflows
2. **Secure:** Credentials expire after one hour, reducing exposure window
3. **No Credential Files:** No need to manage `~/.aws/credentials`
4. **Direct Download:** Uses boto3's robust download mechanism
5. **Error Handling:** boto3 provides detailed S3 error messages

### 3.6 Limitations

1. **Download Required:** Cannot stream data; must download entire files
2. **Disk Space:** Large files consume local storage
3. **Time-Limited:** Credentials expire after ~1 hour; users must re-run for new session
4. **API Dependency:** Requires Lambda endpoint to be available
5. **Single Collection:** Downloads all items sequentially (no batch selection)
6. **No .acs Benefits:** Cannot leverage ArcGIS Pro's native S3 streaming capabilities

---

## 4. Technical Comparison

### 4.1 Workflow Comparison

**Solution 1: VEDA_S3_STAC_Tools.pyt**
```
User Action                     → System Behavior
────────────────────────────────────────────────────────────────
Create Connection (Step 1)      → Read ~/.aws/credentials
                                → Create .acs files with embedded credentials
Browse STAC (Step 2)            → HTTP GET to STAC API
                                → Parse JSON response
                                → Create ArcGIS table with S3 URLs
Add to Map (Step 3)             → Match S3 bucket to .acs file
                                → Construct .acs path
                                → Stream or copy from S3
                                → Add to map as raster layer
```

**Solution 2: STAC_Browser_boto3.pyt**
```
User Action                     → System Behavior
────────────────────────────────────────────────────────────────
Install boto3 (Step 1)          → pip install boto3
Browse & Download (Step 2)      → HTTP GET to Lambda API
                                → Receive temp credentials + session token
                                → Create boto3 session
                                → HTTP GET to STAC API
                                → Parse JSON response
                                → For each S3 asset:
                                    - boto3 s3.download_file()
                                    - Add local file to map
```

### 4.2 Authentication Mechanisms

**Solution 1: AWS Signature V4 via .acs Files**
```
Request Flow:
ArcGIS Pro → .acs file (credentials) → GDAL/S3 driver → AWS S3
                                       ↓
                            AWS Signature V4 signing
                            (access key + secret key)
```

**Solution 2: AWS Signature V4 via boto3**
```
Request Flow:
boto3 session → STS credentials (access + secret + session token)
                ↓
           boto3 S3 client → AWS Signature V4 signing
                ↓
           Authenticated GET request → AWS S3
```

### 4.3 When to Use Each Solution

| Use Case | Recommended Solution | Rationale |
|----------|---------------------|-----------|
| Permanent AWS credentials | Solution 1 | Can leverage streaming, .acs integration |
| AWS SSO with temporary credentials | Solution 2 | Only option that supports session tokens |
| Large files, good bandwidth | Solution 1 (streaming) | Avoid local disk usage |
| Intermittent connection | Solution 2 | Downloads persist offline |
| Frequent credential rotation | Solution 2 | Designed for temporary credentials |
| Multiple users sharing credentials | Neither | Consider Raster API (see Section 5) |
| Production environment | Solution 2 | More secure with expiring credentials |

---

## 5. Next Steps and Future Improvements

### 5.1 Current Limitations

Both solutions have significant limitations that should be addressed:

1. **Solution 1 becomes obsolete** when AWS SSO is enforced (no permanent keys)
2. **Solution 2 requires downloading** entire datasets (cannot stream)
3. **Neither solution integrates** with ArcGIS Pro's native STAC connections
4. **Manual workflows** require multiple steps per data access
5. **Credential management** is cumbersome or short-lived

### 5.2 Potential Improvement: VEDA Raster API

**Description:** VEDA provides a Raster API that can serve tiles and statistics without direct S3 access.

**Endpoint:** `https://dev.openveda.cloud/api/raster/docs`

**Example Use Cases:**
- Retrieve raster statistics: `https://dev.openveda.cloud/api/raster/cog/statistics`
- Retrieve tiles for visualization
- Query data without AWS credentials

**Current Limitation:**
- The Raster API **cannot directly return raw data values**
- API returns **tiles** (rendered images) or **statistics** (min/max/mean)
- Not suitable for analytical workflows requiring pixel-level access
- May be sufficient for visualization-only use cases

**Investigation Needed:**
- Determine if Raster API can be extended to return raw values
- Explore authentication options for Raster API
- Test performance for large-scale tile requests
- Evaluate if tiles can be mosaicked into usable rasters

### 5.3 Potential Improvement: Enhanced S3 Streaming

**Description:** Attempt to enable streaming from S3 without downloading, using GDAL's virtual file systems.

**Approaches Tested (Unsuccessful):**
1. **GDAL /vsis3/ protocol:**
   - GDAL supports streaming from S3 via `/vsis3/bucket/path/file.tif`
   - Requires AWS credentials in environment variables
   - **Issue:** GDAL's `/vsis3/` does not properly handle temporary credentials with session tokens
   - Error: Authentication fails when `AWS_SESSION_TOKEN` is set

2. **Rasterio with S3 URIs:**
   - Rasterio can read from S3 URLs directly
   - Built on GDAL, inherits same credential limitations
   - **Issue:** Same session token compatibility problems

**Further Investigation Needed:**
- Test latest GDAL versions (3.8+) for improved session token support
- Investigate custom GDAL configuration options
- Explore boto3-based GDAL credential provider plugins
- Consider creating custom ArcGIS raster format adapter

**Potential Solutions:**
```python
# Approach 1: GDAL environment variables
os.environ['AWS_ACCESS_KEY_ID'] = access_key
os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
os.environ['AWS_SESSION_TOKEN'] = session_token
os.environ['AWS_REGION'] = 'us-west-2'

# Open via GDAL virtual file system
vsi_path = f'/vsis3/veda-data-store-dev/path/to/file.tif'
dataset = gdal.Open(vsi_path)

# Approach 2: Signed URLs
# Generate pre-signed URL with boto3, valid for limited time
presigned_url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': bucket, 'Key': key},
    ExpiresIn=3600  # 1 hour
)
# Open via HTTP (may work in ArcGIS Pro)
dataset = arcpy.Raster(presigned_url)
```

### 5.4 Recommended Research Areas

1. **Pre-Signed URL Approach:**
   - Use boto3 to generate temporary pre-signed URLs (valid 1-15 minutes)
   - Pass HTTPS URLs to ArcGIS Pro instead of S3 paths
   - ArcGIS may be able to open HTTPS raster URLs directly
   - Avoids need for .acs files or credential management
   - **Test:** `arcpy.Raster("https://signed-url...")` compatibility

2. **Custom ArcGIS Raster Connector:**
   - Develop ArcGIS raster format plugin
   - Implement custom authentication layer for temporary credentials
   - Integrate with boto3 for credential refresh
   - Would enable native ArcGIS Pro streaming with SSO credentials

3. **VEDA API Enhancement Request:**
   - Contact VEDA team to request raw data access endpoint
   - Propose `/api/raster/cog/values` endpoint for pixel value retrieval
   - Could accept bounding box and return GeoTIFF or array
   - Would bypass S3 credential requirements entirely

4. **STS Credential Refresh:**
   - Implement automatic credential refresh in toolbox
   - Background thread to call Lambda API before expiration
   - Update boto3 session and environment variables
   - Enable long-running analysis sessions

5. **ArcGIS Pro Extension:**
   - Package toolboxes as ArcGIS Pro Add-In
   - Provide GUI for credential management
   - Integrate STAC browser into ArcGIS Pro catalog
   - Add background task for automatic downloads

### 5.5 Alternative: Cloud-Native Analysis

**Description:** Perform analysis in cloud environment instead of downloading to ArcGIS Pro.

**Approaches:**
- Use Jupyter notebooks with xarray/rasterio in AWS environment
- Process data in S3 without moving it
- Export only analysis results to ArcGIS Pro
- Leverage AWS compute resources for large datasets

**Tools:**
- AWS SageMaker for analysis notebooks
- Pangeo stack (xarray, dask, rasterio)
- GDAL Python bindings in EC2
- Results exported as small GeoTIFFs or vector layers

---

## 6. Conclusion

Two functional workarounds have been implemented to access VEDA STAC data from ArcGIS Pro, circumventing limitations in ArcGIS Pro's native STAC connection capabilities:

1. **VEDA_S3_STAC_Tools.pyt**: Suitable for users with permanent AWS credentials, leveraging .acs files for streaming or downloading
2. **STAC_Browser_boto3.pyt**: Required for AWS SSO users, using boto3 for authenticated downloads with temporary credentials

Both solutions successfully enable data access but have notable limitations:
- Solution 1 becomes unusable when organizations migrate to SSO
- Solution 2 requires downloading data instead of streaming
- Neither integrates with ArcGIS Pro's native workflows

**Future work should focus on:**

1. Investigating pre-signed URL approaches for credential-free HTTP access
2. Testing enhanced GDAL session token support
3. Requesting VEDA API enhancements for raw data access
4. Developing custom ArcGIS Pro extensions for improved integration

These implementations serve as interim solutions while awaiting either ArcGIS Pro improvements for custom STAC endpoints or VEDA API enhancements for direct data access.


