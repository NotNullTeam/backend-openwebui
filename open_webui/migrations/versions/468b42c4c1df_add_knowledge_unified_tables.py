"""Add knowledge unified tables

Revision ID: 468b42c4c1df
Revises: ceeed12ad009
Create Date: 2025-08-25 21:06:43.625880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '468b42c4c1df'
down_revision: Union[str, None] = 'ceeed12ad009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create knowledge_bases table (unified knowledge base management)
    op.create_table('knowledge_bases',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('access_control', sa.JSON(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('stats', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create documents table (unified document management)
    op.create_table('documents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('file_hash', sa.String(), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('processing_status', sa.String(), nullable=True),
        sa.Column('processing_progress', sa.Integer(), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('processing_params', sa.JSON(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('doc_metadata', sa.JSON(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.Column('vector_count', sa.Integer(), nullable=True),
        sa.Column('access_control', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('processed_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create document_chunks table
    op.create_table('document_chunks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('chunk_type', sa.String(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('start_char', sa.Integer(), nullable=True),
        sa.Column('end_char', sa.Integer(), nullable=True),
        sa.Column('vector_id', sa.String(), nullable=True),
        sa.Column('embedding_model', sa.String(), nullable=True),
        sa.Column('doc_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create knowledge_base_documents association table
    op.create_table('knowledge_base_documents',
        sa.Column('knowledge_base_id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('added_at', sa.BigInteger(), nullable=False),
        sa.Column('added_by', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ),
        sa.PrimaryKeyConstraint('knowledge_base_id', 'document_id')
    )
    
    # Create indexes for knowledge_bases
    op.create_index(op.f('idx_knowledge_bases_user_id'), 'knowledge_bases', ['user_id'], unique=False)
    op.create_index(op.f('idx_knowledge_bases_name'), 'knowledge_bases', ['name'], unique=False)
    op.create_index(op.f('idx_knowledge_bases_category'), 'knowledge_bases', ['category'], unique=False)
    op.create_index(op.f('idx_knowledge_bases_created_at'), 'knowledge_bases', ['created_at'], unique=False)
    
    # Create indexes for documents
    op.create_index(op.f('idx_documents_user_id'), 'documents', ['user_id'], unique=False)
    op.create_index(op.f('idx_documents_filename'), 'documents', ['filename'], unique=False)
    op.create_index(op.f('idx_documents_file_hash'), 'documents', ['file_hash'], unique=False)
    op.create_index(op.f('idx_documents_processing_status'), 'documents', ['processing_status'], unique=False)
    op.create_index(op.f('idx_documents_created_at'), 'documents', ['created_at'], unique=False)
    op.create_index(op.f('idx_documents_content_type'), 'documents', ['content_type'], unique=False)
    
    # Create indexes for document_chunks
    op.create_index(op.f('idx_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('idx_document_chunks_chunk_index'), 'document_chunks', ['document_id', 'chunk_index'], unique=False)
    op.create_index(op.f('idx_document_chunks_vector_id'), 'document_chunks', ['vector_id'], unique=False)
    
    # Create indexes for knowledge_base_documents
    op.create_index(op.f('idx_kb_doc_knowledge_base_id'), 'knowledge_base_documents', ['knowledge_base_id'], unique=False)
    op.create_index(op.f('idx_kb_doc_document_id'), 'knowledge_base_documents', ['document_id'], unique=False)
    op.create_index(op.f('idx_kb_doc_added_at'), 'knowledge_base_documents', ['added_at'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index(op.f('idx_kb_doc_added_at'), table_name='knowledge_base_documents')
    op.drop_index(op.f('idx_kb_doc_document_id'), table_name='knowledge_base_documents')
    op.drop_index(op.f('idx_kb_doc_knowledge_base_id'), table_name='knowledge_base_documents')
    op.drop_index(op.f('idx_document_chunks_vector_id'), table_name='document_chunks')
    op.drop_index(op.f('idx_document_chunks_chunk_index'), table_name='document_chunks')
    op.drop_index(op.f('idx_document_chunks_document_id'), table_name='document_chunks')
    op.drop_index(op.f('idx_documents_content_type'), table_name='documents')
    op.drop_index(op.f('idx_documents_created_at'), table_name='documents')
    op.drop_index(op.f('idx_documents_processing_status'), table_name='documents')
    op.drop_index(op.f('idx_documents_file_hash'), table_name='documents')
    op.drop_index(op.f('idx_documents_filename'), table_name='documents')
    op.drop_index(op.f('idx_documents_user_id'), table_name='documents')
    op.drop_index(op.f('idx_knowledge_bases_created_at'), table_name='knowledge_bases')
    op.drop_index(op.f('idx_knowledge_bases_category'), table_name='knowledge_bases')
    op.drop_index(op.f('idx_knowledge_bases_name'), table_name='knowledge_bases')
    op.drop_index(op.f('idx_knowledge_bases_user_id'), table_name='knowledge_bases')
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('knowledge_base_documents')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('knowledge_bases')
