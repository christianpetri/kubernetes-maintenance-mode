#!/usr/bin/env pwsh
# Test All Buttons - Comprehensive endpoint testing

Write-Host "`n🧪 Testing All Endpoints & Buttons`n" -ForegroundColor Cyan

$baseUrl = "http://localhost:8080"
$passed = 0
$failed = 0

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Method = "GET",
        [int]$ExpectedStatus = 200,
        [string]$ExpectedContent = $null
    )
    
    Write-Host "Testing: $Name" -ForegroundColor Yellow
    
    try {
        if ($Method -eq "POST") {
            $response = Invoke-WebRequest -Uri $Url -Method Post -ErrorAction Stop
        } else {
            $response = Invoke-WebRequest -Uri $Url -Method Get -ErrorAction Stop
        }
        
        if ($response.StatusCode -eq $ExpectedStatus) {
            if ($ExpectedContent -and $response.Content -notmatch $ExpectedContent) {
                Write-Host "  ❌ FAIL - Content mismatch" -ForegroundColor Red
                return $false
            }
            Write-Host "  ✅ PASS ($($response.StatusCode))" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  ❌ FAIL - Expected $ExpectedStatus, got $($response.StatusCode)" -ForegroundColor Red
            return $false
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq $ExpectedStatus) {
            Write-Host "  ✅ PASS ($statusCode)" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  ❌ FAIL - Expected $ExpectedStatus, got $statusCode" -ForegroundColor Red
            return $false
        }
    }
}

# Test 1: Health Check
if (Test-Endpoint "Health Check" "$baseUrl/health" -ExpectedContent "healthy") { $passed++ } else { $failed++ }

# Test 2: Readiness (Normal)
if (Test-Endpoint "Readiness Check" "$baseUrl/ready" -ExpectedContent "ready") { $passed++ } else { $failed++ }

# Test 3: User Home Page
if (Test-Endpoint "User Home Page" "$baseUrl/" -ExpectedContent "Maintenance Mode Demo") { $passed++ } else { $failed++ }

# Test 4: Admin Panel
if (Test-Endpoint "Admin Panel" "$baseUrl/admin" -ExpectedContent "Admin Control Panel") { $passed++ } else { $failed++ }

# Test 5: Enable Maintenance
Write-Host "`nEnabling Maintenance Mode..." -ForegroundColor Cyan
if (Test-Endpoint "Toggle Maintenance ON" "$baseUrl/admin/toggle" -Method "POST") { $passed++ } else { $failed++ }

# Test 6: Readiness (Maintenance)
if (Test-Endpoint "Readiness 503" "$baseUrl/ready" -ExpectedStatus 503) { $passed++ } else { $failed++ }

# Test 7: User Page 503
if (Test-Endpoint "User Page 503" "$baseUrl/" -ExpectedStatus 503) { $passed++ } else { $failed++ }

# Test 8: Admin Still Works
if (Test-Endpoint "Admin During Maintenance" "$baseUrl/admin" -ExpectedContent "ENABLED") { $passed++ } else { $failed++ }

# Test 9: Disable Maintenance
Write-Host "`nDisabling Maintenance Mode..." -ForegroundColor Cyan
if (Test-Endpoint "Toggle Maintenance OFF" "$baseUrl/admin/toggle" -Method "POST") { $passed++ } else { $failed++ }

# Test 10: User Page Restored
if (Test-Endpoint "User Page Restored" "$baseUrl/" -ExpectedContent "Operational") { $passed++ } else { $failed++ }

# Summary
Write-Host "`n" + "═" * 60 -ForegroundColor Green
Write-Host "TEST SUMMARY" -ForegroundColor Green
Write-Host "═" * 60 -ForegroundColor Green
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })
Write-Host "Total:  $($passed + $failed)`n"

if ($failed -eq 0) {
    Write-Host "🎉 All tests passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ Some tests failed" -ForegroundColor Red
    exit 1
}
