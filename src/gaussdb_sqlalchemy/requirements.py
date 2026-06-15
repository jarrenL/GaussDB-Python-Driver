"""SQLAlchemy dialect test-suite requirements."""

from sqlalchemy.testing.requirements import SuiteRequirements
from sqlalchemy.testing import exclusions


class Requirements(SuiteRequirements):
    @property
    def hstore(self):
        return exclusions.closed()

    @property
    def array_type(self):
        return exclusions.open()
