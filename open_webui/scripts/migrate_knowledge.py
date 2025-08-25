"""
知识模块数据迁移脚本

从旧的 knowledge 和 files 表迁移数据到新的统一数据结构
"""

import os
import time
import uuid
import logging
from typing import Dict, List, Any
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from open_webui.internal.db import get_db, DATABASE_URL
from open_webui.models.knowledge_unified import (
    KnowledgeBase,
    Document,
    DocumentChunk,
    KnowledgeBaseDocument
)

logger = logging.getLogger(__name__)


class KnowledgeMigration:
    """知识模块数据迁移器"""
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)
    
    def run_migration(self):
        """执行完整迁移"""
        logger.info("Starting knowledge module migration...")
        
        try:
            # 1. 创建新表结构
            self._create_new_tables()
            
            # 2. 迁移知识库数据
            self._migrate_knowledge_bases()
            
            # 3. 迁移文档数据
            self._migrate_documents()
            
            # 4. 创建知识库-文档关联
            self._create_associations()
            
            # 5. 验证迁移结果
            self._validate_migration()
            
            logger.info("Knowledge module migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            # 回滚操作
            self._rollback_migration()
            raise
    
    def _create_new_tables(self):
        """创建新表结构"""
        logger.info("Creating new table structures...")
        
        # 创建新表的SQL
        create_tables_sql = """
        -- 知识库表
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            tags JSON DEFAULT '[]',
            category TEXT,
            access_control JSON,
            settings JSON DEFAULT '{}',
            stats JSON DEFAULT '{}',
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL
        );
        
        -- 文档表
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT,
            file_hash TEXT,
            file_size BIGINT,
            content_type TEXT,
            processing_status TEXT DEFAULT 'uploaded',
            processing_progress INTEGER DEFAULT 0,
            processing_error TEXT,
            processing_params JSON DEFAULT '{}',
            title TEXT,
            description TEXT,
            tags JSON DEFAULT '[]',
            metadata JSON DEFAULT '{}',
            page_count INTEGER,
            word_count INTEGER,
            chunk_count INTEGER DEFAULT 0,
            vector_count INTEGER DEFAULT 0,
            access_control JSON,
            created_at BIGINT NOT NULL,
            updated_at BIGINT NOT NULL,
            processed_at BIGINT
        );
        
        -- 文档分块表
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            title TEXT,
            chunk_type TEXT DEFAULT 'text',
            page_number INTEGER,
            start_char INTEGER,
            end_char INTEGER,
            vector_id TEXT,
            embedding_model TEXT,
            metadata JSON DEFAULT '{}',
            created_at BIGINT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        
        -- 知识库-文档关联表
        CREATE TABLE IF NOT EXISTS knowledge_base_documents (
            knowledge_base_id TEXT,
            document_id TEXT,
            added_at BIGINT NOT NULL,
            added_by TEXT NOT NULL,
            notes TEXT,
            settings JSON DEFAULT '{}',
            PRIMARY KEY (knowledge_base_id, document_id),
            FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        
        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_knowledge_bases_user_id ON knowledge_bases(user_id);
        CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
        CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_kb_docs_kb_id ON knowledge_base_documents(knowledge_base_id);
        CREATE INDEX IF NOT EXISTS idx_kb_docs_doc_id ON knowledge_base_documents(document_id);
        """
        
        with self.engine.connect() as conn:
            for statement in create_tables_sql.split(';'):
                if statement.strip():
                    conn.execute(text(statement))
            conn.commit()
    
    def _migrate_knowledge_bases(self):
        """迁移知识库数据"""
        logger.info("Migrating knowledge bases...")
        
        # 查询旧的知识库数据
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, user_id, name, description, data, meta, access_control, created_at, updated_at
                FROM knowledge
            """))
            
            old_kbs = result.fetchall()
        
        migrated_count = 0
        
        with self.Session() as session:
            for old_kb in old_kbs:
                try:
                    # 创建新的知识库记录
                    new_kb = KnowledgeBase(
                        id=old_kb.id,
                        user_id=old_kb.user_id,
                        name=old_kb.name,
                        description=old_kb.description,
                        tags=[],  # 旧版本没有标签
                        category=None,  # 旧版本没有分类
                        access_control=old_kb.access_control,
                        settings=old_kb.meta or {},
                        stats={
                            "document_count": len(old_kb.data.get("file_ids", [])) if old_kb.data else 0,
                            "total_size": 0,  # 稍后计算
                            "chunk_count": 0,
                            "vector_count": 0,
                            "last_activity": old_kb.updated_at
                        },
                        created_at=old_kb.created_at,
                        updated_at=old_kb.updated_at
                    )
                    
                    session.add(new_kb)
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to migrate knowledge base {old_kb.id}: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"Migrated {migrated_count} knowledge bases")
    
    def _migrate_documents(self):
        """迁移文档数据"""
        logger.info("Migrating documents...")
        
        # 查询旧的文件数据
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, user_id, hash, filename, path, data, meta, access_control, created_at, updated_at
                FROM file
            """))
            
            old_files = result.fetchall()
        
        migrated_count = 0
        
        with self.Session() as session:
            for old_file in old_files:
                try:
                    # 确定文件大小
                    file_size = 0
                    if old_file.meta and isinstance(old_file.meta, dict):
                        file_size = old_file.meta.get("size", 0)
                    
                    # 确定内容类型
                    content_type = "application/octet-stream"
                    if old_file.meta and isinstance(old_file.meta, dict):
                        content_type = old_file.meta.get("content_type", content_type)
                    
                    # 创建新的文档记录
                    new_doc = Document(
                        id=old_file.id,
                        user_id=old_file.user_id,
                        filename=old_file.filename,
                        original_filename=old_file.filename,  # 旧版本没有区分
                        file_path=old_file.path,
                        file_hash=old_file.hash,
                        file_size=file_size,
                        content_type=content_type,
                        processing_status="completed",  # 假设旧文档都已处理完成
                        processing_progress=100,
                        title=old_file.filename,
                        description=None,
                        tags=[],
                        metadata=old_file.meta or {},
                        access_control=old_file.access_control,
                        created_at=old_file.created_at,
                        updated_at=old_file.updated_at,
                        processed_at=old_file.updated_at
                    )
                    
                    session.add(new_doc)
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to migrate document {old_file.id}: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"Migrated {migrated_count} documents")
    
    def _create_associations(self):
        """创建知识库-文档关联"""
        logger.info("Creating knowledge base-document associations...")
        
        # 查询旧的知识库数据以获取文件关联
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, user_id, data, updated_at
                FROM knowledge
                WHERE data IS NOT NULL
            """))
            
            old_kbs = result.fetchall()
        
        associations_count = 0
        
        with self.Session() as session:
            for old_kb in old_kbs:
                try:
                    if not old_kb.data or not isinstance(old_kb.data, dict):
                        continue
                    
                    file_ids = old_kb.data.get("file_ids", [])
                    if not file_ids:
                        continue
                    
                    for file_id in file_ids:
                        # 检查文档是否存在
                        doc_exists = session.query(Document).filter(Document.id == file_id).first()
                        if not doc_exists:
                            continue
                        
                        # 创建关联
                        association = KnowledgeBaseDocument(
                            knowledge_base_id=old_kb.id,
                            document_id=file_id,
                            added_at=old_kb.updated_at,
                            added_by=old_kb.user_id,
                            notes="Migrated from legacy system"
                        )
                        
                        session.add(association)
                        associations_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to create associations for knowledge base {old_kb.id}: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"Created {associations_count} knowledge base-document associations")
    
    def _update_knowledge_base_stats(self):
        """更新知识库统计信息"""
        logger.info("Updating knowledge base statistics...")
        
        with self.Session() as session:
            kbs = session.query(KnowledgeBase).all()
            
            for kb in kbs:
                try:
                    # 计算关联文档统计
                    associations = session.query(KnowledgeBaseDocument).filter(
                        KnowledgeBaseDocument.knowledge_base_id == kb.id
                    ).all()
                    
                    total_size = 0
                    doc_count = len(associations)
                    
                    for assoc in associations:
                        doc = session.query(Document).filter(Document.id == assoc.document_id).first()
                        if doc:
                            total_size += doc.file_size or 0
                    
                    # 更新统计
                    kb.stats = {
                        "document_count": doc_count,
                        "total_size": total_size,
                        "chunk_count": 0,  # TODO: 计算分块数量
                        "vector_count": 0,  # TODO: 计算向量数量
                        "last_activity": kb.updated_at
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to update stats for knowledge base {kb.id}: {e}")
                    continue
            
            session.commit()
    
    def _validate_migration(self):
        """验证迁移结果"""
        logger.info("Validating migration results...")
        
        with self.engine.connect() as conn:
            # 检查数据一致性
            old_kb_count = conn.execute(text("SELECT COUNT(*) FROM knowledge")).scalar()
            new_kb_count = conn.execute(text("SELECT COUNT(*) FROM knowledge_bases")).scalar()
            
            old_file_count = conn.execute(text("SELECT COUNT(*) FROM file")).scalar()
            new_doc_count = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
            
            logger.info(f"Knowledge bases: {old_kb_count} -> {new_kb_count}")
            logger.info(f"Documents: {old_file_count} -> {new_doc_count}")
            
            if new_kb_count < old_kb_count:
                logger.warning(f"Some knowledge bases were not migrated: {old_kb_count - new_kb_count} missing")
            
            if new_doc_count < old_file_count:
                logger.warning(f"Some documents were not migrated: {old_file_count - new_doc_count} missing")
        
        logger.info("Migration validation completed")
    
    def _rollback_migration(self):
        """回滚迁移"""
        logger.info("Rolling back migration...")
        
        try:
            with self.engine.connect() as conn:
                # 删除新创建的表
                rollback_sql = """
                DROP TABLE IF EXISTS knowledge_base_documents;
                DROP TABLE IF EXISTS document_chunks;
                DROP TABLE IF EXISTS documents;
                DROP TABLE IF EXISTS knowledge_bases;
                """
                
                for statement in rollback_sql.split(';'):
                    if statement.strip():
                        conn.execute(text(statement))
                
                conn.commit()
            
            logger.info("Migration rollback completed")
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
    
    def create_backup(self):
        """创建备份"""
        logger.info("Creating backup of existing data...")
        
        backup_dir = Path("./migration_backup")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = int(time.time())
        
        with self.engine.connect() as conn:
            # 备份知识库数据
            kb_result = conn.execute(text("SELECT * FROM knowledge"))
            kb_data = [dict(row._mapping) for row in kb_result]
            
            import json
            with open(backup_dir / f"knowledge_backup_{timestamp}.json", "w") as f:
                json.dump(kb_data, f, indent=2, default=str)
            
            # 备份文件数据
            file_result = conn.execute(text("SELECT * FROM file"))
            file_data = [dict(row._mapping) for row in file_result]
            
            with open(backup_dir / f"files_backup_{timestamp}.json", "w") as f:
                json.dump(file_data, f, indent=2, default=str)
        
        logger.info(f"Backup created in {backup_dir}")


def run_migration():
    """运行迁移脚本"""
    migration = KnowledgeMigration()
    
    # 创建备份
    migration.create_backup()
    
    # 执行迁移
    migration.run_migration()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
