"""Rozszerzenia Flaska trzymane osobno, zeby uniknac cyklicznych importow."""
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Wspolna baza deklaratywna dla SQLAlchemy 2.x."""


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
login_manager = LoginManager()
