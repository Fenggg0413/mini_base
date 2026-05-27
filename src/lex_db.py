# lex_db.py
# SQL lexer for the project query subsystem.

import ply.lex as lex

from . import common_db

keywords = {
    'select': 'SELECT',
    'from': 'FROM',
    'where': 'WHERE',
    'and': 'AND',
    'or': 'OR',
    'not': 'NOT',
    'insert': 'INSERT',
    'into': 'INTO',
    'values': 'VALUES',
    'update': 'UPDATE',
    'set': 'SET',
    'delete': 'DELETE',
    'create': 'CREATE',
    'drop': 'DROP',
    'table': 'TABLE',
    'order': 'ORDER',
    'by': 'BY',
    'asc': 'ASC',
    'desc': 'DESC',
    'str': 'STRING_TYPE',
    'int': 'INT_TYPE',
    'bool': 'BOOL_TYPE',
    'true': 'BOOL',
    'false': 'BOOL',
    'begin': 'BEGIN',
    'commit': 'COMMIT',
    'rollback': 'ROLLBACK',
    'transaction': 'TRANSACTION',
    'index': 'INDEX',
    'on': 'ON',
    'show': 'SHOW',
    'tables': 'TABLES',
    'describe': 'DESCRIBE',
}

tokens = (
    'SELECT',
    'FROM',
    'WHERE',
    'AND',
    'OR',
    'NOT',
    'INSERT',
    'INTO',
    'VALUES',
    'UPDATE',
    'SET',
    'DELETE',
    'CREATE',
    'DROP',
    'TABLE',
    'ORDER',
    'BY',
    'ASC',
    'DESC',
    'IDENT',
    'INT',
    'STRING',
    'BOOL',
    'STRING_TYPE',
    'INT_TYPE',
    'BOOL_TYPE',
    'EQ',
    'NEQ',
    'LT',
    'GT',
    'LTE',
    'GTE',
    'COMMA',
    'STAR',
    'DOT',
    'SEMI',
    'LPAREN',
    'RPAREN',
    'BEGIN',
    'COMMIT',
    'ROLLBACK',
    'TRANSACTION',
    'INDEX',
    'ON',
    'SHOW',
    'TABLES',
    'DESCRIBE',
)

t_NEQ = r'<>|!='
t_LTE = r'<='
t_GTE = r'>='
t_LT = r'<'
t_GT = r'>'
t_EQ = r'='
t_COMMA = r','
t_STAR = r'\*'
t_DOT = r'\.'
t_SEMI = r';'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_ignore = ' \t\r\n'


def t_IDENT(t):
    r'[A-Za-z_][A-Za-z0-9_]*'
    token_type = keywords.get(t.value.lower())
    if token_type is None:
        return t
    t.type = token_type
    if token_type == 'BOOL':
        t.value = (t.value.lower() == 'true')
    return t


def t_INT(t):
    r'-?\d+'
    t.value = int(t.value)
    return t


def t_STRING(t):
    r"'([^'\\]|\\.|'')*'"
    raw = t.value[1:-1]
    raw = raw.replace("''", "'")
    raw = raw.replace("\\'", "'")
    t.value = raw
    return t


def t_error(t):
    raise SyntaxError("Illegal character '%s' at position %d" % (t.value[0], t.lexpos))


def set_lex_handle():
    common_db.global_lexer = lex.lex()
    if common_db.global_lexer is None:
        if common_db.VERBOSE:
            print('wrong when the global_lexer is created')
