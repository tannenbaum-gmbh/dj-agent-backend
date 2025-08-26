#!/bin/bash

# Quick Deploy Script for DJ Agent Backend
# Usage: ./scripts/quick-deploy.sh [environment]
# Environment: dev, staging, prod (default: dev)

set -e

ENVIRONMENT=${1:-dev}
NAMESPACE="dj-agent"
if [ "$ENVIRONMENT" = "dev" ]; then
    NAMESPACE="dj-agent-dev"
elif [ "$ENVIRONMENT" = "staging" ]; then
    NAMESPACE="dj-agent-staging"
fi

echo "🚀 Quick Deploy DJ Agent Backend to $ENVIRONMENT"
echo "================================================="

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl and configure cluster access."
    exit 1
fi

if ! command -v kustomize &> /dev/null; then
    echo "❌ kustomize not found. Please install kustomize."
    exit 1
fi

echo "✅ Prerequisites met"

# Create namespace
echo "📦 Creating namespace: $NAMESPACE"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Deploy based on environment
case $ENVIRONMENT in
    "dev")
        echo "🔧 Deploying to development environment..."
        kustomize build k8s/overlays/dev/ | kubectl apply -f -
        ;;
    "staging")
        echo "🔧 Deploying to staging environment..."
        if command -v helm &> /dev/null; then
            echo "📦 Using Helm for staging deployment..."
            helm upgrade --install dj-agent-staging k8s/charts/dj-agent-backend/ \
                --namespace "$NAMESPACE" \
                --set replicaCount=2 \
                --set image.tag=staging \
                --set ingress.hosts[0].host=staging-api.dj-agent.local \
                --wait --timeout=5m
        else
            echo "📦 Using Kustomize base configuration..."
            kustomize build k8s/base/ | kubectl apply -f -
        fi
        ;;
    "prod")
        echo "🔧 Deploying to production environment..."
        echo "⚠️  Production deployment should be done via CI/CD pipeline!"
        echo "   For manual deployment, ensure:"
        echo "   - Secrets are properly configured"
        echo "   - Database credentials are set"
        echo "   - SSL certificates are ready"
        echo "   - Monitoring is configured"
        echo ""
        read -p "Continue with production deployment? (y/N): " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kustomize build k8s/overlays/prod/ | kubectl apply -f -
        else
            echo "Production deployment cancelled"
            exit 0
        fi
        ;;
    *)
        echo "❌ Invalid environment: $ENVIRONMENT"
        echo "Valid options: dev, staging, prod"
        exit 1
        ;;
esac

# Wait for deployment
echo "⏳ Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/dj-agent-backend -n "$NAMESPACE"

# Show deployment status
echo ""
echo "📊 Deployment Status:"
kubectl get pods,svc,ingress -n "$NAMESPACE"

echo ""
echo "🎉 Deployment to $ENVIRONMENT completed successfully!"

if [ "$ENVIRONMENT" = "dev" ]; then
    echo ""
    echo "💡 Development Environment Quick Access:"
    echo "   API Health: kubectl port-forward -n $NAMESPACE svc/dj-agent-backend 8080:80"
    echo "   Then visit: http://localhost:8080/health"
    echo ""
    echo "   View logs: kubectl logs -f -n $NAMESPACE deployment/dj-agent-backend"
fi