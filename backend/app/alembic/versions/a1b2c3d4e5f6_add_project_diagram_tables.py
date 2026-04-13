"""Add project, diagram, and component tables

Revision ID: a1b2c3d4e5f6
Revises: fe56fa70289e
Create Date: 2026-01-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'project',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.Column('current_prompt', sqlmodel.sql.sqltypes.AutoString(length=4096), nullable=True),
        sa.Column('cloud_context', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('diagram_type', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'promptrevision',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('prompt_text', sqlmodel.sql.sqltypes.AutoString(length=4096), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'diagramversion',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('diagram_json', sa.Text(), nullable=True),
        sa.Column('layout_json', sa.Text(), nullable=True),
        sa.Column('notes_markdown', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'project_id',
            'version_number',
            name='uq_diagramversion_project_id_version_number',
        ),
    )

    op.create_table(
        'diagramnode',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('diagram_version_id', sa.UUID(), nullable=False),
        sa.Column('label', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('node_type', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('x_position', sa.Float(), nullable=False),
        sa.Column('y_position', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['diagram_version_id'], ['diagramversion.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'diagramedge',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('diagram_version_id', sa.UUID(), nullable=False),
        sa.Column('source_node_id', sa.UUID(), nullable=False),
        sa.Column('target_node_id', sa.UUID(), nullable=False),
        sa.Column('label', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['diagram_version_id'], ['diagramversion.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_node_id'], ['diagramnode.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_node_id'], ['diagramnode.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_diagramedge_source_node_id'),
        'diagramedge',
        ['source_node_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_diagramedge_target_node_id'),
        'diagramedge',
        ['target_node_id'],
        unique=False,
    )

    op.create_table(
        'componentitem',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('diagram_version_id', sa.UUID(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('component_type', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.Column('role_summary', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.ForeignKeyConstraint(['diagram_version_id'], ['diagramversion.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('componentitem')
    op.drop_index(op.f('ix_diagramedge_target_node_id'), table_name='diagramedge')
    op.drop_index(op.f('ix_diagramedge_source_node_id'), table_name='diagramedge')
    op.drop_table('diagramedge')
    op.drop_table('diagramnode')
    op.drop_table('diagramversion')
    op.drop_table('promptrevision')
    op.drop_table('project')
