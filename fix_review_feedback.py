import re
from pathlib import Path

# Fix time_series_store.py shadowing issue
file_ts = 'backend/src/storage/time_series_store.py'
with open(file_ts, 'r') as f:
    content_ts = f.read()

# The shadowing occurs because the loop variable is `table` and it calls `table(table)`
# Let's import `table` as `sa_table`
content_ts = content_ts.replace('from sqlalchemy import and_, func, or_, text, select, delete, insert, update, table, column', 'from sqlalchemy import and_, func, or_, text, select, delete, insert, update, table as sa_table, column as sa_column')
content_ts = content_ts.replace('target_table = table(', 'target_table = sa_table(')
content_ts = content_ts.replace(', column(', ', sa_column(')

with open(file_ts, 'w') as f:
    f.write(content_ts)

# Fix data_retention.py archive_query invalid SQL
file_dr = 'backend/src/storage/data_retention.py'
with open(file_dr, 'r') as f:
    content_dr = f.read()

# Instead of using insert().from_select with incomplete column info, let's revert the archive query to text but without the nosec since it's hardcoded policy.
# Or better, we can use `text(f"INSERT INTO {archive_table} SELECT * FROM {policy.table_name} WHERE created_at < :cutoff_date")`
# since policy.table_name and archive_table are derived from hardcoded config/policies (internal), this is actually safe from SQLi.
# The previous version was using `from_select(["*"], select(...))` which is bad.
content_dr = re.sub(
    r'source_table = table\(policy\.table_name, column\("created_at"\)\)\n\s*target_table = table\(archive_table\)\n\s*archive_query = insert\(target_table\)\.from_select\(\["\*"\]\, select\(source_table\)\.where\(source_table\.c\.created_at < cutoff_date\)\)\n\s*db\.execute\(archive_query\)',
    r'archive_query = text(f"INSERT INTO {archive_table} SELECT * FROM {policy.table_name} WHERE created_at < :cutoff_date")\n                    db.execute(archive_query, {"cutoff_date": cutoff_date})',
    content_dr
)

with open(file_dr, 'w') as f:
    f.write(content_dr)
