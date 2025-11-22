#!/bin/bash
# Validates that CUSTOM_CHANGES.md is up-to-date with git history

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   Custom Changes Validation                   ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# Get base version from CUSTOM_CHANGES.md
if [ -f "fork/CUSTOM_CHANGES.md" ]; then
    DOCUMENTED_VERSION=$(grep "^**Base Version:**" fork/CUSTOM_CHANGES.md | sed 's/.*: //')
    echo "📄 Documented base version: ${BLUE}$DOCUMENTED_VERSION${NC}"
else
    echo "${RED}❌ Error: fork/CUSTOM_CHANGES.md not found${NC}"
    exit 1
fi

# Get actual base version from git
ACTUAL_VERSION=$(git describe --tags --abbrev=0 ojin-release 2>/dev/null || echo "unknown")
echo "🏷️  Actual git base version: ${BLUE}$ACTUAL_VERSION${NC}"
echo ""

# Check if versions match
WARNINGS=0
ERRORS=0

if [ "$DOCUMENTED_VERSION" != "$ACTUAL_VERSION" ]; then
    echo "${YELLOW}⚠️  WARNING: Documented version doesn't match git base tag${NC}"
    echo "   Documented: $DOCUMENTED_VERSION"
    echo "   Actual: $ACTUAL_VERSION"
    echo ""
    WARNINGS=$((WARNINGS + 1))
fi

# Get custom commits since base
echo "📊 Analyzing custom commits..."
COMMIT_COUNT=$(git rev-list --count $ACTUAL_VERSION..HEAD 2>/dev/null || echo "0")
echo "   Custom commits since $ACTUAL_VERSION: ${BLUE}$COMMIT_COUNT${NC}"
echo ""

# Extract commits mentioned in CUSTOM_CHANGES.md
echo "🔍 Checking documented commits..."
DOCUMENTED_COMMITS=$(grep -oE '\`[a-f0-9]{7,}\`' fork/CUSTOM_CHANGES.md | tr -d '`' | sort -u)
DOCUMENTED_COUNT=$(echo "$DOCUMENTED_COMMITS" | wc -l)
echo "   Commits mentioned in CUSTOM_CHANGES.md: ${BLUE}$DOCUMENTED_COUNT${NC}"
echo ""

# Verify each documented commit exists
echo "✓ Verifying documented commits exist..."
INVALID_COMMITS=0
for commit in $DOCUMENTED_COMMITS; do
    if ! git rev-parse "$commit" >/dev/null 2>&1; then
        echo "${RED}   ✗ Commit $commit not found in repository${NC}"
        INVALID_COMMITS=$((INVALID_COMMITS + 1))
        ERRORS=$((ERRORS + 1))
    fi
done

if [ $INVALID_COMMITS -eq 0 ]; then
    echo "${GREEN}   ✓ All documented commits are valid${NC}"
fi
echo ""

# Check for undocumented custom commits
echo "🔎 Checking for undocumented custom commits..."
CUSTOM_COMMITS=$(git log $ACTUAL_VERSION..HEAD --oneline --no-merges)
CUSTOM_COMMIT_HASHES=$(git log $ACTUAL_VERSION..HEAD --format="%h" --no-merges)

UNDOCUMENTED=0
for commit in $CUSTOM_COMMIT_HASHES; do
    if ! echo "$DOCUMENTED_COMMITS" | grep -q "$commit"; then
        if [ $UNDOCUMENTED -eq 0 ]; then
            echo "${YELLOW}⚠️  Undocumented commits found:${NC}"
        fi
        COMMIT_MSG=$(git log --format=%s -n 1 $commit)
        echo "   ${YELLOW}$commit${NC} - $COMMIT_MSG"
        UNDOCUMENTED=$((UNDOCUMENTED + 1))
        WARNINGS=$((WARNINGS + 1))
    fi
done

if [ $UNDOCUMENTED -eq 0 ]; then
    echo "${GREEN}   ✓ All custom commits are documented${NC}"
else
    echo ""
    echo "${YELLOW}   💡 Consider adding these commits to CUSTOM_CHANGES.md${NC}"
fi
echo ""

# Check modified files
echo "📁 Analyzing modified files..."
MODIFIED_FILES=$(git diff $ACTUAL_VERSION..HEAD --name-only | grep -v "^fork/" | grep -v "^_github/" | grep -v "^\.github/workflows/" | grep -v "^Dockerfile" | grep -v "^Makefile" | grep -v "CLAUDE.md" | grep -v "test_" || echo "")
MODIFIED_COUNT=$(echo "$MODIFIED_FILES" | grep -v "^$" | wc -l)
echo "   Modified files (excluding infrastructure): ${BLUE}$MODIFIED_COUNT${NC}"
echo ""

# Extract files mentioned in CUSTOM_CHANGES.md
DOCUMENTED_FILES=$(grep -E '^\s*-\s*`[^`]+\.py`' fork/CUSTOM_CHANGES.md | grep -oE '`[^`]+`' | tr -d '`' | sort -u)
DOCUMENTED_FILE_COUNT=$(echo "$DOCUMENTED_FILES" | grep -v "^$" | wc -l)
echo "   Files documented in CUSTOM_CHANGES.md: ${BLUE}$DOCUMENTED_FILE_COUNT${NC}"
echo ""

# Check for undocumented file modifications
echo "🔎 Checking for undocumented file modifications..."
UNDOCUMENTED_FILES=0
for file in $MODIFIED_FILES; do
    # Skip test files and infrastructure
    if echo "$file" | grep -qE "(test_|__pycache__|\.pyc)"; then
        continue
    fi

    if ! echo "$DOCUMENTED_FILES" | grep -q "$file"; then
        if [ $UNDOCUMENTED_FILES -eq 0 ]; then
            echo "${YELLOW}⚠️  Undocumented file modifications:${NC}"
        fi
        echo "   ${YELLOW}$file${NC}"
        UNDOCUMENTED_FILES=$((UNDOCUMENTED_FILES + 1))
        WARNINGS=$((WARNINGS + 1))
    fi
done

if [ $UNDOCUMENTED_FILES -eq 0 ]; then
    echo "${GREEN}   ✓ All significant file modifications are documented${NC}"
else
    echo ""
    echo "${YELLOW}   💡 Consider documenting these file changes in CUSTOM_CHANGES.md${NC}"
fi
echo ""

# Check last updated date
echo "📅 Checking last update date..."
LAST_UPDATED=$(grep "^**Last Updated:**" fork/CUSTOM_CHANGES.md | sed 's/.*: //')
TODAY=$(date +%Y-%m-%d)
if [ "$LAST_UPDATED" != "$TODAY" ]; then
    echo "${YELLOW}   ⚠️  Last updated: $LAST_UPDATED (not today)${NC}"
    echo "   Consider updating the date if you made changes"
    WARNINGS=$((WARNINGS + 1))
else
    echo "${GREEN}   ✓ Last updated date is current${NC}"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "${GREEN}✅ Validation PASSED - CUSTOM_CHANGES.md is up-to-date${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "${YELLOW}⚠️  Validation PASSED with warnings${NC}"
    echo "   Warnings: $WARNINGS"
    echo ""
    echo "   CUSTOM_CHANGES.md is mostly accurate but could be improved."
    exit 0
else
    echo "${RED}❌ Validation FAILED${NC}"
    echo "   Errors: $ERRORS"
    echo "   Warnings: $WARNINGS"
    echo ""
    echo "   Please update CUSTOM_CHANGES.md to fix the errors."
    exit 1
fi
