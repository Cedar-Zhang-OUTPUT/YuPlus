"""Versioned storage changes; invoked inside the initialization transaction."""
from .core import YuError


def add_open_questions(db):
    # Rebuild the constrained table with FK enforcement temporarily disabled by
    # the caller. Keep all identities, rows, indexes and triggers verbatim.
    sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='objects'").fetchone()[0]
    marker = "'risks','assessment_decision','expression_guide'"
    if marker not in sql:
        raise YuError('INTEGRITY_FAILURE', '对象表结构不匹配，拒绝迁移。')
    dependents = [row[0] for row in db.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name='objects' AND type IN ('index','trigger') AND sql IS NOT NULL")]
    sql = sql.replace('CREATE TABLE objects', 'CREATE TABLE objects_next', 1)
    sql = sql.replace(marker, marker + ",'open_questions'", 1)
    db.execute(sql)
    db.execute('INSERT INTO objects_next SELECT * FROM objects')
    db.execute('DROP TABLE objects')
    # Other tables' triggers refer to objects while its name is briefly absent.
    # Do not rewrite their references to the temporary name.
    db.execute('PRAGMA legacy_alter_table=ON')
    try:
        db.execute('ALTER TABLE objects_next RENAME TO objects')
    finally:
        db.execute('PRAGMA legacy_alter_table=OFF')
    for statement in dependents:
        db.execute(statement)
    if db.execute('PRAGMA foreign_key_check').fetchone():
        raise YuError('INTEGRITY_FAILURE', '迁移后的对象关联校验失败。')
    db.execute('PRAGMA user_version=3')
