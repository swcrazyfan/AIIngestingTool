from setuptools import setup, find_packages

setup(
    name="video_ingest_tool",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "typer",
        "rich",
        "structlog",
        "python-dotenv",
        "av",
        "pymediainfo",
        "pyexiftool",
        "opencv-python",
        "pillow",
        "python-dateutil",
        "polyfile",
    ],
    extras_require={
        "queue": ["procrastinate", "psycopg", "psycopg2-binary"],
    },
    entry_points={
        "console_scripts": [
            "video-ingest=video_ingest_tool.video_ingestor:run",
        ],
    },
)
