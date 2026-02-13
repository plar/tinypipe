"""Unit tests for validate_observer()."""

from typing import Any

import pytest

from justpipe.observability import Observer, validate_observer


class TestValidateObserver:
    def test_base_class_observer_passes(self) -> None:
        """Observer base class satisfies the protocol."""
        validate_observer(Observer())

    def test_custom_valid_observer_passes(self) -> None:
        """Custom class with all required async methods passes."""

        class MyObserver:
            async def on_pipeline_start(
                self, state: Any, context: Any, meta: Any
            ) -> None:
                pass

            async def on_event(
                self, state: Any, context: Any, meta: Any, event: Any
            ) -> None:
                pass

            async def on_pipeline_end(
                self, state: Any, context: Any, meta: Any, duration_s: Any
            ) -> None:
                pass

            async def on_pipeline_error(
                self, state: Any, context: Any, meta: Any, error: Any
            ) -> None:
                pass

        validate_observer(MyObserver())

    def test_extra_methods_ignored(self) -> None:
        """Observer with extra methods still passes validation."""

        class ExtendedObserver(Observer):
            async def custom_hook(self) -> None:
                pass

            def sync_helper(self) -> int:
                return 42

        validate_observer(ExtendedObserver())

    def test_missing_single_method_raises(self) -> None:
        """Observer missing one required method raises TypeError."""

        class Incomplete:
            async def on_pipeline_start(
                self, state: Any, context: Any, meta: Any
            ) -> None:
                pass

            async def on_event(
                self, state: Any, context: Any, meta: Any, event: Any
            ) -> None:
                pass

            async def on_pipeline_end(
                self, state: Any, context: Any, meta: Any, duration_s: Any
            ) -> None:
                pass

            # Missing on_pipeline_error

        with pytest.raises(TypeError, match="on_pipeline_error"):
            validate_observer(Incomplete())

    def test_missing_all_methods_raises(self) -> None:
        """Plain object with no observer methods raises TypeError."""

        class Empty:
            pass

        with pytest.raises(TypeError, match="missing required hooks"):
            validate_observer(Empty())

    def test_sync_method_raises(self) -> None:
        """Observer with a sync method instead of async raises TypeError."""

        class SyncObserver:
            async def on_pipeline_start(
                self, state: Any, context: Any, meta: Any
            ) -> None:
                pass

            async def on_event(
                self, state: Any, context: Any, meta: Any, event: Any
            ) -> None:
                pass

            async def on_pipeline_end(
                self, state: Any, context: Any, meta: Any, duration_s: Any
            ) -> None:
                pass

            def on_pipeline_error(
                self, state: Any, context: Any, meta: Any, error: Any
            ) -> None:  # sync!
                pass

        with pytest.raises(TypeError, match="async def"):
            validate_observer(SyncObserver())

    def test_partial_async_raises_for_sync_method(self) -> None:
        """Observer where only some methods are async raises for the sync one."""

        class PartialAsync:
            async def on_pipeline_start(
                self, state: Any, context: Any, meta: Any
            ) -> None:
                pass

            def on_event(
                self, state: Any, context: Any, meta: Any, event: Any
            ) -> None:  # sync!
                pass

            async def on_pipeline_end(
                self, state: Any, context: Any, meta: Any, duration_s: Any
            ) -> None:
                pass

            async def on_pipeline_error(
                self, state: Any, context: Any, meta: Any, error: Any
            ) -> None:
                pass

        with pytest.raises(TypeError, match="on_event.*async def"):
            validate_observer(PartialAsync())

    def test_non_callable_attribute_raises(self) -> None:
        """Observer with a non-callable attribute for a required method raises."""

        class BadAttr:
            on_pipeline_start = "not a method"
            on_event = 42
            on_pipeline_end = None
            on_pipeline_error = True

        with pytest.raises(TypeError, match="missing required hooks"):
            validate_observer(BadAttr())
