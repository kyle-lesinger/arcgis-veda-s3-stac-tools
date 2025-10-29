import arcpy
import os
import subprocess
import json
import configparser

class CreateACSFromProfile(object):
    """Step 2: Create ACS files from AWS profile in credentials file"""
    
    def __init__(self):
        self.label = "Step 2: Create ACS from AWS Profile"
        self.description = """Reads credentials from ~/.aws/credentials profile and creates ACS files
        
        Uses the profile created in Step 1 to get temporary credentials."""
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []
        
        # Profile Name dropdown - populate with available profiles
        param0 = arcpy.Parameter(
            displayName="AWS Profile",
            name="profile_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        
        # Try to read available profiles
        creds_path = os.path.join(os.path.expanduser("~"), ".aws", "credentials")
        if os.path.exists(creds_path):
            config = configparser.ConfigParser()
            config.read(creds_path)
            profiles = config.sections()
            if profiles:
                param0.filter.type = "ValueList"
                param0.filter.list = profiles
                # Default to nasa-disasters-temp-creds if available
                if "nasa-disasters-temp-creds" in profiles:
                    param0.value = "nasa-disasters-temp-creds"
                else:
                    param0.value = profiles[0]
        else:
            param0.value = "nasa-disasters-temp-creds"
        params.append(param0)
        
        # S3 Bucket selection
        param1 = arcpy.Parameter(
            displayName="S3 Bucket",
            name="bucket_selection",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.filter.type = "ValueList"
        param1.filter.list = [
            "NASA Disasters (nasa-disasters)",
            "VEDA Production (veda-data-store)",
            "VEDA Development (veda-data-store-dev)",
            "VEDA Staging (veda-data-store-staging)",
            "All VEDA Buckets",
            "Custom"
        ]
        param1.value = "NASA Disasters (nasa-disasters)"
        params.append(param1)
        
        # Custom bucket name
        param2 = arcpy.Parameter(
            displayName="Custom Bucket Name",
            name="custom_bucket",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
            enabled=False)
        params.append(param2)
        
        # Connection name prefix
        param3 = arcpy.Parameter(
            displayName="Connection Name Prefix",
            name="connection_prefix",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param3.value = "nasa-disasters"
        params.append(param3)
        
        # Output folder
        param4 = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
        param4.value = arcpy.mp.ArcGISProject("CURRENT").homeFolder
        params.append(param4)
        
        # AWS Region (will be read from config)
        param5 = arcpy.Parameter(
            displayName="AWS Region",
            name="aws_region",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        param5.value = "us-west-2"
        params.append(param5)
        
        return params

    def updateParameters(self, parameters):
        # Enable custom bucket field if Custom selected
        if parameters[1].value == "Custom":
            parameters[2].enabled = True
        else:
            parameters[2].enabled = False
            
        # Try to read region from profile config
        profile_name = parameters[0].value
        if profile_name:
            config_path = os.path.join(os.path.expanduser("~"), ".aws", f"{profile_name}_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        if 'region' in config:
                            parameters[5].value = config['region']
                except:
                    pass

    def execute(self, parameters, messages):
        profile_name = parameters[0].valueAsText
        bucket_selection = parameters[1].valueAsText
        custom_bucket = parameters[2].valueAsText
        connection_prefix = parameters[3].valueAsText
        output_folder = parameters[4].valueAsText
        aws_region = parameters[5].valueAsText
        
        messages.addMessage("=== Step 2: Create ACS from AWS Profile ===")
        messages.addMessage(f"Profile: {profile_name}")
        messages.addMessage(f"Region: {aws_region}")
        
        # Read credentials file to get the credential_process command
        creds_path = os.path.join(os.path.expanduser("~"), ".aws", "credentials")
        if not os.path.exists(creds_path):
            messages.addErrorMessage("AWS credentials file not found")
            messages.addMessage("Please run Step 1 first")
            return
            
        config = configparser.ConfigParser()
        config.read(creds_path)
        
        if profile_name not in config:
            messages.addErrorMessage(f"Profile [{profile_name}] not found in credentials")
            messages.addMessage(f"Available profiles: {', '.join(config.sections())}")
            return
            
        # Get the credential_process command
        if 'credential_process' not in config[profile_name]:
            messages.addErrorMessage(f"Profile [{profile_name}] doesn't have credential_process")
            return
            
        cred_process = config[profile_name]['credential_process']
        messages.addMessage(f"Credential process: {cred_process}")
        
        # Execute the credential process
        messages.addMessage("\nFetching temporary credentials...")
        try:
            # Parse the command (handle quotes and spaces)
            import shlex
            cmd_parts = shlex.split(cred_process)
            
            # Run the command
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                check=True,
                shell=False
            )
            
            # Parse credentials
            creds = json.loads(result.stdout)
            
            access_key = creds.get('AccessKeyId')
            secret_key = creds.get('SecretAccessKey')
            session_token = creds.get('SessionToken')
            expiration = creds.get('Expiration', 'Unknown')
            
            if not access_key or not secret_key:
                messages.addErrorMessage("Invalid credentials returned")
                messages.addMessage(f"Response: {result.stdout}")
                return
                
            messages.addMessage("✓ Retrieved temporary credentials")
            messages.addMessage(f"Expires: {expiration}")
            
            # Determine buckets to create
            bucket_map = {
                "NASA Disasters (nasa-disasters)": [("nasa-disasters", connection_prefix)],
                "VEDA Production (veda-data-store)": [("veda-data-store", f"{connection_prefix}-prod")],
                "VEDA Development (veda-data-store-dev)": [("veda-data-store-dev", f"{connection_prefix}-dev")],
                "VEDA Staging (veda-data-store-staging)": [("veda-data-store-staging", f"{connection_prefix}-staging")],
                "All VEDA Buckets": [
                    ("veda-data-store", f"{connection_prefix}-prod"),
                    ("veda-data-store-dev", f"{connection_prefix}-dev"),
                    ("veda-data-store-staging", f"{connection_prefix}-staging")
                ],
                "Custom": [(custom_bucket, f"{connection_prefix}-custom")] if custom_bucket else []
            }
            
            buckets = bucket_map.get(bucket_selection, [])
            
            # Create ACS files
            messages.addMessage(f"\nCreating {len(buckets)} ACS file(s)...")
            created = 0
            
            for bucket_name, conn_name in buckets:
                try:
                    messages.addMessage(f"\nCreating connection for: {bucket_name}")
                    
                    # Create the ACS file
                    # Note: Session tokens may not work in all ArcGIS versions
                    if session_token:
                        try:
                            arcpy.management.CreateCloudStorageConnectionFile(
                                output_folder,
                                conn_name,
                                "AMAZON",
                                bucket_name,
                                access_key,
                                secret_key,
                                aws_region,
                                session_token=session_token
                            )
                        except:
                            # Try without session token
                            messages.addWarning("Creating without session token")
                            arcpy.management.CreateCloudStorageConnectionFile(
                                output_folder,
                                conn_name,
                                "AMAZON",
                                bucket_name,
                                access_key,
                                secret_key,
                                aws_region
                            )
                    else:
                        arcpy.management.CreateCloudStorageConnectionFile(
                            output_folder,
                            conn_name,
                            "AMAZON",
                            bucket_name,
                            access_key,
                            secret_key,
                            aws_region
                        )
                    
                    acs_path = os.path.join(output_folder, f"{conn_name}.acs")
                    messages.addMessage(f"✓ Created: {acs_path}")
                    created += 1
                    
                except Exception as e:
                    messages.addErrorMessage(f"Failed for {bucket_name}: {str(e)}")
            
            messages.addMessage(f"\n{'='*50}")
            messages.addMessage(f"Successfully created {created} connection(s)")
            if expiration != 'Unknown':
                messages.addMessage(f"\n⚠ Remember: Credentials expire at {expiration}")
                
        except subprocess.CalledProcessError as e:
            messages.addErrorMessage("Failed to run credential_process")
            messages.addErrorMessage(f"Error: {e.stderr}")
        except json.JSONDecodeError as e:
            messages.addErrorMessage("Failed to parse credentials JSON")
            messages.addErrorMessage(f"Output: {result.stdout}")
        except Exception as e:
            messages.addErrorMessage(f"Unexpected error: {str(e)}")
            
        return
