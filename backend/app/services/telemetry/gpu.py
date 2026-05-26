import csv
import shutil
import subprocess
from dataclasses import dataclass
from io import StringIO


GPU_QUERY_FIELDS = [
    "timestamp",
    "name",
    "driver_version",
    "pstate",
    "temperature.gpu",
    "utilization.gpu",
    "utilization.memory",
    "memory.total",
    "memory.used",
    "power.draw",
    "clocks.gr",
    "clocks.mem",
]


@dataclass(frozen=True)
class GpuTelemetrySample:
    timestamp: str | None
    name: str | None
    driver_version: str | None
    pstate: str | None
    temperature_gpu_c: int | None
    utilization_gpu_pct: int | None
    utilization_memory_pct: int | None
    memory_total_mib: int | None
    memory_used_mib: int | None
    power_draw_w: float | None
    clocks_gr_mhz: int | None
    clocks_mem_mhz: int | None


def _none_if_na(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "" or stripped.upper() == "N/A":
        return None
    return stripped


def _int_with_unit(value: str | None) -> int | None:
    cleaned = _none_if_na(value)
    if cleaned is None:
        return None
    return int(float(cleaned.split()[0].replace("%", "")))


def _float_with_unit(value: str | None) -> float | None:
    cleaned = _none_if_na(value)
    if cleaned is None:
        return None
    return float(cleaned.split()[0])


def parse_nvidia_smi_csv(output: str) -> list[GpuTelemetrySample]:
    reader = csv.DictReader(StringIO(output.strip()), skipinitialspace=True)
    samples: list[GpuTelemetrySample] = []
    for row in reader:
        row = {key.strip() if key else key: value for key, value in row.items()}
        samples.append(
            GpuTelemetrySample(
                timestamp=_none_if_na(row.get("timestamp")),
                name=_none_if_na(row.get("name")),
                driver_version=_none_if_na(row.get("driver_version")),
                pstate=_none_if_na(row.get("pstate")),
                temperature_gpu_c=_int_with_unit(row.get("temperature.gpu")),
                utilization_gpu_pct=_int_with_unit(row.get("utilization.gpu")),
                utilization_memory_pct=_int_with_unit(row.get("utilization.memory")),
                memory_total_mib=_int_with_unit(row.get("memory.total")),
                memory_used_mib=_int_with_unit(row.get("memory.used")),
                power_draw_w=_float_with_unit(row.get("power.draw")),
                clocks_gr_mhz=_int_with_unit(row.get("clocks.gr")),
                clocks_mem_mhz=_int_with_unit(row.get("clocks.mem")),
            )
        )
    return samples


class GPUTelemetryService:
    query_args = [
        "nvidia-smi",
        "--query-gpu=" + ",".join(GPU_QUERY_FIELDS),
        "--format=csv",
    ]

    def health(self) -> dict:
        if shutil.which("nvidia-smi") is None:
            return {"status": "unavailable", "available": False, "error": "nvidia-smi not found"}
        try:
            result = subprocess.run(self.query_args, capture_output=True, text=True, timeout=5, check=False)
        except OSError as exc:
            return {"status": "unavailable", "available": False, "error": str(exc)}
        if result.returncode != 0:
            return {"status": "unavailable", "available": False, "error": result.stderr.strip()}
        samples = parse_nvidia_smi_csv(result.stdout)
        return {"status": "ok", "available": True, "sample_count": len(samples)}
