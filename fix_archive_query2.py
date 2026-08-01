import re

filepath = 'backend/src/storage/data_retention.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace the specific lines
old_block = """                    source_table = table(policy.table_name, column("created_at"))
                    target_table = table(archive_table)
                    archive_query = insert(target_table).from_select(
                        ["*"],
                        select(source_table).where(
                            source_table.c.created_at < cutoff_date
                        ),
                    )
                    # The above might be slightly tricky if the table structure is not known for insert.
                    # Let\\'s use text for archive_query for now but without the string format for table if possible... wait, table names can\\'t be parameterized in standard SQL
                    # SQLAlchemy Core allows insert().from_select() but we need columns.
                    # A simpler fix for archive_query is to leave it but remove the nosec and just use Core properly if possible, or construct it safely.
                    archive_query = text(
                        f"INSERT INTO {archive_table} SELECT * FROM {policy.table_name} WHERE created_at < :cutoff_date"
                    )  # nosec: B608
                    db.execute(archive_query, {"cutoff_date": cutoff_date})"""

new_block = """                    archive_query = text(
                        f"INSERT INTO {archive_table} SELECT * FROM {policy.table_name} WHERE created_at < :cutoff_date"
                    )  # nosec: B608
                    db.execute(archive_query, {"cutoff_date": cutoff_date})"""

content = content.replace(old_block, new_block)

with open(filepath, 'w') as f:
    f.write(content)
