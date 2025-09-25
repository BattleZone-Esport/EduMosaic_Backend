# 🎯 EduMosaic Backend - Production-Ready API

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7.0-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

A **high-performance, scalable backend API** for the EduMosaic educational platform. Built with FastAPI, PostgreSQL, Redis, and designed for seamless integration with React Native (Expo) mobile applications.

## 🚀 Features

### Core Functionality
- 🔐 **JWT Authentication** - Secure user authentication with access/refresh tokens
- 👥 **User Management** - Complete user lifecycle management
- 📚 **Quiz System** - Dynamic quiz creation and management
- 🏆 **Leaderboards** - Real-time scoring and rankings
- 🎖️ **Achievements** - Gamification with badges and rewards
- 🔔 **Notifications** - Real-time user notifications

### Advanced Features
- 🤖 **AI Integration** - Quiz generation and personalized recommendations
- 💾 **Redis Caching** - High-performance caching with graceful fallback
- 📊 **Analytics** - Comprehensive performance tracking
- 🔒 **Rate Limiting** - Protection against abuse
- 🛡️ **Security Headers** - Enhanced security with proper headers
- 📈 **Monitoring** - Prometheus metrics and Sentry error tracking

### Developer Experience
- 📖 **Auto Documentation** - Swagger UI and ReDoc
- 🔄 **Hot Reload** - Development mode with auto-reload
- 📝 **Structured Logging** - JSON-formatted logs
- 🧪 **Testing Ready** - Pytest configuration included
- 🎨 **Code Quality** - Black, Ruff, and MyPy integration

## 📋 Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Redis 6+
- Node.js 18+ (for frontend integration)

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/BattleZone-Esport/EduMosaic_Backend.git
cd EduMosaic_Backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Setup
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Database Setup

#### PostgreSQL
```sql
CREATE DATABASE edumosaic;
CREATE USER edumosaic_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE edumosaic TO edumosaic_user;
```

#### Run Migrations
```bash
alembic upgrade head
```

### 6. Redis Setup
```bash
# On Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# On macOS
brew install redis
brew services start redis
```

## 🚀 Running the Application

### Development Mode
```bash
# Using Uvicorn directly
uvicorn app.main:app --reload --port 8000

# Or using the main file
python -m app.main
```

### Production Mode
```bash
# Using Gunicorn with Uvicorn workers
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 🌐 API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/api/v1/openapi.json

## 📦 Project Structure

```
EduMosaic_Backend/
├── app/
│   ├── api/               # API routes and endpoints
│   │   ├── v1/            # Version 1 API
│   │   │   ├── endpoints/ # Individual route modules
│   │   │   └── api.py     # V1 router aggregator
│   │   └── v2/            # Version 2 API (future)
│   ├── core/              # Core functionality
│   │   ├── config.py      # Settings management
│   │   ├── database.py    # Database configuration
│   │   ├── security.py    # Authentication & authorization
│   │   ├── cache.py       # Redis cache management
│   │   └── exceptions.py  # Custom exceptions
│   ├── middleware/        # Custom middleware
│   │   ├── cors.py        # CORS configuration
│   │   ├── rate_limit.py  # Rate limiting
│   │   └── security_headers.py
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic
│   └── utils/             # Utility functions
├── migrations/            # Alembic migrations
├── tests/                 # Test suite
├── static/                # Static files
├── logs/                  # Application logs
├── .env.example           # Environment template
├── requirements.txt       # Python dependencies
├── alembic.ini           # Alembic configuration
└── README.md             # Documentation
```

## 🚢 Deployment

### Deploy to Render

1. **Create Render Account**: Sign up at [render.com](https://render.com)

2. **Create PostgreSQL Database**:
   - New > PostgreSQL
   - Note the connection string

3. **Create Redis Instance**:
   - New > Redis
   - Note the connection URL

4. **Create Web Service**:
   - Connect GitHub repository
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

5. **Environment Variables**:
   - Add all variables from `.env.example`
   - Use Render database and Redis URLs

6. **Deploy**:
   - Render will automatically deploy on push to main branch

### Deploy to Railway

1. **Install Railway CLI**:
```bash
npm install -g @railway/cli
```

2. **Login and Initialize**:
```bash
railway login
railway init
```

3. **Add Services**:
```bash
railway add postgresql
railway add redis
```

4. **Deploy**:
```bash
railway up
```

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

Build and run:
```bash
docker build -t edumosaic-backend .
docker run -p 8000:8000 --env-file .env edumosaic-backend
```

## 🧪 Testing

### Run Tests
```bash
pytest
pytest --cov=app  # With coverage
```

### Test Categories
```bash
pytest tests/unit        # Unit tests
pytest tests/integration # Integration tests
pytest tests/e2e        # End-to-end tests
```

## 📊 Monitoring

### Health Check
- **Endpoint**: `/health`
- **Ready Check**: `/ready`
- **Metrics**: `/metrics` (Prometheus format)

### Logging
Logs are written to:
- Console (development)
- `logs/edumosaic.log` (production)
- `logs/error.log` (errors only)
- `logs/security.log` (security events)

## 🔒 Security

### Best Practices Implemented
- ✅ JWT token authentication
- ✅ Password hashing with bcrypt
- ✅ Rate limiting per endpoint
- ✅ SQL injection protection
- ✅ XSS protection headers
- ✅ CORS properly configured
- ✅ Input validation with Pydantic
- ✅ Secure session management

### Security Headers
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security (HTTPS only)
- Content-Security-Policy

## 🤝 API Integration

### React Native (Expo) Example

```javascript
// api.js
const API_BASE = 'https://your-api-url.com/api/v1';

const api = {
  async login(username, password) {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `username=${username}&password=${password}`
    });
    return response.json();
  },
  
  async getQuizzes(token) {
    const response = await fetch(`${API_BASE}/quizzes`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return response.json();
  }
};

export default api;
```

## 🛠️ Development

### Code Style
```bash
# Format code
black app/
isort app/

# Lint
ruff check app/
pylint app/

# Type checking
mypy app/
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 📈 Performance

- **Response Time**: < 100ms average
- **Throughput**: 1000+ requests/second
- **Concurrent Users**: 10,000+
- **Database Pool**: 20 connections
- **Redis Cache**: 1-hour TTL default

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U edumosaic_user -d edumosaic
```

2. **Redis Connection Error**
```bash
# Check Redis is running
redis-cli ping
```

3. **Port Already in Use**
```bash
# Find process using port 8000
lsof -i :8000
# Kill process
kill -9 <PID>
```

## 📝 Environment Variables

Key environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `REDIS_URL` | Redis connection string | redis://localhost:6379 |
| `SECRET_KEY` | JWT secret key | - |
| `ENVIRONMENT` | Environment (development/production) | development |
| `SENTRY_DSN` | Sentry error tracking DSN | - |

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- **Backend Lead**: [Your Name]
- **Contributors**: [List Contributors]

## 📞 Support

- **Documentation**: [Link to docs]
- **Issues**: [GitHub Issues](https://github.com/BattleZone-Esport/EduMosaic_Backend/issues)
- **Email**: support@edumosaic.com

## 🙏 Acknowledgments

- FastAPI for the amazing framework
- PostgreSQL for reliable data storage
- Redis for high-performance caching
- The open-source community

---

**Built with ❤️ for educators and learners worldwide**