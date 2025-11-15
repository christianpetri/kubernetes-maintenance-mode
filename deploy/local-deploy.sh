#!/bin/bash
set -e

echo "This script is deprecated."
echo "This repository is now OpenShift-only."
echo "Use the manifests in 'openshift/' with the OpenShift CLI (oc)."
echo "Example:"
echo "  oc apply -f openshift/namespace.yaml"
echo "  oc apply -f openshift/configmap.yaml"
echo "  oc apply -f openshift/deployment.yaml"
echo "  oc apply -f openshift/service.yaml"
echo "  oc apply -f openshift/route.yaml"
echo "  oc apply -f openshift/hpa.yaml"
exit 1
