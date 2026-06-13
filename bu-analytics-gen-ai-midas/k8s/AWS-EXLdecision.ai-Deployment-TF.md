# AWS EXLdecision.ai Deployment with Terraform (App Layer Only)

This runbook is aligned to:

- `k8s/terraform-app-deploy.tf`

It deploys only app resources to an existing EKS cluster:

- namespace
- backend secret
- backend deployment/service
- frontend deployment/service

## 1. Build and Push New Images

```bash
export AWS_PROFILE=saiyam-arora
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=882884688997
export TAG=2026-03-17-1

aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | \
docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

docker buildx build --platform linux/amd64 \
  -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-frontend:${TAG} \
  --push ./frontend

docker buildx build --platform linux/amd64 \
  -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-backend:${TAG} \
  --push ./backend
```

## 2. (Private EKS) Start SSM Tunnel

If EKS API endpoint is private-only:

```bash
aws sts get-caller-identity --profile saiyam-arora

aws ssm start-session \
  --target i-016f1a774d0aeb452 \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host="DDBE7EDE47B7DD80F043C33400FC9F80.gr7.us-east-1.eks.amazonaws.com",portNumber="443",localPortNumber="9443" \
  --region us-east-1 \
  --profile saiyam-arora
```

In another terminal:

```bash
kubectl config set-cluster arn:aws:eks:us-east-1:882884688997:cluster/midas-eks \
  --server=https://127.0.0.1:9443 \
  --tls-server-name=DDBE7EDE47B7DD80F043C33400FC9F80.gr7.us-east-1.eks.amazonaws.com
```

## 3. Create tfvars File (Per Environment)

Create `k8s/dev.tfvars`:

```hcl
aws_region   = "us-east-1"
aws_profile  = "saiyam-arora"
cluster_name = "midas-eks"
namespace    = "midas-saiyam-dev"

backend_image  = "882884688997.dkr.ecr.us-east-1.amazonaws.com/midas-backend:2026-03-17-1"
frontend_image = "882884688997.dkr.ecr.us-east-1.amazonaws.com/midas-frontend:2026-03-17-1"

backend_upstream = "http://midas-backend.midas-saiyam-dev.svc.cluster.local:8000"

backend_node_selector = {
  "midas-role" = "backend"
}

frontend_node_selector = {
  "midas-role" = "frontend"
}

backend_secret_data = {
  ENDPOINT          = "replace_me"
  API_KEY           = "replace_me"
  MODEL             = "replace_me"
  EMBEDDING_MODEL   = "replace_me"
  EMBEDDING_ENDPOINT = "replace_me"
  API_KEY_EMBEDDING = "replace_me"
  AZURE_KG_ENDPOINT = "replace_me"
  KG_MODEL          = "replace_me"
}
```

## 4. Terraform Apply

```bash
cd k8s
terraform init
terraform fmt
terraform validate
terraform plan -var-file=dev.tfvars -out=tfplan-dev
terraform apply tfplan-dev
```

## 5. Verify Deployment

```bash
kubectl get ns
kubectl get deploy,svc,pods -n midas-saiyam-dev -o wide
kubectl rollout status deploy/midas-backend -n midas-saiyam-dev
kubectl rollout status deploy/midas-frontend -n midas-saiyam-dev
kubectl get endpoints -n midas-saiyam-dev midas-backend
kubectl get endpoints -n midas-saiyam-dev midas-frontend
```

## 6. Access Frontend

```bash
kubectl port-forward -n midas-saiyam-dev svc/midas-frontend 8080:80
```

Open:

- `http://localhost:8080`

## 7. Manual Changes Required Per Environment

Update these values in tfvars for each new environment:

1. `cluster_name`
2. `namespace`
3. `backend_image`
4. `frontend_image`
5. `backend_upstream`
6. `backend_node_selector` / `frontend_node_selector` (if labels differ)
7. `backend_secret_data` values
