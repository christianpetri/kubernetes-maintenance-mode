#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test all endpoints of the Kubernetes maintenance mode demo
.DESCRIPTION
    Test suite for maintenance mode functionality and dual deployment pattern
#>

param(
    [string]$UserServiceUrl = "http://localhost:52876",
    [string]$AdminServiceUrl = "http://localhost:52875"
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "  TESTING KUBERNETES DEMO APP" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$testsPassed = 0
$testsFailed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$ExpectedPattern,
        [switch]$IsJson,
        [switch]$ExpectFailure
    )
    
    Write-Host "TEST: $Name" -ForegroundColor Cyan
    Write-Host "  URL: $Url" -ForegroundColor Gray
    
    try {
        if ($IsJson) {
            $response = Invoke-RestMethod -Uri $Url -UseBasicParsing -ErrorAction Stop
            Write-Host "  Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor Yellow
            
            if ($ExpectedPattern -and ($response | ConvertTo-Json) -match $ExpectedPattern) {
                Write-Host "  [PASS]: Found pattern '$ExpectedPattern'" -ForegroundColor Green
                return $true
            } elseif (!$ExpectedPattern) {
                Write-Host "  [PASS]: Got valid JSON response" -ForegroundColor Green
                return $true
            } else {
                Write-Host "  [FAIL]: Pattern '$ExpectedPattern' not found" -ForegroundColor Red
                return $false
            }
        } else {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -ErrorAction Stop
            $content = $response.Content
            
            if ($ExpectedPattern -and $content -match $ExpectedPattern) {
                Write-Host "  [PASS]: Found pattern '$ExpectedPattern'" -ForegroundColor Green
                return $true
            } elseif (!$ExpectedPattern) {
                Write-Host "  [PASS]: Got response (Status: $($response.StatusCode))" -ForegroundColor Green
                return $true
            } else {
                Write-Host "  [FAIL]: Pattern '$ExpectedPattern' not found" -ForegroundColor Red
                return $false
            }
        }
    } catch {
        if ($ExpectFailure) {
            Write-Host "  [PASS]: Expected failure occurred" -ForegroundColor Green
            return $true
        }
        Write-Host "  [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Test 1: User Service Landing Page
if (Test-Endpoint -Name "User Service Landing Page" -Url "$UserServiceUrl/" -ExpectedPattern "Kubernetes Maintenance Mode Demo") {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 2: User Service Health Probe
if (Test-Endpoint -Name "User Service Health Probe" -Url "$UserServiceUrl/health" -ExpectedPattern "healthy" -IsJson) {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 3: User Service Readiness Probe
if (Test-Endpoint -Name "User Service Readiness Probe" -Url "$UserServiceUrl/ready" -ExpectedPattern "ready" -IsJson) {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 4: Admin Service Landing Page
if (Test-Endpoint -Name "Admin Service Landing Page" -Url "$AdminServiceUrl/" -ExpectedPattern "ADMIN POD") {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 5: Admin Service Health Probe
if (Test-Endpoint -Name "Admin Service Health Probe" -Url "$AdminServiceUrl/health" -ExpectedPattern "healthy" -IsJson) {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 6: Admin Service Readiness Probe
if (Test-Endpoint -Name "Admin Service Readiness Probe" -Url "$AdminServiceUrl/ready" -ExpectedPattern "ready" -IsJson) {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 7: Admin Control Panel
if (Test-Endpoint -Name "Admin Control Panel" -Url "$AdminServiceUrl/admin" -ExpectedPattern "Admin Control Panel") {
    $testsPassed++
} else {
    $testsFailed++
}
Write-Host ""

# Test 8: Pod Badge Detection
Write-Host "TEST: Pod Badge Detection" -ForegroundColor Cyan
try {
    $userResponse = Invoke-WebRequest -Uri "$UserServiceUrl/" -UseBasicParsing -ErrorAction Stop
    $adminResponse = Invoke-WebRequest -Uri "$AdminServiceUrl/" -UseBasicParsing -ErrorAction Stop
    
    $userHasUserBadge = $userResponse.Content -match "USER POD"
    $adminHasAdminBadge = $adminResponse.Content -match "ADMIN POD"
    
    if ($userHasUserBadge -and $adminHasAdminBadge) {
        Write-Host "  [PASS]: Correct badge detection on both pod types" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "  [FAIL]: Badge detection incorrect (User:$userHasUserBadge, Admin:$adminHasAdminBadge)" -ForegroundColor Red
        $testsFailed++
    }
} catch {
    Write-Host "  [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
}
Write-Host ""

# Test 9: Maintenance Mode Toggle
Write-Host "TEST: Maintenance Mode Toggle" -ForegroundColor Cyan
try {
    # Get current state
    $initialResponse = Invoke-RestMethod -Uri "$AdminServiceUrl/admin" -UseBasicParsing -ErrorAction Stop
    $wasEnabled = $initialResponse -match "ENABLED"
    
    # Toggle maintenance mode
    $toggleResponse = Invoke-RestMethod -Uri "$AdminServiceUrl/admin/toggle" -Method Post -UseBasicParsing -ErrorAction Stop
    
    # Verify state changed
    $newResponse = Invoke-RestMethod -Uri "$AdminServiceUrl/admin" -UseBasicParsing -ErrorAction Stop
    $isEnabled = $newResponse -match "ENABLED"
    
    # Toggle back to original state
    Invoke-RestMethod -Uri "$AdminServiceUrl/admin/toggle" -Method Post -UseBasicParsing -ErrorAction Stop | Out-Null
    
    if ($wasEnabled -ne $isEnabled) {
        Write-Host "  [PASS]: Maintenance mode toggled successfully" -ForegroundColor Green
        $testsPassed++
    } else {
        Write-Host "  [FAIL]: Maintenance mode did not toggle" -ForegroundColor Red
        $testsFailed++
    }
} catch {
    Write-Host "  [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
}
Write-Host ""

# Test 10: Maintenance Page
Write-Host "TEST: Maintenance Page (503)" -ForegroundColor Cyan
try {
    # Enable maintenance mode first
    Invoke-RestMethod -Uri "$AdminServiceUrl/admin/toggle" -Method Post -UseBasicParsing -ErrorAction Stop | Out-Null
    Start-Sleep -Seconds 2
    
    # Try to access user service (should show 503 or connection refused)
    try {
        $response = Invoke-WebRequest -Uri "$UserServiceUrl/" -UseBasicParsing -ErrorAction Stop
        $has503 = $response.Content -match "503|Service Under Maintenance"
        
        if ($has503) {
            Write-Host "  [PASS]: 503 maintenance page displayed" -ForegroundColor Green
            $testsPassed++
        } else {
            Write-Host "  [FAIL]: Maintenance page not displayed correctly" -ForegroundColor Red
            $testsFailed++
        }
    } catch {
        # Check if it's a 503 response or connection issue
        if ($_.Exception.Message -match "503|SERVICE UNAVAILABLE") {
            Write-Host "  [PASS]: 503 maintenance status received" -ForegroundColor Green
            $testsPassed++
        } elseif ($_.Exception.Message -match "refused|reset|timeout") {
            Write-Host "  [PASS]: Connection refused (pods removed from service)" -ForegroundColor Green
            $testsPassed++
        } else {
            throw
        }
    }
    
    # Disable maintenance mode
    Invoke-RestMethod -Uri "$AdminServiceUrl/admin/toggle" -Method Post -UseBasicParsing -ErrorAction Stop | Out-Null
} catch {
    Write-Host "  [FAIL]: $($_.Exception.Message)" -ForegroundColor Red
    $testsFailed++
    # Ensure maintenance mode is disabled
    try {
        Invoke-RestMethod -Uri "$AdminServiceUrl/admin/toggle" -Method Post -UseBasicParsing -ErrorAction Stop | Out-Null
    } catch {}
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Green
Write-Host "  TEST RESULTS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Total Tests: $($testsPassed + $testsFailed)" -ForegroundColor White
Write-Host "  Passed: $testsPassed" -ForegroundColor Green
Write-Host "  Failed: $testsFailed" -ForegroundColor $(if ($testsFailed -gt 0) { "Red" } else { "Green" })
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

if ($testsFailed -eq 0) {
    Write-Host "[PASS] ALL TESTS PASSED!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[FAIL] SOME TESTS FAILED" -ForegroundColor Red
    exit 1
}
