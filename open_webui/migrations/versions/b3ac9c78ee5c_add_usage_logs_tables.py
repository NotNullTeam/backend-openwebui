"""Add usage logs tables

Revision ID: b3ac9c78ee5c
Revises: b1c2d3e4f5a6
Create Date: 2025-08-22 21:11:51.723942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'b3ac9c78ee5c'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建使用日志表
    op.create_table('usage_logs',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.String(length=255), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('idx_usage_user_action', 'usage_logs', ['user_id', 'action_type'], unique=False)
    op.create_index('idx_usage_resource', 'usage_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('idx_usage_created', 'usage_logs', ['created_at'], unique=False)
    
    # 创建知识库使用日志表
    op.create_table('knowledge_usage_logs',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('knowledge_id', sa.String(length=255), nullable=False),
        sa.Column('case_id', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('chunk_id', sa.String(length=255), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('distance', sa.Float(), nullable=True),
        sa.Column('was_helpful', sa.Boolean(), nullable=True),
        sa.Column('user_rating', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('idx_knowledge_usage_knowledge', 'knowledge_usage_logs', ['knowledge_id'], unique=False)
    op.create_index('idx_knowledge_usage_user', 'knowledge_usage_logs', ['user_id'], unique=False)
    op.create_index('idx_knowledge_usage_created', 'knowledge_usage_logs', ['created_at'], unique=False)
    
    # 创建搜索日志表
    op.create_table('search_logs',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('search_type', sa.String(length=50), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('result_count', sa.Integer(), nullable=True),
        sa.Column('clicked_results', sa.JSON(), nullable=True),
        sa.Column('selected_result_id', sa.String(length=255), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('idx_search_user', 'search_logs', ['user_id'], unique=False)
    op.create_index('idx_search_created', 'search_logs', ['created_at'], unique=False)
    op.create_index('idx_search_session', 'search_logs', ['session_id'], unique=False)


def downgrade() -> None:
    # 删除搜索日志表
    op.drop_index('idx_search_session', table_name='search_logs')
    op.drop_index('idx_search_created', table_name='search_logs')
    op.drop_index('idx_search_user', table_name='search_logs')
    op.drop_table('search_logs')
    
    # 删除知识库使用日志表
    op.drop_index('idx_knowledge_usage_created', table_name='knowledge_usage_logs')
    op.drop_index('idx_knowledge_usage_user', table_name='knowledge_usage_logs')
    op.drop_index('idx_knowledge_usage_knowledge', table_name='knowledge_usage_logs')
    op.drop_table('knowledge_usage_logs')
    
    # 删除使用日志表
    op.drop_index('idx_usage_created', table_name='usage_logs')
    op.drop_index('idx_usage_resource', table_name='usage_logs')
    op.drop_index('idx_usage_user_action', table_name='usage_logs')
    op.drop_table('usage_logs')
