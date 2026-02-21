"""Dashboard Showcase — Cloud Video Rendering Pipeline.

A comprehensive example that exercises every dashboard feature:
- DAG view: all 5 node kinds (step, map, switch, sub, barrier)
- Timeline: parallel fetches, map fan-out, barrier sync points
- Events: all event types including TOKEN, BARRIER_*, MAP_*
- Metrics: step latency, barrier stats, map stats, retry counts
- Replay: streaming preview tokens
- Artifacts: state payloads at each step
- Meta: step-level metrics, run-level tags, pipeline-level metadata
- Compare: 3 contrasting scenarios (fast/slow/failed)

Run:
    uv run examples/16_dashboard_showcase/main.py

Then launch dashboard:
    JUSTPIPE_STORAGE_PATH=/tmp/justpipe_showcase uv run justpipe dashboard
"""

import asyncio
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from justpipe import Pipe, EventType, Meta
from justpipe.types import BarrierType, PipelineEndData
from examples.utils import save_graph


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class ScenarioConfig:
    name: str
    num_scenes: int
    cdn_available: bool
    scene_complexity: str  # "simple" or "complex"
    flaky_scene_index: int | None
    render_duration: float
    preview_token_count: int
    project_name: str
    tags: list[str] = field(default_factory=list)


@dataclass
class RenderJob:
    job_id: str = ""
    project_name: str = ""
    resolution: tuple[int, int] = (1920, 1080)
    scenes: list[dict] = field(default_factory=list)
    scene_analyses: list[dict] = field(default_factory=list)
    avg_complexity: float = 0.0
    quality_tier: str = ""
    render_params: dict = field(default_factory=dict)
    rendered_frames: int = 0
    preview_url: str = ""
    manifest: dict = field(default_factory=dict)
    asset_source: str = ""
    assets_fetched: bool = False


@dataclass
class RenderContext:
    config: ScenarioConfig | None = None
    gpu_pool: dict = field(default_factory=dict)
    meta: Meta | None = None


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIO_A = ScenarioConfig(
    name="Quick Promo",
    num_scenes=3,
    cdn_available=True,
    scene_complexity="simple",
    flaky_scene_index=None,
    render_duration=0.1,
    preview_token_count=5,
    project_name="Summer Promo 2026",
    tags=["promo", "fast-track", "1080p"],
)

SCENARIO_B = ScenarioConfig(
    name="Feature Film",
    num_scenes=8,
    cdn_available=False,
    scene_complexity="complex",
    flaky_scene_index=2,
    render_duration=0.5,
    preview_token_count=15,
    project_name="The Last Algorithm",
    tags=["feature", "premium", "4k", "hdr"],
)

SCENARIO_C = ScenarioConfig(
    name="Deadline Crunch",
    num_scenes=5,
    cdn_available=False,
    scene_complexity="complex",
    flaky_scene_index=None,
    render_duration=4.0,  # Exceeds render_frames timeout=3s
    preview_token_count=0,
    project_name="Q4 Launch Trailer",
    tags=["urgent", "deadline", "4k"],
)


# ---------------------------------------------------------------------------
# Sub-Pipeline: GPU Render Farm (3 steps)
# ---------------------------------------------------------------------------

gpu_render_pipe = Pipe(RenderJob, name="GpuRenderFarm")


@gpu_render_pipe.step("allocate_gpu", to="render_frames")
async def allocate_gpu(state: RenderJob):
    await asyncio.sleep(0.02)
    state.render_params["gpu_id"] = f"gpu-{random.randint(0, 7)}"
    state.render_params["vram_mb"] = 24576


@gpu_render_pipe.step("render_frames", to="release_gpu", timeout=3.0)
async def render_frames(state: RenderJob):
    duration = state.render_params.get("duration", 0.1)
    num_frames = len(state.scenes) * 24  # 24 fps per scene
    per_frame = duration / max(num_frames, 1)

    for i in range(num_frames):
        await asyncio.sleep(per_frame)

    state.rendered_frames = num_frames


@gpu_render_pipe.step("release_gpu")
async def release_gpu(state: RenderJob):
    await asyncio.sleep(0.01)
    state.render_params["gpu_released"] = True


# ---------------------------------------------------------------------------
# Main Pipeline: Video Render (15 steps)
# ---------------------------------------------------------------------------

pipe = Pipe(
    RenderJob,
    RenderContext,
    name="VideoRenderPipeline",
    metadata={"version": "2.1", "team": "render-ops", "region": "us-east-1"},
    persist=True,
    flush_interval=20,
)


# --- Lifecycle Hooks ---


@pipe.on_startup
async def warmup_gpu_pool(ctx: RenderContext):
    ctx.gpu_pool = {
        "nodes": ["gpu-0", "gpu-1", "gpu-2", "gpu-3"],
        "status": "warm",
    }
    if ctx.meta:
        ctx.meta.run.set("gpu_pool_size", len(ctx.gpu_pool["nodes"]))


@pipe.on_shutdown
async def release_gpu_pool(ctx: RenderContext):
    ctx.gpu_pool["status"] = "released"


# --- Steps ---


@pipe.step("accept_job", to="validate_job")
async def accept_job(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.01)
    state.project_name = ctx.config.project_name
    if ctx.meta:
        ctx.meta.run.set("project", state.project_name)
        ctx.meta.run.set("job_id", state.job_id)
        ctx.meta.run.set("resolution", f"{state.resolution[0]}x{state.resolution[1]}")
        for tag in ctx.config.tags:
            ctx.meta.run.add_tag(tag)
        ctx.meta.step.set("scenario", ctx.config.name)


@pipe.step("validate_job", to=["fetch_cdn", "fetch_origin"])
async def validate_job(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.01)
    if not state.job_id:
        raise ValueError("Missing job_id")
    if ctx.meta:
        ctx.meta.step.set("validated", True)
        ctx.meta.step.set("num_scenes_requested", ctx.config.num_scenes)


@pipe.step("fetch_cdn", to="normalize_assets")
async def fetch_cdn(state: RenderJob, ctx: RenderContext):
    if ctx.config.cdn_available:
        await asyncio.sleep(0.02)  # Fast CDN hit
        state.asset_source = "cdn"
        state.assets_fetched = True
        if ctx.meta:
            ctx.meta.step.set("source", "cdn")
            ctx.meta.step.record_metric("latency_ms", 20.0)
    else:
        # CDN unavailable — stall (origin wins the ANY-barrier race)
        await asyncio.sleep(0.5)
        if ctx.meta:
            ctx.meta.step.set("source", "cdn_timeout")
            ctx.meta.step.record_metric("latency_ms", 500.0)


@pipe.step("fetch_origin", to="normalize_assets")
async def fetch_origin(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.1)  # Origin is slower but reliable
    state.asset_source = "origin"
    state.assets_fetched = True
    if ctx.meta:
        ctx.meta.step.set("source", "origin")
        ctx.meta.step.record_metric("latency_ms", 100.0)


@pipe.step("normalize_assets", barrier_type=BarrierType.ANY, to="extract_scenes")
async def normalize_assets(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.02)
    if ctx.meta:
        ctx.meta.step.set("asset_source", state.asset_source)


@pipe.map("extract_scenes", each="analyze_scene", to="merge_analysis")
async def extract_scenes(state: RenderJob, ctx: RenderContext):
    state.scenes = [
        {
            "index": i,
            "name": f"scene_{i:03d}",
            "duration_s": round(random.uniform(2.0, 10.0), 2),
            "complexity": round(
                random.uniform(0.5, 1.0)
                if ctx.config.scene_complexity == "complex"
                else random.uniform(0.1, 0.4),
                3,
            ),
        }
        for i in range(ctx.config.num_scenes)
    ]
    if ctx.meta:
        ctx.meta.step.set("scene_count", len(state.scenes))
    return state.scenes


@pipe.step("analyze_scene", retries=2)
async def analyze_scene(state: RenderJob, ctx: RenderContext, scene: dict):
    scene_idx = scene["index"]

    # Track attempts for flaky scene retry demo
    attempts_key = f"scene_{scene_idx}_attempts"
    ctx.gpu_pool[attempts_key] = ctx.gpu_pool.get(attempts_key, 0) + 1

    if (
        ctx.config.flaky_scene_index is not None
        and scene_idx == ctx.config.flaky_scene_index
        and ctx.gpu_pool[attempts_key] == 1
    ):
        raise RuntimeError(f"Scene {scene_idx}: GPU memory fault (transient)")

    await asyncio.sleep(0.02)

    analysis = {
        "index": scene_idx,
        "name": scene["name"],
        "complexity": scene["complexity"],
        "motion_vectors": random.randint(100, 5000),
        "color_depth": "10bit" if scene["complexity"] > 0.5 else "8bit",
    }
    state.scene_analyses.append(analysis)

    if ctx.meta:
        ctx.meta.step.record_metric("complexity", scene["complexity"])
        ctx.meta.step.set("scene_name", scene["name"])


@pipe.step("merge_analysis", barrier_type=BarrierType.ALL, to="select_strategy")
async def merge_analysis(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.01)
    if state.scene_analyses:
        total = sum(a["complexity"] for a in state.scene_analyses)
        state.avg_complexity = total / len(state.scene_analyses)
    if ctx.meta:
        ctx.meta.step.set("avg_complexity", round(state.avg_complexity, 3))
        ctx.meta.step.set("scenes_analyzed", len(state.scene_analyses))
        ctx.meta.step.record_metric("avg_complexity", state.avg_complexity)


@pipe.switch("select_strategy", to={"high": "hi_quality", "low": "lo_quality"})
async def select_strategy(state: RenderJob, ctx: RenderContext):
    if state.avg_complexity > 0.5:
        state.quality_tier = "high"
        return "high"
    else:
        state.quality_tier = "low"
        return "low"


@pipe.step("hi_quality", to="render_farm")
async def hi_quality(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.01)
    state.render_params.update({
        "preset": "ultra",
        "ray_tracing": True,
        "samples": 4096,
        "denoiser": "optix",
    })
    if ctx.meta:
        ctx.meta.step.set("quality_preset", "ultra")
        ctx.meta.run.set("quality_tier", "high")


@pipe.step("lo_quality", to="render_farm")
async def lo_quality(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.01)
    state.render_params.update({
        "preset": "draft",
        "ray_tracing": False,
        "samples": 64,
        "denoiser": "basic",
    })
    if ctx.meta:
        ctx.meta.step.set("quality_preset", "draft")
        ctx.meta.run.set("quality_tier", "low")


@pipe.sub("render_farm", pipeline=gpu_render_pipe, to="composite_frames")
async def render_farm(state: RenderJob, ctx: RenderContext):
    state.render_params["duration"] = ctx.config.render_duration
    if ctx.meta:
        ctx.meta.step.set("render_duration", ctx.config.render_duration)
        ctx.meta.step.set("gpu_nodes_available", len(ctx.gpu_pool.get("nodes", [])))
    return state


@pipe.step(
    "composite_frames",
    barrier_type=BarrierType.ALL,
    barrier_timeout=5.0,
    to="generate_preview",
)
async def composite_frames(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.03)
    state.manifest["frames"] = state.rendered_frames
    state.manifest["format"] = "EXR"
    state.manifest["composited"] = True
    if ctx.meta:
        ctx.meta.step.set("frames_composited", state.rendered_frames)
        ctx.meta.step.record_metric("frame_count", float(state.rendered_frames))


@pipe.step("generate_preview", to="deliver")
async def generate_preview(state: RenderJob, ctx: RenderContext):
    token_count = ctx.config.preview_token_count
    state.preview_url = f"https://renders.example.com/{state.job_id}/preview.mp4"
    if ctx.meta:
        ctx.meta.step.set("token_count", token_count)
    for i in range(token_count):
        await asyncio.sleep(0.03)
        yield f"preview_frame_{i:04d}.jpg"


@pipe.step("deliver")
async def deliver(state: RenderJob, ctx: RenderContext):
    await asyncio.sleep(0.02)
    state.manifest.update({
        "delivery_url": f"https://renders.example.com/{state.job_id}/final.mp4",
        "preview_url": state.preview_url,
        "quality_tier": state.quality_tier,
        "project": state.project_name,
    })
    if ctx.meta:
        ctx.meta.run.set("delivery_url", state.manifest["delivery_url"])
        ctx.meta.run.set("total_frames", state.rendered_frames)
        ctx.meta.step.set("manifest_keys", list(state.manifest.keys()))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def main():
    storage_dir = "/tmp/justpipe_showcase"
    os.environ["JUSTPIPE_STORAGE_PATH"] = storage_dir

    scenarios = [SCENARIO_A, SCENARIO_B, SCENARIO_C]
    results: list[tuple[str, str | None, str]] = []

    print("=" * 70)
    print("VIDEO RENDER PIPELINE - Dashboard Showcase")
    print("=" * 70)
    print()

    for config in scenarios:
        state = RenderJob(
            job_id=uuid4().hex[:12],
            project_name=config.project_name,
            resolution=(3840, 2160) if "4k" in config.tags else (1920, 1080),
        )
        context = RenderContext(config=config)

        print(f"  Running: {config.name} ({config.project_name})")

        run_id: str | None = None
        status_str = "unknown"
        duration = 0.0

        async for event in pipe.run(state, context, start="accept_job"):
            if event.type == EventType.FINISH:
                # Overwrite on each FINISH — the last one is the main pipeline's
                end_data: PipelineEndData = event.payload
                run_id = event.run_id
                status_str = end_data.status.value
                duration = end_data.duration_s

        if run_id:
            print(
                f"    -> {status_str.upper()} in {duration:.2f}s"
                f" (run: {run_id[:12]}...)"
            )

        results.append((config.name, run_id, status_str))
        print()

    # Save Mermaid graph
    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")

    # Print summary
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    for name, rid, status in results:
        rid_short = rid[:12] if rid else "N/A"
        marker = "+" if status == "success" else "x"
        print(f"  [{marker}] {name:20s}  {status:10s}  {rid_short}")
    print()

    # Dashboard launch instructions
    print("=" * 70)
    print("LAUNCH DASHBOARD")
    print("=" * 70)
    print()
    print(f"  JUSTPIPE_STORAGE_PATH={storage_dir} uv run justpipe dashboard")
    print()

    # Compare instructions
    success_runs = [(n, r) for n, r, s in results if s == "success" and r]
    if len(success_runs) >= 2:
        r1 = success_runs[0][1][:12]
        r2 = success_runs[1][1][:12]
        print("Compare runs:")
        print(
            f"  JUSTPIPE_STORAGE_PATH={storage_dir}"
            f" uv run justpipe compare {r1} {r2}"
        )
        print()


if __name__ == "__main__":
    asyncio.run(main())
