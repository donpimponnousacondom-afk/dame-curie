import unicodedata
from dataclasses import dataclass


def cell_width(char: str, column: int) -> int:
    if char == "\t":
        width = 8 - column % 8
    elif unicodedata.combining(char):
        width = 0
    else:
        width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def row_spans(text: str, width: int) -> list[tuple[int, int]]:
    rows = []
    start = column = 0
    for index, char in enumerate(text):
        if char == "\n":
            rows.append((start, index + 1))
            start, column = index + 1, 0
        else:
            size = cell_width(char, column)
            if column + size > width and index > start:
                rows.append((start, index))
                start, column = index, 0
                size = cell_width(char, column)
            column += size
    if start < len(text) or not rows:
        rows.append((start, len(text)))
    return rows


@dataclass(frozen=True)
class Page:
    text: str
    rows: tuple[str, ...]
    number: int
    count: int


def page_text(text: str, width: int, height: int, number: int) -> Page:
    spans = row_spans(text, max(1, width))
    height = max(1, height)
    count = (len(spans) + height - 1) // height
    number = max(0, min(count - 1, number))
    selected = spans[number * height:(number + 1) * height]
    return Page(text[selected[0][0]:selected[-1][1]],
                tuple(text[start:end].removesuffix("\n") for start, end in selected), number, count)


def fit(text: str, width: int) -> str:
    width = max(1, width)
    column = end = 0
    for index, char in enumerate(text):
        if char == "\n":
            break
        size = cell_width(char, column)
        if column + size > width and index:
            break
        column += size
        end = index + 1
    return text[:end]
