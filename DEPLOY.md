# Deploy

El portfolio se sirve con Nginx dentro de EKS. Un ALB compartido enruta `/` al frontend y `/api/*` al backend; CloudFront se coloca delante del ALB para HTTPS y distribución. La web y el batch job no necesitan S3; el CSV del job es local y de ejemplo.

## Probar en local

La opción rápida usa Vite:

```bash
cd frontend
npm install
npm run dev
```

Para probar la misma imagen Nginx que se despliega en Kubernetes:

```bash
docker build -t devops-frontend ./frontend
docker run --rm -p 8080:8080 devops-frontend
```

Abre <http://localhost:8080>.

## Desplegar en AWS

Prerequisitos: AWS CLI con permisos para Terraform, EKS, EC2/VPC, IAM y CloudFront; Terraform, kubectl, Helm, Docker, Git y una cuenta Docker Hub con repositorios públicos para las imágenes. Esta opción evita ECR; si una SCP también bloquea otros servicios AWS, necesitarás que el administrador autorice esos servicios. La región usada por Terraform y estos pasos es `us-east-2`.

**Costos:** no hay una combinación de EKS + ALB + CloudFront que se pueda garantizar sin cargos. AWS cobra el control plane EKS por hora (actualmente USD 0.10/h para versiones con soporte estándar; USD 0.60/h para soporte extendido), aunque la instancia EC2 sea elegible para Free Tier. También se facturan por separado EC2, EBS, direcciones IPv4 públicas, ALB y el uso de CloudFront. Revisa [precios de EKS](https://aws.amazon.com/eks/pricing/), [precios de EC2](https://aws.amazon.com/ec2/pricing/) y [precios de CloudFront](https://aws.amazon.com/cloudfront/pricing/) antes de continuar.

El Free Tier de EC2 depende de la fecha de creación de la cuenta: las cuentas anteriores al 15 de julio de 2025 suelen tener `t3.micro`/`t2.micro` durante sus primeros 12 meses; las cuentas nuevas tienen una lista distinta que incluye `t3.small` y créditos limitados a 6 meses o hasta agotarse. `t3.micro` tiene 1 GiB de RAM y es muy limitado para un nodo EKS; `t3.small` tiene 2 GiB y es un punto de partida más razonable, pero solo será elegible si lo permite el plan de tu cuenta. Consulta el [Free Tier de EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html) y verifica la lista de tu cuenta/región antes de elegir. No hay forma de asegurar que `t3.small` sea gratis para esta cuenta.

### 1. Crear la infraestructura

```bash
cd infra
terraform init
terraform apply
cd ..
```

Terraform provisiona EKS. El primer apply no crea CloudFront porque el ALB se crea después, mediante Kubernetes. Revisa el `terraform plan`: este cambio elimina el bucket y la distribución CloudFront antiguos del frontend, además del repositorio ECR `devops-frontend` que ya no se usa. Si quieres conservar esos recursos o imágenes, no confirmes su eliminación hasta migrarlos. Antes de aplicar, identifica el nombre del bucket viejo (por ejemplo, con `terraform -chdir=infra state show aws_s3_bucket.frontend`) y vacíalo si tiene objetos; Terraform no elimina buckets S3 que no estén vacíos:

```bash
aws s3 rm s3://<frontend_bucket_name> --recursive
```

El tipo de EC2 por defecto es `t3.small`. Puedes consultar los tipos marcados Free Tier en `us-east-2` con:

```bash
aws ec2 describe-instance-types \
  --region us-east-2 \
  --filters Name=free-tier-eligible,Values=true \
  --query "InstanceTypes[*].[InstanceType]" \
  --output text | sort
```

Si `t3.small` no está en la lista, no lo uses esperando que sea gratis. `t3.micro` puede estar disponible para cuentas antiguas, pero sus 1 GiB de RAM pueden ser insuficientes para el cluster y sus pods. Puedes escoger el tipo al aplicar con `-var="eks_node_instance_type=TIPO"`; confirma su precio antes.

### 2. Construir y publicar la imagen Nginx en Docker Hub

El repositorio público `devops-frontend` debe existir en Docker Hub para que EKS pueda descargar la imagen sin credenciales adicionales. Inicia sesión con un Access Token de Docker Hub cuando `docker login` lo solicite. Ejecuta desde la raíz del repositorio:

```bash
cd "$(git rev-parse --show-toplevel)"
set -euo pipefail

DOCKERHUB_USERNAME=tute2781
FRONTEND_REPOSITORY="$DOCKERHUB_USERNAME/devops-frontend"
IMAGE_TAG=$(git rev-parse --short HEAD)

docker login --username "$DOCKERHUB_USERNAME"

docker build --platform linux/amd64 -t "$FRONTEND_REPOSITORY:$IMAGE_TAG" ./frontend
docker push "$FRONTEND_REPOSITORY:$IMAGE_TAG"
```

### 3. Conectar kubectl al cluster e instalar AWS Load Balancer Controller

```bash
aws eks update-kubeconfig --region us-east-2 --name cluster-tutorial
kubectl get nodes
```

El permiso del AWS Load Balancer Controller se adjunta al rol de los nodos porque la SCP bloquea la creación del proveedor OIDC. Para que el controller obtenga credenciales del rol del nodo, la plantilla de lanzamiento de Terraform requiere IMDSv2 con hop limit 2. Esto hace que las credenciales del nodo puedan ser accesibles desde pods del cluster: es menos aislado que IRSA y no debe usarse para workloads no confiables. Terraform aplica el permiso al rol de los nodos. Instala el controller:

```sh
helm repo add eks-charts https://aws.github.io/eks-charts
helm repo update
VPC_ID=$(aws eks describe-cluster --name cluster-tutorial --region us-east-2 --query "cluster.resourcesVpcConfig.vpcId" --output text)
helm upgrade --install aws-load-balancer-controller eks-charts/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName=cluster-tutorial \
  --set serviceAccount.create=true \
  --set region=us-east-2 \
  --set vpcId="$VPC_ID"
```

Espera a que los pods del controller estén `READY` antes de continuar.

### 4. Desplegar el portfolio

Actualiza el Ingress del backend y despliega el frontend. Ambos Ingresses usan el mismo grupo para que el AWS Load Balancer Controller cree un solo ALB; el orden prioriza `/api` antes de `/`.

```bash
DOCKERHUB_USERNAME=tute2781
BACKEND_IMAGE="$DOCKERHUB_USERNAME/http-service"
FRONTEND_REPOSITORY="$DOCKERHUB_USERNAME/devops-frontend"
IMAGE_TAG="api-health-fix-$(date +%Y%m%d-%H%M%S)"

docker login --username "$DOCKERHUB_USERNAME"
docker build --platform linux/amd64 -t "$BACKEND_IMAGE:$IMAGE_TAG" ./http-service
docker build --platform linux/amd64 -t "$FRONTEND_REPOSITORY:$IMAGE_TAG" ./frontend
docker push "$BACKEND_IMAGE:$IMAGE_TAG"
docker push "$FRONTEND_REPOSITORY:$IMAGE_TAG"

helm upgrade --install devop-web eks-devops-web/ \
  --namespace default \
  --set ingress.enabled=true \
  --set image.repository="$BACKEND_IMAGE" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Always

helm upgrade --install devops-frontend eks-devops-frontend/ \
  --namespace default \
  --set image.repository="$FRONTEND_REPOSITORY" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Always \
  --set ingress.enabled=true

kubectl rollout status deployment/devop-web-devops-web -n default --timeout=180s
kubectl rollout status deployment/devops-frontend-devops-frontend -n default --timeout=180s
kubectl get pods,service,ingress -n default
```

Ejecuta el bloque desde la raíz del repositorio y solo después de que ambos `docker push` terminen exitosamente. Usa un tag nuevo en cada publicación; no apuntes Helm a un SHA que no aparezca como tag en Docker Hub.

Espera a que ambos Ingresses muestren la misma dirección en `ADDRESS`. Comprueba primero el ALB directamente:

```bash
ALB_DNS=$(kubectl get ingress devop-web-devops-web -n default -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
curl -i "http://$ALB_DNS/"
curl -i "http://$ALB_DNS/api/"
```

La raíz debe devolver el portfolio y `/api` y `/api/` deben devolver JSON de Flask, ambas con `200` y sin redirigir a HTTP. `/health` devuelve `ok` desde Nginx; `/api/health` devuelve `{"status":"healthy"}` desde Flask.

### 5. Crear CloudFront delante del ALB

Pasa a Terraform el DNS del ALB compartido. Este es el propósito de `alb_dns_name`: ya no se usa para configurar CloudFront → API separadamente, sino como el único origen de CloudFront para frontend y API. La distribución crea HTTPS en el lado del visitante y reenvía las solicitudes al ALB por HTTP.

```bash
ALB_DNS=$(kubectl get ingress devop-web-devops-web -n default -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
printf 'alb_dns_name = "%s"\n' "$ALB_DNS" > infra/terraform.tfvars
terraform -chdir=infra apply

CLOUDFRONT_DOMAIN=$(terraform -chdir=infra output -raw cloudfront_domain_name)
echo "https://$CLOUDFRONT_DOMAIN"
curl -i "https://$CLOUDFRONT_DOMAIN/"
curl -i "https://$CLOUDFRONT_DOMAIN/api"
curl -i "https://$CLOUDFRONT_DOMAIN/api/"
curl -i "https://$CLOUDFRONT_DOMAIN/health"
```

El archivo local `infra/terraform.tfvars` conserva el origen para futuros `terraform plan/apply` y está excluido de Git. CloudFront puede tardar varios minutos en desplegarse. Ambos paths deben responder correctamente por el dominio CloudFront. Si cambia el DNS del ALB, actualiza ese archivo y vuelve a aplicar Terraform.

El workflow de GitHub Actions construye y publica una imagen con el SHA del commit cuando cambia `frontend/`. Configura el secreto de Actions `DOCKERHUB_TOKEN` con un Access Token de Docker Hub. Después de ese paso, despliega con Helm usando el SHA completo del commit:

```bash
FRONTEND_REPOSITORY=tute2781/devops-frontend
IMAGE_TAG=<sha-completo-del-commit>
helm upgrade --install devops-frontend eks-devops-frontend/ \
  --namespace default \
  --set image.repository="$FRONTEND_REPOSITORY" \
  --set image.tag="$IMAGE_TAG" \
  --set ingress.enabled=true
```

## Batch job opcional

El batch job usa `job-script/02_retry_classification.csv`, un CSV local de ejemplo incluido en la imagen. No necesita bucket S3, credenciales de AWS ni un rol IRSA. Para correrlo localmente:

```bash
python3 job-script/python-basics.py
python3 job-script/python-basics.py --run-number 12048
python3 job-script/python-basics.py --csv /ruta/a/otro.csv --run-number 12047
```

### Reconstruir y publicar la imagen del batch job

El repositorio Docker Hub `tute2781/my-image-py` todavía debe crearse como público. Abre Docker Desktop y confirma que `docker info` responde antes de construir. Luego, desde la raíz del repositorio, construye una imagen nueva desde los archivos actuales del job. Usa un tag nuevo para que Kubernetes no reutilice una imagen anterior almacenada en el nodo:

```bash
DOCKERHUB_USERNAME=tute2781
IMAGE_REPOSITORY="$DOCKERHUB_USERNAME/my-image-py"
IMAGE_TAG=$(date +%Y%m%d-%H%M%S)

docker login --username "$DOCKERHUB_USERNAME"
docker build --platform linux/amd64 \
  -t "$IMAGE_REPOSITORY:$IMAGE_TAG" \
  ./job-script
docker run --rm "$IMAGE_REPOSITORY:$IMAGE_TAG"
docker push "$IMAGE_REPOSITORY:$IMAGE_TAG"
```

El contenedor debe imprimir el resultado para `run_number=12047`. Si `docker info` dice que no puede conectar a `/var/run/docker.sock`, el motor de Docker no está iniciado: abre Docker Desktop y espera a que quede listo. Si informa que falta `docker-credential-desktop`, es un problema de la configuración local de credenciales de Docker, no del Dockerfile; corrígelo en Docker Desktop antes del login y el push. Si el build o la ejecución local fallan, no avances al despliegue.

Para volver a crear el Job en EKS, primero confirma que el release que vas a reemplazar se llama `devop-app`. Los Jobs no actualizan su imagen mediante `helm upgrade` porque Kubernetes trata varios campos del Job como inmutables; elimina ese release y créalo otra vez con el tag recién publicado:

```bash
helm list -n default
helm uninstall devop-app -n default
helm install devop-app eks-devops-app/ \
  --namespace default \
  --set image.repository="$IMAGE_REPOSITORY" \
  --set image.tag="$IMAGE_TAG"

kubectl get jobs,pods -n default
kubectl logs -n default job/devop-app-devops-app
```

El archivo CSV de ejemplo contiene datos demostrativos, no los datos originales del bucket anterior. La imagen `tute2781/my-image-py` necesita estar configurada como pública en Docker Hub para que el cluster pueda descargarla sin `imagePullSecret`.

### Actualizar los pods existentes desde Docker Hub

Los pods que fallaron siguen vinculados a Helm releases antiguos con repositorios ECR. Actualiza el backend para que use la imagen pública de Docker Hub:

```bash
helm upgrade devop-web eks-devops-web/ \
  --namespace default \
  --set image.repository=tute2781/http-service \
  --set image.tag=latest

kubectl rollout status deployment/devop-web-devops-web -n default
```

El batch job es un recurso `Job`; para reemplazar el pod que quedó con la imagen ECR, primero construye y publica la imagen como se explica en “Reconstruir y publicar la imagen del batch job”, luego elimina y recrea su release usando el tag publicado:

```bash
helm uninstall devop-app -n default
helm install devop-app eks-devops-app/ \
  --namespace default \
  --set image.repository=tute2781/my-image-py \
  --set image.tag="$IMAGE_TAG"

kubectl get pods,jobs -n default
kubectl logs -n default job/devop-app-devops-app
```

Comprueba en los eventos que el backend descarga `docker.io/tute2781/http-service:latest` y el Job `docker.io/tute2781/my-image-py:$IMAGE_TAG`.

## Limpieza

Desinstala primero el release para que AWS Load Balancer Controller elimine el ALB:

```bash
helm uninstall devops-frontend -n default
```

Después, si quieres eliminar toda la infraestructura:

```bash
cd infra
terraform destroy
```

Las imágenes de Docker Hub son independientes de Terraform y no se eliminan al destruir la infraestructura. El resumen completo y actualizado del despliegue está en [README.md](README.md).
