"""Shared pytest fixtures for MigrationIQ test suite."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from migrationiq.adapters.base import MigrationInfo
from migrationiq.config.settings import MigrationIQSettings

DJANGO_MIGRATION_0001 = textwrap.dedent("""\
    from django.db import migrations, models

    class Migration(migrations.Migration):

        initial = True
        dependencies = []

        operations = [
            migrations.CreateModel(
                name='User',
                fields=[
                    ('id', models.AutoField(primary_key=True)),
                    ('username', models.CharField(max_length=150)),
                ],
            ),
        ]
""")

DJANGO_MIGRATION_0002 = textwrap.dedent("""\
    from django.db import migrations, models

    class Migration(migrations.Migration):

        dependencies = [
            ('myapp', '0001_initial'),
        ]

        operations = [
            migrations.AddField(
                model_name='User',
                name='email',
                field=models.EmailField(null=False),
            ),
        ]
""")

DJANGO_MIGRATION_DROP = textwrap.dedent("""\
    from django.db import migrations

    class Migration(migrations.Migration):

        dependencies = [
            ('myapp', '0002_add_email'),
        ]

        operations = [
            migrations.DeleteModel(name='User'),
            migrations.RemoveField(model_name='Profile', name='bio'),
        ]
""")

DJANGO_MIGRATION_ALTER = textwrap.dedent("""\
    from django.db import migrations, models

    class Migration(migrations.Migration):

        dependencies = [
            ('myapp', '0002_add_email'),
        ]

        operations = [
            migrations.AlterField(
                model_name='User',
                name='email',
                field=models.TextField(),
            ),
        ]
""")

ALEMBIC_REVISION_001 = textwrap.dedent("""\
    \"\"\"create users table\"\"\"
    revision = 'abc123'
    down_revision = None

    from alembic import op
    import sqlalchemy as sa

    def upgrade():
        op.create_table('users',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(50)),
        )

    def downgrade():
        op.drop_table('users')
""")

ALEMBIC_REVISION_002 = textwrap.dedent("""\
    \"\"\"add email column\"\"\"
    revision = 'def456'
    down_revision = 'abc123'

    from alembic import op
    import sqlalchemy as sa

    def upgrade():
        op.add_column('users', sa.Column('email', sa.String(255), nullable=False))

    def downgrade():
        op.drop_column('users', 'email')
""")

ALEMBIC_REVISION_DROP = textwrap.dedent("""\
    \"\"\"drop users table\"\"\"
    revision = 'ghi789'
    down_revision = 'def456'

    from alembic import op

    def upgrade():
        op.drop_table('users')

    def downgrade():
        pass
""")

ALEMBIC_REVISION_ALTER = textwrap.dedent("""\
    \"\"\"change column type\"\"\"
    revision = 'jkl012'
    down_revision = 'def456'

    from alembic import op
    import sqlalchemy as sa

    def upgrade():
        op.alter_column('users', 'name', type_=sa.Text())

    def downgrade():
        op.alter_column('users', 'name', type_=sa.String(50))
""")


@pytest.fixture
def tmp_django_project(tmp_path: Path) -> Path:
    app_dir = tmp_path / "myapp" / "migrations"
    app_dir.mkdir(parents=True)
    (app_dir / "__init__.py").write_text("")
    (app_dir / "0001_initial.py").write_text(DJANGO_MIGRATION_0001)
    (app_dir / "0002_add_email.py").write_text(DJANGO_MIGRATION_0002)
    (tmp_path / "manage.py").write_text("# manage.py stub")
    return tmp_path


@pytest.fixture
def tmp_alembic_project(tmp_path: Path) -> Path:
    versions_dir = tmp_path / "alembic" / "versions"
    versions_dir.mkdir(parents=True)
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    (tmp_path / "alembic" / "env.py").write_text("# env.py stub")
    (versions_dir / "001_create_users.py").write_text(ALEMBIC_REVISION_001)
    (versions_dir / "002_add_email.py").write_text(ALEMBIC_REVISION_002)
    return tmp_path


@pytest.fixture
def default_settings() -> MigrationIQSettings:
    return MigrationIQSettings()


@pytest.fixture
def sample_migration_info() -> MigrationInfo:
    return MigrationInfo(
        migration_id="myapp.0001_initial", app_label="myapp",
        dependencies=[], operations=["CREATE TABLE: User"],
        sql_content=DJANGO_MIGRATION_0001,
    )


@pytest.fixture
def drop_migration_info() -> MigrationInfo:
    return MigrationInfo(
        migration_id="myapp.0003_drop", app_label="myapp",
        dependencies=["myapp.0002_add_email"],
        operations=["DROP TABLE: User", "DROP COLUMN: bio"],
        sql_content=DJANGO_MIGRATION_DROP,
    )


@pytest.fixture
def alter_migration_info() -> MigrationInfo:
    return MigrationInfo(
        migration_id="myapp.0003_alter", app_label="myapp",
        dependencies=["myapp.0002_add_email"],
        operations=["ALTER TABLE ALTER COLUMN: email"],
        sql_content=DJANGO_MIGRATION_ALTER,
    )
