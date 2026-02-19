import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path
from justpipe import Pipe, EventType
from justpipe.types import BarrierType
from examples.utils import save_graph


@dataclass
class State:
    user_id: int = 123
    user_data: dict = field(default_factory=dict)
    source: str = "unknown"
    fraud_score: int = 0
    credit_score: int = 0
    is_approved: bool = False


pipe = Pipe(State)


# --- Phase 1: Redundant Data Fetch (BarrierType.ANY) ---

@pipe.step(to="normalize_user_data")
async def fetch_from_cache(state: State):
    """Simulates a fast but unreliable cache."""
    delay = random.uniform(0.01, 0.05)
    await asyncio.sleep(delay)
    
    # 50% chance of cache hit
    if random.choice([True, False]):
        state.user_data = {"name": "Alice (Cached)", "level": "Gold"}
        state.source = "Cache"
        print(f"✅ Cache hit! ({delay:.3f}s)")
    else:
        print(f"❌ Cache miss! ({delay:.3f}s)")
        # In a real app, you might raise Skip() or just return
        # Here we just don't set user_data, so the check downstream might fail
        # if DB hasn't finished. But for ANY, we usually want a valid result.
        # Let's simulate a 'soft failure' by not setting data.


@pipe.step(to="normalize_user_data")
async def fetch_from_db(state: State):
    """Simulates a slow but reliable database."""
    # Always slower than cache hit, but maybe faster than cache miss + timeout
    await asyncio.sleep(0.1) 
    state.user_data = {"name": "Alice (DB)", "level": "Gold"}
    state.source = "Database"
    print("🐢 DB fetch complete.")


@pipe.step(barrier_type=BarrierType.ANY, to=["check_fraud", "check_credit"])
async def normalize_user_data(state: State):
    """
    Runs as soon as the FIRST fetch finishes.
    In a real app, you'd check if the data is valid.
    If 'fetch_from_cache' finished but empty, you might skip this 
    and wait for DB (requires more complex logic), 
    or here we assume the first *successful* one wins.
    """
    if not state.user_data:
        # Cache finished (missed) but DB is still running?
        # With BarrierType.ANY, this step triggers once.
        # If cache missed, we might be in trouble unless we handle it.
        # For this example, let's assume cache hit OR DB hit.
        # If cache missed, this runs with empty data. 
        # (This highlights why ANY requires care!)
        print("⚠️  Warning: Triggered by empty source (Cache miss?), waiting for DB would be better.")
    
    print(f"🔄 Normalizing data from: {state.source}")


# --- Phase 2: Parallel Checks (BarrierType.ALL) ---

@pipe.step(to="finalize_decision")
async def check_fraud(state: State):
    await asyncio.sleep(0.05)
    state.fraud_score = 10
    print("🕵️  Fraud check done.")


@pipe.step(to="finalize_decision")
async def check_credit(state: State):
    await asyncio.sleep(0.05)
    state.credit_score = 750
    print("💳 Credit check done.")


@pipe.step(to=[fetch_from_cache, fetch_from_db])
async def start(state: State):
    print(f"🚀 Starting fetch for user {state.user_id}...")


# Default BarrierType.ALL
@pipe.step(barrier_type=BarrierType.ALL)
async def finalize_decision(state: State):
    print("📝 Finalizing decision...")
    print(f"   Source: {state.source}")
    print(f"   Fraud Score: {state.fraud_score}")
    print(f"   Credit Score: {state.credit_score}")
    
    if state.fraud_score < 50 and state.credit_score > 700:
        state.is_approved = True
        print("✅ User APPROVED")
    else:
        print("❌ User REJECTED")


async def main():
    state = State()
    print("--- Race: Cache vs DB ---")
    
    # We run it multiple times to see the race
    async for event in pipe.run(state):
        if event.type == EventType.STEP_ERROR:
            print(f"🔥 Error: {event.payload}")

    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")
    print(f"\nGraph saved to {Path(__file__).parent / 'pipeline.mmd'}")


if __name__ == "__main__":
    asyncio.run(main())
