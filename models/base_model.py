from abc import abstractmethod

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):

    @staticmethod
    @abstractmethod
    def create_from_json(json: dict) -> "Base":
        ...

    @abstractmethod
    def serialize(self) -> dict:
        ...


db = SQLAlchemy(model_class=Base)
