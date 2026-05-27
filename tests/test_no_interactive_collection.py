"""守门用例：确保交互式脚本不会被 pytest 当作测试收集。"""
import subprocess
import sys


def test_pytest_collection_skips_manual_scripts():
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/', '--collect-only', '-q'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert 'manual/transaction_demo' not in result.stdout
    assert 'manual/transaction_demo' not in result.stderr
