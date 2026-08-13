"""Reference-data identity parity: compare committed fixtures against a database.

Pure logic, deliberately free of Django imports, so the diff can be unit-tested
with `SimpleTestCase` and no database at all.

The question this module answers is narrow and specific: does primary key N mean
the same row in this database as it does in the committed fixture? That is the
invariant `.exactproject` import has always assumed and never verified. See
`djangoexact/docs/guides/offline-db-bootstrap.md`.

Category semantics mirror the existing dump guardrail described in
`docs/guides/fixtures-guide.md`: adding rows is always allowed, removing rows
warns, and reusing a primary key for a different row is the fatal case.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# (pk, fixture identity, database identity)
ChangedRow = Tuple[int, tuple, tuple]


@dataclass(frozen=True)
class IdentityDiff:
    """Outcome of comparing one reference model's fixture rows to its DB rows."""

    model: str = ""
    changed: List[ChangedRow] = field(default_factory=list)
    missing_in_db: List[int] = field(default_factory=list)
    extra_in_db: List[int] = field(default_factory=list)

    @property
    def is_fatal(self) -> bool:
        """Only semantic drift is fatal. Row count differences are warnings."""
        return bool(self.changed)

    @property
    def is_clean(self) -> bool:
        return not (self.changed or self.missing_in_db or self.extra_in_db)

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "changed": [
                {"pk": pk, "fixture": list(fixture), "db": list(db)}
                for pk, fixture, db in self.changed
            ],
            "missing_in_db": list(self.missing_in_db),
            "extra_in_db": list(self.extra_in_db),
            "fatal": self.is_fatal,
        }


def diff_reference_identity(
    fixture_rows: Dict[int, tuple],
    db_rows: Dict[int, tuple],
    model: str = "",
) -> IdentityDiff:
    """Diff two `{pk: identity tuple}` mappings.

    `changed` holds every pk present on both sides whose identity differs. That
    is the semantic-drift case and the only fatal one: it means an exported
    integer pk resolves to a different row here than it did there.

    `missing_in_db` and `extra_in_db` hold pks present on only one side. They are
    reported as warnings.
    """
    fixture_pks = set(fixture_rows)
    db_pks = set(db_rows)

    changed = [
        (pk, fixture_rows[pk], db_rows[pk])
        for pk in sorted(fixture_pks & db_pks)
        if fixture_rows[pk] != db_rows[pk]
    ]

    return IdentityDiff(
        model=model,
        changed=changed,
        missing_in_db=sorted(fixture_pks - db_pks),
        extra_in_db=sorted(db_pks - fixture_pks),
    )
