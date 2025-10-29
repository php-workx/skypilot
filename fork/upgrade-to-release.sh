#!/bin/bash
# SkyPilot Fork Upgrade Script
# Upgrades ojin-release and ojin-pre-release to a new upstream release

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  SkyPilot Fork Upgrade Script         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo

# Get current base version
CURRENT_BASE=$(git tag --list | grep "^ojin-base-" | sort -V | tail -1)
if [ -z "$CURRENT_BASE" ]; then
    echo -e "${RED}Error: No ojin-base tag found${NC}"
    echo "Run: git tag ojin-base-v0.10.3.post2 v0.10.3.post2"
    exit 1
fi

echo -e "${BLUE}Current base:${NC} ${YELLOW}${CURRENT_BASE}${NC}"

# Fetch latest tags
echo -e "${GREEN}Fetching upstream tags...${NC}"
git fetch upstream --tags
git fetch origin

# List available releases
echo
echo -e "${BLUE}Available upstream releases:${NC}"
git tag --list | grep "^v0\." | sort -V | tail -10 | nl

echo
read -p "$(echo -e ${YELLOW}Enter new version to upgrade to \(e.g., v0.10.4\): ${NC})" NEW_VERSION

# Validate tag exists
if ! git rev-parse "$NEW_VERSION" >/dev/null 2>&1; then
    echo -e "${RED}Error: Tag $NEW_VERSION not found${NC}"
    exit 1
fi

# Extract version from tag
OLD_VERSION=${CURRENT_BASE#ojin-base-}

echo
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Upgrade Plan                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo -e "${BLUE}From:${NC} ${YELLOW}${OLD_VERSION}${NC}"
echo -e "${BLUE}To:${NC}   ${YELLOW}${NEW_VERSION}${NC}"
echo
echo "Steps:"
echo "  1. Rebase ojin-release onto ${NEW_VERSION}"
echo "  2. Rebase ojin-pre-release onto ${NEW_VERSION}"
echo "  3. Tag new base as ojin-base-${NEW_VERSION}"
echo "  4. Push both branches and tag"
echo

read -p "$(echo -e ${YELLOW}Continue? \(y/n\): ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}Step 1: Rebasing ojin-release${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"

git checkout ojin-release
echo -e "${BLUE}Current branch:${NC} ojin-release"
echo -e "${BLUE}Rebasing from:${NC} ${OLD_VERSION}"
echo -e "${BLUE}Rebasing onto:${NC} ${NEW_VERSION}"
echo

if git rebase --onto "$NEW_VERSION" "$OLD_VERSION"; then
    echo -e "${GREEN}✓ ojin-release rebased successfully${NC}"
else
    echo -e "${RED}✗ Rebase failed or has conflicts${NC}"
    echo
    echo "To resolve:"
    echo "  1. Fix conflicts in the files"
    echo "  2. git add <resolved-files>"
    echo "  3. git rebase --continue"
    echo "  4. Re-run this script"
    echo
    echo "To abort:"
    echo "  git rebase --abort"
    exit 1
fi

echo
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}Step 2: Rebasing ojin-pre-release${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"

git checkout ojin-pre-release
echo -e "${BLUE}Current branch:${NC} ojin-pre-release"
echo -e "${BLUE}Rebasing from:${NC} ${OLD_VERSION}"
echo -e "${BLUE}Rebasing onto:${NC} ${NEW_VERSION}"
echo

if git rebase --onto "$NEW_VERSION" "$OLD_VERSION"; then
    echo -e "${GREEN}✓ ojin-pre-release rebased successfully${NC}"
else
    echo -e "${RED}✗ Rebase failed or has conflicts${NC}"
    echo
    echo "To resolve:"
    echo "  1. Fix conflicts in the files"
    echo "  2. git add <resolved-files>"
    echo "  3. git rebase --continue"
    echo "  4. Re-run this script"
    echo
    echo "To abort:"
    echo "  git rebase --abort"
    exit 1
fi

echo
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}Step 3: Tagging new base${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"

git tag -f "ojin-base-$NEW_VERSION" "$NEW_VERSION"
echo -e "${GREEN}✓ Tagged ojin-base-${NEW_VERSION}${NC}"

echo
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ Upgrade Complete!                   ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo
echo -e "${BLUE}Branches updated:${NC}"
echo "  • ojin-release      → ${NEW_VERSION}"
echo "  • ojin-pre-release  → ${NEW_VERSION}"
echo
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo
echo "1. ${BLUE}Test thoroughly${NC}"
echo "   • Run your tests"
echo "   • Verify custom features work"
echo
echo "2. ${BLUE}Push changes:${NC}"
echo "   git push origin ojin-release --force"
echo "   git push origin ojin-pre-release --force"
echo "   git push origin ojin-base-${NEW_VERSION}"
echo
echo "3. ${BLUE}Tag the release:${NC}"
echo "   git checkout ojin-release"
echo "   git tag ${NEW_VERSION}-ojin-custom"
echo "   git push origin ${NEW_VERSION}-ojin-custom"
echo
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo
echo -e "${BLUE}To rollback if needed:${NC}"
echo "  git checkout ojin-release"
echo "  git reset --hard origin/ojin-release"
echo "  git checkout ojin-pre-release"
echo "  git reset --hard origin/ojin-pre-release"
echo
