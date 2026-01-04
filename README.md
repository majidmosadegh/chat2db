# SQL PT - Professional SQL Prompt Tuning

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/your-repo/sql-pt)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node.js-16+-green.svg)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Enterprise-Grade SQL Query Generation & Optimization Platform**

SQL PT is a professional platform for generating optimized SQL queries using advanced AI models. Built with Clean Architecture and Domain-Driven Design principles.

## 🚀 Quick Start

### ✅ LATEST UPDATES: Project Fully Organized!

#### **Recent Improvements:**
- ✅ **Test Organization**: All test files moved to proper directories
- ✅ **Clean Architecture**: Implemented Domain-Driven Design
- ✅ **File Structure**: Backend tests consolidated in `backend/tests/` (65 files)
- ✅ **Integration Tests**: Root-level tests moved to `tests/` directory
- ✅ **Dependency Management**: Resolved all circular import issues
- ✅ **API Structure**: All routers properly exported and configured
- ✅ **Database Layer**: Clean separation of concerns implemented
- ✅ **Configuration**: Centralized config management
- ✅ **Virtual Environments**: Separate venvs for backend and frontend
- ✅ **Launcher Scripts**: Comprehensive batch files with error handling

### One-Click Launch (Recommended)
```bash
# Double-click this file to start everything automatically
START_PRODUCT.bat
```

This will automatically:
- ✅ Setup Python virtual environment
- ✅ Install all dependencies
- ✅ Start backend API server (port 8000) with logs visible
- ✅ Start frontend web interface (port 3000)

### Individual Server Launch (For Development)

#### Backend Only (with logs)
```bash
# Run backend server only with visible logs
start-backend.bat
```
- Shows all backend logs in terminal
- Perfect for debugging API issues
- Runs on http://localhost:8000

#### Frontend Only
```bash
# Run frontend server only
start-frontend.bat
```
- Runs React/Next.js development server
- Runs on http://localhost:3000

## 📁 Project Structure

```
sql_pt/
├── backend/                      # FastAPI Backend Application
│   ├── api/                      # REST API Endpoints
│   │   ├── ai_dictionary.py      # AI Dictionary Generation
│   │   ├── data_dictionary.py    # Data Dictionary Management
│   │   ├── database.py           # Database Operations
│   │   ├── llm.py               # LLM Integration
│   │   └── text_generation.py    # Text Generation Services
│   ├── chat/                     # Chat/Conversation Engine
│   │   ├── engine/               # Chat Processing Logic
│   │   └── router.py             # Chat API Router
│   ├── core/                     # Core Application Components
│   ├── db/                       # Database Layer
│   ├── llm/                      # Large Language Model Providers
│   ├── services/                 # Business Logic Services
│   ├── config/                   # Configuration Management
│   ├── tests/                    # Backend Unit Tests (65 files)
│   ├── scripts/                  # Maintenance Scripts
│   └── logs/                     # Application Logs
├── frontend/                     # Next.js Web Interface
│   ├── app/                      # Next.js App Router Pages
│   ├── components/               # React Components
│   ├── lib/                      # Utility Libraries
│   └── config/                   # Frontend Configuration
├── src/                          # Clean Architecture Implementation
│   ├── domain/                   # Domain Entities & Business Rules
│   ├── application/              # Use Cases & Application Services
│   ├── infrastructure/           # External Services & Repositories
│   └── presentation/             # API Controllers & DTOs
├── tests/                        # Integration & E2E Tests
│   ├── test_ai_generation.py     # AI Generation Tests
│   ├── test_db.py               # Database Tests
│   └── test_request.json         # Test Data
├── venv/                         # Python Virtual Environment
├── frontend/venv/               # Frontend Virtual Environment
├── *.bat                         # Windows Launcher Scripts
├── *.ps1                         # PowerShell Scripts
├── requirements.txt             # Python Dependencies
├── README.md                    # Project Documentation
└── START_SERVERS_README.md      # Server Startup Guide
```

## 🧪 Testing Structure

The project maintains a comprehensive test suite organized as follows:

### Backend Unit Tests (`backend/tests/`)
- **65 test files** covering all backend functionality
- Unit tests for API endpoints, services, and utilities
- Database connection and operation tests
- AI/LLM integration tests
- Chat engine and conversation flow tests

### Integration Tests (`tests/`)
- End-to-end API testing scripts
- Database integration tests
- Request/response validation tests
- Cross-service integration tests

### Test Categories
- **API Tests**: REST endpoint functionality
- **Database Tests**: Connection, queries, and data operations
- **AI Tests**: LLM integration and prompt generation
- **Chat Tests**: Conversation engine and routing
- **Integration Tests**: Full workflow validation

### Running Tests
```bash
# Run all backend tests
cd backend
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_api*.py -v
python -m pytest tests/test_db*.py -v
python -m pytest tests/test_chat*.py -v

# Run integration tests
cd tests
python test_ai_generation.py
python test_db.py
```

### Development Commands
```bash
# Backend development
cd backend
python main.py                    # Start FastAPI server
python -m pytest tests/ -v       # Run all tests
python test_simple.py            # Quick functionality test

# Frontend development
cd frontend
npm run dev                      # Start Next.js dev server
npm run build                    # Build for production
npm run lint                     # Code linting

# Database utilities
cd backend
python check_db.py               # Check database connection
python list_tables.py            # List database tables
```

## 🎯 Features

### Core Capabilities
- 🤖 **AI-Powered SQL Generation** - Generate optimized SQL using GPT-4, Claude, Ollama
- 📊 **Multi-Database Support** - PostgreSQL, MySQL, SQL Server, Oracle
- 🔒 **Enterprise Security** - Encrypted connections, secure API keys
- 📈 **Performance Monitoring** - Query execution tracking, optimization suggestions
- 🎨 **Modern Web Interface** - Beautiful, responsive UI with real-time updates

### Advanced Features
- 🎯 **Domain-Specific Optimization** - Business context-aware query generation
- 🔄 **Real-time Collaboration** - Multi-user editing and review workflows
- 📋 **Template Management** - Reusable query templates and patterns
- 📊 **Analytics Dashboard** - Usage metrics, performance insights
- 🔗 **API Integration** - RESTful APIs for seamless integration

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.8+)
- **Architecture**: Clean Architecture + Domain-Driven Design
- **Database**: SQLAlchemy + SQLite/PostgreSQL/MySQL/SQL Server
- **AI Integration**: OpenAI GPT, Anthropic Claude, Ollama, Local LLMs
- **Async Support**: aioodbc, aiomysql, asyncpg
- **Security**: Cryptography, API Key Management
- **Logging**: Structured logging with loguru
- **Testing**: Comprehensive pytest suite (65+ tests)

### Frontend
- **Framework**: Next.js 14 (React with TypeScript)
- **Styling**: Tailwind CSS + Custom Design System
- **State Management**: React Context + Custom Hooks
- **UI Components**: Radix UI + Custom Component Library
- **Forms**: React Hook Form with validation
- **API Client**: Custom hooks for API integration
- **Build Tool**: Next.js with TypeScript

### Infrastructure
- **Containerization**: Docker (planned)
- **Orchestration**: Kubernetes (planned)
- **CI/CD**: GitHub Actions (planned)
- **Monitoring**: Prometheus + Grafana (planned)

## 📋 Prerequisites

- **Python 3.8+** - Backend runtime (3.13 recommended)
- **Node.js 16+** - Frontend build tools (18+ recommended)
- **Git** - Version control
- **Windows PowerShell** - For automation scripts
- **Database** - PostgreSQL/MySQL/SQL Server/Oracle (SQLite included for development)
- **AI API Keys** - OpenAI or Anthropic API keys (optional, Ollama for local AI)

## 🚀 Installation & Setup

### Option 1: One-Click Setup (Recommended)
```bash
# Simply run the launcher
START_PRODUCT.bat
```

### Option 2: Manual Setup

#### Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install dependencies (virtual environment handled automatically)
pip install -r requirements.txt

# Start development server
python main.py
```
**Note**: The project uses automatic virtual environment management through batch files.

#### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

#### Database Setup (Optional)
The project includes SQLite by default. For production databases:

1. **PostgreSQL**: Install PostgreSQL and update connection string
2. **MySQL**: Install MySQL and configure connection
3. **SQL Server**: Install SQL Server drivers and configure

Database configuration is handled in `backend/config/config.py`.

## 🎮 Usage

### Web Interface
1. **Access Application**: Open http://localhost:3000
2. **Database Connection**: Configure database connections
3. **Schema Management**: Upload or define database schemas
4. **AI Dictionary**: Generate intelligent data dictionaries
5. **Query Generation**: Create optimized SQL queries with AI
6. **Chat Interface**: Interactive SQL assistance and optimization

### API Endpoints

#### Core APIs
- `GET/POST /api/data-dictionary` - Data dictionary management
- `POST /api/ai/dictionary/generate` - AI-powered dictionary generation
- `POST /api/text-generation/generate` - Text generation services
- `GET/POST /api/database/connections` - Database connection management
- `POST /api/chat` - Interactive chat for SQL assistance

#### Advanced Features
- **Schema Analysis**: Automatic schema understanding and documentation
- **Relationship Detection**: Foreign key and relationship mapping
- **Use Case Generation**: Business context-aware query templates
- **Performance Monitoring**: Query execution tracking and optimization

### Development Workflow
1. **Setup Environment**: Run `START_PRODUCT.bat` for complete setup
2. **Database Connection**: Configure your target database
3. **Schema Upload**: Import database schema or define manually
4. **AI Configuration**: Set up API keys for OpenAI/Anthropic or use local Ollama
5. **Generate Queries**: Use AI assistance for complex SQL generation
6. **Test & Optimize**: Execute queries and review performance metrics

## 📚 Documentation

- 📖 **[User Guide](docs/guides/)** - Complete user manual
- 🔧 **[API Documentation](docs/api/)** - REST API reference
- 💡 **[Examples](docs/examples/)** - Sample queries and templates
- 🐛 **[Server Setup Guide](START_SERVERS_README.md)** - Server startup instructions
- 🔧 **[Backend Services](backend/services/README.md)** - Service layer documentation
- 🧪 **[Testing Guide](tests/)** - Test execution and development

## 🔧 Troubleshooting

### Common Issues

#### Backend Issues
- **Port 8000 already in use**: Kill process using `netstat -ano | findstr :8000` then `taskkill /PID <PID>`
- **Database connection failed**: Check database credentials in `backend/config/config.py`
- **Import errors**: Ensure virtual environment is activated: `backend\venv\Scripts\activate`
- **AI API errors**: Verify API keys are set in environment variables

#### Frontend Issues
- **Port 3000 already in use**: Kill process or change port in `frontend/package.json`
- **Build errors**: Clear cache with `rm -rf frontend/.next` and `npm install`
- **API connection failed**: Ensure backend is running on port 8000

#### Database Issues
- **SQL Server connection**: Install `pyodbc` drivers and check connection string
- **Permission denied**: Ensure database user has proper permissions
- **Connection timeout**: Check firewall settings and network connectivity

### Logs Location
- **Backend logs**: `backend/logs/` directory
- **Frontend logs**: Browser developer console
- **System logs**: Check batch file outputs for startup issues

## 🔧 Development

### Project Setup for Contributors
```bash
# Clone repository
git clone <repository-url>
cd sql_pt

# One-click setup (recommended)
START_PRODUCT.bat

# Or manual setup
# Backend setup
cd backend
pip install -r requirements.txt
python main.py

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev

# Run tests
cd backend
python -m pytest tests/ -v
```

### Code Quality
```bash
# Backend linting and formatting
cd backend
pip install black flake8 mypy
black .                          # Format code
flake8 .                         # Lint code
mypy .                           # Type checking

# Frontend linting
cd frontend
npm run lint                     # ESLint
npm run type-check              # TypeScript checking
```

### Architecture Overview
This project follows **Clean Architecture** principles:
- **Domain Layer**: Core business logic
- **Application Layer**: Use cases and orchestration
- **Infrastructure Layer**: External dependencies
- **Presentation Layer**: User interfaces

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Workflow
1. **Fork** the repository
2. **Clone** your fork: `git clone <your-fork-url>`
3. **Create** feature branch: `git checkout -b feature/your-feature`
4. **Setup** environment: Run `START_PRODUCT.bat`
5. **Make changes** with proper tests
6. **Run tests**: `cd backend && python -m pytest tests/ -v`
7. **Commit**: `git commit -m "Add: your feature description"`
8. **Push**: `git push origin feature/your-feature`
9. **Create Pull Request**

### Code Standards
- **Backend**: Follow PEP 8, add type hints, write comprehensive tests
- **Frontend**: Use TypeScript, follow React best practices
- **Tests**: Maintain >80% coverage, test both happy path and error cases
- **Documentation**: Update README and docstrings for new features

### Areas for Contribution
- 🔧 **Database Connectors**: Add support for new database types
- 🤖 **AI Providers**: Integrate new LLM providers (Gemini, Mistral, etc.)
- 🎨 **UI Components**: Improve frontend user experience
- 📊 **Analytics**: Add query performance metrics and insights
- 🌐 **Internationalization**: Add multi-language support
- 📱 **Mobile Support**: Responsive design improvements

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋 Support & Community

### Getting Help
- 🐛 **Bug Reports**: [Create an Issue](https://github.com/your-repo/sql-pt/issues)
- 💡 **Feature Requests**: [Create an Issue](https://github.com/your-repo/sql-pt/issues)
- 📧 **General Questions**: Check existing issues first

### Documentation
- 📖 **[Setup Guide](START_SERVERS_README.md)** - Complete server setup
- 🔧 **[API Docs](backend/api/)** - Backend API documentation
- 🧪 **[Testing](backend/tests/)** - Test suite documentation

## 🏢 About SQL PT

**SQL PT (Professional SQL Prompt Tuning)** is an enterprise-grade platform that revolutionizes SQL development through:

- **🤖 AI-Powered Intelligence**: Advanced LLM integration for natural language to SQL conversion
- **🏗️ Clean Architecture**: Domain-Driven Design with proper separation of concerns
- **🔒 Enterprise Security**: Secure database connections and encrypted API communications
- **📈 Performance Focus**: Query optimization and execution monitoring
- **🎯 Business Alignment**: Domain-specific query generation and use case building

### Technology Philosophy
Built with modern development practices:
- **Clean Architecture** for maintainability
- **Domain-Driven Design** for business alignment
- **Test-Driven Development** for reliability
- **Microservices Architecture** for scalability

---

**🚀 Ready to transform your SQL development workflow?**

**[Get Started Now](START_PRODUCT.bat)** | **[Explore the Code](backend/)** | **[Run Tests](backend/tests/)**