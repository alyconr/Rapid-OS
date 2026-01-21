# AWS DEPLOYMENT STANDARDS
Target: App Runner or ECS Fargate.
1. Use Multi-stage Docker builds (Alpine/Slim).
2. Infrastructure as Code: Terraform preferred.
3. CI/CD: GitHub Actions -> ECR -> ECS.