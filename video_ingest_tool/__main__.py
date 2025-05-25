"""
Entry point for the video ingest tool.

Import and run the CLI when the package is invoked directly.
"""

from .cli import app

if __name__ == "__main__":
    app()
