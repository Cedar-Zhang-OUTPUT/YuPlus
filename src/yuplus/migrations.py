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


def retire_object_types(db):
    from .core import now
    stamp = now()
    db.execute("""UPDATE objects SET archived_at=COALESCE(archived_at,?)
        WHERE type_key IN ('project_assessment','creator_brief') OR
        (type_key='expression_guide' AND EXISTS (SELECT 1 FROM objects r
          WHERE r.project_id=objects.project_id AND r.type_key='creator_brief'
          AND objects.scope_key='review:' || r.id))""", (stamp,))
    # Keep immutable old revisions and their FKs; prevent reintroduction through old clients.
    for event in ('INSERT', 'UPDATE'):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS supported_active_objects_{event.lower()}
            BEFORE {event} ON objects WHEN NEW.archived_at IS NULL AND
            (NEW.type_key IN ('project_assessment','creator_brief') OR
             (NEW.type_key='expression_guide' AND EXISTS (SELECT 1 FROM objects r
              WHERE r.project_id=NEW.project_id AND r.type_key='creator_brief'
              AND NEW.scope_key='review:' || r.id)))
            BEGIN SELECT RAISE(ABORT,'unsupported active object type'); END""")
    db.execute('PRAGMA user_version=8')
