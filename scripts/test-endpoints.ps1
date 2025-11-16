#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test all endpoints of the Kubernetes demo app
.DESCRIPTION
    Comprehensive test suite for active user tracking and graceful drain features
#>

param(
    [string]$UserServiceUrl = "http://localhost:9090",
    [string]$AdminServiceUrl = "http://localhost:9092"
)

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  TESTING KUBERNETES DEMO APP" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

$testsPassed = 0
$testsFailed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedPattern,
        [switch]$IsJson
    )
    
    Write-Host "TEST: $Name" -ForegroundColor Cyan
    Write-Host "  URL: $Url" -ForegroundColor Gray
    
    try {
        if ($IsJson) {
            $response = Invoke-RestMethod -Uri $Url -UseBasicParsing -ErrorAction Stop
            Write-Host "  Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor Yellow
            
            if ($ExpectedPattern -and ($response | ConvertTo-Json) -match $ExpectedPattern) {
                Write-Host "  ✓ PASS: Found pattern '$ExpectedPattern'" -ForegroundColor Green
                return $true
            } elseif (!$ExpectedPattern) {
                Write-Host "  ✓ PASS: Got valid JSON response" -ForegroundColor Green
                return $true
            } else {
                Write-Host "  ✗ FAIL: Pattern '$ExpectedPattern' not found" -ForegroundColor Red
                return $false
            }
        } else {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -ErrorAction Stop
            $content = $response.Content
            
            if ($ExpectedPattern -and $content -match $ExpectedPattern) {
                Write-Host "  ✓ PASS: Found pattern '$ExpectedPattern'" -ForegroundColor Green
                return $true
            } elseif (!$ExpectedPattern) {
                Write-Host "  ✓ PASS: Got response (Status: $($response.StatusCode))" -ForegroundColor Green
                return $true
            } else {
                Write-Host "  ✗ FAIL: Pattern '$ExpectedPattern' not found" -ForegroundColor Red
                return $false
            }
        }
    } catch {
        Write-Host "  ✗ FAIL: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Test 1: Health Probe
if (Test-Endpoint -Name "Health Probe" -Url "$UserServiceUrl/health" -ExpectedPattern "healthy" -IsJson) {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 2: Readiness Probe
if (Test-Endpoint -Name "Readiness Probe" -Url "$UserServiceUrl/ready" -ExpectedPattern "ready" -IsJson) {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 3: Main Page SSE
Write-Host "TEST: Main Page SSE Integration" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "$UserServiceUrl/" -UseBasicParsing -ErrorAction Stop
    $hasSSE = $response.Content -match "EventSource"
    $hasDrainBanner = $response.Content -match "drain-banner"
    $hasCountdown = $response.Content -match "countdown"
    
    if ($hasSSE -and $hasDrainBanner -and $hasCountdown) {
        Write-Host "  ✓ PASS: SSE, drain banner, and countdown found" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "  ✗ FAIL: Missing features (SSE:$hasSSE, Banner:$hasDrainBanner, Countdown:$hasCountdown)" -ForegroundColor Red
        $testsFailed++
    }
} catch {
    Write-Host "  ✗ FAIL: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
}
Write-Host ""

# Test 4: Session Creation
Write-Host "TEST: Session Cookie Creation" -ForegroundColor Cyan
try {
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $response = Invoke-WebRequest -Uri "$UserServiceUrl/" -WebSession $session -UseBasicParsing -ErrorAction Stop
    $cookies = $session.Cookies.GetCookies($UserServiceUrl)
    
    if ($cookies.Count -gt 0) {
        Write-Host "  ✓ PASS: Session cookie created ($($cookies[0].Name))" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "  ✗ FAIL: No session cookie created" -ForegroundColor Red
        $testsFailed++
    }
} catch {
    Write-Host "  ✗ FAIL: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
}
Write-Host ""

# Test 5: Metrics Endpoint
if (Test-Endpoint -Name "Metrics Endpoint (Prometheus)" -Url "$AdminServiceUrl/metrics" -ExpectedPattern "active_sessions_total") {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 6: Admin Users Dashboard
Write-Host "TEST: Admin Users Dashboard" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "$AdminServiceUrl/admin/users" -UseBasicParsing -ErrorAction Stop
    $hasTitle = $response.Content -match "Active Users Dashboard"
    $hasSessions = $response.Content -match "Active Sessions"
    $hasTable = $response.Content -match "<table"
    
    if ($hasTitle -and $hasSessions -and $hasTable) {
        Write-Host "  ✓ PASS: Dashboard with session tracking found" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "  ✗ FAIL: Missing dashboard elements" -ForegroundColor Red
        $testsFailed++
    }
} catch {
    Write-Host "  ✗ FAIL: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
}
Write-Host ""

# Test 7: Logout Endpoint
if (Test-Endpoint -Name "Logout Endpoint" -Url "$UserServiceUrl/logout" -ExpectedPattern "Successfully Logged Out") {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 8: Admin Panel
if (Test-Endpoint -Name "Admin Panel" -Url "$AdminServiceUrl/admin" -ExpectedPattern "Admin Panel") {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Summary
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  TEST RESULTS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Total Tests: $($testsPassed + $testsFailed)" -ForegroundColor White
Write-Host "  Passed: $testsPassed" -ForegroundColor Green
Write-Host "  Failed: $testsFailed" -ForegroundColor $(if ($testsFailed -gt 0) { "Red" } else { "Green" })
Write-Host "========================================`n" -ForegroundColor Green

if ($testsFailed -eq 0) {
    Write-Host "✓ ALL TESTS PASSED!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "✗ SOME TESTS FAILED" -ForegroundColor Red
    exit 1
}
