from dataclasses import dataclass
from pydantic import BaseModel, Field
import json
from typing import List


class WordSegment(BaseModel):
    word: str
    start: float = Field(default=0.0)
    end: float

    def to_json_str(self) -> str:
        return json.dumps(self.model_dump())    


def merge_sherpa_subwords(tokens, timestamps, frame_duration=0.08) -> List[WordSegment]:
    words = []
    current_tokens = []
    start_time = None
    
    for token, ts in zip(tokens, timestamps):
        # Clean up any trailing dots or punctuation spaces
        token_clean = token.strip('.')
        if not token_clean:
            continue

        # Check if the subword marks the start of a NEW word (starts with ' ')
        if token_clean.startswith(" "):
            # Save the previous accumulated word
            if current_tokens:
                full_word = "".join(current_tokens)
                words.append(WordSegment(word=full_word, start=start_time, end=last_ts + frame_duration))
                current_tokens = []
            
            # Start a new word (strip the ' ' prefix)
            start_time = ts
            current_tokens.append(token_clean.replace(" ", ""))
        else:
            # Continuation subword -> attach to the active word
            current_tokens.append(token_clean)
            
        last_ts = ts

    # Save the final word
    if current_tokens:
        full_word = "".join(current_tokens)
        words.append(WordSegment(word=full_word, start=start_time, end=last_ts + frame_duration))

    return words
