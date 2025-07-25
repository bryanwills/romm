from collections.abc import Sequence

from decorators.database import begin_session
from models.user import Role, User
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .base_handler import DBBaseHandler


class DBUsersHandler(DBBaseHandler):
    @begin_session
    def add_user(self, user: User, session: Session = None) -> User:
        return session.merge(user)

    @begin_session
    def get_user_by_username(
        self, username: str, session: Session = None
    ) -> User | None:
        return session.scalar(
            select(User).filter(func.lower(User.username) == username.lower()).limit(1)
        )

    @begin_session
    def get_user_by_email(self, email: str, session: Session = None) -> User | None:
        return session.scalar(
            select(User).filter(func.lower(User.email) == email.lower()).limit(1)
        )

    @begin_session
    def get_user(self, id: int, session: Session = None) -> User | None:
        return session.get(User, id)

    @begin_session
    def update_user(self, id: int, data: dict, session: Session = None) -> User:
        session.execute(
            update(User)
            .where(User.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )
        return session.query(User).filter_by(id=id).one()

    @begin_session
    def get_users(self, session: Session = None) -> Sequence[User]:
        return session.scalars(select(User)).all()

    @begin_session
    def delete_user(self, id: int, session: Session = None):
        return session.execute(
            delete(User)
            .where(User.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_admin_users(self, session: Session = None) -> Sequence[User]:
        return session.scalars(select(User).filter_by(role=Role.ADMIN)).all()
