param()

$ErrorActionPreference = "Stop"

Write-Host "This script is deprecated." -ForegroundColor Yellow
Write-Host "This repository is now OpenShift-only." -ForegroundColor Yellow
Write-Host "Use the manifests in 'openshift/' with the OpenShift CLI (oc)." -ForegroundColor Yellow
Write-Host "Example:" -ForegroundColor Yellow
Write-Host "  oc apply -f openshift/namespace.yaml" -ForegroundColor White
Write-Host "  oc apply -f openshift/configmap.yaml" -ForegroundColor White
Write-Host "  oc apply -f openshift/deployment.yaml" -ForegroundColor White
Write-Host "  oc apply -f openshift/service.yaml" -ForegroundColor White
Write-Host "  oc apply -f openshift/route.yaml" -ForegroundColor White
Write-Host "  oc apply -f openshift/hpa.yaml" -ForegroundColor White
exit 1
