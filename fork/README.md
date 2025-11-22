# SkyPilot Fork Documentation

Navigation index for fork-specific documentation and tools.

## Documentation

| Document | Purpose |
|----------|---------|
| [UPGRADE_PROCESS.md](./UPGRADE_PROCESS.md) | Complete upgrade guide with conflict resolution strategies |
| [CUSTOM_CHANGES.md](./CUSTOM_CHANGES.md) | **Source of truth** - Detailed change tracking with AI agent instructions |
| [CUSTOMIZATIONS.md](./CUSTOMIZATIONS.md) | High-level feature summary for quick overview |
| [WORKFLOW.md](./WORKFLOW.md) | Daily development workflow and branching strategy |

## Scripts

| Script | Purpose |
|--------|---------|
| [upgrade-prep.sh](./upgrade-prep.sh) | Create backup and document state before upgrade |
| [validate-changes.sh](./validate-changes.sh) | Validate CUSTOM_CHANGES.md matches git history |

## Quick Start for AI Agents

**Upgrading SkyPilot:**
```bash
./fork/upgrade-prep.sh v0.10.6        # 1. Prepare
# Follow UPGRADE_PROCESS.md             # 2. Execute
# Update CUSTOM_CHANGES.md              # 3. Document
./fork/validate-changes.sh            # 4. Validate
```

**Adding Custom Features:**
- See AI agent instructions at top of [CUSTOM_CHANGES.md](./CUSTOM_CHANGES.md)
