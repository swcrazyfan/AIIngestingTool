#!/usr/bin/env python3
"""
Script to test loading the depth_pro model and identifying path issues.
"""

import os
import sys
import torch
from pathlib import Path

# Add ml-depth-pro/src to the path
src_path = "/Users/developer/Development/GitHub/AIIngestingTool/ml-depth-pro/src"
sys.path.append(src_path)

# Try to import depth_pro
try:
    import depth_pro
    from depth_pro.depth_pro import DEFAULT_MONODEPTH_CONFIG_DICT
    
    # Print information about the module and expected checkpoint path
    print("depth_pro module location:", depth_pro.__file__)
    print("Default checkpoint path:", DEFAULT_MONODEPTH_CONFIG_DICT.checkpoint_uri)
    
    # Check if the expected checkpoint file exists
    expected_path = DEFAULT_MONODEPTH_CONFIG_DICT.checkpoint_uri
    if os.path.isabs(expected_path):
        print(f"Expected checkpoint path is absolute: {expected_path}")
        print(f"File exists: {os.path.exists(expected_path)}")
    else:
        # If it's a relative path, check both relative to current directory and module directory
        print(f"Expected checkpoint path is relative: {expected_path}")
        
        # Check relative to current directory
        current_dir_path = os.path.join(os.getcwd(), expected_path)
        print(f"Relative to current directory: {current_dir_path}")
        print(f"File exists: {os.path.exists(current_dir_path)}")
        
        # Check relative to module directory
        module_dir = os.path.dirname(depth_pro.__file__)
        module_root = os.path.dirname(os.path.dirname(module_dir))
        module_path = os.path.join(module_root, expected_path)
        print(f"Relative to module root: {module_path}")
        print(f"File exists: {os.path.exists(module_path)}")
        
        # Check all known potential locations
        potential_locations = [
            os.path.join(module_root, "checkpoints", "depth_pro.pt"),
            os.path.join(module_dir, "checkpoints", "depth_pro.pt"),
            os.path.join("./checkpoints", "depth_pro.pt"),
        ]
        
        print("\nChecking all potential model locations:")
        for loc in potential_locations:
            print(f"  {loc}: {os.path.exists(loc)}")
    
except ImportError as e:
    print(f"Error importing depth_pro: {e}")
except Exception as e:
    print(f"Error: {e}")
