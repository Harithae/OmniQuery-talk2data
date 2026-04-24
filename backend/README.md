# OmniQuery Multi-Database Engine (Backend)

This backend system translates natural language questions into accurate SQL and NoSQL queries, executes them across multiple databases, and joins the results in-memory.

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.13+
- Node.js (for frontend)
- Databases: PostgreSQL, SQL Server, and MongoDB

### 2. Installation

#### Backend Setup
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### UI Setup
```powershell
cd frontend
npm install
```

### 3. Real-Time Configuration

#### Backend (`backend/.env`)
Create a `.env` file in the `backend` directory. (See example below).

#### UI (`frontend/src/app/chat.service.ts`)
Ensure the `apiUrl` matches your backend address:
```typescript
private apiUrl = 'http://localhost:8000/chat';
```

### 4. Environment Example (`backend/.env`)
```env
# LLM Provider
MODEL_PROVIDER=groq
MODEL_NAME=openai/gpt-oss-120b
GROQ_API_KEY=your_groq_api_key

# PostgreSQL (Sales Database)
POSTGRES_DB=SalesDB
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# SQL Server (Inventory Database)
SQLSERVER_CONNECTION_STRING="DRIVER={ODBC Driver 17 for SQL Server};SERVER=(localdb)\MSSQLLocalDB;DATABASE=InventoryDB;Trusted_Connection=yes;"

# MongoDB (Customer Database)
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=CustomerDB
```

---

## 🛠️ Running the Application

### The Unified Flow (Recommended)
The **Master Agent** orchestrates all steps automatically. This is what the frontend uses.
```powershell
python main.py
```
This starts the FastAPI server on `http://localhost:8000`.

**Start UI:**
```powershell
cd frontend
npm run dev
```
This starts the development server on `http://localhost:4200`.

If you want to run the pipeline manually for debugging:

1. **Extract DB Schema**:
   `python DBSchemaExtractor.py`
2. **Generate Query Plan**:
   `python multipleDB_QueryGenerator.py "Your question here"`
3. **Execute Queries**:
   `python QueryExecutor.py`
4. **Join Final Results**:
   `python DataJoiner.py`

---

## 📂 Project Structure
- `master_agent.py`: Orchestrates the sequential call of all scripts.
- `main.py`: FastAPI server for streaming results to the UI.
- `DBSchemas/`: Cached JSON schemas extracted from your databases.
- `llm_output.json`: The generated multi-DB query plan.
- `QueryOutput.json`: Raw results from each database.
- `FinalResult.json`: The final merged and projected result set.