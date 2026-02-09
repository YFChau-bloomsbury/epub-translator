from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, auto
from xml.etree.ElementTree import Element

from ..segment import TextSegment, combine_text_segments
from ..xml import index_of_parent, is_inline_element, iter_with_stack
from .stream_mapper import InlineSegmentMapping


class SubmitKind(Enum):
    REPLACE = auto()
    APPEND_TEXT = auto()
    APPEND_BLOCK = auto()


def submit(element: Element, action: SubmitKind, mappings: list[InlineSegmentMapping]) -> Element:
    submitter = _Submitter(
        element=element,
        action=action,
        mappings=mappings,
    )
    replaced_root = submitter.do()
    if replaced_root is not None:
        return replaced_root

    return element


@dataclass
class _Node:
    raw_element: Element
    items: list[tuple[list[TextSegment], "_Node"]]  # empty for peak, non-empty for platform
    tail_text_segments: list[TextSegment]


class _Submitter:
    def __init__(
        self,
        element: Element,
        action: SubmitKind,
        mappings: list[InlineSegmentMapping],
    ) -> None:
        self._action: SubmitKind = action
        self._nodes: list[_Node] = list(_nest_nodes(mappings))
        self._parents: dict[int, Element] = self._collect_parents(element, mappings)

    def _collect_parents(self, element: Element, mappings: list[InlineSegmentMapping]):
        ids: set[int] = set(id(e) for e, _ in mappings)
        parents_dict: dict[int, Element] = {}
        for parents, child in iter_with_stack(element):
            if parents and id(child) in ids:
                parents_dict[id(child)] = parents[-1]
        return parents_dict

    def do(self):
        replaced_root: Element | None = None

        for node in self._nodes:
            submitted = self._submit_node(node)
            if replaced_root is None:
                replaced_root = submitted

        return replaced_root

    # @return replaced root element, or None if appended to parent
    def _submit_node(self, node: _Node) -> Element | None:
        if node.items or self._action == SubmitKind.APPEND_TEXT:
            return self._submit_by_text(node)
        else:
            return self._submit_by_block(node)

    def _submit_by_block(self, node: _Node) -> Element | None:
        parent = self._parents.get(id(node.raw_element), None)
        if parent is None:
            return node.raw_element

        preserved_elements: list[Element] = []
        if self._action == SubmitKind.REPLACE:
            for child in list(node.raw_element):
                if not is_inline_element(child):
                    child.tail = None
                    preserved_elements.append(child)

        index = index_of_parent(parent, node.raw_element)
        combined = self._combine_text_segments(node.tail_text_segments)

        if combined is not None:
            # In APPEND_BLOCK mode, if it's an inline tag, add a space before the text
            if self._action == SubmitKind.APPEND_BLOCK and is_inline_element(combined) and combined.text:
                combined.text = " " + combined.text
            parent.insert(index + 1, combined)
            index += 1

        for elem in preserved_elements:
            parent.insert(index + 1, elem)
            index += 1

        if combined is not None or preserved_elements:
            if preserved_elements:
                preserved_elements[-1].tail = node.raw_element.tail
            elif combined is not None:
                combined.tail = node.raw_element.tail
            node.raw_element.tail = None

            if self._action == SubmitKind.REPLACE:
                parent.remove(node.raw_element)

        return None

    def _submit_by_text(self, node: _Node) -> Element | None:
        replaced_root: Element | None = None
        child_nodes = dict((id(node), node) for _, node in node.items)
        last_tail_element: Element | None = None
        tail_elements: dict[int, Element] = {}

        for child_element in node.raw_element:
            child_node = child_nodes.get(id(child_element), None)
            if child_node is not None:
                if last_tail_element is not None:
                    tail_elements[id(child_element)] = last_tail_element
                last_tail_element = child_element

        for text_segments, child_node in node.items:
            anchor_element = _find_anchor_in_parent(node.raw_element, child_node.raw_element)
            if anchor_element is None:
                # Defensive programming: Theoretically anchor_element should not be None,
                # because _nest_nodes has already verified the inclusion relationship via _check_includes.
                continue

            tail_element = tail_elements.get(id(anchor_element), None)
            items_preserved_elements: list[Element] = []

            if self._action == SubmitKind.REPLACE:
                end_index = index_of_parent(node.raw_element, anchor_element)
                items_preserved_elements = self._remove_elements_after_tail(
                    node_element=node.raw_element,
                    tail_element=tail_element,
                    end_index=end_index,
                )

            self._append_combined_after_tail(
                node_element=node.raw_element,
                text_segments=text_segments,
                tail_element=tail_element,
                anchor_element=anchor_element,
                append_to_end=False,
            )
            if items_preserved_elements:
                insert_position = index_of_parent(node.raw_element, anchor_element)
                for i, elem in enumerate(items_preserved_elements):
                    node.raw_element.insert(insert_position + i, elem)

        for _, child_node in node.items:
            submitted = self._submit_node(child_node)
            if replaced_root is None:
                replaced_root = submitted

        if node.raw_element:
            last_tail_element = node.raw_element[-1]
        else:
            last_tail_element = None

        tail_preserved_elements: list[Element] = []
        if self._action == SubmitKind.REPLACE:
            tail_preserved_elements = self._remove_elements_after_tail(
                node_element=node.raw_element,
                tail_element=last_tail_element,
                end_index=None,  # None means delete to the end
            )
        self._append_combined_after_tail(
            node_element=node.raw_element,
            text_segments=node.tail_text_segments,
            tail_element=last_tail_element,
            anchor_element=None,
            append_to_end=True,
        )
        if tail_preserved_elements:
            for elem in tail_preserved_elements:
                node.raw_element.append(elem)

        return replaced_root

    def _remove_elements_after_tail(
        self,
        node_element: Element,
        tail_element: Element | None,
        end_index: int | None = None,
    ) -> list[Element]:
        if tail_element is None:
            start_index = 0
            node_element.text = None
        else:
            start_index = index_of_parent(node_element, tail_element) + 1
            tail_element.tail = None

        if end_index is None:
            end_index = len(node_element)

        preserved_elements: list[Element] = []
        for i in range(start_index, end_index):
            elem = node_element[i]
            if not is_inline_element(elem):
                elem.tail = None
                preserved_elements.append(elem)

        for i in range(end_index - 1, start_index - 1, -1):
            node_element.remove(node_element[i])

        return preserved_elements

    def _append_combined_after_tail(
        self,
        node_element: Element,
        text_segments: list[TextSegment],
        tail_element: Element | None,
        anchor_element: Element | None,
        append_to_end: bool,
    ) -> None:
        combined = self._combine_text_segments(text_segments)
        if combined is None:
            return

        if combined.text:
            will_inject_space = self._action == SubmitKind.APPEND_TEXT or (
                is_inline_element(combined) and self._action == SubmitKind.APPEND_BLOCK
            )
            if tail_element is not None:
                tail_element.tail = self._append_text_in_element(
                    origin_text=tail_element.tail,
                    append_text=combined.text,
                    will_inject_space=will_inject_space,
                )
            elif anchor_element is None:
                node_element.text = self._append_text_in_element(
                    origin_text=node_element.text,
                    append_text=combined.text,
                    will_inject_space=will_inject_space,
                )
            else:
                ref_index = index_of_parent(node_element, anchor_element)
                if ref_index > 0:
                    # Add to the tail of the previous element
                    prev_element = node_element[ref_index - 1]
                    prev_element.tail = self._append_text_in_element(
                        origin_text=prev_element.tail,
                        append_text=combined.text,
                        will_inject_space=will_inject_space,
                    )
                else:
                    # ref_element is the first element, add to node_element.text
                    node_element.text = self._append_text_in_element(
                        origin_text=node_element.text,
                        append_text=combined.text,
                        will_inject_space=will_inject_space,
                    )

        if tail_element is not None:
            insert_position = index_of_parent(node_element, tail_element) + 1
        elif append_to_end:
            insert_position = len(node_element)
        elif anchor_element is not None:
            # Use ref_element to locate the insertion position
            # If text was added to the tail of the previous element, insert after the previous element
            ref_index = index_of_parent(node_element, anchor_element)
            if ref_index > 0:
                # Insert after the previous element
                insert_position = ref_index
            else:
                # ref_element is the first element, insert at the beginning
                insert_position = 0
        else:
            insert_position = 0

        for i, child in enumerate(combined):
            node_element.insert(insert_position + i, child)

    def _combine_text_segments(self, text_segments: list[TextSegment]) -> Element | None:
        segments = (t.strip_block_parents() for t in text_segments)
        combined = next(combine_text_segments(segments), None)
        if combined is None:
            return None
        else:
            return combined[0]

    def _append_text_in_element(
        self,
        origin_text: str | None,
        append_text: str,
        will_inject_space: bool,
    ) -> str:
        if origin_text is None:
            return append_text
        elif will_inject_space:
            return origin_text.rstrip() + " " + append_text.lstrip()
        else:
            return origin_text + append_text


def _nest_nodes(mappings: list[InlineSegmentMapping]) -> Generator[_Node, None, None]:
    # Text that needs translation will be nested into two different structures.
    # The most common is the peak structure, for example the following structure, without any sub-structure
    # (inline tags are not considered sub-structures).
    # Can be directly replaced or appended with text.
    # <div>Some text <b>bold text</b> more text.</div>
    #
    # However, there is also a rare platform structure, which is cut internally by other peak/platform structures.
    #   <div>
    #     Some text before.
    #     <!-- The following peak cuts its reading flow -->
    #     <div>Paragraph 1.</div>
    #     Some text in between.
    #   </div>
    # If directly replaced or appended, the reader's flow will be broken, making it read weirdly.
    # Because of this structure, it must be restored to a tree structure, and then the platform structure
    # is handled in a special way.
    #
    # In short, we assume 95% of the reading experience is provided by peak, but to accommodate the remaining platform structures, this step is added.
    stack: list[_Node] = []

    for block_element, text_segments in mappings:
        keep_depth: int = 0
        upwards: bool = False
        for i in range(len(stack) - 1, -1, -1):
            if stack[i].raw_element is block_element:
                keep_depth = i + 1
                upwards = True
                break

        if not upwards:
            for i in range(len(stack) - 1, -1, -1):
                if _check_includes(stack[i].raw_element, block_element):
                    keep_depth = i + 1
                    break

        while len(stack) > keep_depth:
            child_node = _fold_top_of_stack(stack)
            if not upwards and child_node is not None:
                yield child_node

        if upwards:
            stack[keep_depth - 1].tail_text_segments.extend(text_segments)
        else:
            stack.append(
                _Node(
                    raw_element=block_element,
                    items=[],
                    tail_text_segments=list(text_segments),
                )
            )
    while stack:
        child_node = _fold_top_of_stack(stack)
        if child_node is not None:
            yield child_node


def _find_anchor_in_parent(parent: Element, descendant: Element) -> Element | None:
    for child in parent:
        if child is descendant:
            return descendant

    for child in parent:
        if _check_includes(child, descendant):
            return child

    return None


def _fold_top_of_stack(stack: list[_Node]):
    child_node = stack.pop()
    if not stack:
        return child_node
    parent_node = stack[-1]
    parent_node.items.append((parent_node.tail_text_segments, child_node))
    parent_node.tail_text_segments = []
    return None


def _check_includes(parent: Element, child: Element) -> bool:
    for _, checked in iter_with_stack(parent):
        if child is checked:
            return True
    return False
