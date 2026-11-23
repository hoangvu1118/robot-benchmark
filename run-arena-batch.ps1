param(
    [ValidateRange(1, 999)][int]$Trials = 20,
    [ValidateSet('map2_static', 'map2_obs10')][string[]]$Scenario = @('map2_static', 'map2_obs10'),
    [ValidateSet('teb', 'dwa')][string[]]$Planner = @('teb', 'dwa'),
    [ValidateRange(2, 900)][int]$SimSeconds,
    [switch]$Smoke
)

$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot 'compose.yaml'
$running = docker ps -q --filter 'label=com.docker.compose.project=arena-benchmark'
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop must be running.' }
if ($running) { throw 'Stop the running Arena container before starting a batch.' }
if ($Smoke -and $SimSeconds) { throw '-SimSeconds applies to scored runs.' }
if (-not $Smoke) {
    docker compose -f $compose run --rm -T benchmark -lc 'cmake -S /work/scoring -B /arena_ws/safety_build && cmake --build /arena_ws/safety_build -j2'
    if ($LASTEXITCODE -ne 0) { throw 'Could not build the Gazebo safety recorder.' }
}

$scenarios = @($Scenario | ForEach-Object { $_.ToLowerInvariant() } | Select-Object -Unique)
$planners = @($Planner | ForEach-Object { $_.ToLowerInvariant() } | Select-Object -Unique)
$stamp = [DateTime]::UtcNow.ToString("yyyyMMdd'T'HHmmss'Z'")
$suffix = [Guid]::NewGuid().ToString('N').Substring(0, 8)
$mode = if ($Smoke) { 'baseline' } else { 'scored' }
$batch = "$mode-$stamp-$suffix"
$runOptions = if (-not $Smoke) {
    @('-e', 'ARENA_SCORED=true', '-e', ('ARENA_SIM_SECONDS=' + $(if ($SimSeconds) { $SimSeconds })))
} else { @() }
$batchRoot = Join-Path (Join-Path $PSScriptRoot 'results') $batch
New-Item -ItemType Directory -Path $batchRoot | Out-Null
$index = Join-Path $batchRoot 'trials.csv'
Write-Host "Results folder is $batchRoot"

foreach ($case in $scenarios) {
    for ($attempt = 1; $attempt -le $Trials; $attempt++) {
        for ($offset = 0; $offset -lt $planners.Count; $offset++) {
            $method = $planners[($attempt - 1 + $offset) % $planners.Count]
            $trial = $attempt.ToString('D3')
            $relativePath = "$case/$method/$trial"
            $run = Join-Path $batchRoot $relativePath
            Write-Host "`n$case / $method / attempt $attempt of $Trials"
            docker compose -f $compose run --rm -T --name arena-benchmark-trial `
                -e "ARENA_BATCH_ID=$batch" -e "ARENA_TRIAL=$trial" `
                -e "ARENA_SCENARIO=$case" -e "ARENA_PLANNER=$method" @runOptions `
                benchmark -lc 'cp /work/smoke.sh /tmp/arena-smoke.sh && bash /tmp/arena-smoke.sh'
            $containerExit = $LASTEXITCODE

            if (-not $Smoke) {
                $scorePath = Join-Path $run 'score.json'
                $score = if (Test-Path -LiteralPath $scorePath) {
                    Get-Content -Raw -LiteralPath $scorePath | ConvertFrom-Json
                } else {
                    @{ outcome = 'invalid'; reason = 'No score was written. See trial logs.' }
                }
                [pscustomobject]@{
                    Scenario = $case
                    Planner = $method
                    Attempt = $attempt
                    Outcome = $score.outcome
                    Reason = $score.reason
                    MoveBaseStatus = $score.move_base_status
                    SimSeconds = $score.sim_seconds
                    CollisionCount = $score.collision_count
                    ClearanceM = $score.clearance_m
                    TimeToGoalS = $score.time_to_goal_s
                    PathLengthM = $score.path_length_m
                    JerkRmsMS3 = $score.jerk_rms_m_s3
                    TrajectoryRoughnessRadPerM = $score.trajectory_roughness_rad_per_m
                    ContainerExit = $containerExit
                    RunFolder = $relativePath
                } | Export-Csv -LiteralPath $index -Append -NoTypeInformation
                Write-Host "Recorded outcome $($score.outcome) $($score.reason)"
                continue
            }

            $outcome = 'recording_or_setup_failure'
            $actionStatus = $null
            $elapsed = $null
            $distance = $null
            $summary = Join-Path $run 'bag-summary.json'
            if (Test-Path -LiteralPath $summary) {
                $bag = Get-Content -Raw -LiteralPath $summary | ConvertFrom-Json
                $distance = [Math]::Round($bag.odometry_distance_excluding_jumps_over_1m, 3)
                $outcome = 'incomplete'
                $goals = @($bag.goals)
                $results = @($bag.results)
                if ($goals.Count -eq 1 -and $results.Count -eq 1 -and
                    $results[0].stamp -ge $goals[0].stamp) {
                    $actionStatus = $results[0].status
                    $elapsed = [Math]::Round($results[0].stamp - $goals[0].stamp, 3)
                    $outcome = if ($actionStatus -eq 3) { 'goal_reached' } else { 'navigation_failure' }
                }
                if ($containerExit -ne 0) { $outcome = 'recording_or_setup_failure' }
            }
            [pscustomobject]@{
                Scenario = $case
                Planner = $method
                Attempt = $attempt
                Outcome = $outcome
                MoveBaseStatus = $actionStatus
                SimSecondsToResult = $elapsed
                DiagnosticOdometryDistanceM = $distance
                ContainerExit = $containerExit
                RunFolder = $relativePath
            } | Export-Csv -LiteralPath $index -Append -NoTypeInformation
            Write-Host "Recorded outcome $outcome"
        }
    }
}

$allRows = Import-Csv -LiteralPath $index
$allRows |
    Group-Object Scenario, Planner, Outcome |
    Select-Object Count, Name |
    Format-Table -AutoSize
Write-Host "Trial index is $index"
if (-not $Smoke) {
    function Get-Mean($Rows, $Property) {
        $values = @($Rows | ForEach-Object { $_.$Property } | Where-Object { $_ -ne '' })
        if ($values.Count) {
            $invariant = [Globalization.CultureInfo]::InvariantCulture
            return ($values | ForEach-Object { [double]::Parse($_, $invariant) } |
                Measure-Object -Average).Average
        }
    }

    $summary = Join-Path $batchRoot 'metrics.csv'
    $allRows | Group-Object Scenario, Planner | ForEach-Object {
        $valid = @($_.Group | Where-Object Outcome -ne 'invalid')
        $success = @($valid | Where-Object Outcome -eq 'success')
        $timeouts = @($valid | Where-Object Outcome -eq 'timeout')
        $successRate = $null
        $timeoutRate = $null
        if ($valid.Count) {
            $successRate = 100 * $success.Count / $valid.Count
            $timeoutRate = 100 * $timeouts.Count / $valid.Count
        }
        [pscustomobject]@{
            Scenario = $_.Group[0].Scenario
            Planner = $_.Group[0].Planner
            ValidAttempts = $valid.Count
            InvalidAttempts = $_.Count - $valid.Count
            SuccessfulAttempts = $success.Count
            TimedOutAttempts = $timeouts.Count
            SuccessRatePct = $successRate
            TimeoutRatePct = $timeoutRate
            MeanCollisionCount = Get-Mean $valid 'CollisionCount'
            MeanMinimumClearanceM = Get-Mean $valid 'ClearanceM'
            MeanTimeToGoalS = Get-Mean $success 'TimeToGoalS'
            MeanPathLengthM = Get-Mean $success 'PathLengthM'
            MeanJerkRmsMS3 = Get-Mean $success 'JerkRmsMS3'
            MeanTrajectoryRoughnessRadPerM = Get-Mean $success 'TrajectoryRoughnessRadPerM'
        }
    } | Export-Csv -LiteralPath $summary -NoTypeInformation
    Write-Host "Metric summary is $summary"
}
