from typing import Callable
import time


class Timer:
    def __init__(self, operation_name: str):
        self.operation_name = operation_name

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.end_time = time.time()
        print(f"{self.operation_name} took {self.end_time - self.start_time} seconds")