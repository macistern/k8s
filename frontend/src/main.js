async function loadApiMessage() {
  const el = document.getElementById('api-message');
  try {
    const response = await fetch('/api/');
    const data = await response.json();
    el.textContent = `${data.message} (status: ${data.status})`;
  } catch (error) {
    el.textContent = 'No se pudo contactar la API en este momento.';
  }
}

const SERVICES = [
  { name: 'VPC', description: 'Red aislada con subnets públicas y privadas para el cluster.' },
  { name: 'EKS', description: 'Control plane administrado de Kubernetes donde corren los pods.' },
  { name: 'ECR', description: 'Registro de imágenes Docker para el batch job y el servicio Flask.' },
  { name: 'IAM / IRSA', description: 'Roles de AWS asumidos por Service Accounts de Kubernetes sin credenciales estáticas.' },
  { name: 'Helm', description: 'Empaqueta y despliega los recursos de Kubernetes (Job y Deployment) como charts versionados.' },
  { name: 'S3', description: 'Almacena el CSV que procesa el batch job y aloja los archivos estáticos de este frontend.' },
  { name: 'CloudFront', description: 'CDN que sirve el frontend y reenvía las llamadas /api/* al backend.' },
  { name: 'ALB', description: 'Balanceador creado por el AWS Load Balancer Controller para exponer el Ingress del backend.' },
];

function renderServices() {
  const list = document.getElementById('service-list');
  for (const service of SERVICES) {
    const item = document.createElement('li');

    const name = document.createElement('span');
    name.className = 'service-name';
    name.textContent = service.name;

    const description = document.createElement('span');
    description.className = 'body-md';
    description.textContent = service.description;

    item.append(name, description);
    list.append(item);
  }
}

const RUNBOOK_COMMANDS = [
  { label: 'Construir la imagen del batch job', command: 'docker build --platform linux/amd64 -t my-image-py:latest .' },
  { label: 'Publicar la imagen en ECR', command: 'docker push <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/my-image-py:latest' },
  { label: 'Provisionar la infraestructura', command: 'cd infra && terraform apply' },
  { label: 'Configurar kubeconfig', command: 'aws eks update-kubeconfig --region us-east-1 --name cluster-tutorial' },
  { label: 'Desplegar el backend con Helm', command: 'helm install devops-web eks-devops-web/ -n default' },
  { label: 'Publicar el frontend en S3', command: 'aws s3 sync dist/ s3://<frontend_bucket_name>' },
];

function renderRunbookCommands() {
  const container = document.getElementById('runbook-commands');
  for (const entry of RUNBOOK_COMMANDS) {
    const label = document.createElement('span');
    label.className = 'runbook-command-label';
    label.textContent = entry.label;

    const command = document.createElement('pre');
    command.className = 'runbook-command';
    command.textContent = entry.command;

    container.append(label, command);
  }
}

loadApiMessage();
renderServices();
renderRunbookCommands();
