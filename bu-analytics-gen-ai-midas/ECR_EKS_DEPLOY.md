# ECR + EKS Deployment

## 1. Build images locally

```bash
cd /Users/saiyam268728/Library/CloudStorage/OneDrive-EXLService.com(I)Pvt.Ltd/Desktop/UC-Github/Docker/bu-analytics-gen-ai-midas
docker compose -f docker-compose.yml build backend frontend
```

## 2. Tag images for ECR

```bash
AWS_ACCOUNT_ID=<your-account-id>
AWS_REGION=<your-region>
BACKEND_REPO=midas-backend
FRONTEND_REPO=midas-frontend
TAG=<release-tag>

docker tag bu-analytics-gen-ai-midas-backend:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${BACKEND_REPO}:${TAG}

docker tag bu-analytics-gen-ai-midas-frontend:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${FRONTEND_REPO}:${TAG}
```

## 3. Push to ECR

```bash
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${BACKEND_REPO}:${TAG}
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${FRONTEND_REPO}:${TAG}
```

## 4. Update Kubernetes manifests

1. Replace image placeholders in:
1. [k8s/backend-deployment.yaml](/Users/saiyam268728/Library/CloudStorage/OneDrive-EXLService.com(I)Pvt.Ltd/Desktop/UC-Github/Docker/bu-analytics-gen-ai-midas/k8s/backend-deployment.yaml)
1. [k8s/frontend-deployment.yaml](/Users/saiyam268728/Library/CloudStorage/OneDrive-EXLService.com(I)Pvt.Ltd/Desktop/UC-Github/Docker/bu-analytics-gen-ai-midas/k8s/frontend-deployment.yaml)

2. Create backend secret from:
1. [k8s/backend-secret.template.yaml](/Users/saiyam268728/Library/CloudStorage/OneDrive-EXLService.com(I)Pvt.Ltd/Desktop/UC-Github/Docker/bu-analytics-gen-ai-midas/k8s/backend-secret.template.yaml)

3. Set ingress host in:
1. [k8s/ingress.yaml](/Users/saiyam268728/Library/CloudStorage/OneDrive-EXLService.com(I)Pvt.Ltd/Desktop/UC-Github/Docker/bu-analytics-gen-ai-midas/k8s/ingress.yaml)

## 5. Deploy to EKS

```bash
kubectl apply -f k8s/backend-secret.template.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

## Notes

1. Backend image is production-ready via Gunicorn.
2. Frontend image now supports runtime backend URL through `BACKEND_UPSTREAM`.
3. In EKS, frontend uses `http://midas-backend:8000` by default.
