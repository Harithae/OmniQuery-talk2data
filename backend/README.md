1. **Create and activate a virtual environment**:
   python -m venv venv
   .\venv\Scripts\Activate.ps1  

2. **Install required packages**: 
pip install -r requirements.txt

3. **Extract DB schema**:
python .\DBSchemaExtractor.py

4. **Generate SQL query**:
python .\multipleDB_QueryGenerator.py

5. **Execute SQL query**:
python .\QueryExecutor.py

6. **Joining the final results**:
python .\DataJoiner.py