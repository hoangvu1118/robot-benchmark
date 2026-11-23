param(
    [switch]$Rviz,
    [string]$Distro = 'Ubuntu-22.04',
    [string]$LinuxWorkspace = '',
    [ValidateSet('teb', 'dwa')][string]$Planner = 'teb',
    [ValidateSet('map2_static', 'map2_obs05', 'map2_obs10')][string]$Scenario = 'map2_obs05',
    [switch]$Record
)
$ErrorActionPreference = 'Stop'
$running = docker ps -q --filter 'label=com.docker.compose.project=arena-benchmark'
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop must be running.' }
if ($running) { throw 'An Arena container is already running. Stop it before starting a new run.' }
$rvizValue = if ($Rviz) { 'true' } else { 'false' }
$portableRoot = $PSScriptRoot.Replace('\', '/')
# wslpath can resolve an existing Docker bind alias, breaking sibling mounts.
# Keep the original Windows-drive path under WSL's default /mnt mount instead.
if ($LinuxWorkspace) { $linuxRoot = $LinuxWorkspace }
elseif ($portableRoot -match '^([A-Za-z]):/(.*)$') {
    $linuxRoot = '/mnt/' + $Matches[1].ToLowerInvariant() + '/' + $Matches[2]
} else { throw 'Specify -LinuxWorkspace with the full WSL path to benchmark_ws.' }
$options = @(
    '-e', "ARENA_RVIZ=$rvizValue",
    '-e', "ARENA_PLANNER=$($Planner.ToLowerInvariant())",
    '-e', "ARENA_SCENARIO=$($Scenario.ToLowerInvariant())"
)
if ($Record) {
    $options += @('-e', 'ARENA_GUI=true')
    $command = 'cp /work/smoke.sh /tmp/arena-smoke.sh && bash /tmp/arena-smoke.sh'
} else {
    $command = 'cp /work/view.sh /tmp/arena-view.sh && bash /tmp/arena-view.sh'
}
wsl -d $Distro --cd $linuxRoot -- docker compose -f compose.yaml -f compose.gui.yaml run --rm --name arena-benchmark-view @options benchmark -lc $command
if ($LASTEXITCODE -ne 0) { throw 'Arena viewer exited with an error. Check the terminal output.' }
