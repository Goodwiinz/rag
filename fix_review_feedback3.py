import re

file_ts = 'backend/src/storage/time_series_store.py'
with open(file_ts, 'r') as f:
    content_ts = f.read()

# Make sure sa_table and sa_column are imported
# Looks like the replacement failed or was not complete
content_ts = content_ts.replace('from sqlalchemy import and_, func, or_, text, select, delete, insert, update, table as sa_table, column as sa_column', 'from sqlalchemy import and_, func, or_, text, select, delete, table as sa_table, column as sa_column')

if 'table as sa_table, column as sa_column' not in content_ts:
    content_ts = content_ts.replace('from sqlalchemy import and_, func, or_, text, select, delete, insert, update, table, column', 'from sqlalchemy import and_, func, or_, text, select, delete, table as sa_table, column as sa_column')
    content_ts = content_ts.replace('from sqlalchemy import and_, func, or_, text, select, delete, table, column', 'from sqlalchemy import and_, func, or_, text, select, delete, table as sa_table, column as sa_column')

with open(file_ts, 'w') as f:
    f.write(content_ts)
