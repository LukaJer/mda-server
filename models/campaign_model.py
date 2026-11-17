from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base_model import db


class Campaign(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[datetime] = mapped_column(DateTime)
    end: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=True)

    @staticmethod
    def create_from_json(json: dict) -> "Campaign":
        return Campaign(
                start=datetime.fromisoformat(json["start"]),
                end=datetime.fromisoformat(json["end"]),
                name=json["name"],
                author=json["author"],
                description=json["description"]
            )

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "type": self.type,
            "concentration": self.concentration,
            "unit": self.unit
        }

    def __str__(self) -> str:
        return (f"Campaign("
                f"start={self.start}, "
                f"end={self.end}, "
                f"name={self.name}, "
                f"author={self.author}, "
                f"description={self.description})")
