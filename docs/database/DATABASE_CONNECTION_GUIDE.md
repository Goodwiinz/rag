# PostgreSQL Database Connection Guide

## 🎯 Your Database Details

**Connection Information:**
- **Host**: `localhost` (or `postgres` from within Docker containers)
- **Port**: `5432`
- **Database**: `ragdb`
- **Username**: `raguser`
- **Password**: `REDACTED`

**Connection String:**
```
postgresql://raguser:REDACTED@localhost:5432/ragdb
```

---

## 📊 Connection Methods

### Method 1: Using psql Command Line (Recommended)

```bash
# Connect from your host machine
psql -h localhost -p 5432 -U raguser -d ragdb

# When prompted, enter password: REDACTED

# Or use this one-liner (password in connection string)
PGPASSWORD=REDACTED psql -h localhost -p 5432 -U raguser -d ragdb
```

### Method 2: Using Docker Exec (If psql not installed locally)

```bash
# Connect from inside the container
docker exec -it rag-postgres-1 psql -U raguser -d ragdb

# No password needed when connecting from inside the container
```

### Method 3: Using GUI Tools

#### **DBeaver** (Free, Cross-platform)
1. Download from: https://dbeaver.io/download/
2. Create New Connection → PostgreSQL
3. Enter:
   - Host: `localhost`
   - Port: `5432`
   - Database: `ragdb`
   - Username: `raguser`
   - Password: `REDACTED`
4. Test Connection → Finish

#### **pgAdmin 4** (Free, Cross-platform)
1. Download from: https://www.pgadmin.org/download/
2. Right-click "Servers" → Register → Server
3. General Tab:
   - Name: `RAG System`
4. Connection Tab:
   - Host: `localhost`
   - Port: `5432`
   - Database: `ragdb`
   - Username: `raguser`
   - Password: `REDACTED`
5. Save

#### **TablePlus** (Paid, macOS/Windows)
1. Download from: https://tableplus.com/
2. Create New Connection → PostgreSQL
3. Enter connection details above
4. Test → Connect

#### **Postico** (macOS only)
1. Download from: https://eggerapps.at/postico/
2. New Favorite → Enter details
3. Connect

---

## 🔍 Quick Database Exploration

Once connected, try these commands:

### List All Tables
```sql
\dt
-- or
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

### Show Table Structure
```sql
\d table_name
-- or
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'your_table_name';
```

### Common Queries

```sql
-- List all databases
\l

-- List all schemas
\dn

-- Show current database
SELECT current_database();

-- Show current user
SELECT current_user;

-- List all tables with row counts
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_stat_get_live_tuples(c.oid) AS rows
FROM pg_tables t
JOIN pg_class c ON t.tablename = c.relname
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Show running queries
SELECT pid, usename, application_name, state, query 
FROM pg_stat_activity 
WHERE state != 'idle';
```

---

## 🐍 Connect from Python

### Using psycopg2

```python
import psycopg2

# Create connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="ragdb",
    user="raguser",
    password="REDACTED"
)

# Create cursor
cur = conn.cursor()

# Execute query
cur.execute("SELECT version();")
version = cur.fetchone()
print(f"PostgreSQL version: {version[0]}")

# Close connection
cur.close()
conn.close()
```

### Using SQLAlchemy (Your backend uses this)

```python
from sqlalchemy import create_engine, text

# Create engine
engine = create_engine(
    "postgresql://raguser:REDACTED@localhost:5432/ragdb"
)

# Test connection
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    print(result.fetchone()[0])
```

### Using asyncpg (Async)

```python
import asyncio
import asyncpg

async def connect():
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        database="ragdb",
        user="raguser",
        password="REDACTED"
    )
    
    version = await conn.fetchval("SELECT version()")
    print(f"PostgreSQL version: {version}")
    
    await conn.close()

asyncio.run(connect())
```

---

## 🔧 Troubleshooting

### Connection Refused

If you get "Connection refused":

```bash
# 1. Check if container is running
docker ps | grep postgres

# 2. Check if port is exposed
docker port rag-postgres-1

# 3. Check PostgreSQL logs
docker logs rag-postgres-1 --tail 50

# 4. Restart PostgreSQL container
docker restart rag-postgres-1
```

### Authentication Failed

If you get "Authentication failed":

```bash
# Verify password in .env file
cat .env | grep DB_PASSWORD

# Reset password (if needed)
docker exec -it rag-postgres-1 psql -U postgres -c "ALTER USER raguser PASSWORD 'new_password';"
```

### Database Does Not Exist

```bash
# List all databases
docker exec -it rag-postgres-1 psql -U raguser -l

# Create database if missing
docker exec -it rag-postgres-1 psql -U postgres -c "CREATE DATABASE ragdb OWNER raguser;"
```

### Too Many Connections

```sql
-- Check current connections
SELECT count(*) FROM pg_stat_activity;

-- Show max connections
SHOW max_connections;

-- Kill idle connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
AND pid <> pg_backend_pid();
```

---

## 📝 Database Maintenance

### Create Backup

```bash
# Backup database
docker exec -t rag-postgres-1 pg_dump -U raguser ragdb > backup_$(date +%Y%m%d_%H%M%S).sql

# Or with custom format (smaller, faster restore)
docker exec -t rag-postgres-1 pg_dump -U raguser -Fc ragdb > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Restore Backup

```bash
# Restore from SQL file
cat backup.sql | docker exec -i rag-postgres-1 psql -U raguser ragdb

# Restore from custom format
docker exec -i rag-postgres-1 pg_restore -U raguser -d ragdb < backup.dump
```

### Check Database Size

```sql
SELECT 
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'ragdb';
```

### Vacuum and Analyze

```sql
-- Full vacuum
VACUUM FULL VERBOSE;

-- Analyze tables
ANALYZE VERBOSE;

-- Both
VACUUM FULL ANALYZE VERBOSE;
```

---

## 🚀 Quick Start Commands

```bash
# Connect to database
docker exec -it rag-postgres-1 psql -U raguser -d ragdb

# Inside psql, try these:
\dt                    # List tables
\d table_name         # Describe table
\du                   # List users
\l                    # List databases
\q                    # Quit

# One-liner queries from host
PGPASSWORD=REDACTED psql -h localhost -U raguser -d ragdb -c "SELECT version();"
PGPASSWORD=REDACTED psql -h localhost -U raguser -d ragdb -c "\dt"
```

---

## 🔐 Security Notes

⚠️ **Important**: The credentials shown here are from your `.env` file. Never commit this file to version control!

Current `.env` has:
- Username: `raguser`
- Password: `REDACTED`
- Database: `ragdb`

For production, use:
- Strong passwords (20+ characters)
- Environment-specific credentials
- Secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- SSL/TLS connections

---

## 📚 Additional Resources

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
- [psql Command Reference](https://www.postgresql.org/docs/current/app-psql.html)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Docker PostgreSQL Image](https://hub.docker.com/_/postgres)

---

**Status**: ✅ Your PostgreSQL database is running and accessible on `localhost:5432`

**Quick Test**:
```bash
docker exec -it rag-postgres-1 psql -U raguser -d ragdb -c "SELECT 'Connection successful!' as status;"
```
