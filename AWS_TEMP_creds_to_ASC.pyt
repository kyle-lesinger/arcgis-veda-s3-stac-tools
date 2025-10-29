import arcpy
import os
import requests
import json
import base64
import xml.etree.ElementTree as ET

class Toolbox(object):
    def __init__(self):
        """Create ACS Files with Temporary AWS Credentials"""
        self.label = "AWS Temporary Credentials to ACS"
        self.alias = "aws_temp_to_acs"
        self.tools = [CreateACSFromTempCredentials]

class CreateACSFromTempCredentials(object):
    def __init__(self):
        self.label = "Create ACS from Temporary Credentials"
        self.description = """Creates ACS connection files that properly handle AWS temporary credentials with session tokens.
        
        This tool tries multiple ACS file formats to find one that works with your ArcGIS Pro version."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # API URL
        param0 = arcpy.Parameter(
            displayName="Credential API URL",
            name="api_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param0.value = "https://athykwu6ld.execute-api.us-west-2.amazonaws.com/get-s3-upload-creds"
        params.append(param0)
        
        # API Key
        param1 = arcpy.Parameter(
            displayName="API Key",
            name="api_key",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        params.append(param1)
        
        # Bucket selection
        param2 = arcpy.Parameter(
            displayName="S3 Buckets to Create",
            name="buckets",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
            multiValue=True)
        param2.filter.type = "ValueList"
        param2.filter.list = [
            "nasa-disasters",
            "veda-data-store-dev",
            "veda-data-store",
            "veda-data-store-staging"
        ]
        param2.values = ["veda-data-store-dev"]
        params.append(param2)
        
        # Output folder
        param3 = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        param3.value = arcpy.mp.ArcGISProject("CURRENT").homeFolder
        params.append(param3)
        
        # Region
        param4 = arcpy.Parameter(
            displayName="AWS Region",
            name="region",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param4.value = "us-west-2"
        params.append(param4)
        
        # Method selection
        param5 = arcpy.Parameter(
            displayName="Creation Method",
            name="method",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param5.filter.type = "ValueList"
        param5.filter.list = [
            "All Methods (Recommended)",
            "ArcGIS Tool with Environment",
            "Manual JSON Format",
            "Manual XML Format",
            "Connection String Format"
        ]
        param5.value = "All Methods (Recommended)"
        params.append(param5)
        
        return params

    def execute(self, parameters, messages):
        api_url = parameters[0].valueAsText
        api_key = parameters[1].valueAsText
        buckets = parameters[2].values
        output_folder = parameters[3].valueAsText
        region = parameters[4].valueAsText
        method = parameters[5].valueAsText
        
        messages.addMessage("=== Creating ACS with Temporary Credentials ===")
        
        try:
            # Get credentials from API
            messages.addMessage(f"\nFetching credentials from API...")
            headers = {"api-key": api_key}
            response = requests.get(api_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                messages.addErrorMessage(f"API request failed: {response.status_code}")
                messages.addMessage(f"Response: {response.text}")
                return
                
            creds = response.json()
            access_key = creds.get('AccessKeyId')
            secret_key = creds.get('SecretAccessKey')
            session_token = creds.get('SessionToken')
            expiration = creds.get('Expiration', 'Unknown')
            
            if not all([access_key, secret_key, session_token]):
                messages.addErrorMessage("Missing required credential components")
                return
                
            messages.addMessage("[+] Retrieved temporary credentials")
            messages.addMessage(f"    AccessKey: {access_key[:10]}...")
            messages.addMessage(f"    Has SessionToken: Yes")
            messages.addMessage(f"    Expires: {expiration}")
            
            # Create ACS files for each bucket
            created_files = []
            
            for bucket in buckets:
                messages.addMessage(f"\n--- Creating ACS for bucket: {bucket} ---")
                
                if method == "All Methods (Recommended)":
                    # Try all methods until one works
                    methods = [
                        self.method1_arcgis_with_env,
                        self.method2_manual_json,
                        self.method3_manual_xml,
                        self.method4_connection_string
                    ]
                    
                    for i, create_method in enumerate(methods, 1):
                        try:
                            messages.addMessage(f"\nTrying Method {i}...")
                            acs_file = create_method(bucket, access_key, secret_key, session_token, 
                                                    region, output_folder, messages)
                            if acs_file and os.path.exists(acs_file):
                                # Test if it works
                                if self.test_acs_file(acs_file, bucket, messages):
                                    messages.addMessage(f"[+] Method {i} succeeded!")
                                    created_files.append(acs_file)
                                    break
                                else:
                                    os.remove(acs_file)
                                    messages.addMessage(f"[-] Method {i} created file but test failed")
                        except Exception as e:
                            messages.addMessage(f"[-] Method {i} failed: {str(e)}")
                else:
                    # Use specific method
                    method_map = {
                        "ArcGIS Tool with Environment": self.method1_arcgis_with_env,
                        "Manual JSON Format": self.method2_manual_json,
                        "Manual XML Format": self.method3_manual_xml,
                        "Connection String Format": self.method4_connection_string
                    }
                    create_method = method_map.get(method)
                    if create_method:
                        acs_file = create_method(bucket, access_key, secret_key, session_token, 
                                               region, output_folder, messages)
                        if acs_file and os.path.exists(acs_file):
                            created_files.append(acs_file)
            
            # Summary
            messages.addMessage(f"\n{'='*60}")
            messages.addMessage(f"Created {len(created_files)} ACS file(s)")
            for f in created_files:
                messages.addMessage(f"  - {os.path.basename(f)}")
            
            if created_files:
                messages.addMessage(f"\nIMPORTANT: Credentials expire at {expiration}")
                messages.addMessage("You will need to recreate the ACS files before then")
            else:
                messages.addMessage("\nNo ACS files were successfully created")
                messages.addMessage("Troubleshooting:")
                messages.addMessage("1. Check if your ArcGIS Pro version supports session tokens")
                messages.addMessage("2. Try installing boto3 and using direct S3 access instead")
                messages.addMessage("3. Contact Esri support about temporary credential support")
                
        except Exception as e:
            messages.addErrorMessage(f"Error: {str(e)}")
            import traceback
            messages.addMessage(traceback.format_exc())
    
    def method1_arcgis_with_env(self, bucket, access_key, secret_key, session_token, region, output_folder, messages):
        """Method 1: Use ArcGIS tool with environment variable"""
        messages.addMessage("  Method 1: ArcGIS tool with AWS_SESSION_TOKEN environment")
        
        # Set environment variable
        os.environ['AWS_SESSION_TOKEN'] = session_token
        os.environ['AWS_SECURITY_TOKEN'] = session_token  # Alternative name
        
        try:
            conn_name = f"{bucket}_temp"
            arcpy.management.CreateCloudStorageConnectionFile(
                output_folder,
                conn_name,
                "AMAZON",
                bucket,
                access_key,
                secret_key,
                region
            )
            
            acs_path = os.path.join(output_folder, f"{conn_name}.acs")
            messages.addMessage(f"  Created: {acs_path}")
            return acs_path
            
        finally:
            # Clean up environment
            if 'AWS_SESSION_TOKEN' in os.environ:
                del os.environ['AWS_SESSION_TOKEN']
            if 'AWS_SECURITY_TOKEN' in os.environ:
                del os.environ['AWS_SECURITY_TOKEN']
    
    def method2_manual_json(self, bucket, access_key, secret_key, session_token, region, output_folder, messages):
        """Method 2: Create ACS file manually in JSON format"""
        messages.addMessage("  Method 2: Manual JSON format")
        
        conn_name = f"{bucket}_temp"
        acs_path = os.path.join(output_folder, f"{conn_name}.acs")
        
        # Format 1: Simple JSON
        acs_content = {
            "version": "1.0",
            "type": "CloudStore", 
            "cloudStoreType": "AMAZON",
            "connectionProperties": {
                "bucketName": bucket,
                "region": region,
                "accessKeyId": access_key,
                "secretAccessKey": secret_key,
                "sessionToken": session_token
            },
            "name": conn_name
        }
        
        with open(acs_path, 'w', encoding='utf-8') as f:
            json.dump(acs_content, f, indent=2)
        
        messages.addMessage(f"  Created: {acs_path}")
        return acs_path
    
    def method3_manual_xml(self, bucket, access_key, secret_key, session_token, region, output_folder, messages):
        """Method 3: Create ACS file in XML format"""
        messages.addMessage("  Method 3: Manual XML format")
        
        conn_name = f"{bucket}_temp"
        acs_path = os.path.join(output_folder, f"{conn_name}.acs")
        
        # Create XML structure
        root = ET.Element("AmazonS3Connection")
        ET.SubElement(root, "Name").text = conn_name
        ET.SubElement(root, "BucketName").text = bucket
        ET.SubElement(root, "Region").text = region
        ET.SubElement(root, "AccessKeyId").text = access_key
        ET.SubElement(root, "SecretAccessKey").text = secret_key
        ET.SubElement(root, "SessionToken").text = session_token
        ET.SubElement(root, "AuthenticationType").text = "TEMPORARY"
        
        # Pretty print XML
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        
        with open(acs_path, 'wb') as f:
            tree.write(f, encoding='utf-8', xml_declaration=True)
        
        messages.addMessage(f"  Created: {acs_path}")
        return acs_path
    
    def method4_connection_string(self, bucket, access_key, secret_key, session_token, region, output_folder, messages):
        """Method 4: Connection string format"""
        messages.addMessage("  Method 4: Connection string format")
        
        conn_name = f"{bucket}_temp"
        acs_path = os.path.join(output_folder, f"{conn_name}.acs")
        
        # Build connection string
        conn_str = f"PROVIDER=AMAZON;BUCKET={bucket};REGION={region};"
        conn_str += f"ACCESS_KEY_ID={access_key};SECRET_ACCESS_KEY={secret_key};"
        conn_str += f"SESSION_TOKEN={session_token};AUTH_TYPE=TEMPORARY"
        
        # Encode as base64 (some versions use this)
        conn_str_b64 = base64.b64encode(conn_str.encode()).decode()
        
        acs_content = {
            "version": "2.0",
            "cloudStore": {
                "type": "S3",
                "connectionString": conn_str,
                "connectionStringEncoded": conn_str_b64,
                "name": conn_name
            }
        }
        
        with open(acs_path, 'w', encoding='utf-8') as f:
            json.dump(acs_content, f, indent=2)
        
        messages.addMessage(f"  Created: {acs_path}")
        return acs_path
    
    def test_acs_file(self, acs_path, bucket, messages):
        """Test if the ACS file works"""
        try:
            # Simple test - try to access the root of the bucket
            test_path = acs_path + "\\"
            if arcpy.Exists(test_path):
                messages.addMessage("  [+] ACS file test passed")
                return True
            else:
                messages.addMessage("  [-] ACS file test failed - cannot access bucket")
                return False
        except Exception as e:
            messages.addMessage(f"  [-] ACS file test error: {str(e)}")
            return False
