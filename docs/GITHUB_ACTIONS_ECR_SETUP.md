# GitHub Actions ECR Build Pipeline - Setup Guide

**Complete setup instructions for building and pushing custom SkyPilot images to AWS ECR**

---

## Overview

The GitHub Actions workflow (`.github/workflows/build-push-ecr-custom.yaml`) automates building and pushing custom SkyPilot Docker images to your existing ECR registry.

**Key Features**:
- ✅ OIDC authentication (no long-lived credentials)
- ✅ Multi-platform builds (amd64/arm64)
- ✅ Multiple image tags (version, commit, date)
- ✅ Build from source with dashboard
- ✅ GitHub cache for faster rebuilds
- ✅ Automatic on push or manual trigger

---

## Prerequisites

### 1. AWS Resources

**ECR Repository**:
- Repository name: `skypilot` (or customize in workflow line 85)
- Region: `us-east-1` (or customize in workflow line 31)
- Must exist before first build

**Check if repository exists**:
```bash
aws ecr describe-repositories --repository-names skypilot --region us-east-1
```

**Create if needed**:
```bash
aws ecr create-repository \
  --repository-name skypilot \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256
```

### 2. GitHub Repository Access

You'll need:
- Admin access to the GitHub repository
- Ability to add secrets to repository settings
- Access to AWS console or CLI

---

## Setup Option 1: OIDC Authentication (Recommended)

OIDC provides secure authentication without storing long-lived credentials in GitHub.

### Step 1: Create OIDC Provider in AWS

**Via AWS Console**:
1. Go to AWS Console → IAM → Identity Providers
2. Click "Add provider"
3. Provider type: OpenID Connect
4. Provider URL: `https://token.actions.githubusercontent.com`
5. Audience: `sts.amazonaws.com`
6. Click "Add provider"

**Via AWS CLI**:
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### Step 2: Create IAM Role for GitHub Actions

**Trust Policy** (`github-oidc-trust-policy.json`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/skypilot:*"
        }
      }
    }
  ]
}
```

**Replace placeholders**:
- `YOUR_AWS_ACCOUNT_ID`: Your 12-digit AWS account ID
- `YOUR_GITHUB_ORG`: Your GitHub organization or username

**Create the role**:
```bash
# Create role with trust policy
aws iam create-role \
  --role-name GitHubActions-SkyPilot-ECR \
  --assume-role-policy-document file://github-oidc-trust-policy.json \
  --description "Role for GitHub Actions to push SkyPilot images to ECR"

# Get the role ARN (save this for GitHub secrets)
aws iam get-role --role-name GitHubActions-SkyPilot-ECR --query 'Role.Arn' --output text
```

### Step 3: Attach ECR Permissions to Role

**Permission Policy** (`ecr-push-policy.json`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:us-east-1:YOUR_AWS_ACCOUNT_ID:repository/skypilot"
    }
  ]
}
```

**Attach policy**:
```bash
# Create policy
aws iam create-policy \
  --policy-name SkyPilot-ECR-Push \
  --policy-document file://ecr-push-policy.json

# Attach to role
aws iam attach-role-policy \
  --role-name GitHubActions-SkyPilot-ECR \
  --policy-arn arn:aws:iam::YOUR_AWS_ACCOUNT_ID:policy/SkyPilot-ECR-Push
```

### Step 4: Configure GitHub Secret

**Add secret to GitHub repository**:

1. Go to GitHub repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `AWS_ECR_ROLE_ARN`
4. Value: The role ARN from Step 2 (format: `arn:aws:iam::123456789012:role/GitHubActions-SkyPilot-ECR`)
5. Click "Add secret"

**Verify workflow configuration**:
The workflow should have this in the AWS credentials step (lines 65-75):
```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.AWS_ECR_ROLE_ARN }}
    aws-region: ${{ env.AWS_REGION }}
```

---

## Setup Option 2: Access Keys (Fallback)

If OIDC setup is not possible, use IAM user access keys.

⚠️ **Warning**: Less secure than OIDC. Rotate keys regularly.

### Step 1: Create IAM User

```bash
# Create user
aws iam create-user --user-name github-actions-skypilot-ecr

# Create access key (save the output!)
aws iam create-access-key --user-name github-actions-skypilot-ecr
```

**Save the output**:
- `AccessKeyId`: Save as GitHub secret `AWS_ACCESS_KEY_ID`
- `SecretAccessKey`: Save as GitHub secret `AWS_SECRET_ACCESS_KEY`

### Step 2: Attach ECR Permissions

Use the same `ecr-push-policy.json` from Option 1:

```bash
# Create policy if not already created
aws iam create-policy \
  --policy-name SkyPilot-ECR-Push \
  --policy-document file://ecr-push-policy.json

# Attach to user
aws iam attach-user-policy \
  --user-name github-actions-skypilot-ecr \
  --policy-arn arn:aws:iam::YOUR_AWS_ACCOUNT_ID:policy/SkyPilot-ECR-Push
```

### Step 3: Configure GitHub Secrets

Add two secrets to GitHub repository:

1. `AWS_ACCESS_KEY_ID`: The access key ID from Step 1
2. `AWS_SECRET_ACCESS_KEY`: The secret access key from Step 1

### Step 4: Modify Workflow

**Uncomment the access key configuration in workflow** (lines 72-75):
```yaml
# Uncomment these lines:
# aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
# aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
# aws-region: ${{ env.AWS_REGION }}

# Comment out the OIDC line:
# role-to-assume: ${{ secrets.AWS_ECR_ROLE_ARN }}
```

---

## Using the Workflow

### Manual Trigger (Workflow Dispatch)

**Via GitHub UI**:
1. Go to repository → Actions → "Build and Push Custom SkyPilot to ECR"
2. Click "Run workflow"
3. Select branch: `feature/runpod-catalog-fetcher` (or desired branch)
4. Enter inputs:
   - **version_tag**: e.g., `v0.9.1-runpod-catalog` or `latest`
   - **build_from_branch**: e.g., `feature/runpod-catalog-fetcher`
   - **push_latest**: Check if you want to also tag as `:latest`
5. Click "Run workflow"

**Via GitHub CLI**:
```bash
gh workflow run build-push-ecr-custom.yaml \
  --ref feature/runpod-catalog-fetcher \
  -f version_tag=v0.9.1-runpod-catalog \
  -f build_from_branch=feature/runpod-catalog-fetcher \
  -f push_latest=false
```

### Automatic Trigger (On Push)

The workflow automatically runs when you push changes to:
- Branch: `feature/runpod-catalog-fetcher`
- Paths:
  - `sky/**`
  - `Dockerfile`
  - `.github/workflows/build-push-ecr-custom.yaml`

**Example**:
```bash
# Make changes to sky/catalog/runpod_catalog.py
git add sky/catalog/runpod_catalog.py
git commit -m "Update RunPod catalog refresh frequency"
git push origin feature/runpod-catalog-fetcher

# Workflow triggers automatically
# Image tagged as: latest-<commit_sha>-<date>
```

---

## Understanding Image Tags

Each build creates multiple tags for flexibility:

**Example**: Manual trigger with `version_tag=v0.9.1-runpod-catalog`

```
YOUR_ECR_REGISTRY/skypilot:v0.9.1-runpod-catalog              # Primary tag
YOUR_ECR_REGISTRY/skypilot:v0.9.1-runpod-catalog-a1b2c3d      # With commit SHA
YOUR_ECR_REGISTRY/skypilot:v0.9.1-runpod-catalog-2025-10-27   # With date
YOUR_ECR_REGISTRY/skypilot:latest                             # If push_latest=true
```

**Tag strategy**:
- **Primary tag** (`version_tag`): Main identifier for this build
- **Commit tag** (`version_tag-<sha>`): Traceable to exact commit
- **Date tag** (`version_tag-<date>`): Identifies when built
- **Latest tag** (optional): Points to most recent build

**Use cases**:
- Development: Use commit-tagged images for exact reproducibility
- Staging: Use date-tagged images for time-based testing
- Production: Use version-tagged images for stable releases
- Rolling updates: Use `:latest` for automatic updates (if desired)

---

## Monitoring the Build

### GitHub Actions UI

**During build**:
1. Go to repository → Actions
2. Click on the running workflow
3. Expand steps to see:
   - Checkout and commit info
   - Docker Buildx setup
   - AWS authentication
   - ECR login
   - Tag generation
   - Image build and push
   - Deployment summary

**After completion**:
- Summary tab shows deployment details
- Artifacts tab (none for this workflow)
- Logs available for debugging

### Expected Build Time

**First build** (no cache):
- Stage 1 (gcloud): ~2-3 minutes
- Stage 2 (source processing): ~1-2 minutes
- Stage 3 (main image): ~3-5 minutes
- Push to ECR: ~2-3 minutes
- **Total**: ~10-15 minutes

**Subsequent builds** (with cache):
- Most layers cached
- Only changed layers rebuilt
- **Total**: ~3-5 minutes

### Deployment Summary

The workflow creates a deployment summary in GitHub Actions UI:

```markdown
## 🚀 Docker Image Build Summary

**Status**: ✅ Success

### Image Details
- **Primary Tag**: `123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog`
- **Commit**: `a1b2c3d`
- **Date**: `2025-10-27`
- **Branch**: `feature/runpod-catalog-fetcher`

### All Tags
```
123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog
123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog-a1b2c3d
123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog-2025-10-27
```

### Features in This Build
- ✅ RunPod catalog hourly refresh (1-hour frequency)
- ✅ PR #6824 integration (dynamic catalog fetcher)
- ✅ Built from source with full dashboard

### Usage
```bash
# Pull this image
docker pull 123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog

# Or use in Kubernetes/ECS
image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog
```

### Next Steps
- Deploy to staging environment
- Test RunPod provisioning with hourly refresh
- Monitor catalog updates in logs
```

---

## Verifying the Build

### Check ECR Registry

**List images**:
```bash
aws ecr describe-images \
  --repository-name skypilot \
  --region us-east-1 \
  --query 'imageDetails[*].[imageTags[0],imagePushedAt]' \
  --output table
```

**Get specific image details**:
```bash
aws ecr describe-images \
  --repository-name skypilot \
  --region us-east-1 \
  --image-ids imageTag=v0.9.1-runpod-catalog
```

### Pull and Test Locally

**Pull the image**:
```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Pull the image
docker pull 123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog
```

**Verify build features**:
```bash
# Run container
docker run --rm -it \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/skypilot:v0.9.1-runpod-catalog \
  /bin/bash

# Inside container, verify:
# 1. RunPod catalog exists
ls -lh ~/.sky/catalogs/v8/runpod/vms.csv

# 2. Check refresh frequency in code
grep "_PULL_FREQUENCY_HOURS" /sky/sky/catalog/runpod_catalog.py
# Should show: _PULL_FREQUENCY_HOURS = 1

# 3. Check fetcher exists
ls -lh /sky/sky/catalog/data_fetchers/fetch_runpod.py

# 4. Verify dashboard is installed
ls -lh /sky/sky/dashboard/

# Exit container
exit
```

---

## Troubleshooting

### Build Fails: AWS Authentication

**Error**:
```
Error: Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity
```

**Solutions**:
1. Verify OIDC provider exists in AWS IAM
2. Check trust policy matches your GitHub org/repo
3. Verify `AWS_ECR_ROLE_ARN` secret is correct
4. Check role has ECR permissions attached

**Debug**:
```bash
# Verify OIDC provider
aws iam list-open-id-connect-providers

# Verify role exists
aws iam get-role --role-name GitHubActions-SkyPilot-ECR

# Check role trust policy
aws iam get-role --role-name GitHubActions-SkyPilot-ECR --query 'Role.AssumeRolePolicyDocument'

# Check attached policies
aws iam list-attached-role-policies --role-name GitHubActions-SkyPilot-ECR
```

### Build Fails: ECR Repository Not Found

**Error**:
```
Error: repository skypilot not found
```

**Solution**:
```bash
# Create the repository
aws ecr create-repository \
  --repository-name skypilot \
  --region us-east-1
```

### Build Fails: Insufficient Permissions

**Error**:
```
Error: denied: User: arn:aws:sts::123456789012:assumed-role/GitHubActions-SkyPilot-ECR is not authorized to perform: ecr:PutImage
```

**Solution**:
Verify and re-attach ECR permissions:
```bash
# Check current permissions
aws iam get-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/SkyPilot-ECR-Push \
  --version-id v1

# If incorrect, update policy document and create new version
aws iam create-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/SkyPilot-ECR-Push \
  --policy-document file://ecr-push-policy.json \
  --set-as-default
```

### Build Succeeds But Image Missing Tags

**Problem**: Only one tag appears in ECR

**Cause**: Tag generation step may have failed

**Debug**:
1. Check workflow logs → "Generate image tags" step
2. Verify all tags are generated correctly
3. Check build step received all tags

**Fix**: Re-run workflow with explicit version_tag

### Slow Builds

**Problem**: Builds take >20 minutes

**Causes**:
1. GitHub cache not working
2. Network issues downloading dependencies
3. Multi-platform builds rebuilding from scratch

**Solutions**:
```yaml
# Verify cache configuration in workflow
cache-from: type=gha
cache-to: type=gha,mode=max

# Check cache hit rate in build logs
# Look for: "CACHED" next to layer descriptions
```

**Temporary workaround**: Build single platform
```yaml
# Change from:
platforms: linux/amd64,linux/arm64
# To:
platforms: linux/amd64
```

---

## Security Best Practices

### 1. Use OIDC (Not Access Keys)
- No long-lived credentials in GitHub
- Automatic credential rotation
- Scoped to specific repository

### 2. Minimal Permissions
- Grant only required ECR permissions
- Don't use `ecr:*` or `*` permissions
- Restrict to specific repository ARN

### 3. Enable Image Scanning
```bash
aws ecr put-image-scanning-configuration \
  --repository-name skypilot \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true
```

### 4. Enable Encryption
ECR encrypts images at rest by default with AWS-managed keys.

For customer-managed keys (KMS):
```bash
aws ecr create-repository \
  --repository-name skypilot \
  --region us-east-1 \
  --encryption-configuration encryptionType=KMS,kmsKey=arn:aws:kms:us-east-1:123456789012:key/abcd1234
```

### 5. Review Workflow Logs
- Logs contain no secrets (GitHub masks them)
- Review for unexpected behavior
- Monitor for unauthorized builds

### 6. Limit GitHub Secrets Access
- Only repository admins should access secrets
- Audit secret usage in repository settings
- Rotate OIDC role or access keys periodically

---

## Next Steps

After successful build:

1. **Deploy to Staging Environment**:
   ```bash
   # Pull image to staging server
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin YOUR_ECR_REGISTRY

   docker pull YOUR_ECR_REGISTRY/skypilot:v0.9.1-runpod-catalog

   # Run SkyPilot with new image
   # (specific deployment steps depend on your environment)
   ```

2. **Verify Hourly Refresh Works**:
   ```bash
   # Inside container, check catalog age
   stat ~/.sky/catalogs/v8/runpod/vms.csv

   # Monitor catalog updates
   watch -n 300 'stat ~/.sky/catalogs/v8/runpod/vms.csv'
   ```

3. **Test L40S Provisioning**:
   ```bash
   # Test provisioning L40S in EU regions
   sky launch --cloud runpod --region IS --gpus L40S:1 --dry-run
   ```

4. **Generate Fresh Catalog**:
   - Obtain RunPod API key
   - Run `fetch_runpod.py` to generate fresh catalog
   - Test with real RunPod inventory

5. **Complete Remaining Implementation Phases**:
   - See `docs/RUNPOD_CATALOG_IMPROVEMENT_PLAN.md`
   - Phases 2-6: Testing, validation, production deployment

---

## Reference

**Related Documentation**:
- **Main workflow**: `.github/workflows/build-push-ecr-custom.yaml`
- **Implementation plan**: `docs/RUNPOD_CATALOG_IMPROVEMENT_PLAN.md`
- **Catalog auto-refresh**: `docs/CATALOG_AUTO_REFRESH_EXPLAINED.md`
- **Hourly refresh guide**: `docs/HOURLY_CATALOG_REFRESH_GUIDE.md`
- **Fetcher quick start**: `docs/RUNPOD_FETCHER_QUICK_START.md`

**AWS Resources**:
- [OIDC in GitHub Actions](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [ECR User Guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/)
- [Docker Build Push Action](https://github.com/docker/build-push-action)

**SkyPilot Resources**:
- [SkyPilot Documentation](https://skypilot.readthedocs.io/)
- [PR #6824 (RunPod Fetcher)](https://github.com/skypilot-org/skypilot/pull/6824)
- [Original Docker Build Workflow](https://github.com/skypilot-org/skypilot/blob/master/.github/workflows/docker-build.yaml)

---

**Last Updated**: 2025-10-27
**Version**: 1.0
**Status**: Ready for use - requires AWS credentials configuration
