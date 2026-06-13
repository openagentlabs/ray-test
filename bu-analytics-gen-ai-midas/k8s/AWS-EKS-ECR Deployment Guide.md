# AWS EKS + ECR Deployment Guide

This guide documents a clean deployment flow for new frontend/backend code to EKS using ECR images.

## 1. Prerequisites

- AWS CLI authenticated (`saiyam-arora` profile used below).
- `kubectl` configured for cluster `midas-eks`.
- Docker with `buildx` available.
- EKS worker nodes are `Ready`.
- Namespace used: `midas-saiyam`.

Set once:

```bash
export AWS_PROFILE=saiyam-arora
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=882884688997
export TAG=2026-03-17-1
export AWS_PAGER=""
```

## 2. Connect to Cluster

Profile identity check:

```bash
aws sts get-caller-identity --profile saiyam-arora
```

If EKS API is private-only, start SSM port-forward session (keep this terminal open):

```bash
aws ssm start-session \
  --target i-016f1a774d0aeb452 \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host="DDBE7EDE47B7DD80F043C33400FC9F80.gr7.us-east-1.eks.amazonaws.com",portNumber="443",localPortNumber="9443" \
  --region us-east-1 \
  --profile saiyam-arora
```

Then point kubectl cluster server to localhost tunnel:

```bash
kubectl config set-cluster arn:aws:eks:us-east-1:882884688997:cluster/midas-eks \
  --server=https://127.0.0.1:9443 \
  --tls-server-name=DDBE7EDE47B7DD80F043C33400FC9F80.gr7.us-east-1.eks.amazonaws.com
```

Standard kubeconfig refresh command:

```bash
aws eks update-kubeconfig --name midas-eks --region $AWS_REGION --profile $AWS_PROFILE
kubectl config current-context
kubectl get nodes -o wide
```

## 3. Namespace and Node Placement

Create namespace (only once):

```bash
kubectl create namespace midas-saiyam
```

Label nodes (only once unless nodes are replaced):

```bash
kubectl label node ip-10-85-171-37.ec2.internal midas-role=frontend
kubectl label node ip-10-85-171-55.ec2.internal midas-role=backend
kubectl get nodes --show-labels | grep midas-role
```

## 4. Prepare Kubernetes Manifests

Update these files:

- `k8s/backend-deployment.yaml`
- `k8s/frontend-deployment.yaml`
- `k8s/backend-secret.template.yaml`

Required changes:

1. Add `namespace: midas-saiyam` in both Deployment and Service metadata.
2. Set backend image to:
   - `882884688997.dkr.ecr.us-east-1.amazonaws.com/midas-backend:<TAG>`
3. Set frontend image to:
   - `882884688997.dkr.ecr.us-east-1.amazonaws.com/midas-frontend:<TAG>`
4. Add node selectors:
   - frontend: `midas-role: frontend`
   - backend: `midas-role: backend`
5. Set frontend backend upstream:
   - `http://midas-backend.midas-saiyam.svc.cluster.local:8000`
6. Fill backend secret values in `k8s/backend-secret.template.yaml`.
7. Add deployment strategy to avoid extra rolling pods:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 0
    maxUnavailable: 1
```

## 5. Create ECR Repositories (One-Time)

```bash
aws ecr create-repository --repository-name midas-frontend --region $AWS_REGION --profile $AWS_PROFILE
aws ecr create-repository --repository-name midas-backend --region $AWS_REGION --profile $AWS_PROFILE
```

## 6. Build and Push Images (New Release)

Login:

```bash
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | \
docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

Build/push amd64 images (required for EKS Linux amd64 nodes):

```bash
docker buildx build --platform linux/amd64 \
  -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-frontend:${TAG} \
  --push ./frontend

docker buildx build --platform linux/amd64 \
  -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/midas-backend:${TAG} \
  --push ./backend
```

## 7. Deploy to EKS

Preview changes:

```bash
kubectl diff -f k8s/backend-secret.template.yaml
kubectl diff -f k8s/backend-deployment.yaml
kubectl diff -f k8s/frontend-deployment.yaml
```

Apply:

```bash
kubectl apply -f k8s/backend-secret.template.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
```

Verify rollout:

```bash
kubectl rollout status deploy/midas-backend -n midas-saiyam
kubectl rollout status deploy/midas-frontend -n midas-saiyam
kubectl get pods -n midas-saiyam -o wide
kubectl get svc -n midas-saiyam
kubectl get deploy -n midas-saiyam
```

## 8. Access the Frontend

### Option A: Port-forward (fastest)

```bash
kubectl port-forward -n midas-saiyam svc/midas-frontend 8080:80
```

Open:

- `http://localhost:8080`

### Option B: NodePort from jumpbox

If frontend Service is NodePort and port is `30174`, open:

- `http://10.85.171.37:30174`
- `http://10.85.171.55:30174`

## 9. Security Group Rules for NodePort Access

If NodePort is not reachable from `midas-windows-2022`, check SGs:

```bash
aws ec2 describe-security-groups \
  --group-ids sg-01d41a72ccb4b4364 sg-04aed60f397b6eac0 sg-0c78cb289b53cbe65 \
  --region us-east-1 \
  --query "SecurityGroups[].{GroupId:GroupId,Name:GroupName,Ingress:IpPermissions,Egress:IpPermissionsEgress}" \
  --output json
```

Allow jumpbox SG to worker SGs on NodePort:

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-04aed60f397b6eac0 \
  --ip-permissions 'IpProtocol=tcp,FromPort=30174,ToPort=30174,UserIdGroupPairs=[{GroupId=sg-01d41a72ccb4b4364}]' \
  --region us-east-1

aws ec2 authorize-security-group-ingress \
  --group-id sg-0c78cb289b53cbe65 \
  --ip-permissions 'IpProtocol=tcp,FromPort=30174,ToPort=30174,UserIdGroupPairs=[{GroupId=sg-01d41a72ccb4b4364}]' \
  --region us-east-1
```

From `midas-windows-2022` PowerShell:

```powershell
Test-NetConnection 10.85.171.37 -Port 30174
Test-NetConnection 10.85.171.55 -Port 30174
```

## 10. Troubleshooting

1. `InvalidImageName`
- Cause: image has `${TAG}` literal or malformed tag (example `::latest`).
- Fix: set explicit image tags in YAML, then `kubectl apply`.

2. `exec format error` in frontend
- Cause: architecture mismatch (arm64 image on amd64 node).
- Fix: rebuild with `docker buildx build --platform linux/amd64`.

3. Old pods keep reappearing
- Expected with Deployment controller.
- If rollout stuck:

```bash
kubectl scale deploy/midas-backend -n midas-saiyam --replicas=0
kubectl scale deploy/midas-frontend -n midas-saiyam --replicas=0
kubectl get pods -n midas-saiyam -w
kubectl scale deploy/midas-backend -n midas-saiyam --replicas=1
kubectl scale deploy/midas-frontend -n midas-saiyam --replicas=1
```

Force delete only if stuck terminating:

```bash
kubectl delete pod -n midas-saiyam <pod-name> --force --grace-period=0
```

4. Service has no endpoints
- Check pod readiness:

```bash
kubectl get endpoints -n midas-saiyam midas-frontend
kubectl get endpoints -n midas-saiyam midas-backend
kubectl logs -n midas-saiyam deploy/midas-frontend --tail=100
kubectl logs -n midas-saiyam deploy/midas-backend --tail=100
```

5. In-cluster service test

```bash
kubectl run tmp-curl -n midas-saiyam --image=curlimages/curl --restart=Never -- sleep 3600
kubectl exec -n midas-saiyam tmp-curl -- curl -I http://midas-frontend
kubectl delete pod tmp-curl -n midas-saiyam
```

## 11. Clean Release Habit

- Use immutable tags (`2026-03-17-1`, `2026-03-17-2`, etc.), avoid relying on `latest`.
- Keep namespace-scoped deployment (`midas-saiyam`) to avoid affecting existing workloads.
- Prefer `kubectl diff` before every apply.
