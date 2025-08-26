#!/bin/bash
set -e

# Kubernetes Deployment Validation Script
# This script validates the Kubernetes deployment configurations

echo "🔍 Validating Kubernetes Deployment Configurations"
echo "=================================================="

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl."
    exit 1
fi

if ! command -v kustomize &> /dev/null; then
    echo "❌ kustomize not found. Please install kustomize."
    exit 1
fi

if command -v helm &> /dev/null; then
    echo "✅ helm found"
else
    echo "⚠️  helm not found (optional for Helm deployments)"
fi

echo "✅ Prerequisites check passed"

# Validate YAML syntax
echo ""
echo "📝 Validating YAML syntax..."
find k8s -name "*.yaml" | while read -r file; do
    if python -c "import yaml; yaml.safe_load_all(open('$file').read())" 2>/dev/null; then
        echo "✅ $file"
    else
        echo "❌ $file has YAML syntax errors"
        exit 1
    fi
done

# Test Kustomize builds
echo ""
echo "🔨 Testing Kustomize builds..."

echo "  Testing base configuration..."
if kustomize build k8s/base/ > /tmp/base-validation.yaml; then
    echo "  ✅ Base configuration builds successfully"
    echo "     Generated $(wc -l < /tmp/base-validation.yaml) lines of Kubernetes manifests"
else
    echo "  ❌ Base configuration failed to build"
    exit 1
fi

echo "  Testing development overlay..."
if kustomize build k8s/overlays/dev/ > /tmp/dev-validation.yaml; then
    echo "  ✅ Development overlay builds successfully"
    echo "     Generated $(wc -l < /tmp/dev-validation.yaml) lines of Kubernetes manifests"
else
    echo "  ❌ Development overlay failed to build"
    exit 1
fi

echo "  Testing production overlay..."
if kustomize build k8s/overlays/prod/ > /tmp/prod-validation.yaml; then
    echo "  ✅ Production overlay builds successfully"
    echo "     Generated $(wc -l < /tmp/prod-validation.yaml) lines of Kubernetes manifests"
else
    echo "  ❌ Production overlay failed to build"
    exit 1
fi

# Validate Helm chart (if helm is available)
if command -v helm &> /dev/null; then
    echo ""
    echo "⛵ Testing Helm chart..."
    if helm lint k8s/charts/dj-agent-backend/; then
        echo "  ✅ Helm chart passes linting"
    else
        echo "  ❌ Helm chart failed linting"
        exit 1
    fi
    
    if helm template test-release k8s/charts/dj-agent-backend/ > /tmp/helm-validation.yaml; then
        echo "  ✅ Helm chart templates successfully"
        echo "     Generated $(wc -l < /tmp/helm-validation.yaml) lines of Kubernetes manifests"
    else
        echo "  ❌ Helm chart template failed"
        exit 1
    fi
fi

# Security validation
echo ""
echo "🛡️  Security validation..."

echo "  Checking for hardcoded secrets..."
if grep -r "password\|secret\|key" k8s/ --exclude-dir=.git | grep -v "secretName\|secretKeyRef\|# " | grep -v "name.*secret" | grep -v "password.*change"; then
    echo "  ⚠️  Potential hardcoded secrets found (review above)"
else
    echo "  ✅ No obvious hardcoded secrets found"
fi

echo "  Checking for non-root security contexts..."
if grep -r "runAsNonRoot: true" k8s/ > /dev/null; then
    echo "  ✅ Non-root security contexts configured"
else
    echo "  ❌ Non-root security contexts not found"
fi

echo "  Checking for resource limits..."
if grep -r "limits:" k8s/ > /dev/null; then
    echo "  ✅ Resource limits configured"
else
    echo "  ❌ Resource limits not configured"
fi

# Performance validation
echo ""
echo "📊 Performance configuration validation..."

echo "  Checking for HPA configuration..."
if grep -r "HorizontalPodAutoscaler" k8s/ > /dev/null; then
    echo "  ✅ HPA configured for auto-scaling"
else
    echo "  ❌ HPA not configured"
fi

echo "  Checking for PDB configuration..."
if grep -r "PodDisruptionBudget" k8s/ > /dev/null; then
    echo "  ✅ PDB configured for high availability"
else
    echo "  ❌ PDB not configured"
fi

echo "  Checking for health checks..."
if grep -r "livenessProbe" k8s/ > /dev/null && grep -r "readinessProbe" k8s/ > /dev/null; then
    echo "  ✅ Health checks configured"
else
    echo "  ❌ Health checks not properly configured"
fi

# Cleanup
echo ""
echo "🧹 Cleaning up temporary files..."
rm -f /tmp/*-validation.yaml

echo ""
echo "🎉 Validation completed successfully!"
echo ""
echo "💡 Next steps:"
echo "   1. Review the generated manifests in /tmp/ if needed"
echo "   2. Configure secrets management for production"
echo "   3. Set up monitoring and alerting"
echo "   4. Test deployment in a development cluster"
echo ""
echo "🚀 Ready for deployment!"