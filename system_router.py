from fastapi import APIRouter
from config_analyzer import get_system_specs, analyze_logs, calculate_optimal_config, LOG_PATH

router = APIRouter(prefix="/api/system", tags=["System Tuning"])

@router.get("/tune")
def get_tuning_recommendations():
    cpu, mem_total, mem_avail = get_system_specs()
    metrics = analyze_logs(LOG_PATH)
    config = calculate_optimal_config(cpu, mem_total, mem_avail, metrics)
    return {
        "hardware": {"cpu_cores": cpu, "total_ram_mb": mem_total, "available_ram_mb": mem_avail},
        "metrics": metrics,
        "recommendations": config
    }
