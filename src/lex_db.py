# lex_db.py
# SQL lexer for the project query subsystem.

import ply.lex as lex

from . import common_db

keywords = {
    'select': 'SELECT',
    'from': 'FROM',
    'where': 'WHERE',
    'and': 'AND',
    'true': 'BOOL',
    'false': 'BOOL',
}

tokens = (
    'SELECT',
    'FROM',
    'WHERE',
    'AND',
    'IDENT',
    'INT',
    'STRING',
    'BOOL',
    'EQ',
    'COMMA',
    'STAR',
    'DOT',
    'SEMI',
)

t_EQ = r'='
t_COMMA = r','
t_STAR = r'\*'
t_DOT = r'\.'
t_SEMI = r';'
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
        print('wrong when the global_lex is created')
