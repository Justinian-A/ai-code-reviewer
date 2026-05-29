#!/bin/bash
# scripts/version.sh

set -e

# Get current version
CURRENT_VERSION=$(grep -oP 'version = "\K[^"]+' pyproject.toml)

if [ -z "$CURRENT_VERSION" ]; then
    echo "Error: Could not find version in pyproject.toml"
    exit 1
fi

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump patch version
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH"

# Update pyproject.toml
sed -i "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml

echo "Version bumped from $CURRENT_VERSION to $NEW_VERSION"
