from dataclasses import dataclass, field
from src.data.reqs import FinalScoreResponse


@dataclass
class ReadingSession:
    doc_id: str
    page_number: int = 1
    pages_total: int = 0
    cursor: int = 0
    words_total: int = 0
    words_correct: int = 0
    words_skipped: int = 0
    words_retried_correct: int = 0
    pages_completed: int = 0
    last_words_on_page: int = 0
    pending_mismatch: bool = field(default=False)

    def reset_page(self, page_number: int, words_on_page: int) -> None:
        self.page_number = page_number
        self.cursor = 0
        self.last_words_on_page = words_on_page
        self.pending_mismatch = False

    def mark_mismatch(self) -> None:
        self.pending_mismatch = True

    def apply_check(self, previous_cursor: int, new_cursor: int, page_complete: bool) -> None:
        gained = max(0, new_cursor - previous_cursor)
        if gained > 0:
            if self.pending_mismatch:
                self.words_retried_correct += 1
                self.pending_mismatch = False
            self.words_total += gained
            self.words_correct += gained
        self.cursor = new_cursor
        if page_complete:
            self.pages_completed += 1

    def skip_current_word(self) -> tuple[int, bool]:
        if not self.pending_mismatch:
            raise ValueError("Nothing to skip")
        self.words_total += 1
        self.words_skipped += 1
        self.cursor += 1
        self.pending_mismatch = False
        page_complete = self.cursor >= self.last_words_on_page
        if page_complete:
            self.pages_completed += 1
        return self.cursor, page_complete

    def to_score(self) -> FinalScoreResponse:
        accuracy = (self.words_correct / self.words_total) if self.words_total else 0.0
        return FinalScoreResponse(
            doc_id=self.doc_id,
            words_total=self.words_total,
            words_correct=self.words_correct,
            words_skipped=self.words_skipped,
            words_retried_correct=self.words_retried_correct,
            pages_completed=self.pages_completed,
            pages_total=self.pages_total,
            accuracy=round(accuracy, 4),
        )
