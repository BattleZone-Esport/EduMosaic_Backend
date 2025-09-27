"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-09-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tables will be handled by Base.metadata.create_all()
    # This is just a placeholder migration
    pass


def downgrade() -> None:
    # Drop tables if needed
    pass