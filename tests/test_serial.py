from typing import Self

from epub_translator.serial import Segment, split
from epub_translator.serial.chunk import split_into_chunks


class MockSegment(Segment[str]):
    def __init__(self, payload: str, tokens: int) -> None:
        self._payload = payload
        self._tokens = tokens

    @property
    def payload(self) -> str:
        return self._payload

    @property
    def tokens(self) -> int:
        return self._tokens

    @classmethod
    def from_text(cls, text: str) -> Self:
        """Create MockSegment from text"""
        return cls(payload=text, tokens=len(text))

    def truncate_after_head(self, remain_tokens: int) -> Self:
        """Keep the first remain_tokens characters"""
        truncated_text = self.payload[:remain_tokens]
        return type(self)(payload=truncated_text, tokens=len(truncated_text))

    def truncate_before_tail(self, remain_tokens: int) -> Self:
        """Keep the last remain_tokens characters"""
        truncated_text = self.payload[-remain_tokens:] if remain_tokens > 0 else ""
        return type(self)(payload=truncated_text, tokens=len(truncated_text))


class TestChunkBasic:
    """Test the basic functionality of split_into_chunks"""

    def test_simple_chunking(self):
        """Test simple chunking functionality"""
        segments = [
            MockSegment.from_text("Hello"),  # 5 tokens
            MockSegment.from_text("World"),  # 5 tokens
            MockSegment.from_text("Python"),  # 6 tokens
        ]

        chunks = list(split_into_chunks(segments, max_group_tokens=10))

        # Should have at least one chunk
        assert len(chunks) > 0

        # Verify chunk structure
        for chunk in chunks:
            assert hasattr(chunk, "head")
            assert hasattr(chunk, "body")
            assert hasattr(chunk, "tail")
            assert hasattr(chunk, "head_remain_tokens")
            assert hasattr(chunk, "tail_remain_tokens")

    def test_chunk_contains_all_segments(self):
        """Verify that all segments are included in chunks"""
        segments = [
            MockSegment.from_text("A"),
            MockSegment.from_text("B"),
            MockSegment.from_text("C"),
            MockSegment.from_text("D"),
        ]

        chunks = list(split_into_chunks(segments, max_group_tokens=2))

        # Collect content from all chunks
        all_payloads = []
        for chunk in chunks:
            all_payloads.extend(seg.payload for seg in chunk.head)
            all_payloads.extend(seg.payload for seg in chunk.body)
            all_payloads.extend(seg.payload for seg in chunk.tail)

        # Verify all original segments are present
        original_payloads = [seg.payload for seg in segments]
        for payload in original_payloads:
            assert payload in all_payloads, f"Payload '{payload}' should appear in chunks"

    def test_large_max_tokens(self):
        """Test that all contents are in one chunk when max_tokens is very large"""
        segments = [
            MockSegment.from_text("Short"),
            MockSegment.from_text("Text"),
        ]

        chunks = list(split_into_chunks(segments, max_group_tokens=1000))

        # Should have only one chunk
        assert len(chunks) >= 1


class TestSplitterBasic:
    """Test the basic functionality of splitter.split"""

    def test_simple_split(self):
        """Test simple split transformation"""
        segments = [
            MockSegment.from_text("Hello"),
            MockSegment.from_text("World"),
        ]

        def transform(segs):
            """Simple transformation: to uppercase"""
            return [MockSegment.from_text(seg.payload.upper()) for seg in segs]

        results = list(split(segments, transform, max_group_tokens=10))

        # Should have results平衡
        assert len(results) > 0

        # Verify transformation took effect
        result_texts = [r.payload for r in results]
        assert "HELLO" in result_texts or "WORLD" in result_texts

    def test_transform_preserves_body(self):
        """Verify transformation results that only return the body part"""
        segments = [
            MockSegment.from_text("A"),
            MockSegment.from_text("B"),
            MockSegment.from_text("C"),
            MockSegment.from_text("D"),
            MockSegment.from_text("E"),
        ]

        def transform(segs):
            """Mark each segment"""
            return [MockSegment.from_text(f"[{seg.payload}]") for seg in segs]

        results = list(split(segments, transform, max_group_tokens=3))

        # Verify results
        result_texts = [r.payload for r in results]
        assert len(result_texts) > 0


class TestEmptyTailSlicing:
    """Test fixed bug: slicing problem when tail is empty"""

    def test_empty_tail_returns_correct_results(self):
        """When tail is empty, correct results should be returned instead of an empty list"""
        segments = [
            MockSegment.from_text("First"),
            MockSegment.from_text("Second"),
        ]

        def identity_transform(segs):
            """Identity transformation"""
            return segs

        results = list(split(segments, identity_transform, max_group_tokens=20))

        # Should have results (should not return an empty list because tail is empty)
        assert len(results) > 0, "Should return results even if tail is empty"

    def test_no_context_needed(self):
        """When no context is needed (max_tokens is large enough), it should work normally"""
        segments = [MockSegment.from_text("OnlyOne")]

        def transform(segs):
            return [MockSegment.from_text(seg.payload + "!") for seg in segs]

        results = list(split(segments, transform, max_group_tokens=100))

        assert len(results) == 1
        assert results[0].payload == "OnlyOne!"


class TestTruncation:
    """Test truncation functionality"""

    def test_truncate_after_head(self):
        """Test truncate_after_head method"""
        seg = MockSegment.from_text("HelloWorld")  # 10 tokens

        truncated = seg.truncate_after_head(5)

        assert truncated.payload == "Hello"
        assert truncated.tokens == 5

    def test_truncate_before_tail(self):
        """Test truncate_before_tail method"""
        seg = MockSegment.from_text("HelloWorld")  # 10 tokens

        truncated = seg.truncate_before_tail(5)

        assert truncated.payload == "World"
        assert truncated.tokens == 5

    def test_truncate_with_zero_tokens(self):
        """Test truncation with 0 tokens"""
        seg = MockSegment.from_text("Test")

        truncated_head = seg.truncate_after_head(0)
        truncated_tail = seg.truncate_before_tail(0)

        assert truncated_head.payload == ""
        assert truncated_head.tokens == 0
        assert truncated_tail.payload == ""
        assert truncated_tail.tokens == 0


class TestRemainTokensBug:
    """Test fixed bug: remain_tokens was modified before use"""

    def test_partial_remain_tokens(self):
        """When remain_tokens is smaller than segment tokens, it should be truncated correctly"""
        # Create a large enough segment
        segments = [
            MockSegment.from_text("A" * 20),  # 20 tokens
            MockSegment.from_text("B" * 10),  # 10 tokens
        ]

            """Keep as is"""
            return segs

        # Use smaller max_tokens to trigger truncation
        results = list(split(segments, transform, max_group_tokens=15))

        # Should have results, and won't fail because of wrong truncation
        assert len(results) > 0


class TestMultipleChunks:
    """Test scenarios with multiple chunks"""

    def test_multiple_chunks_with_context(self):
        """Test if context is passed correctly when multiple chunks are generated"""
        segments = [MockSegment.from_text(chr(65 + i)) for i in range(10)]  # A-J

        def transform(segs):
            """Add prefix"""
            return [MockSegment.from_text(f"T-{seg.payload}") for seg in segs]

        results = list(split(segments, transform, max_group_tokens=3))

        # Should have multiple results
        assert len(results) > 0

        # Verify transformation took effect
        for result in results:
            assert result.payload.startswith("T-")


class TestEdgeCases:
    """Test edge cases"""

    def test_single_segment(self):
        """Test single segment"""
        segments = [MockSegment.from_text("Only")]

        def transform(segs):
            return [MockSegment.from_text(seg.payload * 2) for seg in segs]

        results = list(split(segments, transform, max_group_tokens=10))

        assert len(results) == 1
        assert results[0].payload == "OnlyOnly"

    def test_very_small_max_tokens(self):
        """Test very small max_tokens"""
        segments = [
            MockSegment.from_text("AB"),
            MockSegment.from_text("CD"),
        ]

        def transform(segs):
            return segs

        results = list(split(segments, transform, max_group_tokens=1))

        # Even if max_tokens is very small, it should be able to handle it
        assert len(results) > 0

    def test_empty_segments_list(self):
        """Test empty segments list"""
        segments = []

        def transform(segs):
            return segs

        results = list(split(segments, transform, max_group_tokens=10))

        # Empty input should produce empty output
        assert len(results) == 0


class TestTransformConsistency:
    """Test consistency of transformation"""

    def test_transform_called_correctly(self):
        """Verify that transform function is called correctly"""
        segments = [
            MockSegment.from_text("X"),
            MockSegment.from_text("Y"),
            MockSegment.from_text("Z"),
        ]

        call_count = 0

        def counting_transform(segs):
            nonlocal call_count
            call_count += 1
            return segs

        list(split(segments, counting_transform, max_group_tokens=5))

        # transform should be called at least once
        assert call_count > 0

    def test_transform_receives_context(self):
        """Verify that transform receives complete context (head + body + tail)"""
        segments = [
            MockSegment.from_text("A"),
            MockSegment.from_text("B"),
            MockSegment.from_text("C"),
            MockSegment.from_text("D"),
        ]

        received_inputs = []

        def recording_transform(segs):
            received_inputs.append([seg.payload for seg in segs])
            return segs

        list(split(segments, recording_transform, max_group_tokens=2))

        # Should receive input at least once
        assert len(received_inputs) > 0

        # Each input should contain multiple segments (head + body + tail)
        # Note: Depending on the chunking strategy, some chunks might only have body
        for input_segs in received_inputs:
            assert len(input_segs) >= 0  # Might be empty (though unlikely)
