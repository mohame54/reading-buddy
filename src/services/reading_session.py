from dataclasses import dataclass
from typing import Optional

from src.data.reqs import FinalScoreResponse


@dataclass
class ReadingSession:
    doc_id: str
    page_number: int = 1
    pages_total: int = 0
    cursor: int = 0
    words_total: int = 0
    words_correct: int = 0
    pages_completed: int = 0
    last_words_on_page: int = 0

    def reset_page(self, page_number: int, words_on_page: int) -> None:
        self.page_number = page_number
        self.cursor = 0
        self.last_words_on_page = words_on_page

    def apply_check(self, previous_cursor: int, new_cursor: int, page_complete: bool) -> None:
        gained = max(0, new_cursor - previous_cursor)
        self.words_total += gained
        self.words_correct += gained
        self.cursor = new_cursor
        if page_complete:
            self.pages_completed += 1

    def to_score(self) -> FinalScoreResponse:
        accuracy = (self.words_correct / self.words_total) if self.words_total else 0.0
        return FinalScoreResponse(
            doc_id=self.doc_id,
            words_total=self.words_total,
            words_correct=self.words_correct,
            pages_completed=self.pages_completed,
            pages_total=self.pages_total,
            accuracy=round(accuracy, 4),
        )
