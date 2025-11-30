## Project Overview

AITTA is an Agentic AI system that automatically triages incidents from Splunk alerts and creates high-quality Jira tickets. The agent uses multiple MCP (Model Context Protocol) servers to:

1. Query Splunk logs for incident details
2. Enrich context from CMDB (asset ownership, dependencies)
3. Analyze with LLM (Gemini/Claude) for intelligent triage
4. Create Jira tickets with proper priority and assignment

## Installation
 1. Prerequisites

- Python 3.10+
- Node.js (for MCP CLI tools, optional)
- Splunk instance (or use mock data)
- Jira instance (or use mock data)

 2. Install Dependencies

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt


### 3. Configuration

Create a `.env` file:

env
# LLM Configuration
GEMINI_API_KEY=your-gemini-api-key
# Or use Claude
# ANTHROPIC_API_KEY=your-claude-api-key

# Splunk Configuration
SPLUNK_HOST=https://your-splunk.com:8089
SPLUNK_TOKEN=your-splunk-token

# Jira Configuration
JIRA_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-token

# CMDB Configuration (if using external CMDB)
CMDB_API_URL=https://your-cmdb-api.com

## Running the Application
### 1. Start the Backend

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### 2. Open the Frontend

Simply open `index.html` in your browser, or serve it:

```bash
# Using Python's built-in server
python -m http.server 8080
# Then open http://localhost:8080
```

### 3. Test the Agent
or use http://localhost:8000/docs 
Send a test alert:
curl -X 'POST' \
  'http://localhost:8000/api/process-alert' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "alert_id": "alert-001",
  "severity": "High",
  "message": "CPU usage above 95%",
  "host": "prod-web-03",
  "timestamp": "2025-11-21T02:10:31.484Z",
  "metadata": {}
}'


##  API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics` | GET | Dashboard metrics |
| `/api/agent-activity` | GET | Recent agent actions |
| `/api/incident-patterns` | GET | Top incident patterns |
| `/api/ticket-timeline` | GET | Ticket creation timeline |
| `/api/process-alert` | POST | Process new alert (main agent workflow) |
| `/api/mcp/tools/{server}` | GET | List MCP server tools |

## 🧪 Testing MCP Servers Independently

Each MCP server can be tested independently:

```bash
# Test Splunk server
python mcp_servers/splunk_server.py

# Test Jira server
python mcp_servers/jira_server.py

# Test CMDB server
python mcp_servers/cmdb_server.py