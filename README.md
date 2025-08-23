# backend-openwebui

## 快速开始
Python 3.11（建议虚拟环境），并安装依赖。

- 安装依赖
  - pip: `pip install -r requirements.txt -U`

- 启动服务
  - Windows（PowerShell）：`./start_windows.bat`
  - Linux/macOS：`./start.sh`（或 `sh dev.sh`）

- 接口文档：`http://localhost:8080/docs`。

## 数据库迁移

首次启动该服务时，会自动执行 Alembic 迁移。

### 自动迁移
应用启动时会**自动执行数据库迁移**（通过 `config.py` 中的 `run_migrations()` 函数）。正常情况下，开发者无需手动执行迁移命令。

### 何时需要手动迁移
以下情况可能需要手动干预：

1. **迁移失败时**：查看错误日志，修复问题后重新启动
2. **迁移冲突时**：多个分支合并导致迁移链断裂
3. **回滚操作时**：需要回退到之前的数据库版本

### 手动迁移命令
```bash
# 激活虚拟环境
source .venv/Scripts/activate  # Windows

# 查看当前版本
alembic current

# 升级到最新版本
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 查看迁移历史
alembic history
```

### 迁移故障排查
如果遇到迁移问题，可使用迁移管理工具：

```bash
# 检查迁移问题
python scripts/migration_manager.py check

# 自动修复迁移链
python scripts/migration_manager.py fix-all

# 修复迁移链断裂
python scripts/migration_manager.py fix-chain

# 删除重复迁移
python scripts/migration_manager.py fix-duplicates
```

### 创建新迁移
```bash
# 自动生成迁移文件（基于模型变更）
alembic revision --autogenerate -m "描述变更内容"

# 手动创建迁移文件
alembic revision -m "描述变更内容"
```

**注意**：
- 数据库文件位于 `data/webui.db`
- 迁移文件位于 `open_webui/migrations/versions/`
- 确保迁移文件使用标准的 12 位十六进制 revision ID
