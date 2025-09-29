# 🎯 EduMosaic Backend - India's No 1 Quiz Application

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-316192.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-ready, scalable backend for India's premier quiz application, built with FastAPI, PostgreSQL, and modern Python best practices.

## 🚀 Features

### Core Functionality
- **🔐 Advanced Authentication**: JWT-based auth with refresh tokens
- **👥 User Management**: Role-based access control (Student, Teacher, Admin)
- **📚 Quiz Management**: Create, edit, and manage quizzes with multiple question types
- **🏆 Leaderboards**: Real-time scoring and rankings
- **📊 Analytics**: Detailed performance tracking and insights
- **🌍 Multi-language Support**: 10+ Indian languages supported

### Technical Features
- **⚡ High Performance**: Async FastAPI with Redis caching
- **🔒 Security**: Rate limiting, CORS, password hashing
- **📈 Monitoring**: Sentry integration, Prometheus metrics
- **🖼️ Media Storage**: Cloudinary integration for images
- **📱 Mobile Ready**: Optimized for React Native Expo frontend

## 📖 API Documentation

Once running, access the interactive API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🛠️ Tech Stack

- **Framework**: FastAPI 0.111.0
- **Database**: PostgreSQL 13+ with SQLAlchemy ORM
- **Caching**: Redis (optional)
- **Authentication**: JWT with python-jose
- **File Storage**: Cloudinary
- **Monitoring**: Sentry, Prometheus
- **Deployment**: Render (Gunicorn + Uvicorn)

## 🏗️ Project Structure

```
edumosaic-backend/
├── app/
│   ├── api/           # API endpoints
│   │   └── v1/
│   │       └── endpoints/
│   ├── core/          # Core configuration
│   ├── db/            # Database setup
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   ├── utils/         # Utilities
│   └── middleware/    # Custom middleware
├── tests/             # Test suite
├── alembic/           # Database migrations
├── scripts/           # Utility scripts
└── requirements.txt   # Dependencies
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 13+
- Redis (optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/edumosaic-backend.git
cd edumosaic-backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize database**
```bash
alembic upgrade head
```

6. **Run the application**
```bash
uvicorn app.main:app --reload --port 8000
```

## 🌐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection URL | Yes |
| `SECRET_KEY` | JWT secret key | Yes |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name | Yes |
| `CLOUDINARY_API_KEY` | Cloudinary API key | Yes |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret | Yes |
| `REDIS_URL` | Redis connection URL | No |
| `SENTRY_DSN` | Sentry error tracking DSN | No |

## 🧪 Testing

Run the test suite:
```bash
pytest
```

With coverage:
```bash
pytest --cov=app tests/
```

## 🚢 Deployment

### Deploy to Render

1. Connect your GitHub repository to Render
2. Use the provided `render.yaml` for automatic configuration
3. Set environment variables in Render dashboard
4. Deploy!

### Manual Deployment

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

## 📊 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/refresh` - Refresh token

### Quizzes
- `GET /api/v1/quizzes` - List quizzes
- `GET /api/v1/quizzes/{id}` - Get quiz details
- `POST /api/v1/quizzes` - Create quiz (Teacher/Admin)
- `PUT /api/v1/quizzes/{id}` - Update quiz
- `POST /api/v1/quizzes/attempt` - Submit quiz attempt

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- FastAPI for the amazing framework
- The open-source community for invaluable tools and libraries
- Our users for making EduMosaic India's No 1 Quiz App

## 📞 Support

For support, email support@edumosaic.in or join our [Discord community](https://discord.gg/edumosaic).

---

**Made with ❤️ for students across India**
