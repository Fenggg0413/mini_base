"""测试通用 fixture。隔离 data 目录、清理共享状态。"""
import pytest

from src import common_db, schema_db, transaction_db


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """把 data 目录重定向到 tmp_path，并清空共享单例。

    覆盖：
      - common_db.DATA_DIR
      - schema_db.Schema.fileName（类属性，导入时已固化，需单独 patch）
      - common_db.shared_schema（避免上一个测试残留）
      - transaction_db.transaction_manager（单例）
      - common_db.current_transaction_id
    """
    monkeypatch.setattr(common_db, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(
        schema_db.Schema, 'fileName',
        common_db.data_path('all.sch'),
    )
    monkeypatch.setattr(common_db, 'shared_schema', None)
    monkeypatch.setattr(common_db, 'current_transaction_id', None)
    monkeypatch.setattr(transaction_db, 'transaction_manager', None)
    yield tmp_path
