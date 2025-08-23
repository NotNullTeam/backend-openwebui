#!/usr/bin/env python3
"""
数据库迁移管理工具
整合了检查、修复和维护数据库迁移的所有功能
"""

import os
import re
import sys
import sqlite3
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, Tuple, Optional, List, Union


class MigrationManager:
    """迁移管理器主类"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.migrations_dir = self.project_root / "open_webui" / "migrations" / "versions"
        self.db_path = self.project_root / "data" / "webui.db"
        self.backup_dir = self.project_root / "data" / "migration_backups"
        
    def setup(self):
        """初始化设置"""
        os.chdir(self.project_root)
        if not self.migrations_dir.exists():
            print("❌ 迁移目录不存在")
            return False
        return True
    
    # ========== 检查功能 ==========
    
    def check_duplicate_tables(self) -> bool:
        """检查是否有重复创建表的迁移"""
        table_migrations = defaultdict(list)
        
        for migration_file in self.migrations_dir.glob("*.py"):
            if migration_file.name.startswith("__"):
                continue
                
            with open(migration_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 查找 create_table 调用
            create_table_matches = re.findall(r'create_table\([\'"]([^\'"]+)[\'"]', content)
            for table_name in create_table_matches:
                table_migrations[table_name].append(migration_file.name)
        
        # 检查重复
        duplicates = {table: files for table, files in table_migrations.items() if len(files) > 1}
        
        if duplicates:
            print("❌ 发现重复的表创建:")
            for table, files in duplicates.items():
                print(f"  表 '{table}' 在以下文件中被创建:")
                for file in files:
                    print(f"    - {file}")
            return False
        else:
            print("✅ 没有发现重复的表创建")
            return True
    
    def check_migration_chain(self) -> bool:
        """检查迁移链是否连续"""
        migrations = self._load_migrations()
        
        # 检查迁移链
        heads = []
        for revision, info in migrations.items():
            if info['down_revision'] is None:
                heads.append(revision)
            elif isinstance(info['down_revision'], tuple):
                # 处理合并迁移
                for down_rev in info['down_revision']:
                    if down_rev not in migrations:
                        print(f"❌ 迁移 {revision} ({info['file']}) 的 down_revision {down_rev} 不存在")
                        return False
            elif info['down_revision'] not in migrations:
                print(f"❌ 迁移 {revision} ({info['file']}) 的 down_revision {info['down_revision']} 不存在")
                return False
        
        if len(heads) > 1:
            print(f"❌ 发现多个头节点: {heads}")
            return False
        elif len(heads) == 0:
            print("❌ 没有找到头节点")
            return False
        else:
            print(f"✅ 迁移链正常，头节点: {heads[0]}")
            return True
    
    def check_custom_revision_ids(self) -> bool:
        """检查是否有自定义的revision ID"""
        custom_revisions = []
        
        for migration_file in self.migrations_dir.glob("*.py"):
            if migration_file.name.startswith("__"):
                continue
                
            with open(migration_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 检查是否有自定义的revision ID（不是标准的12位十六进制）
            revision_match = re.search(r'revision\s*[:=]\s*[\'"]([^\'"]+)[\'"]', content)
            if revision_match:
                revision = revision_match.group(1)
                # 检查是否是标准的Alembic revision ID格式（12位十六进制）
                if not re.match(r'^[a-f0-9]{12}$', revision):
                    custom_revisions.append((migration_file.name, revision))
        
        if custom_revisions:
            print("❌ 发现自定义的revision ID:")
            for file, revision in custom_revisions:
                print(f"  {file}: {revision}")
            return False
        else:
            print("✅ 所有迁移都使用标准的revision ID")
            return True
    
    def check_all(self):
        """运行所有检查"""
        print("🔍 开始检查数据库迁移...")
        print("=" * 50)
        
        if not self.setup():
            return False
        
        checks = [
            ("重复表检查", self.check_duplicate_tables),
            ("迁移链检查", self.check_migration_chain),
            ("Revision ID检查", self.check_custom_revision_ids),
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            print(f"\n📋 {check_name}:")
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                print(f"❌ 检查失败: {e}")
                all_passed = False
        
        print("\n" + "=" * 50)
        if all_passed:
            print("✅ 所有检查都通过了！")
            return True
        else:
            print("❌ 发现了一些问题，请修复后重新检查")
            return False
    
    # ========== 修复功能 ==========
    
    def _load_migrations(self) -> Dict:
        """加载所有迁移文件信息"""
        migrations = {}
        
        for migration_file in self.migrations_dir.glob("*.py"):
            if migration_file.name.startswith("__"):
                continue
                
            with open(migration_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 增强的正则表达式匹配
            revision = self._extract_revision(content)
            down_revision = self._extract_down_revision(content)
            
            if revision:
                migrations[revision] = {
                    'file': migration_file.name,
                    'down_revision': down_revision,
                    'content': content
                }
        
        return migrations
    
    def _extract_revision(self, content: str) -> Optional[str]:
        """提取 revision ID，支持多种格式"""
        patterns = [
            r'revision\s*[:=]\s*[\'"]([^\'"]+)[\'"]',  # 基础格式
            r'revision\s*:\s*str\s*=\s*[\'"]([^\'"]+)[\'"]',  # 类型注解
            r'revision\s*:\s*Optional\[str\]\s*=\s*[\'"]([^\'"]+)[\'"]',  # Optional类型
            r'revision\s*=\s*[\'"]([^\'"]+)[\'"]',  # 简单赋值
            # 多行格式
            r'revision\s*[:=]\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                return match.group(1)
        return None
    
    def _extract_down_revision(self, content: str) -> Optional[Union[str, tuple]]:
        """提取 down_revision，支持多种格式"""
        # 检查 None 值
        if re.search(r'down_revision\s*[:=]\s*None', content):
            return None
            
        patterns = [
            # 单个字符串
            r'down_revision\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
            r'down_revision\s*:\s*Union\[str,\s*None\]\s*=\s*[\'"]([^\'"]+)[\'"]',
            r'down_revision\s*:\s*Optional\[str\]\s*=\s*[\'"]([^\'"]+)[\'"]',
            # 元组格式 (合并迁移)
            r'down_revision\s*[:=]\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'down_revision\s*:\s*Union\[str,\s*tuple\[str,\s*str\],\s*None\]\s*=\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'down_revision\s*:\s*Tuple\[str,\s*str\]\s*=\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)',
            # 多行元组格式
            r'down_revision\s*[:=]\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                groups = match.groups()
                if len(groups) == 1:
                    return groups[0]
                elif len(groups) == 2:
                    return (groups[0], groups[1])
        
        return None
    
    def _find_valid_head(self, migrations: Dict) -> Optional[str]:
        """找到一个有效的头节点"""
        # 找到所有没有被其他迁移指向的revision
        all_down_revisions = set()
        for info in migrations.values():
            if info['down_revision']:
                if isinstance(info['down_revision'], tuple):
                    all_down_revisions.update(info['down_revision'])
                else:
                    all_down_revisions.add(info['down_revision'])
        
        heads = [rev for rev in migrations.keys() if rev not in all_down_revisions]
        
        if len(heads) == 1:
            return heads[0]
        elif len(heads) > 1:
            print(f"⚠️  发现多个头节点: {heads}")
            # 选择最新的一个（按文件名排序）
            heads.sort(key=lambda x: migrations[x]['file'])
            return heads[-1]
        else:
            print("❌ 没有找到头节点")
            return None
    
    def _update_database_version(self, target_revision: str) -> bool:
        """更新数据库版本记录"""
        if not self.db_path.exists():
            print("⚠️  数据库文件不存在，跳过版本更新")
            return True
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查当前版本
            cursor.execute("SELECT version_num FROM alembic_version")
            current_version = cursor.fetchone()
            
            if current_version:
                print(f"当前数据库版本: {current_version[0]}")
            
            # 更新版本
            cursor.execute("UPDATE alembic_version SET version_num = ?", (target_revision,))
            conn.commit()
            
            print(f"✅ 数据库版本已更新为: {target_revision}")
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ 更新数据库版本失败: {e}")
            return False
    
    def fix_chain(self):
        """修复迁移链断裂问题"""
        print("🔧 迁移链修复工具")
        print("=" * 50)
        
        if not self.setup():
            return False
        
        # 分析迁移链
        print("📋 步骤1: 分析迁移链")
        migrations = self._load_migrations()
        
        # 检查缺失的revision
        missing_revisions = set()
        for revision, info in migrations.items():
            if info['down_revision']:
                if isinstance(info['down_revision'], tuple):
                    for down_rev in info['down_revision']:
                        if down_rev not in migrations:
                            missing_revisions.add(down_rev)
                            print(f"❌ 迁移 {revision} ({info['file']}) 的 down_revision {down_rev} 不存在")
                elif info['down_revision'] not in migrations:
                    missing_revisions.add(info['down_revision'])
                    print(f"❌ 迁移 {revision} ({info['file']}) 的 down_revision {info['down_revision']} 不存在")
        
        if not missing_revisions:
            print("✅ 迁移链正常，无需修复")
            return True
        
        # 找到有效的头节点
        print("\n📋 步骤2: 找到有效的头节点")
        target_head = self._find_valid_head(migrations)
        if not target_head:
            print("❌ 无法找到有效的头节点")
            return False
        
        print(f"✅ 找到有效头节点: {target_head}")
        
        # 修复迁移链
        print("\n📋 步骤3: 修复迁移链")
        print(f"🔧 开始修复迁移链，目标头节点: {target_head}")
        
        # 构建从目标头节点开始的完整链
        valid_chain = set()
        current = target_head
        
        while current and current in migrations:
            valid_chain.add(current)
            down_rev = migrations[current]['down_revision']
            if isinstance(down_rev, tuple):
                # 对于合并迁移，选择第一个有效的下游
                for rev in down_rev:
                    if rev in migrations:
                        current = rev
                        break
                else:
                    current = None
            else:
                current = down_rev
        
        print(f"✅ 有效迁移链包含 {len(valid_chain)} 个迁移文件")
        
        # 找出不在有效链中的迁移文件
        invalid_migrations = []
        for revision, info in migrations.items():
            if revision not in valid_chain:
                invalid_migrations.append((revision, info['file']))
        
        if invalid_migrations:
            print(f"\n⚠️  发现 {len(invalid_migrations)} 个无效的迁移文件:")
            for revision, filename in invalid_migrations:
                print(f"  - {filename} (revision: {revision})")
            
            # 询问是否删除
            response = input("\n是否删除这些无效的迁移文件？(y/N): ").strip().lower()
            if response == 'y':
                deleted_count = 0
                for revision, filename in invalid_migrations:
                    try:
                        file_path = self.migrations_dir / filename
                        # 备份文件
                        if self._backup_file(file_path):
                            file_path.unlink()
                            print(f"  ✅ 已删除: {filename}")
                            deleted_count += 1
                        else:
                            print(f"  ❌ 备份失败，跳过删除: {filename}")
                    except Exception as e:
                        print(f"  ❌ 删除失败 {filename}: {e}")
                
                print(f"\n✅ 共删除了 {deleted_count} 个无效的迁移文件")
            else:
                print("❌ 用户取消了删除操作")
                return False
        
        # 更新数据库版本
        print("\n📋 步骤4: 更新数据库版本")
        self._update_database_version(target_head)
        
        print("\n" + "=" * 50)
        print("✅ 迁移链修复完成！")
        self._print_suggestions()
        return True
    
    def fix_duplicates(self):
        """删除重复的迁移文件并修复数据库版本"""
        print("🔧 数据库迁移修复工具")
        print("=" * 50)
        
        if not self.setup():
            return False
        
        print(f"📁 数据库文件: {self.db_path}")
        
        # 1. 删除重复的迁移文件
        print("\n📋 步骤1: 删除重复的迁移文件")
        
        # 按表名分组迁移文件
        table_migrations = defaultdict(list)
        
        for migration_file in self.migrations_dir.glob("*.py"):
            if migration_file.name.startswith("__"):
                continue
                
            with open(migration_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 查找 create_table 调用
            create_table_matches = re.findall(r'create_table\([\'"]([^\'"]+)[\'"]', content)
            for table_name in create_table_matches:
                table_migrations[table_name].append(migration_file)
        
        # 删除重复的迁移文件
        deleted_files = []
        for table, files in table_migrations.items():
            if len(files) > 1:
                print(f"发现重复创建表 '{table}' 的迁移文件:")
                for file in files:
                    print(f"  - {file.name}")
                
                # 保留最新的文件（按文件名排序，通常包含时间戳）
                files.sort(key=lambda x: x.name)
                files_to_delete = files[:-1]  # 删除除了最后一个之外的所有文件
                
                for file in files_to_delete:
                    try:
                        # 备份文件
                        if self._backup_file(file):
                            file.unlink()
                            deleted_files.append(file.name)
                            print(f"  ✅ 已删除: {file.name}")
                        else:
                            print(f"  ❌ 备份失败，跳过删除: {file.name}")
                    except Exception as e:
                        print(f"  ❌ 删除失败 {file.name}: {e}")
        
        if deleted_files:
            print(f"\n✅ 共删除了 {len(deleted_files)} 个重复的迁移文件")
        else:
            print("✅ 没有发现重复的迁移文件")
        
        # 2. 找到最新的迁移版本
        print("\n📋 步骤2: 找到最新的迁移版本")
        migrations = self._load_migrations()
        latest_revision = self._find_valid_head(migrations)
        
        if not latest_revision:
            print("❌ 无法找到最新的迁移版本")
            return False
        
        print(f"✅ 最新迁移版本: {latest_revision}")
        
        # 3. 修复数据库版本
        print("\n📋 步骤3: 修复数据库版本")
        if not self._update_database_version(latest_revision):
            print("❌ 修复数据库版本失败")
            return False
        
        print("\n" + "=" * 50)
        print("✅ 迁移修复完成！")
        self._print_suggestions()
        return True
    
    def fix_all(self):
        """执行所有修复操作"""
        print("🔧 完整修复流程")
        print("=" * 50)
        
        if not self.setup():
            return False
        
        # 先检查问题
        print("\n📋 第一步：检查现有问题")
        self.check_all()
        
        # 询问是否继续修复
        response = input("\n是否继续执行自动修复？(y/N): ").strip().lower()
        if response != 'y':
            print("❌ 用户取消了修复操作")
            return False
        
        # 执行修复
        print("\n📋 第二步：删除重复迁移")
        self.fix_duplicates()
        
        print("\n📋 第三步：修复迁移链")
        self.fix_chain()
        
        # 再次检查
        print("\n📋 第四步：验证修复结果")
        return self.check_all()
    
    def _backup_file(self, file_path: Path) -> bool:
        """备份文件到备份目录"""
        try:
            # 创建备份目录
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成备份文件名（包含时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            backup_path = self.backup_dir / backup_filename
            
            # 复制文件
            shutil.copy2(file_path, backup_path)
            print(f"  📁 已备份到: {backup_path.relative_to(self.project_root)}")
            return True
            
        except Exception as e:
            print(f"  ❌ 备份失败: {e}")
            return False
    
    def _print_suggestions(self):
        """打印后续建议"""
        print("\n📝 建议:")
        print("1. 重新启动应用: ./dev.sh 或 start_windows.bat")
        print("2. 检查应用是否正常运行")
        print("3. 运行迁移检查: python scripts/migration_manager.py check")
        if self.backup_dir.exists() and any(self.backup_dir.iterdir()):
            print(f"4. 备份文件位于: {self.backup_dir.relative_to(self.project_root)}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='数据库迁移管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/migration_manager.py check          # 检查迁移问题
  python scripts/migration_manager.py fix-chain      # 修复迁移链
  python scripts/migration_manager.py fix-duplicates # 删除重复迁移
  python scripts/migration_manager.py fix-all        # 执行所有修复
        """
    )
    
    parser.add_argument(
        'command',
        choices=['check', 'fix-chain', 'fix-duplicates', 'fix-all'],
        help='要执行的操作'
    )
    
    args = parser.parse_args()
    
    manager = MigrationManager()
    
    try:
        if args.command == 'check':
            success = manager.check_all()
        elif args.command == 'fix-chain':
            success = manager.fix_chain()
        elif args.command == 'fix-duplicates':
            success = manager.fix_duplicates()
        elif args.command == 'fix-all':
            success = manager.fix_all()
        else:
            print(f"❌ 未知命令: {args.command}")
            success = False
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
