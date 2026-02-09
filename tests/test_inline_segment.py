import unittest
from xml.etree.ElementTree import fromstring, tostring

from epub_translator.segment.inline_segment import (
    InlineSegment,
    InlineUnexpectedIDError,
    InlineWrongTagCountError,
    search_inline_segments,
)
from epub_translator.segment.text_segment import search_text_segments
from epub_translator.xml import ID_KEY, iter_with_stack


def _get_first_inline_segment(segments):
    """Helper function: Get the first InlineSegment from segments"""
    inline_segments = list(search_inline_segments(segments))
    return inline_segments[0] if inline_segments else None


class TestCollectInlineSegment(unittest.TestCase):
    """Test functionality of collecting inline segments"""

    def test_collect_simple_inline(self):
        """Test collecting simple inline elements"""
        # <p>Hello <em>world</em></p>
        root = fromstring("<p>Hello <em>world</em></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        # Should collect two text segments
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 2)

    def test_collect_nested_inline(self):
        """Test collecting nested inline elements"""
        # <p>A<span>B<em>C</em>D</span>E</p>
        root = fromstring("<p>A<span>B<em>C</em>D</span>E</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 5)
        self.assertEqual([s.text for s in text_segments], ["A", "B", "C", "D", "E"])

    def test_collect_separated_same_tags(self):
        """Test collecting same tags separated by text"""
        # <p>X<em>A</em>Y<em>B</em>Z</p>
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        # Should have 5 children: X, em, Y, em, Z
        self.assertEqual(len(inline_segment.children), 5)


class TestInlineSegmentIDAssignment(unittest.TestCase):
    """Test InlineSegment ID assignment logic"""

    def test_identical_elements_no_id(self):
        """Test that elements with same attributes don't get IDs (identical particles)"""
        # <p>X<em>A</em>Y<em>B</em>Z</p> - Two em tags are identical
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # Check IDs of two em InlineSegments
        em_segments = [c for c in inline_segment.children if isinstance(c, InlineSegment)]
        self.assertEqual(len(em_segments), 2)
        # Identical elements should not have IDs
        self.assertIsNone(em_segments[0].id)
        self.assertIsNone(em_segments[1].id)

    def test_different_tags_no_id(self):
        """Test that different tags don't get IDs"""
        # <p><strong>A</strong><em>B</em></p> - Different tags
        root = fromstring("<p><strong>A</strong><em>B</em></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        inline_children = [c for c in inline_segment.children if isinstance(c, InlineSegment)]
        # Different tags don't need IDs
        for child in inline_children:
            self.assertIsNone(child.id)


class TestCreateElement(unittest.TestCase):
    """Test create_element functionality to create XML elements"""

    def test_create_simple_element(self):
        """Test creating simple elements"""
        root = fromstring("<p>Hello <em>world</em></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        self.assertEqual(element.tag, "p")
        self.assertTrue("Hello" in (element.text or ""))
        children = list(element)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].tag, "em")
        self.assertEqual(children[0].text, "world")

    def test_create_element_no_attributes(self):
        """Test that create_element does not copy attributes (to reduce LLM tokens)"""
        root = fromstring('<p class="text" id="p1">Hello</p>')
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        for _, child_element in iter_with_stack(element):
            if id(child_element) == id(element):
                continue
            # Attributes should not be copied
            self.assertIsNone(child_element.get("class"))
            self.assertIsNone(child_element.get("id"))

    def test_create_nested_structure(self):
        """Test creating nested structures"""
        root = fromstring("<p>A<span>B<em>C</em>D</span>E</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # Verify nested structure
        self.assertEqual(element.tag, "p")
        self.assertTrue("A" in (element.text or ""))

        span = element.find(".//span")
        self.assertIsNotNone(span)
        assert span is not None  # for type checker

        em = span.find(".//em")
        self.assertIsNotNone(em)
        assert em is not None  # for type checker
        self.assertEqual(em.text, "C")


class TestValidate(unittest.TestCase):
    """Test validate functionality"""

    def test_validate_correct_structure(self):
        """Test validating correct structures"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # Create validation element with same structure
        validated = fromstring("<p>trans-X<em>trans-A</em>trans-Y<em>trans-B</em>trans-Z</p>")

        errors = list(inline_segment.validate(validated))
        self.assertEqual(len(errors), 0)

    def test_validate_wrong_tag_count(self):
        """Test validating wrong tag count"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # Missing one em
        validated = fromstring("<p>trans-X<em>trans-A</em>trans-YZ</p>")

        errors = list(inline_segment.validate(validated))
        self.assertGreater(len(errors), 0)
        # Should have InlineWrongTagCountError
        self.assertTrue(any(isinstance(e, InlineWrongTagCountError) for e in errors))

    def test_validate_unexpected_id(self):
        """Test validating unexpected IDs"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # Add ID_KEY that shouldn't exist
        validated = fromstring(f'<p>trans-X<em {ID_KEY}="999">trans-A</em>trans-Y<em>trans-B</em>trans-Z</p>')

        errors = list(inline_segment.validate(validated))
        # Should have InlineUnexpectedIDError
        unexpected_errors = [e for e in errors if isinstance(e, InlineUnexpectedIDError)]
        self.assertGreater(len(unexpected_errors), 0)


class TestAssignAttributes(unittest.TestCase):
    """Test assign_attributes attribute mapping functionality"""

    def test_assign_preserves_original_attributes(self):
        """Test preserving original element attributes"""
        root = fromstring('<p class="original">Hello <em>world</em></p>')
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        # Template element has different attributes
        template = fromstring('<p class="translated">trans-Hello <em>trans-world</em></p>')

        result = inline_segment.assign_attributes(template)

        # Original attributes should be preserved
        self.assertEqual(result.get("class"), "original")
        self.assertEqual(result.tag, "p")


class TestMatchChildren(unittest.TestCase):
    """Test _match_children child element matching functionality"""

    def test_match_by_natural_order(self):
        """Test matching by natural order (no ID)"""
        root = fromstring("<p>X<em>A</em>Y<em>B</em>Z</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        # No ID, match in order
        template = fromstring("<p>trans-X<em>trans-A</em>trans-Y<em>trans-B</em>trans-Z</p>")

        # pylint: disable=protected-access
        matches = list(inline_segment._match_children(template))  # type: ignore[attr-defined]

        self.assertEqual(len(matches), 2)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases"""

    def test_empty_inline_segment(self):
        """Test empty inline structure"""
        root = fromstring("<p></p>")
        segments = list(search_text_segments(root))

        # Empty elements have no segments
        self.assertEqual(len(segments), 0)

    def test_single_text_segment(self):
        """Test single text segment"""
        root = fromstring("<p>Hello</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        self.assertIsNotNone(inline_segment)
        assert inline_segment is not None  # for type checker
        text_segments = list(inline_segment)
        self.assertEqual(len(text_segments), 1)

    def test_deeply_nested_structure(self):
        """Test deeply nested structure"""
        root = fromstring("<p><span><em><strong>Deep</strong></em></span></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # Verify deep nesting
        strong = element.find(".//strong")
        self.assertIsNotNone(strong)
        assert strong is not None  # for type checker
        self.assertEqual(strong.text, "Deep")

    def test_chinese_text_handling(self):
        """Test Chinese text handling"""
        root = fromstring("<p>This is <em>Chinese</em> text</p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        result_str = tostring(element, encoding="unicode")
        self.assertIn("This is", result_str)
        self.assertIn("Chinese", result_str)
        self.assertIn("text", result_str)

    def test_multiple_different_tags(self):
        """Test mixing multiple different tags - adjacent different tags will be merged"""
        root = fromstring("<p><em>A</em><strong>B</strong><span>C</span></p>")
        segments = list(search_text_segments(root))

        inline_segment = _get_first_inline_segment(segments)

        assert inline_segment is not None  # for type checker
        element = inline_segment.create_element()

        # Verify element is created
        self.assertGreater(len(list(element)), 0)
        # Verify it contains at least one tag
        result_str = tostring(element, encoding="unicode")
        self.assertIn("<em>", result_str)

    def test_parent_with_text_and_child_blocks_not_merged(self):
        root = fromstring("<body>The main text begins:<p>Paragraph text</p><div>Division text</div></body>")
        segments = list(search_text_segments(root))

        # Should have 3 text segments:
        # 1. "The main text begins:" in body
        # 2. "Paragraph text" in p
        # 3. "Division text" in div
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].block_parent.tag, "body")
        self.assertEqual(segments[1].block_parent.tag, "p")
        self.assertEqual(segments[2].block_parent.tag, "div")

        # Get all inline segments
        inline_segments = list(search_inline_segments(segments))

        # Should have 3 independent inline segments
        self.assertEqual(len(inline_segments), 3)

        # Verify the first inline segment (text in body)
        inline1 = inline_segments[0]
        body_texts = list(inline1)
        self.assertEqual(len(body_texts), 1)
        self.assertEqual(body_texts[0].text, "The main text begins:")
        self.assertEqual(inline1.parent.tag, "body")

        # Verify the second inline segment (text in p)
        inline2 = inline_segments[1]
        p_texts = list(inline2)
        self.assertEqual(len(p_texts), 1)
        self.assertEqual(p_texts[0].text, "Paragraph text")
        self.assertEqual(inline2.parent.tag, "p")

        # Verify the third inline segment (text in div)
        inline3 = inline_segments[2]
        div_texts = list(inline3)
        self.assertEqual(len(div_texts), 1)
        self.assertEqual(div_texts[0].text, "Division text")
        self.assertEqual(inline3.parent.tag, "div")


if __name__ == "__main__":
    unittest.main()
