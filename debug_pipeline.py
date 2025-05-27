#!/usr/bin/env python
"""
Debug script for the pipeline configuration and execution.
"""

import os
import logging
import json
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_pipeline")

# Import pipeline components
from video_ingest_tool.pipeline.registry import get_all_steps, get_default_pipeline
from video_ingest_tool.pipeline.base import ProcessingPipeline
from video_ingest_tool.steps import (
    reorder_pipeline_steps,
    process_video_file
)
from video_ingest_tool.config import DEFAULT_COMPRESSION_CONFIG

def display_pipeline_steps():
    """Display all registered pipeline steps and their default status."""
    steps = get_all_steps()
    
    print("\nAll registered pipeline steps:")
    print("-" * 80)
    print(f"{'Step Name':<30} {'Default Status':<15} {'Description'}")
    print("-" * 80)
    
    for step in steps:
        status = "Enabled" if step["enabled"] else "Disabled"
        print(f"{step['name']:<30} {status:<15} {step['description']}")
    
    # Look specifically for our target steps
    ai_video_analysis = next((s for s in steps if s['name'] == 'ai_video_analysis'), None)
    ai_thumbnail_selection = next((s for s in steps if s['name'] == 'ai_thumbnail_selection'), None)
    generate_embeddings = next((s for s in steps if s['name'] == 'generate_embeddings'), None)
    
    print("\nTarget Steps Status:")
    print("-" * 80)
    if ai_video_analysis:
        print(f"AI Video Analysis: {'Enabled' if ai_video_analysis['enabled'] else 'Disabled'} by default")
    else:
        print("AI Video Analysis: Not registered")
        
    if ai_thumbnail_selection:
        print(f"AI Thumbnail Selection: {'Enabled' if ai_thumbnail_selection['enabled'] else 'Disabled'} by default")
    else:
        print("AI Thumbnail Selection: Not registered")
        
    if generate_embeddings:
        print(f"Generate Embeddings: {'Enabled' if generate_embeddings['enabled'] else 'Disabled'} by default")
    else:
        print("Generate Embeddings: Not registered")

def create_test_pipeline_config(enable_ai_steps=True, enable_embeddings=True):
    """Create a test pipeline configuration."""
    # Start with default pipeline config
    pipeline = get_default_pipeline()
    pipeline_config = {}
    
    # Get default configuration for all steps
    for step in get_all_steps():
        pipeline_config[step['name']] = step['enabled']
    
    # Enable or disable AI steps
    if enable_ai_steps:
        pipeline_config['ai_video_analysis'] = True
        pipeline_config['ai_thumbnail_selection'] = True
    
    # Enable or disable embeddings
    if enable_embeddings:
        pipeline_config['generate_embeddings'] = True
        pipeline_config['database_storage'] = True  # Required for embeddings
    
    return pipeline_config

def simulate_cli_command():
    """Simulate the CLI command execution with parameters."""
    print("\nSimulating CLI command:")
    print("conda activate video-ingest && python -m video_ingest_tool ingest ./test_new_vid "
          "--force-reprocess --generate-embeddings --store-database --enable=ai_video_analysis")
    
    # Create pipeline config as it would be from the CLI command
    pipeline_config = create_test_pipeline_config()
    
    # Apply the enable=ai_video_analysis flag
    pipeline_config['ai_video_analysis'] = True
    
    # Debug the final configuration
    print("\nPipeline Configuration After CLI Options:")
    print("-" * 80)
    for step_name, enabled in sorted(pipeline_config.items()):
        print(f"{step_name:<30} {'Enabled' if enabled else 'Disabled'}")
    
    # Check if ai_thumbnail_selection would be enabled based on dependencies
    print("\nChecking ai_thumbnail_selection dependency:")
    print("The ai_thumbnail_selection step requires data from ai_video_analysis to function.")
    if pipeline_config.get('ai_video_analysis') and not pipeline_config.get('ai_thumbnail_selection'):
        print("⚠️ Warning: ai_video_analysis is enabled but ai_thumbnail_selection is not explicitly enabled.")
        print("   This might prevent AI thumbnails from being selected and their embeddings from being generated.")
    
    return pipeline_config

def debug_pipeline_execution(pipeline_config):
    """Debug the pipeline execution process."""
    # Create a pipeline instance
    pipeline = get_default_pipeline()
    
    # Configure steps based on the config
    for step_name, enabled in pipeline_config.items():
        pipeline.configure_step(step_name, enabled=enabled)
    
    # Get the execution order
    print("\nPipeline Execution Order:")
    print("-" * 80)
    execution_order = pipeline.get_enabled_steps()
    for i, step in enumerate(execution_order):
        print(f"{i+1}. {step.name}")
    
    # Check for the presence of our target steps
    ai_video_analysis_step = next((s for s in execution_order if s.name == 'ai_video_analysis'), None)
    ai_thumbnail_selection_step = next((s for s in execution_order if s.name == 'ai_thumbnail_selection'), None)
    generate_embeddings_step = next((s for s in execution_order if s.name == 'generate_embeddings'), None)
    
    print("\nTarget Steps in Execution Order:")
    print("-" * 80)
    if ai_video_analysis_step:
        ai_video_index = [s.name for s in execution_order].index('ai_video_analysis') + 1
        print(f"AI Video Analysis will run at position {ai_video_index}")
    else:
        print("AI Video Analysis will not run")
        
    if ai_thumbnail_selection_step:
        ai_thumbnail_index = [s.name for s in execution_order].index('ai_thumbnail_selection') + 1
        print(f"AI Thumbnail Selection will run at position {ai_thumbnail_index}")
    else:
        print("AI Thumbnail Selection will not run")
        
    if generate_embeddings_step:
        generate_embeddings_index = [s.name for s in execution_order].index('generate_embeddings') + 1
        print(f"Generate Embeddings will run at position {generate_embeddings_index}")
    else:
        print("Generate Embeddings will not run")
    
    # Check execution order dependencies
    if ai_video_analysis_step and ai_thumbnail_selection_step:
        ai_video_index = [s.name for s in execution_order].index('ai_video_analysis')
        ai_thumbnail_index = [s.name for s in execution_order].index('ai_thumbnail_selection')
        
        if ai_thumbnail_index < ai_video_index:
            print("\n⚠️ Warning: AI Thumbnail Selection runs BEFORE AI Video Analysis!")
            print("   This is a dependency problem - AI Thumbnail Selection needs AI Video Analysis results.")
        else:
            print("\n✅ AI Thumbnail Selection correctly runs after AI Video Analysis.")
    
    if ai_thumbnail_selection_step and generate_embeddings_step:
        ai_thumbnail_index = [s.name for s in execution_order].index('ai_thumbnail_selection')
        generate_embeddings_index = [s.name for s in execution_order].index('generate_embeddings')
        
        if generate_embeddings_index < ai_thumbnail_index:
            print("\n⚠️ Warning: Generate Embeddings runs BEFORE AI Thumbnail Selection!")
            print("   This is a dependency problem - Embeddings needs AI Thumbnail paths.")
        else:
            print("\n✅ Generate Embeddings correctly runs after AI Thumbnail Selection.")

def main():
    """Main function."""
    print("\n" + "=" * 80)
    print("Pipeline Debug Script".center(80))
    print("=" * 80)
    
    # Display all registered pipeline steps
    display_pipeline_steps()
    
    # Simulate CLI command and get resulting pipeline configuration
    pipeline_config = simulate_cli_command()
    
    # Debug pipeline execution
    debug_pipeline_execution(pipeline_config)
    
    print("\n" + "=" * 80)
    
    # Provide recommendations
    print("\nRecommendations:")
    print("-" * 80)
    print("1. When using --enable=ai_video_analysis, also include --enable=ai_thumbnail_selection")
    print("   Full command: python -m video_ingest_tool ingest ./test_new_vid --force-reprocess ")
    print("                 --generate-embeddings --store-database --enable=ai_video_analysis,ai_thumbnail_selection")
    print("\n2. Check the logs to verify that the AI analysis is being performed")
    print("   Look for logs related to the 'ai_video_analysis' step")
    print("\n3. Check the logs to verify that AI thumbnails are being selected")
    print("   Look for logs related to the 'ai_thumbnail_selection' step")
    print("\n4. Check the logs to verify that embeddings are being generated")
    print("   Look for logs related to the 'generate_embeddings' step")

if __name__ == "__main__":
    main() 