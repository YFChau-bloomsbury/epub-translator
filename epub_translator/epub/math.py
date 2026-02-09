from xml.etree.ElementTree import Element

# Operator mapping table
_OPERATOR_MAP = {
    "→": r"\rightarrow",
    "←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "×": r"\times",
    "·": r"\cdot",
    "÷": r"\div",
    "±": r"\pm",
    "∓": r"\mp",
    "≤": r"\leq",
    "≥": r"\geq",
    "≠": r"\neq",
    "≈": r"\approx",
    "∞": r"\infty",
    "∫": r"\int",
    "∑": r"\sum",
    "∏": r"\prod",
    "√": r"\sqrt",
    "∂": r"\partial",
    "∇": r"\nabla",
    "∈": r"\in",
    "∉": r"\notin",
    "⊂": r"\subset",
    "⊃": r"\supset",
    "⊆": r"\subseteq",
    "⊇": r"\supseteq",
    "∪": r"\cup",
    "∩": r"\cap",
    "∅": r"\emptyset",
    "∀": r"\forall",
    "∃": r"\exists",
    "¬": r"\neg",
    "∧": r"\land",
    "∨": r"\lor",
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ε": r"\epsilon",
    "θ": r"\theta",
    "λ": r"\lambda",
    "μ": r"\mu",
    "π": r"\pi",
    "σ": r"\sigma",
    "φ": r"\phi",
    "ω": r"\omega",
    "Δ": r"\Delta",
    "Σ": r"\Sigma",
    "Ω": r"\Omega",
}


def xml_to_latex(element: Element) -> str:
    tag = element.tag

    # Convert based on element type
    if tag == "math":
        # Root element, only process children
        return "".join(xml_to_latex(child) for child in element)

    elif tag == "mrow":
        # Group element, recursively process all children
        return "".join(xml_to_latex(child) for child in element)

    elif tag == "mi":
        # Identifier (variable name)
        text = element.text or ""
        # Use \mathrm for multi-character identifiers
        if len(text) > 1:
            return f"\\mathrm{{{text}}}"
        return text

    elif tag == "mn":
        # Number
        return element.text or ""

    elif tag == "mo":
        # Operator
        text = (element.text or "").strip()
        return _OPERATOR_MAP.get(text, text)

    elif tag == "mfrac":
        # Fraction
        children = list(element)
        if len(children) >= 2:
            numerator = xml_to_latex(children[0])
            denominator = xml_to_latex(children[1])
            return f"\\frac{{{numerator}}}{{{denominator}}}"
        return ""

    elif tag == "msub":
        # Subscript
        children = list(element)
        if len(children) >= 2:
            base = xml_to_latex(children[0])
            subscript = xml_to_latex(children[1])
            return f"{base}_{{{subscript}}}"
        return ""

    elif tag == "msup":
        # Superscript
        children = list(element)
        if len(children) >= 2:
            base = xml_to_latex(children[0])
            superscript = xml_to_latex(children[1])
            return f"{base}^{{{superscript}}}"
        return ""

    elif tag == "msubsup":
        # Both subscript and superscript
        children = list(element)
        if len(children) >= 3:
            base = xml_to_latex(children[0])
            subscript = xml_to_latex(children[1])
            superscript = xml_to_latex(children[2])
            return f"{base}_{{{subscript}}}^{{{superscript}}}"
        return ""

    elif tag == "msqrt":
        # Square root
        content = "".join(xml_to_latex(child) for child in element)
        return f"\\sqrt{{{content}}}"

    elif tag == "mroot":
        # n-th root
        children = list(element)
        if len(children) >= 2:
            base = xml_to_latex(children[0])
            index = xml_to_latex(children[1])
            return f"\\sqrt[{index}]{{{base}}}"
        return ""

    elif tag == "munder":
        # Under-script symbol
        children = list(element)
        if len(children) >= 2:
            base = xml_to_latex(children[0])
            under = xml_to_latex(children[1])
            return f"\\underset{{{under}}}{{{base}}}"
        return ""

    elif tag == "mover":
        # Over-script symbol
        children = list(element)
        if len(children) >= 2:
            base = xml_to_latex(children[0])
            over = xml_to_latex(children[1])
            return f"\\overset{{{over}}}{{{base}}}"
        return ""

    elif tag == "munderover":
        # Under-over-script symbol
        children = list(element)
        if len(children) >= 3:
            base = xml_to_latex(children[0])
            under = xml_to_latex(children[1])
            over = xml_to_latex(children[2])
            # Special handling for sum, integral, etc.
            base_str = base.strip()
            if base_str in (r"\sum", r"\int", r"\prod"):
                return f"{base}_{{{under}}}^{{{over}}}"
            return f"\\overset{{{over}}}{{\\underset{{{under}}}{{{base}}}}}"
        return ""

    elif tag == "mtext":
        # Text
        text = element.text or ""
        return f"\\text{{{text}}}"

    elif tag == "mspace":
        # Space
        return r"\,"

    elif tag == "mtable":
        # Table/Matrix
        rows = [xml_to_latex(child) for child in element if child.tag.endswith("mtr")]
        return f"\\begin{{array}}{{{rows[0].count('&') + 1}}}\n" + "\\\\\n".join(rows) + "\n\\end{array}"

    elif tag == "mtr":
        # Table row
        cells = [xml_to_latex(child) for child in element if child.tag.endswith("mtd")]
        return " & ".join(cells)

    elif tag == "mtd":
        # Table cell
        return "".join(xml_to_latex(child) for child in element)

    else:
        # Unknown element, recursively process children
        return "".join(xml_to_latex(child) for child in element)
