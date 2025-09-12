# Mobasher Staging-Live Deployment Guide

This branch (`staging-live`) is configured for deployment with DigitalOcean managed services.

## Quick Start

1. **Copy the environment template:**
   ```bash
   cp .env.template .env
   ```

2. **Update `.env` with your actual DigitalOcean credentials:**
   - Replace all `your-*` placeholders with real values
   - Get credentials from DigitalOcean Control Panel > Databases

## Required DigitalOcean Managed Services

### PostgreSQL Database
- Service: DigitalOcean Managed PostgreSQL
- Version: PostgreSQL 12+ recommended
- SSL: Required (`DB_SSLMODE=require`)
- Default Port: 25060

### Redis Database  
- Service: DigitalOcean Managed Redis
- SSL: Required (`rediss://` protocol)
- Default Port: 25061

## Environment Variables to Update

Replace these placeholders in your `.env` file:

```bash
# PostgreSQL
DB_HOST=your-postgres-host.db.ondigitalocean.com      # Your actual PostgreSQL host
DB_USER=your-postgres-username                        # Your PostgreSQL username  
DB_PASSWORD=your-postgres-password                    # Your PostgreSQL password

# Redis
REDIS_URL=rediss://your-redis-username:your-redis-password@your-redis-host.db.ondigitalocean.com:25061
```

## Security Checklist

- [ ] Ensure your droplet IP is added to database trusted sources
- [ ] Verify SSL connections are working for both PostgreSQL and Redis
- [ ] Test database connectivity before running workers
- [ ] Keep `.env` file secure and never commit it to git

## Data Volume

The configuration expects data to be stored at:
```
MOBASHER_DATA_ROOT=/root/MediaView/mobasher/data
```

This should point to your mounted DigitalOcean volume for persistent storage.

## Installation & Deployment

1. **Install dependencies:**
   ```bash
   cd mobasher
   pip install -r requirements.txt
   ```

2. **Test database connection:**
   ```bash
   python -c "from mobasher.storage.db import init_engine; init_engine()"
   ```

3. **Initialize database:**
   ```bash
   # Run migrations if needed
   alembic upgrade head
   ```

4. **Start services:**
   ```bash
   # Start API server
   ./cli.py api serve --host 0.0.0.0 --port 8010
   
   # Start workers (in separate terminals)
   ./cli.py asr worker
   ./cli.py vision worker  
   ./cli.py nlp worker
   ```

## Monitoring

Prometheus metrics are available on these ports:
- ASR Worker: 9109
- NLP Worker: 9112

## Troubleshooting

1. **Database connection issues:**
   - Verify your droplet IP is in the database firewall rules
   - Check SSL requirements are met
   - Test connection manually with `psql` or `redis-cli`

2. **Permission issues:**
   - Ensure the data directory is writable
   - Check volume mount permissions

3. **Worker failures:**
   - Check Redis connectivity
   - Verify all environment variables are set
   - Review worker logs for specific errors

---

**Note:** This is a template setup. Always test thoroughly in a staging environment before production deployment.
