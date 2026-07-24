# Deploy Guide

Orden lógico para desplegar este repositorio tal como está (asume que todos los archivos — `infra/`, `eks-devops-app/`, `eks-devops-web/`, `http-service/`, `job-script/`, `frontend/` — ya existen). 

**Prerrequisitos:** AWS CLI configurado, Terraform, kubectl, helm, Docker y Node.js instalados; credenciales con permisos de IAM/EKS/EC2/VPC/S3/CloudFront/ECR.

---

## Fase 1: Construir y publicar las imágenes en ECR

```bash
# Batch job (job-script/)
aws ecr create-repository --repository-name my-image-py --region us-east-1 2>/dev/null || true
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

cd job-script
docker build --platform linux/amd64 -t my-image-py:latest .
docker tag my-image-py:latest <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/my-image-py:latest
docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/my-image-py:latest
cd ..

# Backend Flask (http-service/)
aws ecr create-repository --repository-name devops-web --region us-east-1 2>/dev/null || true

cd http-service
docker build --platform linux/amd64 -t devops-web:latest .
docker tag devops-web:latest <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/devops-web:latest
docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/devops-web:latest
cd ..
```

Ajusta `eks-devops-app/values.yaml` y `eks-devops-web/values.yaml` si el `image.repository` no apunta ya a tu cuenta/tag.

---

## Fase 2: Infraestructura base (primer `terraform apply`)

```bash
cd infra
terraform init
terraform apply
```

Esto crea VPC, subnets, EKS cluster + node group, roles IAM, IRSA (batch job y AWS Load Balancer Controller), y el bucket S3 + CloudFront del frontend (con el origin del ALB todavía en placeholder).

Tarda 10-15 min por el control plane de EKS.

```bash
aws eks update-kubeconfig --region us-east-1 --name cluster-tutorial
kubectl cluster-info
kubectl get nodes
```

Si `kubectl` falla con `no such host`, corre de nuevo `aws eks update-kubeconfig` (o espera 1-2 min a que propague el DNS del endpoint).

---

## Fase 3: Desplegar el batch job y el backend

```bash
helm install devops-app eks-devops-app/ -n default
kubectl get jobs
kubectl logs -n default -l app.kubernetes.io/name=devops-app   # debe terminar en Complete 1/1

helm install devops-web eks-devops-web/ -n default
kubectl get pods -n default   # debe quedar Running / 1/1 READY
```

Verificación rápida (opcional, dentro del cluster):

```bash
export POD_NAME=$(kubectl get pods --namespace default -l "app.kubernetes.io/name=devops-web,app.kubernetes.io/instance=devops-web" -o jsonpath="{.items[0].metadata.name}")
kubectl port-forward $POD_NAME 8080:5000
curl http://localhost:8080/health
```

---

## Fase 4: AWS Load Balancer Controller

```bash
helm repo add eks-charts https://aws.github.io/eks-charts
helm repo update

ROLE_ARN=$(terraform -chdir=infra output -raw aws_load_balancer_controller_role_arn)
VPC_ID=$(aws eks describe-cluster --name cluster-tutorial --query "cluster.resourcesVpcConfig.vpcId" --output text)

kubectl create serviceaccount aws-load-balancer-controller -n kube-system --dry-run=client -o yaml | kubectl apply -f -
kubectl annotate serviceaccount aws-load-balancer-controller -n kube-system \
  eks.amazonaws.com/role-arn=$ROLE_ARN --overwrite

helm install aws-load-balancer-controller eks-charts/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=cluster-tutorial \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=us-east-1 \
  --set vpcId=$VPC_ID

kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```

Espera a `2/2 READY` antes de seguir.

---

## Fase 5: Exponer la API (Ingress) y reconectar CloudFront (segundo `terraform apply`)

```bash
helm upgrade devops-web eks-devops-web/ -n default --set ingress.enabled=true
kubectl get ingress -n default -w   # espera el DNS del ALB en ADDRESS, Ctrl+C al verlo

ALB_DNS=$(kubectl get ingress -n default -o jsonpath="{.items[0].status.loadBalancer.ingress[0].hostname}")
curl -i http://$ALB_DNS/api/         # valida el ALB directo antes de tocar CloudFront

cd infra
terraform apply -var="alb_dns_name=$ALB_DNS"
cd ..

CLOUDFRONT_DOMAIN=$(terraform -chdir=infra output -raw cloudfront_domain_name)
curl -i https://$CLOUDFRONT_DOMAIN/api/
```

Nota: el path debe llevar la barra final (`/api/`, no `/api`) — el `path_pattern` de CloudFront es `/api/*`.

---

## Fase 6: Build y deploy del frontend

```bash
cd frontend
npm install
npm run build

BUCKET=$(terraform -chdir=../infra output -raw frontend_bucket_name)
DISTRIBUTION_ID=$(terraform -chdir=../infra output -raw cloudfront_distribution_id)

aws s3 sync dist/ s3://$BUCKET --delete
aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
cd ..
```

Abre `https://$CLOUDFRONT_DOMAIN` en el navegador para confirmar el mensaje de la API en vivo, la sección de servicios y la de comandos del runbook.

---

## Fase 7: Verificación end-to-end

```bash
kubectl get jobs
curl -i http://$ALB_DNS/api/health
curl -i https://$CLOUDFRONT_DOMAIN/api/
curl -sI https://$CLOUDFRONT_DOMAIN/ | head -1
```

---

## Fase 8: Limpieza / destruir

El ALB lo crea el AWS Load Balancer Controller (Kubernetes), no Terraform — hay que desinstalar los Helm releases antes de destruir, o el ALB queda huérfano.

```bash
helm uninstall devops-web -n default
helm uninstall devops-app -n default
helm uninstall aws-load-balancer-controller -n kube-system

kubectl get ingress -n default   # confirma que no quedó Ingress/ALB colgado

BUCKET=$(terraform -chdir=infra output -raw frontend_bucket_name)
aws s3 rm s3://$BUCKET --recursive

cd infra
terraform destroy
cd ..

kubectl get pods
kubectl get svc
aws eks list-clusters --region us-east-1
```
