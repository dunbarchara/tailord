# Day 3.5 — Cloud-Agnostic Infrastructure

*March 2026 | Provider portability: AWS ↔ Azure*

---

## Goal

Make it trivially easy to deploy the full stack (frontend + backend + database + object storage) to either AWS or Azure by switching a Terraform configuration. No application code should contain cloud-provider-specific logic — all cloud calls go through an abstraction layer.

Additionally: properly containerize and deploy the backend alongside the frontend (currently it has a Dockerfile but no production deployment path).

---

## What "Provider Portability" Means Here

- **Active on one cloud at a time** — not active-active multi-cloud (too complex for current scale)
- **Single command switch** — `cd infra/providers/azure && terraform apply` deploys the same product on Azure
- **Application layer is cloud-blind** — Python backend doesn't import `boto3` directly; it goes through `StorageClient`
- **Long-term option**: as Azure credits reduce cost (especially for managed Postgres and compute), individual services can migrate independently

---

## Current AWS-Specific Dependencies

| Layer | Dependency | Abstraction needed? |
|-------|-----------|-------------------|
| Backend Python | `boto3` S3 (presigned URLs, get, delete) | Yes — StorageClient interface |
| Backend Python | Hardcoded `DATABASE_URL = "postgresql+psycopg://app:app@localhost:5432/app"` | Yes — env var |
| Terraform | ECS Cluster, ECS Service, ECS Task Definition | Module interface |
| Terraform | ECR repository | Module interface |
| Terraform | S3 bucket (uploads) | Module interface |
| Terraform | RDS (not provisioned yet, needed) | Module interface |
| Terraform | ALB + Target Group | Module interface |
| Terraform | ACM certificate | Module interface |
| Terraform | CloudWatch log group | Module interface |
| Terraform | IAM roles (ECS task role, execution role) | Module interface |
| CI/CD | GitHub Actions → ECR → ECS | Per-provider jobs |
| DNS | Cloudflare CNAME → ALB DNS | Already cloud-agnostic ✅ |

---

## Architecture: Terraform Module Structure

Refactor `infra/` from a flat collection of `.tf` files into a layered module system:

```
infra/
├── modules/                    # Cloud-agnostic interfaces (variables + outputs only, no resources)
│   ├── networking/             # Inputs: cidr_block, az_count. Outputs: vpc_id, public_subnet_ids, private_subnet_ids
│   ├── registry/               # Inputs: name. Outputs: repository_url, registry_server
│   ├── storage/                # Inputs: bucket_name, allowed_origins[]. Outputs: bucket_name, endpoint_url
│   ├── database/               # Inputs: engine_version, instance_tier, db_name, username, password. Outputs: connection_string, endpoint
│   ├── compute/                # Inputs: image_uri, cpu, memory, env_vars, secrets. Outputs: service_endpoint
│   └── tls/                    # Inputs: domain_names[]. Outputs: certificate_arn_or_id
├── providers/
│   ├── aws/
│   │   ├── main.tf             # Wires modules/ together using AWS resources
│   │   ├── variables.tf        # provider = "aws", region, etc.
│   │   ├── outputs.tf
│   │   └── backend.tf          # S3 + DynamoDB state backend
│   └── azure/
│       ├── main.tf             # Wires modules/ together using Azure resources
│       ├── variables.tf        # provider = "azurerm", location, subscription_id, etc.
│       ├── outputs.tf
│       └── backend.tf          # Azure Blob Storage state backend
└── environments/
    ├── dev.tfvars
    └── prod.tfvars
```

**Key principle:** `modules/` contains only `variables.tf` and `outputs.tf` — no actual resources. The `providers/aws/` and `providers/azure/` directories contain the real resource implementations that fulfill each module's interface.

---

## AWS Provider Implementation (Current Resources, Reorganised)

Migrate the existing flat `infra/*.tf` files into `infra/providers/aws/`:

| Module | AWS Resource |
|--------|-------------|
| `networking` | VPC, public/private subnets, IGW, NAT GW, route tables, security groups |
| `registry` | ECR repository (with scan-on-push) |
| `storage` | S3 bucket (AES256 encryption, CORS, block public access) |
| `database` | RDS for PostgreSQL (currently not provisioned — add it now) |
| `compute` | ECS Cluster + Service + Task Definition (frontend + backend containers), ASG |
| `tls` | ACM certificate + Cloudflare DNS validation records |
| `load_balancer` | ALB, target group, HTTP→HTTPS redirect listener, HTTPS listener |

---

## Azure Provider Implementation (New)

| Module | Azure Resource |
|--------|---------------|
| `networking` | Virtual Network, subnets (public + private), NSGs |
| `registry` | Azure Container Registry (ACR), Basic SKU |
| `storage` | Storage Account + Blob Container (equivalent CORS config) |
| `database` | Azure Database for PostgreSQL Flexible Server |
| `compute` | Azure Container Apps (frontend app + backend app, same environment) |
| `tls` | Azure-managed certificate via Container Apps custom domain |
| `load_balancer` | Azure Application Gateway or Container Apps built-in ingress |

**Azure Container Apps** is the right choice over AKS or ACI — it's the closest semantic equivalent to ECS (managed containers, autoscaling, built-in ingress), with no cluster management overhead.

---

## Application Layer: StorageClient Abstraction

**File to create:** `backend/app/clients/storage_client.py`

Define an abstract `StorageClient` class with three methods:
- `generate_upload_url(key: str, content_type: str, expires_in: int) -> str`
- `download_bytes(key: str) -> bytes`
- `delete_object(key: str) -> None`

**AWS implementation** (`backend/app/clients/storage_aws.py`):
- Wraps existing `boto3` S3 logic from `s3_client.py` (rename/refactor, don't rewrite)
- Presigned PUT URL via `generate_presigned_url("put_object", ...)`

**Azure implementation** (`backend/app/clients/storage_azure.py`):
- Uses `azure-storage-blob` SDK
- SAS token generation via `generate_blob_sas()` for upload URL
- `BlobClient.download_blob().readall()` for download
- `BlobClient.delete_blob()` for delete

**Factory in `backend/app/clients/storage_client.py`:**
```python
def get_storage_client() -> StorageClient:
    if settings.storage_provider == "azure":
        return AzureStorageClient(...)
    return S3StorageClient(...)   # default
```

**Config changes (`backend/app/config.py`):**
- Add `storage_provider: str = "aws"` (`"aws"` | `"azure"`)
- Add `azure_storage_connection_string: str | None = None`
- Add `azure_storage_container: str = "tailord-uploads"`
- Existing `aws_*` fields remain, but become optional when `storage_provider = "azure"`

**Replace all `s3_client` imports** in `backend/app/api/experience.py` with `get_storage_client()`.

---

## Backend Production Fix: DATABASE_URL

**File to change:** `backend/app/clients/database.py`

Current (broken in production):
```python
DATABASE_URL = "postgresql+psycopg://app:app@localhost:5432/app"
```

Change to:
```python
DATABASE_URL = settings.database_url  # reads from env var
```

**Config change (`backend/app/config.py`):**
```python
database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
```
Default preserves local dev behaviour. Production injects the managed Postgres connection string via env var.

---

## Backend Containerization

The backend `Dockerfile` already exists but is not deployed. Add it to the ECS task definition / Container Apps environment:

**ECS (AWS):** Add backend as a second container in the existing task definition (sidecar pattern):
- Image: `{ECR_URL}/tailord-backend:latest`
- Port: 8000
- Communicates with frontend over `localhost` (same task)
- IAM task role extended to include S3 permissions (already exists, just add backend container)

**Container Apps (Azure):** Create a second app in the same Container Apps environment:
- Frontend app: port 3000, public ingress
- Backend app: port 8000, internal ingress only (not public)
- Frontend calls backend via internal DNS: `http://tailord-backend.internal`

**Env vars to inject (both providers):**
```
DATABASE_URL=<from Terraform output>
API_KEY=<from secrets manager>
LLM_PROVIDER=openai
LLM_API_KEY=<from secrets manager>
LLM_MODEL=gpt-4o-mini
STORAGE_PROVIDER=aws|azure
S3_UPLOADS_BUCKET=tailord-uploads      # AWS only
AWS_REGION=us-east-2                   # AWS only (or use instance role)
AZURE_STORAGE_CONNECTION_STRING=...    # Azure only
AZURE_STORAGE_CONTAINER=tailord-uploads # Azure only
```

---

## CI/CD Updates

Current: single GitHub Actions workflow `docker-image.yml` builds and deploys frontend to AWS ECS.

New structure — two workflow files:

**`.github/workflows/deploy-aws.yml`:**
- Trigger: push to `main` + `DEPLOY_TARGET=aws` env
- Steps: build frontend image → ECR, build backend image → ECR, update ECS task def, deploy service

**`.github/workflows/deploy-azure.yml`:**
- Trigger: push to `main` + `DEPLOY_TARGET=azure` env (or manual trigger)
- Steps: build frontend image → ACR, build backend image → ACR, deploy to Container Apps

Both use GitHub OIDC for keyless auth (AWS already configured; Azure OIDC setup required).

---

## Complications & Things to Be Aware Of

### 1. Presigned URLs vs Azure SAS Tokens
S3 presigned PUT URLs and Azure SAS tokens are conceptually identical but mechanically different. The upload URL returned to the browser will look different. The CORS configuration on the storage container must also be set equivalently. The `StorageClient.generate_upload_url()` abstraction handles this, but test both paths end-to-end.

### 2. Managed Identity vs IAM Roles
On AWS, the ECS task role grants the container access to S3 without credentials. On Azure, the Container App needs a system-assigned Managed Identity with the `Storage Blob Data Contributor` role on the storage account. If using a connection string instead, it's simpler but less secure. The `storage_azure.py` client should prefer Managed Identity when running in Azure.

### 3. Container Apps Internal Networking
In ECS, sidecar containers in the same task share `localhost`. In Container Apps, frontend and backend are separate apps and communicate via internal DNS (e.g., `http://tailord-backend`). The frontend's `API_BASE_URL` env var will be different per provider:
- AWS: `http://localhost:8000` (sidecar)
- Azure: `http://tailord-backend` (internal Container Apps DNS)

### 4. Terraform State Backend Migration
The Terraform state is currently in an S3 bucket (`tailord-tf-state`). If applying the Azure provider, its state backend should use Azure Blob Storage — a separate `backend.tf` in `providers/azure/`. Do NOT share state between providers.

### 5. Database Migration on Deploy
Alembic migrations are run manually today. With managed Postgres, the migration must run before the new app version serves traffic. Options:
- **Init container** (ECS: depends_on / Azure: startup command before uvicorn)
- **GitHub Actions step** that runs `alembic upgrade head` via a one-off task after Postgres is up but before the service rolls out

### 6. Azure Flexible Server Cold Start
Azure Database for PostgreSQL Flexible Server takes 2–5 minutes to provision and can have cold start latency on the cheapest tier (Burstable B1ms). Plan for this in initial deploy timing.

### 7. ACM vs Azure Managed Certs
ACM certificates are free and auto-renewing but AWS-only. Azure Container Apps supports custom domains with managed certs (also free, also auto-renewing) but the validation mechanism differs. Since Cloudflare is already proxying the domain, TLS between Cloudflare and the origin can use a self-signed or origin certificate, simplifying both setups.

### 8. Backend Image Size (Playwright)
The backend Dockerfile installs Playwright + Chromium, making the image ~1.5–2 GB. This is the same on both clouds but affects:
- ECR/ACR storage cost
- Container startup time
- CI/CD build time (consider caching layers in GitHub Actions)

### 9. `pyproject.toml` New Dependency
Adding `azure-storage-blob` as an optional dependency (only installed when `STORAGE_PROVIDER=azure`) keeps the AWS image lean. Use a dependency group or extras:
```toml
[project.optional-dependencies]
azure = ["azure-storage-blob>=12.0"]
```

---

## Implementation Order

1. **Fix `DATABASE_URL`** — env var in config.py, update database.py (30 min, highest leverage, needed regardless)
2. **StorageClient abstraction** — create interface + refactor existing boto3 code into `S3StorageClient` (1–2 hr)
3. **Azure StorageClient** — implement `AzureStorageClient` with SAS tokens (1 hr)
4. **Terraform module refactor** — extract current flat infra into `providers/aws/` + define `modules/` interfaces (2–3 hr)
5. **AWS provider: add RDS** — managed Postgres was missing, add it to AWS infra (1 hr)
6. **Azure provider** — implement `providers/azure/` using Container Apps, ACR, Azure Blob, Azure DB for PG (3–4 hr)
7. **Backend container in task definition** — add to ECS task def (AWS) and Container Apps (Azure) (1 hr)
8. **CI/CD split** — two workflow files, one per provider (1 hr)
9. **End-to-end test on Azure** — deploy, run Alembic, verify upload flow, verify tailoring generation (1–2 hr)

**Total estimated effort: ~2–3 focused sessions**

---

## Verification

- [ ] `cd infra/providers/aws && terraform plan` shows no destructive changes (only reorganisation)
- [ ] `cd infra/providers/azure && terraform apply` provisions a working Azure environment
- [ ] Frontend loads at `tailord.app` (or a test domain) on Azure
- [ ] Backend health check endpoint responds from within Container Apps
- [ ] Resume upload flow works end-to-end on Azure (presigned URL → Azure SAS → blob upload → process → ready)
- [ ] Tailoring generation works end-to-end on Azure
- [ ] `STORAGE_PROVIDER=aws` → S3 path still works (regression check)
- [ ] `DATABASE_URL` env var works in both local dev and production

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `backend/app/clients/storage_client.py` | Create — abstract base + factory |
| `backend/app/clients/storage_aws.py` | Create — refactor existing s3_client.py logic here |
| `backend/app/clients/storage_azure.py` | Create — Azure Blob implementation |
| `backend/app/clients/s3_client.py` | Delete (absorbed into storage_aws.py) |
| `backend/app/config.py` | Modify — add database_url, storage_provider, azure_* fields |
| `backend/app/clients/database.py` | Modify — read DATABASE_URL from settings |
| `backend/app/api/experience.py` | Modify — replace s3_client imports with get_storage_client() |
| `backend/pyproject.toml` | Modify — add azure optional dependency group |
| `infra/providers/aws/` | Create — move + reorganise existing flat infra/*.tf files |
| `infra/providers/azure/` | Create — new Azure provider implementation |
| `infra/modules/` | Create — module interface definitions |
| `.github/workflows/deploy-aws.yml` | Create — rename + extend current docker-image.yml |
| `.github/workflows/deploy-azure.yml` | Create — Azure deployment workflow |
