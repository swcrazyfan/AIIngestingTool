from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="video_ingest_tool",
    version="0.1.0",
    author="AI Ingesting Tool Team",
    author_email="developer@example.com",
    description="AI-Powered Video Ingest & Catalog Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/AIIngestingTool",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "av>=14.4.0",
        "pymediainfo>=6.0.0",
        "PyExifTool>=0.5.0",
        "opencv-python>=4.8.0",
        "typer[all]>=0.9.0",
        "rich>=13.4.0",
        "pydantic>=2.4.0",
        "structlog>=23.1.0",
        "numpy>=1.24.0",
        "pillow>=10.0.0",
        "polyfile>=0.5.5",
        "hachoir==3.3.0",
        "tqdm>=4.65.0",
        "colorama>=0.4.6",
        "python-dateutil>=2.8.2",
    ],
    entry_points={
        "console_scripts": [
            "video-ingest=video_ingest_tool.video_ingestor:app",
        ],
    },
)
