# Kubernetes Deployment Guide

This guide provides comprehensive instructions for deploying and managing the DJ Agent Backend on Kubernetes with optimized resource utilization and reliability.

## 🏗️ Architecture Overview

The deployment consists of:
- **FastAPI Backend**: 3-50 replicas (auto-scaling)
- **PostgreSQL**: Persistent database with optimized configuration
- **Redis**: In-memory cache with persistence
- **Ingress**: NGINX ingress with SSL termination and rate limiting
- **Monitoring**: Prometheus metrics and Grafana dashboards
- **Security**: Network policies, RBAC, pod security standards

## 📋 Prerequisites

- Kubernetes cluster (v1.25+)
- kubectl configured
- Helm 3.x installed
- NGINX Ingress Controller
- Prometheus Operator (for monitoring)
- cert-manager (for SSL certificates)

## 🚀 Quick Start

### 1. Using Kustomize (Recommended for GitOps)

```bash
# Deploy to development
kubectl apply -k k8s/overlays/dev/

# Deploy to production
kubectl apply -k k8s/overlays/prod/
```

### 2. Using Helm Charts

```bash
# Add dependencies
helm dependency update k8s/charts/dj-agent-backend/

# Deploy to development
helm install dj-agent-dev k8s/charts/dj-agent-backend/ \
  --namespace dj-agent-dev \
  --create-namespace \
  --values k8s/charts/dj-agent-backend/values-dev.yaml

# Deploy to production
helm install dj-agent-prod k8s/charts/dj-agent-backend/ \
  --namespace dj-agent \
  --create-namespace \
  --values k8s/charts/dj-agent-backend/values-prod.yaml
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment | `production` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `POSTGRES_HOST` | PostgreSQL hostname | `postgresql` |
| `REDIS_HOST` | Redis hostname | `redis` |
| `OPENAI_API_KEY` | OpenAI API key | (required) |
| `PINECONE_API_KEY` | Pinecone API key | (required) |

### Resource Configuration

#### Development
- CPU: 100m requests, 500m limits
- Memory: 256Mi requests, 512Mi limits
- Replicas: 1

#### Production
- CPU: 500m requests, 2000m limits
- Memory: 1Gi requests, 2Gi limits
- Replicas: 5-50 (auto-scaling)

## 🔐 Security Features

### Pod Security Standards
- Non-root user execution
- Read-only root filesystem
- Dropped capabilities
- Security context enforcement

### Network Policies
- Ingress: Only from ingress controller and monitoring
- Egress: Database, cache, and HTTPS APIs only
- Default deny-all with explicit allows

### RBAC
- Minimal service account permissions
- Namespace-scoped roles
- Principle of least privilege

## 📊 Monitoring & Observability

### Prometheus Metrics
- HTTP request metrics
- Application performance metrics
- Resource utilization metrics
- Custom business metrics

### Health Checks
- **Liveness**: `/health` endpoint
- **Readiness**: `/readiness` endpoint
- **Startup**: Progressive health checking

### Logging
- Structured JSON logging
- Log aggregation ready
- Configurable log levels

## 🔄 Auto-scaling Configuration

### Horizontal Pod Autoscaler (HPA)
```yaml
CPU Target: 70%
Memory Target: 80%
Min Replicas: 3 (dev: 1, prod: 5)
Max Replicas: 20 (dev: 5, prod: 50)
Scale Up: Max 50% or 2 pods per minute
Scale Down: Max 25% or 1 pod per minute (5-min stabilization)
```

### Vertical Pod Autoscaler (VPA) - Optional
```bash
# Install VPA if not available
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/download/vertical-pod-autoscaler-0.13.0/vpa-release-0.13.0-yaml
```

## 🚦 High Availability

### Pod Disruption Budget
- Minimum available: 2 pods
- Ensures service availability during maintenance

### Anti-Affinity Rules
- Pods scheduled on different nodes
- Improves fault tolerance

### Rolling Updates
- MaxSurge: 1
- MaxUnavailable: 1
- Zero-downtime deployments

## 🔍 Troubleshooting

### Common Issues

1. **Pods not starting**
   ```bash
   kubectl describe pod -n dj-agent -l app.kubernetes.io/name=dj-agent-backend
   kubectl logs -n dj-agent -l app.kubernetes.io/name=dj-agent-backend --tail=100
   ```

2. **Database connection issues**
   ```bash
   kubectl exec -it -n dj-agent postgresql-0 -- psql -U dj_agent -d dj_agent
   ```

3. **Memory/CPU limits**
   ```bash
   kubectl top pods -n dj-agent
   kubectl describe hpa -n dj-agent
   ```

### Performance Optimization

1. **Adjust resource requests/limits**
2. **Tune JVM/Python parameters**
3. **Optimize database queries**
4. **Configure connection pooling**
5. **Enable compression**

## 🔄 CI/CD Integration

### GitHub Actions
The repository includes a complete CI/CD pipeline with:
- Automated testing and security scanning
- Multi-environment deployments
- Container image building and scanning
- Deployment validation

### ArgoCD GitOps (Recommended)
```yaml
# argocd-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: dj-agent-backend
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/tannenbaum-gmbh/dj-agent-backend
    targetRevision: HEAD
    path: k8s/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: dj-agent
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## 📈 Performance Benchmarks

### Expected Performance
- **Throughput**: 1000+ RPS per pod
- **Latency**: P95 < 200ms, P99 < 500ms
- **Resource Usage**: 70% CPU, 80% Memory at scale
- **Startup Time**: < 30 seconds

### Load Testing
```bash
# Using k6
k6 run --vus 100 --duration 30s load-test.js

# Using hey
hey -z 30s -c 100 -q 50 https://api.dj-agent.com/health
```

## 🛠️ Maintenance

### Regular Tasks
- Monitor resource usage and adjust limits
- Update dependencies and base images
- Review and rotate secrets
- Analyze logs for errors and performance
- Test disaster recovery procedures

### Backup & Recovery
```bash
# Database backup
kubectl exec -n dj-agent postgresql-0 -- pg_dump -U dj_agent dj_agent > backup.sql

# Restore database
kubectl exec -i -n dj-agent postgresql-0 -- psql -U dj_agent -d dj_agent < backup.sql
```

## 📞 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review Kubernetes events and logs
3. Consult monitoring dashboards
4. Open an issue in the repository

## 📚 Additional Resources

- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Prometheus Monitoring](https://prometheus.io/docs/practices/naming/)
- [FastAPI Performance](https://fastapi.tiangolo.com/deployment/concepts/)
- [PostgreSQL Tuning](https://pgtune.leopard.in.ua/)