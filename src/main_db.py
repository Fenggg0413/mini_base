# -----------------------
# main_db.py
# SQL REPL for mini_base
# -----------------------

from . import schema_db
from . import query_plan_db
from . import common_db
from . import transaction_db


PROMPT = 'mini_base> '

HELP_TEXT = """\
Available SQL statements:
  SELECT ... FROM ... [WHERE ...] [ORDER BY ...];
  INSERT INTO table [(cols)] VALUES (vals);
  UPDATE table SET field=val [WHERE ...];
  DELETE FROM table [WHERE ...];
  CREATE TABLE table (field_def, ...);
  DROP TABLE table;
  CREATE INDEX ON table(field);
  DROP INDEX ON table(field);
  BEGIN [TRANSACTION];
  COMMIT;
  ROLLBACK;
  SHOW TABLES;
  SHOW INDEX [FROM table];
  DESCRIBE table;

Dot-commands:
  .help    - Show this help
  .quit    - Exit mini_base
"""


def main():
    print('mini_base SQL REPL')
    print("Type .help for help, .quit to exit.\n")

    # 初始化事务管理器并进行崩溃恢复
    transaction_db.get_transaction_manager()
    # 加载 schema（确保 all.sch 就绪）
    schema_db.Schema()

    while True:
        try:
            line = input(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print('\nBye.')
            break

        if not line:
            continue

        # Dot-commands
        if line.startswith('.'):
            cmd = line.lower()
            if cmd in ('.quit', '.exit', '.q'):
                print('Bye.')
                break
            elif cmd == '.help':
                print(HELP_TEXT)
            else:
                print("Unknown dot-command: %s" % line)
                print("Type .help for available commands.")
            continue

        # SQL statement
        try:
            query_plan_db.execute_sql(line)
        except Exception as e:
            print('Error: %s' % str(e))


if __name__ == '__main__':
    main()
