$ErrorActionPreference = 'Stop'
$dependencyRoot = Join-Path $PSScriptRoot 'dependencies'
New-Item -ItemType Directory -Force -Path $dependencyRoot | Out-Null
foreach ($dependency in (Get-Content -Raw (Join-Path $PSScriptRoot 'dependencies.json') | ConvertFrom-Json)) {
    $destination = Join-Path $dependencyRoot $dependency.name
    if (-not (Test-Path -LiteralPath $destination)) {
        git init $destination
        if ($LASTEXITCODE -ne 0) { throw "Cannot initialize $destination" }
        git -C $destination remote add origin $dependency.url
        if ($LASTEXITCODE -ne 0) { throw "Cannot set remote for $destination" }
    }
    $changes = git -C $destination status --porcelain
    if ($LASTEXITCODE -ne 0 -or $changes) { throw "Dependency is not clean: $destination" }
    git -C $destination fetch --depth 1 origin $dependency.commit
    if ($LASTEXITCODE -ne 0) { throw "Fetch failed for $($dependency.name)" }
    git -C $destination checkout --detach $dependency.commit
    if ($LASTEXITCODE -ne 0) { throw "Checkout failed for $($dependency.name)" }
}
