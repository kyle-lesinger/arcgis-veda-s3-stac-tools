import arcpy
import subprocess
import sys
import os

class InstallBoto3(object):
    """Install boto3 in ArcGIS Pro Python environment"""
    
    def __init__(self):
        self.label = "Install boto3 for S3 Access"
        self.description = "Installs boto3 package in ArcGIS Pro's Python environment"
        self.canRunInBackground = False

    def getParameterInfo(self):
        return []

    def execute(self, parameters, messages):
        messages.addMessage("=== Installing boto3 ===")
        
        # Get ArcGIS Pro's Python executable
        python_exe = sys.executable
        messages.addMessage(f"Python: {python_exe}")
        
        # Check if boto3 already installed
        try:
            import boto3
            messages.addMessage(f"boto3 already installed: {boto3.__version__}")
            return
        except ImportError:
            messages.addMessage("boto3 not found, installing...")
        
        # Install boto3
        try:
            # Method 1: Using pip directly
            messages.addMessage("\nMethod 1: Using pip...")
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "boto3"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                messages.addMessage("[+] Successfully installed boto3")
                messages.addMessage(result.stdout)
            else:
                messages.addMessage("[-] pip install failed")
                messages.addMessage(result.stderr)
                
                # Method 2: Using conda if available
                messages.addMessage("\nMethod 2: Trying conda...")
                conda_exe = os.path.join(os.path.dirname(python_exe), "Scripts", "conda.exe")
                
                if os.path.exists(conda_exe):
                    result = subprocess.run(
                        [conda_exe, "install", "-y", "boto3"],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        messages.addMessage("[+] Successfully installed via conda")
                    else:
                        messages.addMessage("[-] conda install also failed")
                        messages.addMessage(result.stderr)
                else:
                    messages.addMessage("[-] conda not found")
                    
        except Exception as e:
            messages.addErrorMessage(f"Installation failed: {str(e)}")
            
        # Verify installation
        try:
            import boto3
            messages.addMessage(f"\n[+] Verification: boto3 {boto3.__version__} is now installed!")
        except ImportError:
            messages.addMessage("\n[-] boto3 still not available")
            messages.addMessage("You may need to:")
            messages.addMessage("1. Run as administrator")
            messages.addMessage("2. Install manually via ArcGIS Pro Package Manager")
            messages.addMessage("3. Use conda prompt: conda install boto3")
        
        return