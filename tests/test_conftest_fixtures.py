"""验证 conftest.py 的 fixture 行为契约。"""
import os
from src import common_db, schema_db


def test_isolated_data_dir_redirects_common_db(isolated_data_dir):
    assert common_db.DATA_DIR == str(isolated_data_dir)
    assert os.path.dirname(common_db.data_path('foo.dat')) == str(isolated_data_dir)


def test_isolated_data_dir_redirects_schema_filename(isolated_data_dir):
    assert os.path.dirname(schema_db.Schema.fileName) == str(isolated_data_dir)


def test_isolated_data_dir_clears_shared_schema(isolated_data_dir):
    assert common_db.shared_schema is None


def test_isolated_data_dir_resets_transaction_manager(isolated_data_dir):
    from src import transaction_db
    assert transaction_db.transaction_manager is None
