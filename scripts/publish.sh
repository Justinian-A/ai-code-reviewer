#!/bin/bash
# scripts/publish.sh

set -e

echo "Building package..."
python -m build

echo "Uploading to PyPI..."
twine upload dist/*

echo "Cleaning up..."
rm -rf dist/ build/ *.egg-info

echo "Published successfully!"
