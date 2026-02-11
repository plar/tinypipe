import asyncio
from pathlib import Path
from justpipe import Pipe, TestPipe, Skip
from examples.utils import save_graph

# 1. Define domain models
class UserState:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.processed = False
        self.logs: list[str] = []

class UserContext:
    def __init__(self):
        self.db_connected = False

# 2. Define a more complex pipeline to show off the full Test API
pipe: Pipe[UserState, UserContext] = Pipe(
    state_type=UserState, 
    context_type=UserContext, 
    name="AdvancedTestingDemo"
)

@pipe.on_startup
async def connect_db(ctx: UserContext):
    print("Connecting to production DB...")
    ctx.db_connected = True

@pipe.step(to="process_stream")
async def check_connection(ctx: UserContext):
    if not ctx.db_connected:
        raise RuntimeError("Database not connected!")

@pipe.step(to="notify_user")
async def process_stream(state: UserState):
    """A step that yields multiple tokens."""
    yield "analyzing_profile"
    yield "checking_permissions"
    state.processed = True

@pipe.step()
async def notify_user(state: UserState):
    print(f"Sending real email to {state.user_id}...")

@pipe.on_error
async def handle_error(error: Exception, state: UserState):
    print(f"Global recovery from: {error}")
    state.logs.append("error_recovered")

# 3. Comprehensive Test Demo
async def run_comprehensive_demo():
    print("=== Advanced Testing Harness API Demo ===")
    
    state = UserState(user_id=99)
    context = UserContext()

    with TestPipe(pipe) as tester:
        # A. Mock Startup Hooks (prevent real DB connection)
        mock_startup = tester.mock_startup()
        
        # B. Mock Step with Side Effect
        mock_notify = tester.mock("notify_user")
        
        # C. Mock On Error
        mock_error = tester.mock_on_error()

        print("\nRun 1: Full Mocks")
        result = await tester.run(state, context=context)

        print("\n--- API Coverage Assertions ---")
        # 1. Verify Startup Mock
        mock_startup.assert_called_once()
        print(f"✓ Startup was mocked (DB connected: {context.db_connected})")

        # 2. Verify Tokens (result.tokens)
        print(f"✓ Collected tokens: {result.tokens}")
        assert "analyzing_profile" in result.tokens

        # 3. Verify Step Path (result.was_called)
        assert result.was_called("process_stream")
        print(f"✓ Step 'process_stream' was executed: {result.was_called('process_stream')}")
        
        # 4. Verify Sequence (result.step_starts)
        print(f"✓ Execution sequence: {' -> '.join(result.step_starts)}")

        # 5. Verify Mock Interaction
        mock_notify.assert_called_once()
        print("✓ Notification mock was triggered")

    # ---------------------------------------------------------
    # D. Run 2: Test Branch Skipping
    # ---------------------------------------------------------
    print("\nRun 2: Test Branch Skipping (via Skip)")
    with TestPipe(pipe) as tester:
        tester.mock_startup()
        tester.mock_on_error(return_value=Skip())
        tester.mock("check_connection", side_effect=RuntimeError("Connection Failure"))
        mock_notify = tester.mock("notify_user")
        
        result = await tester.run(UserState(user_id=1), context=UserContext())
        
        print(f"✓ Sequence stops after error: {' -> '.join(result.step_starts)}")
        assert not mock_notify.called
        print("✓ Downstream step was skipped as expected")

    # ---------------------------------------------------------
    # E. Run 3: Test Error Inspection (find_error)
    # ---------------------------------------------------------
    print("\nRun 3: Test Error Inspection")
    with TestPipe(pipe) as tester:
        tester.mock_startup()
        # Mock on_error to raise an exception, making it a terminal failure
        tester.mock_on_error(side_effect=ValueError("Handler Failed"))
        tester.mock("check_connection", side_effect=RuntimeError("Original Failure"))
        
        result = await tester.run(UserState(user_id=2), context=UserContext())
        
        # 6. Find Error in Result (result.find_error)
        err_msg = result.find_error("check_connection")
        print(f"✓ Captured error message: {err_msg}")
        assert "Handler Failed" in str(err_msg)

    # 4. Save Visualization
    save_graph(pipe, Path(__file__).parent / "pipeline.mmd")
    print("\nDemo completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_demo())
