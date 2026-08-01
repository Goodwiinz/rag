import re

file_ts = 'backend/src/storage/time_series_store.py'
with open(file_ts, 'r') as f:
    content_ts = f.read()

# Fix the hacky mock object: `count_result = type('obj', (object,), {'count': count_result[0] if count_result else 0})`
# The original code did `count_result = db.execute(text(count_sql)).first()`, which returns a Row. We access `.count` on it.
# Wait, SQLAlchemy Core func.count() returns a row where we can access count by index or label. Let's label it.
content_ts = content_ts.replace(
    '''                count_query = select(func.count()).select_from(sa_table(table))
                count_result = db.execute(count_query).first()
                count_result = type('obj', (object,), {'count': count_result[0] if count_result else 0})''',
    '''                count_query = select(func.count().label('count')).select_from(sa_table(table))
                count_result = db.execute(count_query).first()'''
)

with open(file_ts, 'w') as f:
    f.write(content_ts)
