# Portfolio DevOps de Matías Cisterna

Portfolio personal y laboratorio de DevOps desplegado en AWS con Terraform, Kubernetes (EKS), Nginx, Flask, un Application Load Balancer (ALB) y CloudFront.

## Arquitectura actual

```text
Navegador
  └── HTTPS → CloudFront
                └── HTTP → ALB compartido
                            ├── /        → Nginx: portfolio estático
                            └── /api*    → Flask: API de ejemplo

Batch Job de Kubernetes → CSV de ejemplo incluido en la imagen
```

Las imágenes Docker públicas se alojan en Docker Hub bajo `tute2781`. El sitio y el batch job ya no dependen de S3. Terraform no crea el ALB: lo crea AWS Load Balancer Controller a partir de los Ingress de Kubernetes. CloudFront se configura después de que exista el ALB.

## Contenido del repositorio

- [`frontend/`](frontend/) — portfolio estático; Vite sirve el desarrollo y Nginx sirve la imagen de producción.
- [`http-service/`](http-service/) — API Flask. `/api` y `/api/` entregan el mensaje; `/api/health` comprueba la API.
- [`job-script/`](job-script/) — script Python que busca un `run_number` en un CSV local de ejemplo.
- [`eks-devops-frontend/`](eks-devops-frontend/) — chart Helm para Nginx, servicio e Ingress del sitio.
- [`eks-devops-web/`](eks-devops-web/) — chart Helm para Flask, servicio e Ingress de la API.
- [`eks-devops-app/`](eks-devops-app/) — chart Helm para ejecutar el batch Job.
- [`infra/`](infra/) — Terraform para red, EKS, roles, permisos del Load Balancer Controller y CloudFront.
- [`.github/workflows/`](.github/workflows/) — workflows que construyen y publican imágenes en Docker Hub.
- [`DEPLOY.md`](DEPLOY.md) — guía ampliada de despliegue y ejecución del batch job.

## Rutas del sitio y verificaciones

| URL | Respuesta esperada | Componente |
| --- | --- | --- |
| `/` | Portfolio de Matías | Nginx |
| `/health` | HTTP `200`, texto `ok` | Health check de Nginx |
| `/api` y `/api/` | HTTP `200`, JSON con `message` y `status` | Flask |
| `/api/health` | HTTP `200`, `{"status":"healthy"}` | Health check de Flask |
| `/api/ready` | HTTP `200`, `{"status":"ready"}` | Readiness de Flask |

`/healthz` no se usa: el health check del frontend se llama `/health`.

## Probar localmente

### Portfolio con Vite

Requiere Node.js y npm:

```bash
cd frontend
npm ci
npm run dev
```

Abre la URL local que muestra Vite. El portfolio estático no requiere la API ni credenciales AWS.

### Portfolio con Nginx

Requiere Docker Desktop iniciado:

```bash
docker info
docker build --platform linux/amd64 -t devops-frontend:local ./frontend
docker run --rm -p 8080:8080 devops-frontend:local
```

Abre <http://localhost:8080>; comprueba el health check con `curl -i http://localhost:8080/health`.

### API Flask

```bash
cd http-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

En otra terminal, prueba `curl -i http://localhost:5001/api` y `curl -i http://localhost:5001/api/health`.

### Batch Job

Desde la raíz del repositorio:

```bash
python3 job-script/python-basics.py
python3 job-script/python-basics.py --run-number 12048
python3 job-script/python-basics.py --csv /ruta/a/otro.csv --run-number 12047
```

El archivo incluido contiene datos demostrativos, no una copia del CSV de S3 que usaba la versión anterior.

## Despliegue en AWS

### Prerrequisitos y costos

Se requieren AWS CLI, Terraform, kubectl, Helm, Docker Desktop, Git y una cuenta Docker Hub. Terraform usa la región `us-east-2`, cluster `cluster-tutorial` y el node group `node-group-tutorial`. Los repositorios Docker Hub deben ser públicos para que EKS descargue sus imágenes sin `imagePullSecret`.

La cuenta de pruebas tiene una SCP que bloquea ECR y la creación de proveedores OIDC. Por eso las imágenes se publican en Docker Hub y los permisos del AWS Load Balancer Controller se adjuntan al rol de los nodos. Con IMDSv2 y hop limit 2, los pods podrían obtener credenciales de ese rol: es menos aislado que IRSA y solo debe usarse con workloads de confianza.

**Este despliegue no es gratuito garantizado.** EKS factura el control plane por hora; EC2, volúmenes EBS, direcciones IP públicas, ALB y CloudFront pueden generar cargos adicionales. Que un tipo de EC2 sea elegible para Free Tier no hace gratuito el cluster. La elegibilidad depende de la fecha/plan de la cuenta y de la región. Consulta [precios de EKS](https://aws.amazon.com/eks/pricing/), [precios de EC2](https://aws.amazon.com/ec2/pricing/) y [Free Tier de EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html) antes de crear recursos.

El tipo predeterminado del nodo es `t3.small` (2 GiB de RAM). Verifica elegibilidad en `us-east-2`:

```bash
aws ec2 describe-instance-types \
  --region us-east-2 \
  --filters Name=free-tier-eligible,Values=true \
  --query "InstanceTypes[*].[InstanceType]" \
  --output text | sort
```

Si cambias el tipo, pásalo a Terraform con `-var="eks_node_instance_type=TIPO"` y revisa el precio antes de aplicar.

### 1. Crear o actualizar infraestructura

Desde la raíz:

```bash
terraform -chdir=infra init
terraform -chdir=infra plan
```

Lee el plan antes de confirmar. El cambio desde la arquitectura S3/CloudFront/ECR anterior puede proponer retirar recursos viejos; no confirmes eliminaciones inesperadas. Si Terraform indica que un bucket S3 antiguo no está vacío, identifica el bucket en el estado y decide qué hacer con su contenido antes de destruirlo.

```bash
terraform -chdir=infra apply
```

El primer apply crea el cluster, el node group y los permisos IAM, pero no CloudFront: el ALB todavía no existe. Si el node group falla por elegibilidad o capacidad de EC2, revisa tipo, región y las restricciones de la cuenta antes de volver a aplicar.

### 2. Publicar imágenes en Docker Hub

Crea como **públicos** estos repositorios Docker Hub:

- `tute2781/http-service`
- `tute2781/devops-frontend`
- `tute2781/my-image-py` (solo si también vas a ejecutar el batch Job)

Abre Docker Desktop y confirma que `docker info` responde. Desde la raíz del repo, usa un tag nuevo para cada publicación:

```bash
export DOCKERHUB_USERNAME=tute2781
export BACKEND_IMAGE="$DOCKERHUB_USERNAME/http-service"
export FRONTEND_IMAGE="$DOCKERHUB_USERNAME/devops-frontend"
export IMAGE_TAG="release-$(date +%Y%m%d-%H%M%S)"

docker login --username "$DOCKERHUB_USERNAME"

docker build --platform linux/amd64 -t "$BACKEND_IMAGE:$IMAGE_TAG" ./http-service
docker build --platform linux/amd64 -t "$FRONTEND_IMAGE:$IMAGE_TAG" ./frontend

docker push "$BACKEND_IMAGE:$IMAGE_TAG"
docker push "$FRONTEND_IMAGE:$IMAGE_TAG"
```

Continúa solo si ambos `push` terminan correctamente. Conserva esta terminal: contiene `BACKEND_IMAGE`, `FRONTEND_IMAGE` e `IMAGE_TAG`, que se usan en los pasos siguientes. No despliegues un tag SHA/versión hasta confirmar que ese tag existe en Docker Hub.

Los workflows de GitHub Actions también publican las imágenes modificadas al hacer push a `main`. Configura el secreto de repositorio `DOCKERHUB_TOKEN` con un Access Token de Docker Hub. El workflow construye tags SHA completos y `latest` para backend/job, y un tag SHA completo para frontend. Que exista el commit no garantiza que se haya publicado su imagen: verifica que la ejecución de Actions terminó bien y que el tag está en Docker Hub antes de pasar el SHA a Helm.

### 3. Configurar kubectl e instalar AWS Load Balancer Controller

```bash
aws eks update-kubeconfig --region us-east-2 --name cluster-tutorial
kubectl config current-context
kubectl get nodes
```

El nodo debe aparecer `Ready`. Terraform adjunta la política del Load Balancer Controller al rol del node group debido al bloqueo OIDC. Instala el controller:

```bash
helm repo add eks-charts https://aws.github.io/eks-charts
helm repo update

VPC_ID=$(aws eks describe-cluster \
  --name cluster-tutorial \
  --region us-east-2 \
  --query 'cluster.resourcesVpcConfig.vpcId' \
  --output text)

helm upgrade --install aws-load-balancer-controller \
  eks-charts/aws-load-balancer-controller \
  --namespace kube-system \
  --set clusterName=cluster-tutorial \
  --set serviceAccount.create=true \
  --set region=us-east-2 \
  --set vpcId="$VPC_ID"

kubectl get pods -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller
```

Espera a que el pod del controller esté `Running` y `Ready` antes de crear Ingresses.

### 4. Desplegar API y portfolio detrás de un ALB compartido

Ambos Ingresses usan el grupo ALB `devops-portfolio`: `/api` tiene prioridad sobre `/` y ambos deben mostrar el mismo DNS.

```bash
helm upgrade --install devop-web eks-devops-web/ \
  --namespace default \
  --set image.repository="$BACKEND_IMAGE" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Always \
  --set ingress.enabled=true

helm upgrade --install devops-frontend eks-devops-frontend/ \
  --namespace default \
  --set image.repository="$FRONTEND_IMAGE" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Always \
  --set ingress.enabled=true

kubectl rollout status deployment/devop-web-devops-web \
  -n default --timeout=180s
kubectl rollout status deployment/devops-frontend-devops-frontend \
  -n default --timeout=180s
kubectl get pods,services,ingress -n default
```

Espera hasta que ambos Ingresses tengan el mismo `ADDRESS`. Obtén y prueba el ALB antes de configurar CloudFront:

```bash
export ALB_DNS=$(kubectl get ingress devop-web-devops-web \
  -n default \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

curl -i "http://$ALB_DNS/"
curl -i "http://$ALB_DNS/health"
curl -i "http://$ALB_DNS/api"
curl -i "http://$ALB_DNS/api/"
curl -i "http://$ALB_DNS/api/health"
```

La raíz debe servir el portfolio; `/health` debe responder `200`; `/api` y `/api/` deben responder `200` con JSON sin redirigir a HTTP; `/api/health` debe devolver `{"status":"healthy"}`. No avances a CloudFront si falla el acceso directo al ALB.

### 5. Crear o actualizar CloudFront

CloudFront usa el ALB como origen único. Terraform recibe el DNS del ALB por un archivo local ignorado por Git, `infra/terraform.tfvars`; este archivo evita perder el valor en futuros `plan/apply`.

```bash
printf 'alb_dns_name = "%s"\n' "$ALB_DNS" > infra/terraform.tfvars
terraform -chdir=infra plan
```

Comprueba que el plan solo cree/actualice la distribución CloudFront con el ALB correcto y que no destruya recursos inesperados. Luego aplica:

```bash
terraform -chdir=infra apply
```

CloudFront puede tardar varios minutos en desplegar. Obtén el dominio y valida las mismas rutas:

```bash
export CLOUDFRONT_DOMAIN=$(terraform -chdir=infra output -raw cloudfront_domain_name)

curl -i "https://$CLOUDFRONT_DOMAIN/"
curl -i "https://$CLOUDFRONT_DOMAIN/health"
curl -i "https://$CLOUDFRONT_DOMAIN/api"
curl -i "https://$CLOUDFRONT_DOMAIN/api/"
curl -i "https://$CLOUDFRONT_DOMAIN/api/health"
```

Si se recrea el ALB y cambia su DNS, actualiza `infra/terraform.tfvars` con el nuevo `ADDRESS`, revisa `terraform plan` y aplica Terraform de nuevo. Un `502` con el mensaje de CloudFront sobre no poder resolver el origin suele indicar que la distribución conserva un DNS de ALB viejo.

### 6. Ejecutar el batch Job (opcional)

El Job lee el CSV local de ejemplo y no necesita S3, AWS credentials ni IRSA. Para publicar la imagen:

```bash
export JOB_IMAGE="$DOCKERHUB_USERNAME/my-image-py"
export JOB_TAG="job-$(date +%Y%m%d-%H%M%S)"

docker build --platform linux/amd64 -t "$JOB_IMAGE:$JOB_TAG" ./job-script
docker run --rm "$JOB_IMAGE:$JOB_TAG"
docker push "$JOB_IMAGE:$JOB_TAG"
```

El contenedor debe imprimir el resultado de `run_number=12047`. El repositorio Docker Hub `my-image-py` debe ser público. Como Kubernetes Jobs son recursos inmutables, elimina y recrea el release para cambiar su imagen:

```bash
helm uninstall devop-app -n default
helm install devop-app eks-devops-app/ \
  --namespace default \
  --set image.repository="$JOB_IMAGE" \
  --set image.tag="$JOB_TAG"

kubectl get jobs,pods -n default
kubectl logs -n default job/devop-app-devops-app
```

`Completed` indica que el Job terminó correctamente.

## Actualizar imágenes existentes

Construye y publica las nuevas imágenes con un tag único como en el paso 2. Luego actualiza ambos Deployments con ese mismo tag:

```bash
helm upgrade devop-web eks-devops-web/ \
  -n default \
  --set image.repository="$BACKEND_IMAGE" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Always

helm upgrade devops-frontend eks-devops-frontend/ \
  -n default \
  --set image.repository="$FRONTEND_IMAGE" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Always

kubectl rollout status deployment/devop-web-devops-web -n default --timeout=180s
kubectl rollout status deployment/devops-frontend-devops-frontend -n default --timeout=180s
```

Incluye `--set ingress.enabled=true` al actualizar un release si su Ingress estaba deshabilitado. Si un rollout apunta a un tag que no existe, restaura temporalmente el tag público anterior y publica el nuevo tag antes de intentarlo otra vez.

## Diagnóstico rápido

```bash
kubectl get nodes
kubectl get pods,services,ingress -n default
kubectl get jobs -n default
helm list -n default
```

- `ImagePullBackOff` / `ErrImagePull`: comprueba que `image.repository:tag` existe y es público en Docker Hub. `docker build` por sí solo no publica una imagen; hace falta `docker push`.
- `ImagePullBackOff` con un SHA: no uses el tag hasta que GitHub Actions haya publicado exactamente ese SHA.
- `kubectl rollout status` expira: inspecciona `kubectl describe pod POD -n default` y los eventos con `kubectl get events -n default --sort-by=.lastTimestamp`.
- `helm upgrade` dice que el release no está desplegado: revisa `helm list --all -n default` y usa el nombre real del release; `--install` crea el release si no existe.
- Ingress sin dirección: revisa que el Load Balancer Controller esté `Ready`, y consulta `kubectl describe ingress INGRESS -n default`.
- CloudFront responde `502`: compara `infra/terraform.tfvars` con el `ADDRESS` actual de ambos Ingress y actualiza Terraform si el ALB cambió.
- `/api` devuelve `404` o redirección: confirma que el backend corre la imagen nueva; prueba tanto `/api` como `/api/` y revisa que CloudFront tenga el comportamiento `/api*`.
- `/healthz` da `404`: la ruta actual es `/health`; las probes de Nginx y el health check del ALB deben apuntar a `/health`.
- Docker no conecta con `/var/run/docker.sock`: inicia Docker Desktop y espera a que el engine esté listo. `buildx` es parte del ecosistema Docker, no se instala con `pip`.

## Limpieza y costos

Un ALB creado por el controller debe eliminarse quitando los Ingress/releases que lo usan. CloudFront y EKS se gestionan con Terraform:

```bash
helm uninstall devop-app -n default
helm uninstall devops-frontend -n default
helm uninstall devop-web -n default
helm uninstall aws-load-balancer-controller -n kube-system

terraform -chdir=infra plan -destroy
terraform -chdir=infra destroy
```

Revisa el plan de destrucción antes de confirmar. Si la cuenta todavía conserva buckets u otros recursos de una configuración anterior, resuélvelos explícitamente; no borres recursos compartidos sin comprobar su contenido. Las imágenes publicadas en Docker Hub no se eliminan con Terraform.
