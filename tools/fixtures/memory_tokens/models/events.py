"""Entidades del planificador local, sin efectos de almacenamiento."""
from dataclasses import dataclass

@dataclass
class Task:
    identifier: str
    title: str
    completed: bool = False
    priority: int = 0

    def __post_init__(self):
        self.title = self.title.strip()
        if not self.identifier or not self.title:
            raise ValueError("Missing task fields")
        if len(self.title) > 240 or not 0 <= self.priority <= 3:
            raise ValueError("Invalid task fields")

    def to_dict(self):
        return {"id": self.identifier, "title": self.title,
                "completed": self.completed, "priority": self.priority}

    def rename(self, title):
        title = title.strip()
        if not title or len(title) > 240:
            raise ValueError("Invalid title")
        self.title = title
