# OmniQuery: Multi-Database AI Intelligence 🚀

OmniQuery is a high-performance, context-aware NL2SQL engine designed to bridge the gap between fragmented data sources. It allows users to ask complex business questions in natural language and receive unified, joined results from **PostgreSQL**, **MS SQL Server**, and **MongoDB**.

---

## 🏗️ Architecture

The application follows a modular, pipeline-based architecture designed for scalability and intelligence:

*   **Frontend**: A modern Angular (v18) application providing a rich, responsive chat interface with real-time streaming capabilities.
*   **Backend API**: A FastAPI server that handles chat requests and orchestrates the AI agent logic.
*   **Master Agent**: A sophisticated orchestrator that manages the end-to-end pipeline from schema extraction to final data joining.
*   **Data Joiner**: An in-memory graph-based engine that merges SQL and NoSQL datasets using complex join logic.
*   **Data Layers**:
    *   **PostgreSQL**: Stores Sales and Order transaction data.
    *   **SQL Server**: Manages Inventory and Product stock datasets.
    *   **MongoDB**: Contains Customer profiles and address information.

---

## ✨ Core Features

*   **Natural Language Data Querying**: Query complex datasets without knowing SQL or NoSQL syntax.
*   **Multi-Database Support**: Securely interact with three different database types through a single interface.
*   **Real-Time Streaming**: Tokens and tool activity events are streamed to the UI using NDJSON for a "live" feel.
*   **Persistent Schema Architecture**: Optimized schema extraction reduces token usage and improves response time.
*   **Automatic UI Cleanliness**: Intelligently hides technical IDs and normalizes headers for a business-ready presentation.

---

## 🛠️ Setup & Installation

### Prerequisites
*   **Python 3.13+**
*   **Node.js (LTS)** & **npm**
*   **PostgreSQL**, **SQL Server**, and **MongoDB** (Running locally or accessible via URI)

### Backend Setup
1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```
2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Frontend Setup
1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```
2. **Install dependencies**:
   ```bash
   npm install
   ```

---

## 🚀 Running the Application

1. **Start the FastAPI Backend**: From the `backend` directory:
   ```bash
   python main.py
   ```
   The API will run on `http://localhost:8000`.

2. **Start the Frontend**: From the `frontend` directory:
   ```bash
   npm start
   ```
   The app will be available at `http://localhost:4200`.

---

## ⚙️ Environment Variables (Backend)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | API Key for Groq (Llama 3 inference) | - |
| `MODEL_NAME` | The model identifier (e.g., `llama3-70b-8192`) | `llama3-70b-8192` |
| `POSTGRES_DB` | Sales Database Name | `SalesDB` |
| `SQL_DB_CONN` | SQL Server connection string for Inventory | - |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017/` |

---

## ⚖️ License
Internal Proprietary Project - OmniQuery Team.
