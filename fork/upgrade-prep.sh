#!/bin/bash
# Prepares for upgrade - creates backup, documents state
# Designed to be called by AI agents before starting upgrade

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version-tag>"
    exit 1
fi

set -e

# Ensure on ojin-release
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "ojin-release" ]; then
    echo "Error: Must be on ojin-release branch (currently on: $CURRENT_BRANCH)"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: Uncommitted changes detected"
    exit 1
fi

# Fetch upstream
git remote add upstream https://github.com/skypilot-org/skypilot.git 2>/dev/null || true
git fetch upstream --tags

# Verify version exists
if ! git rev-parse "$VERSION" >/dev/null 2>&1; then
    echo "Error: Version tag '$VERSION' not found"
    exit 1
fi

# Get last base version
LAST_TAG=$(git describe --tags --abbrev=0 ojin-release 2>/dev/null || echo "v0.10.3.post2")

# Create backup branch
BACKUP_BRANCH="backup-ojin-release-before-$VERSION-upgrade"
git branch -D "$BACKUP_BRANCH" 2>/dev/null || true
git branch "$BACKUP_BRANCH"
git push origin "$BACKUP_BRANCH" 2>/dev/null || true

# Document current state
DOCS_DIR="/tmp/skypilot-upgrade-$VERSION"
mkdir -p "$DOCS_DIR"
git log $LAST_TAG..HEAD --oneline > "$DOCS_DIR/custom-commits.txt"
git diff $LAST_TAG..HEAD --stat > "$DOCS_DIR/custom-changes.txt"
git diff $LAST_TAG..HEAD --name-only > "$DOCS_DIR/changed-files.txt"

# Output summary for agent
echo "BACKUP_BRANCH=$BACKUP_BRANCH"
echo "DOCS_DIR=$DOCS_DIR"
echo "LAST_TAG=$LAST_TAG"
echo "COMMITS_BEHIND=$(git rev-list --count $LAST_TAG..$VERSION 2>/dev/null)"
echo "COMMITS_AHEAD=$(git rev-list --count $LAST_TAG..HEAD 2>/dev/null)"
echo "UPGRADE_BRANCH=upgrade/$VERSION-merge"
