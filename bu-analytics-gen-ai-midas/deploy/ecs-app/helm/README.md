# MIDAS Helm charts (`deploy/ecs-app/helm`)

Application Helm charts for workloads on the MIDAS **EKS** cluster (private API). Cluster-level add-ons (e.g. AWS Load Balancer Controller) remain documented under [`deploy/k8s/aws-load-balancer-controller/`](../../k8s/aws-load-balancer-controller/).

- **Release order:** [`releases.yaml`](releases.yaml) - processed in order by **`deploy/scripts/ci/helm-deploy-releases.sh`** from Jenkins when **`ENABLE_HELM_DEPLOY`** is enabled.
- **Images:** Set repository and tag via values or `--set image.tag=${IMAGE_TAG}` to match the **`Push images to ECR`** stage. Repository URIs come from Terraform outputs (`ecr_*_repository_url`).
- **Ingress:** Internal ALBs only - see [`deploy/k8s/aws-load-balancer-controller/README.md`](../../k8s/aws-load-balancer-controller/README.md).
- **Solution doc index:** [Solution documentation index](../../../README.midas.md)
- **Docker builds:** [Docker README](../docker/README.md)
- **Web chart:** `midas-web-frontend-svc` probes use **`GET /health`** on port 80; the nginx image serves a static **`/usr/share/nginx/html/health`** file (see the service Dockerfile).

## Private cluster note

If Jenkins agents cannot reach the Kubernetes API, **disable `ENABLE_HELM_DEPLOY`** for that build (the job defaults it **on**) and run `helm upgrade --install` from an in-VPC path (e.g. SSM jump box) using the same charts and values.
