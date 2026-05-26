from backend.app.services.telemetry.gpu import parse_nvidia_smi_csv


def test_nvidia_smi_parser_full_csv():
    output = """timestamp, name, driver_version, pstate, temperature.gpu, utilization.gpu, utilization.memory, memory.total, memory.used, power.draw, clocks.gr, clocks.mem
2026/05/26 00:00:00.000, NVIDIA RTX 5090 Laptop GPU, 555.55, P0, 71, 92 %, 48 %, 24564 MiB, 22000 MiB, 145.30 W, 2100 MHz, 9001 MHz
"""
    sample = parse_nvidia_smi_csv(output)[0]
    assert sample.name == "NVIDIA RTX 5090 Laptop GPU"
    assert sample.memory_total_mib == 24564
    assert sample.power_draw_w == 145.30
    assert sample.clocks_mem_mhz == 9001


def test_nvidia_smi_parser_tolerates_na_fields():
    output = """timestamp, name, driver_version, pstate, temperature.gpu, utilization.gpu, utilization.memory, memory.total, memory.used, power.draw, clocks.gr, clocks.mem
2026/05/26 00:00:00.000, NVIDIA GPU, 555.55, P8, N/A, N/A, 0 %, 24564 MiB, N/A, N/A, N/A, N/A
"""
    sample = parse_nvidia_smi_csv(output)[0]
    assert sample.temperature_gpu_c is None
    assert sample.utilization_gpu_pct is None
    assert sample.power_draw_w is None
    assert sample.memory_total_mib == 24564

