# including-basics-devops

Proyecto de práctica de DevOps que despliega una aplicación completa en AWS usando Kubernetes (EKS). Sirve como laboratorio end-to-end para aprender infraestructura como código, contenedores y orquestación.

## Qué incluye

- **`infra/`** — Terraform que provisiona VPC, cluster EKS, IAM/IRSA, y el bucket S3 + CloudFront del frontend.
- **`http-service/`** — API backend en Flask con endpoints de salud (`/health`, `/ready`) y datos (`/api/`).
- **`job-script/`** — Job batch en Python que procesa un CSV desde S3.
- **`eks-devops-app/`** / **`eks-devops-web/`** — Charts de Helm para desplegar el job y el backend en el cluster.
- **`frontend/`** — SPA estática (Vite) servida vía S3 + CloudFront, que consume la API a través de un Ingress/ALB.

## Documentación

- [`DEPLOY.md`](DEPLOY.md) — guía paso a paso para desplegar el stack completo tal como está.
- [`RUNBOOK.md`](RUNBOOK.md) — cómo se construyó cada pieza desde cero.
