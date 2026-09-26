"""
JARVIS AI OS — Comprehensive Runtime Performance Benchmark Suite.

Measures:
1. Python startup and module import latency
2. Application startup & lifespan bootstrap latency
3. ServiceManager lazy loading & caching performance
4. Memory hierarchy (Working, LongTerm, Episodic, Semantic) latency
5. ToolRegistry lookup, schema validation, and tool execution latency
6. FastIntentRouter vs RequestRouter vs Planner latency
7. Automation orchestrator and ActionExecutionVerifier latency
8. API endpoint latency (cold, warm, median, p95)
9. Process RSS memory profile across subsystem initialization
"""

import os
import sys
import time
import json
import psutil
import asyncio
from pathlib import Path
from typing import Dict, Any, List
import statistics

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def measure_rss_mb() -> float:
    process = psutil.Process(os.getpid())
    return round(process.memory_info().rss / (1024 * 1024), 2)


async def run_full_benchmark():
    print("=" * 70)
    print("JARVIS AI OS - RUNTIME PERFORMANCE BENCHMARK SUITE")
    print("=" * 70)

    results: Dict[str, Any] = {}
    baseline_rss = measure_rss_mb()
    results["baseline_rss_mb"] = baseline_rss
    print(f"Process Initial Baseline RSS: {baseline_rss:.2f} MB")

    # 1. Module Import Times
    print("\n1. Measuring Subsystem Import Times...")
    import_times = {}
    
    modules_to_measure = [
        ("backend.config", "Config Settings"),
        ("backend.utils.event_bus", "EventBus"),
        ("backend.services.manager", "ServiceManager Container"),
        ("backend.services.safety_gatekeeper", "SafetyGatekeeper"),
        ("backend.services.fast_intent_router", "FastIntentRouter"),
        ("backend.services.tool_registry", "ToolRegistry"),
        ("backend.agents.router", "Hierarchical RequestRouter"),
        ("backend.agents.planner.planner", "PlannerAgent & TaskDecomposer"),
        ("backend.services.automation.orchestrator", "AutomationOrchestrator"),
        ("backend.services.automation.verifier", "ActionExecutionVerifier"),
        ("backend.services.memory.manager", "MemoryManager"),
        ("backend.api.routes", "API Routes"),
        ("backend.api.mobile_router", "Mobile Router"),
        ("backend.main", "Full FastAPI Main Lifespan Entrypoint")
    ]

    for mod_name, desc in modules_to_measure:
        t0 = time.perf_counter()
        __import__(mod_name)
        dt_ms = (time.perf_counter() - t0) * 1000
        import_times[mod_name] = round(dt_ms, 2)
        print(f"   |- {desc:35s} ({mod_name}): {dt_ms:.2f} ms")

    results["import_times_ms"] = import_times

    # 2. Application Creation & Core Bootstrap
    print("\n2. Measuring Application Startup & ServiceManager Bootstrap...")
    from backend.main import app
    from backend.services.bootstrap import bootstrap_core_services, register_lazy_factories
    from backend.services.manager import ServiceManager
    from backend.utils.event_bus import EventBus
    from backend.api.websocket import RobustConnectionManager

    t_boot_start = time.perf_counter()
    event_bus = EventBus()
    conn_mgr = RobustConnectionManager()
    bootstrap_core_services(app, event_bus)
    register_lazy_factories(event_bus, conn_mgr)
    t_boot_end = time.perf_counter()
    core_boot_ms = (t_boot_end - t_boot_start) * 1000
    results["core_bootstrap_ms"] = round(core_boot_ms, 2)
    boot_rss = measure_rss_mb()
    results["post_bootstrap_rss_mb"] = boot_rss
    print(f"   |- Core Bootstrap Duration: {core_boot_ms:.2f} ms")
    print(f"   |- Registered ServiceManager Factories: {len(ServiceManager._factories)}")
    print(f"   |- Post-Bootstrap RSS Memory: {boot_rss:.2f} MB (Delta: +{boot_rss - baseline_rss:.2f} MB)")

    # 3. ServiceManager Lookup & Lazy Factory Latency
    print("\n3. Benchmarking ServiceManager Lazy Instantiation vs Warm Cache...")
    svc_benchmarks = {}
    test_services = [
        ("safety_gatekeeper", "Safety Gatekeeper"),
        ("fast_intent_router", "Fast Intent Router"),
        ("tool_registry", "Tool Registry"),
        ("agent_ecosystem", "Agent Ecosystem"),
        ("self_diagnostic_engine", "Self Diagnostic Engine"),
        ("self_healing_engine", "Self Healing Engine"),
    ]

    for svc_key, desc in test_services:
        t0 = time.perf_counter()
        inst1 = ServiceManager.get_instance(svc_key)
        cold_ms = (time.perf_counter() - t0) * 1000
        
        warm_times = []
        for _ in range(50):
            t1 = time.perf_counter()
            inst2 = ServiceManager.get_instance(svc_key)
            warm_times.append((time.perf_counter() - t1) * 1000)
            assert inst1 is inst2, "ServiceManager instance caching violated!"
            
        warm_median_us = statistics.median(warm_times) * 1000
        svc_benchmarks[svc_key] = {
            "cold_init_ms": round(cold_ms, 3),
            "warm_median_us": round(warm_median_us, 2)
        }
        print(f"   |- {desc:25s} Cold Init: {cold_ms:6.2f} ms | Warm Lookup: {warm_median_us:6.2f} us")

    results["service_manager_benchmarks"] = svc_benchmarks

    # 4. Intent Routing & Planner Latency
    print("\n4. Benchmarking Intent Routing & Planning Latency...")
    from backend.services.fast_intent_router import FastIntentRouter
    from backend.agents.router import classify_request, RequestCategory
    from backend.agents.planner.plan_validator import PlanValidator

    fast_router = FastIntentRouter()
    validator = PlanValidator()

    fast_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        res = fast_router.classify("lock the pc")
        fast_times.append((time.perf_counter() - t0) * 1000)
    fast_median_us = statistics.median(fast_times) * 1000

    hier_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        cat = classify_request("Open Google Chrome and search for quantum computing papers")
        hier_times.append((time.perf_counter() - t0) * 1000)
    hier_median_us = statistics.median(hier_times) * 1000

    val_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        v = validator.evaluate_safety("open_application", {"app_name": "notepad"})
        val_times.append((time.perf_counter() - t0) * 1000)
    val_median_us = statistics.median(val_times) * 1000

    print(f"   |- FastIntentRouter Median Latency:       {fast_median_us:.2f} us (Sub-millisecond)")
    print(f"   |- Hierarchical RequestRouter Median:    {hier_median_us:.2f} us")
    print(f"   |- PlanValidator Safety Check Median:    {val_median_us:.2f} us")

    results["routing_planning_benchmarks"] = {
        "fast_intent_router_median_us": round(fast_median_us, 2),
        "request_router_median_us": round(hier_median_us, 2),
        "plan_validator_median_us": round(val_median_us, 2)
    }

    # 5. ToolRegistry Lookup, Validation & Execution Latency
    print("\n5. Benchmarking ToolRegistry & ActionExecutionVerifier...")
    from backend.services.tool_registry import ToolRegistry
    from backend.services.safety_gatekeeper import SafetyGatekeeper
    from backend.services.automation.verifier import ActionExecutionVerifier

    registry = ToolRegistry()
    gatekeeper = SafetyGatekeeper()
    verifier = ActionExecutionVerifier()

    lookup_times = []
    for _ in range(1000):
        t0 = time.perf_counter()
        tool = registry.get_tool("get_system_status")
        lookup_times.append((time.perf_counter() - t0) * 1000000)
    lookup_median_us = statistics.median(lookup_times)

    gate_times = []
    for _ in range(1000):
        t0 = time.perf_counter()
        dec = gatekeeper.evaluate_tool_call("open_application", {"app_name": "notepad"})
        gate_times.append((time.perf_counter() - t0) * 1000000)
    gate_median_us = statistics.median(gate_times)

    tool_exec_benchmarks = {}
    for tool_name, args in [
        ("get_system_status", {}),
        ("get_monitors", {}),
        ("get_running_processes", {})
    ]:
        exec_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            r = await registry.execute_tool(tool_name, args)
            exec_times.append((time.perf_counter() - t0) * 1000)
        tool_exec_benchmarks[tool_name] = {
            "median_ms": round(statistics.median(exec_times), 2),
            "min_ms": round(min(exec_times), 2),
            "max_ms": round(max(exec_times), 2)
        }
        print(f"   |- Tool '{tool_name:22s}' Median Execution: {statistics.median(exec_times):6.2f} ms")

    t0 = time.perf_counter()
    v_res = await verifier.execute_and_verify("get_system_status", {}, registry)
    verifier_ms = (time.perf_counter() - t0) * 1000
    print(f"   |- ToolRegistry Lookup Median:           {lookup_median_us:.2f} us")
    print(f"   |- SafetyGatekeeper Evaluation Median:   {gate_median_us:.2f} us")
    print(f"   |- ActionExecutionVerifier Loop:         {verifier_ms:.2f} ms")

    results["tool_benchmarks"] = {
        "lookup_median_us": round(lookup_median_us, 2),
        "gatekeeper_median_us": round(gate_median_us, 2),
        "verifier_loop_ms": round(verifier_ms, 2),
        "tools": tool_exec_benchmarks
    }

    # 6. Memory Hierarchy Read/Write/Retrieve Latency
    print("\n6. Benchmarking Unified Memory Hierarchy...")
    from backend.services.memory import MemoryManager

    mem_manager = MemoryManager()
    t_mem_init_start = time.perf_counter()
    await mem_manager.init()
    mem_init_ms = (time.perf_counter() - t_mem_init_start) * 1000
    print(f"   |- MemoryManager Full Layer Init:        {mem_init_ms:.2f} ms")

    wm_times = []
    for i in range(100):
        t0 = time.perf_counter()
        mem_manager.working.add_turn("user", f"Turn message {i}")
        turns = mem_manager.working.get_turns()
        wm_times.append((time.perf_counter() - t0) * 1000)
    wm_median_us = statistics.median(wm_times) * 1000

    ltm_times = []
    for i in range(50):
        t0 = time.perf_counter()
        await mem_manager.long_term.set_user_preference(f"bench_key_{i}", f"bench_val_{i}")
        val = await mem_manager.long_term.get_user_preference(f"bench_key_{i}")
        ltm_times.append((time.perf_counter() - t0) * 1000)
    ltm_median_ms = statistics.median(ltm_times)

    epi_times = []
    for i in range(20):
        t0 = time.perf_counter()
        mem_manager.store_episode(goal=f"bench_goal_{i}", result="success", success=True)
        epi_times.append((time.perf_counter() - t0) * 1000)
    epi_median_ms = statistics.median(epi_times)

    print(f"   |- WorkingMemory Turn Cycle Median:      {wm_median_us:.2f} us")
    print(f"   |- LongTerm Memory KV Store/Read Median: {ltm_median_ms:.2f} ms")
    print(f"   |- Episodic Memory Record Trace Median:  {epi_median_ms:.2f} ms")

    results["memory_benchmarks"] = {
        "manager_init_ms": round(mem_init_ms, 2),
        "working_memory_median_us": round(wm_median_us, 2),
        "long_term_median_ms": round(ltm_median_ms, 3),
        "episodic_median_ms": round(epi_median_ms, 3)
    }

    # 7. Subsystem RAM Profile
    print("\n7. Profiling Subsystem RSS Memory Impact...")
    ram_profile = {}
    ram_profile["baseline_startup"] = measure_rss_mb()

    from backend.services.world_model import WorldModel
    wm = WorldModel()
    ram_profile["after_world_model"] = measure_rss_mb()

    from backend.services.automation.orchestrator import AutomationOrchestrator
    ao = AutomationOrchestrator()
    ram_profile["after_automation"] = measure_rss_mb()

    from backend.services.voice.voice_manager import VoiceManager
    vm = VoiceManager()
    ram_profile["after_voice_manager"] = measure_rss_mb()

    for k, v in ram_profile.items():
        delta = v - ram_profile["baseline_startup"]
        print(f"   |- {k:25s}: {v:6.2f} MB (Delta: +{delta:5.2f} MB)")

    results["ram_profile_mb"] = ram_profile

    # 8. API Endpoint Latency
    print("\n8. Benchmarking REST API Endpoints (Local In-Memory ASGI)...")
    import httpx
    api_benchmarks = {}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        test_endpoints = [
            ("GET", "/api/health", "Health Check"),
            ("GET", "/api/system/status", "System Status HUD"),
            ("GET", "/api/v1/tools", "Tool Catalog"),
            ("GET", "/api/v1/mobile/telemetry", "Mobile Telemetry HUD"),
            ("GET", "/api/v1/mobile/live_mode/status", "Mobile Live Mode Status"),
            ("GET", "/api/v1/mobile/devices", "Trusted Devices"),
        ]

        for method, path, desc in test_endpoints:
            t0 = time.perf_counter()
            resp = await client.request(method, path)
            cold_ms = (time.perf_counter() - t0) * 1000
            assert resp.status_code < 500, f"Endpoint {path} failed with {resp.status_code}"

            warm_times = []
            for _ in range(25):
                t1 = time.perf_counter()
                resp = await client.request(method, path)
                warm_times.append((time.perf_counter() - t1) * 1000)

            median_ms = statistics.median(warm_times)
            sorted_warm = sorted(warm_times)
            p95_index = int(len(sorted_warm) * 0.95)
            p95_ms = sorted_warm[p95_index]

            api_benchmarks[path] = {
                "cold_ms": round(cold_ms, 2),
                "median_ms": round(median_ms, 2),
                "p95_ms": round(p95_ms, 2)
            }
            print(f"   |- {desc:25s} ({path:30s}) Cold: {cold_ms:6.2f} ms | Warm Median: {median_ms:5.2f} ms | p95: {p95_ms:5.2f} ms")

    results["api_benchmarks"] = api_benchmarks

    print("\n" + "=" * 70)
    print("BENCHMARK SUITE EXECUTION COMPLETE - ALL CHECKS PASSED")
    print("=" * 70)

    out_path = PROJECT_ROOT / "data" / "benchmark_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark output persisted to {out_path}")

    return results


if __name__ == "__main__":
    asyncio.run(run_full_benchmark())
