from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from src.domain.models import DigestDashboard, DigestPublication, DigestPublishReport, DigestRun, NewsItem, TextPublishResult


class Base(DeclarativeBase):
    pass


class DigestEntryRow(Base):
    __tablename__ = "digest_entries"
    source_url: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(120))
    source_published_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    telegram_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DigestRunRow(Base):
    __tablename__ = "digest_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trigger: Mapped[str] = mapped_column(String(20))
    candidates: Mapped[int] = mapped_column(Integer)
    attempted: Mapped[int] = mapped_column(Integer)
    published: Mapped[int] = mapped_column(Integer)
    failed: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _source_name(url: str) -> str:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    return {"datacenterdynamics.com": "Data Center Dynamics", "blog.equinix.com": "Equinix Blog"}.get(host, host)


class SqlAlchemyDigestRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session = sessionmaker(self._engine, expire_on_commit=False)

    def dispose(self) -> None:
        self._engine.dispose()

    def reserve_new(self, items: tuple[NewsItem, ...]) -> tuple[NewsItem, ...]:
        now = datetime.now(UTC)
        reserved: list[NewsItem] = []
        with self._session() as session:
            for item in items:
                if session.get(DigestEntryRow, item.url) is not None:
                    continue
                try:
                    # A savepoint keeps already reserved URLs intact if another
                    # process inserted the same article between our check and flush.
                    with session.begin_nested():
                        session.add(
                            DigestEntryRow(
                                source_url=item.url,
                                title=item.title,
                                source_name=_source_name(item.url),
                                source_published_at=item.published_at,
                                status="pending",
                                telegram_message_id=None,
                                created_at=now,
                                published_at=None,
                            )
                        )
                        session.flush()
                    reserved.append(item)
                except IntegrityError:
                    continue
            session.commit()
        return tuple(reserved)

    def mark_result(self, item: NewsItem, result: TextPublishResult) -> None:
        with self._session() as session:
            row = session.get(DigestEntryRow, item.url)
            if row is None:
                return
            row.status = "published" if result.success else "failed"
            row.telegram_message_id = result.external_id
            row.published_at = datetime.now(UTC) if result.success else None
            session.commit()

    def remember_without_publishing(self, items: tuple[NewsItem, ...]) -> None:
        for item in self.reserve_new(items):
            with self._session() as session:
                row = session.get(DigestEntryRow, item.url)
                if row:
                    row.status = "baseline"
                session.commit()

    def record_run(self, report: DigestPublishReport, trigger: str) -> None:
        now = datetime.now(UTC)
        with self._session() as session:
            session.add(
                DigestRunRow(
                    trigger=trigger,
                    candidates=report.candidates,
                    attempted=report.attempted,
                    published=report.published,
                    failed=report.failed,
                    started_at=now,
                    finished_at=now,
                )
            )
            session.commit()

    def has_runs(self) -> bool:
        with self._session() as session:
            return (session.scalar(select(func.count()).select_from(DigestRunRow)) or 0) > 0

    def dashboard(self, limit: int = 20) -> DigestDashboard:
        with self._session() as session:
            rows = session.scalars(select(DigestEntryRow).order_by(DigestEntryRow.created_at.desc()).limit(limit)).all()
            published = session.scalar(select(func.count()).select_from(DigestEntryRow).where(DigestEntryRow.status == "published")) or 0
            today = datetime.now(UTC).date()
            published_today = (
                session.scalar(
                    select(func.count())
                    .select_from(DigestEntryRow)
                    .where(
                        DigestEntryRow.status == "published",
                        func.date(DigestEntryRow.published_at) == today,
                    )
                )
                or 0
            )
            run = session.scalars(select(DigestRunRow).order_by(DigestRunRow.finished_at.desc()).limit(1)).first()
            last_run = (
                DigestRun(
                    run.trigger,
                    run.candidates,
                    run.attempted,
                    run.published,
                    run.failed,
                    run.started_at,
                    run.finished_at,
                )
                if run
                else None
            )
            records = tuple(
                DigestPublication(
                    row.title,
                    row.source_name,
                    row.source_url,
                    row.source_published_at,
                    row.status,
                    row.telegram_message_id,
                    row.created_at,
                    row.published_at,
                )
                for row in rows
            )
            return DigestDashboard(published, published_today, last_run, records)
