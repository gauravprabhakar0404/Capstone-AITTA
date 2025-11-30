# AITTA Setup Guide
## Automated Incident Triage & Ticketing Agent

This guide will help you set up and configure AITTA to work with Jira, Splunk, and CMDB systems for a complete enterprise incident management solution.

---

## 📋 Prerequisites

- Python 3.11+
- Docker (optional, for containerized deployment)
- Access to enterprise systems (Jira, Splunk, CMDB) or mock mode for testing

---

## 🚀 Quick Start (Mock Mode)

For immediate testing without enterprise system access:

```bash
# Clone the repository
git clone https://github.com/gauravprabhakar0404/Capstone-AITTA.git
cd Capstone-AITTA

# Install dependencies
pip install -r requirements.txt

# Run in mock mode (no external dependencies)
python app.py
```

The application will start on `http://localhost:8000` with all integrations in mock mode.

---

## ⚙️ Environment Configuration

### 1. Create .env file

Create a `.env` file in the project root with your enterprise system credentials:

```bash
# AITTA Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
API_KEY=your-secure-api-key-here

# Mock Mode (set to true for testing without enterprise systems)
USE_MOCK_JIRA=false
USE_MOCK_SPLUNK=false
USE_MOCK_CMDB=false

# Jira Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-jira-username@company.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=PROJ

# Splunk Configuration
SPLUNK_HOST=https://your-splunk-server:8089
SPLUNK_USERNAME=your-splunk-username
SPLUNK_PASSWORD=your-splunk-password
SPLUNK_TOKEN=your-splunk-hec-token  # For event ingestion
SPLUNK_HEC_URL=https://your-splunk-server:8088
SPLUNK_VERIFY_SSL=true

# ServiceNow/CMDB Configuration
CMDB_BASE_URL=https://your-servicenow-instance.service-now.com
CMDB_USERNAME=your-servicenow-username
CMDB_PASSWORD=your-servicenow-password

# LLM Configuration (choose one or both)
LLM_PROVIDER=gemini  # or 'claude'
GEMINI_API_KEY=your-gemini-api-key
ANTHROPIC_API_KEY=your-claude-api-key

# Agent Configuration
AGENT_LOG_TIMERANGE=30  # minutes to look back for logs
```

### 2. Generate API Tokens

#### Jira API Token
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Create new API token
3. Copy the token to `JIRA_API_TOKEN`

#### Splunk HEC Token
1. In Splunk Web: Settings → Data Inputs → HTTP Event Collector
2. Create new token with sourcetype `aitta:test`
3. Copy token to `SPLUNK_TOKEN`

#### ServiceNow Personal Access Token
1. In ServiceNow: User menu → Personal Access Tokens
2. Create new token with necessary permissions
3. Copy to `CMDB_PASSWORD`

---

## 🔧 Jira Setup

### 1. Create Jira Project

```bash
# Create a project for incident tickets
# Project Key: PROJ (or your preferred key)
# Project Name: AITTA Incidents
# Issue Types: Bug, Task, Story
```

### 2. Configure Custom Fields (Optional)

Add these custom fields to your project for better incident tracking:

- **Incident Severity**: Single-select (Critical, High, Medium, Low)
- **Affected Host**: Single-line text
- **Root Cause**: Multi-line text
- **Business Impact**: Single-select (High, Medium, Low)

### 3. Set Up Automation Rules (Optional)

Create Jira automation rules:
- When issue created with label "incident" → Notify SRE team
- When priority = Critical → Escalate immediately

### 4. Test Jira Connection

```bash
# Test Jira integration
curl -X POST "http://localhost:8000/api/process-alert" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "alert_id": "test-001",
    "severity": "High",
    "message": "Test alert for Jira integration",
    "host": "test-server-01",
    "timestamp": "2025-11-30T12:00:00Z"
  }'
```

Expected: Jira ticket created successfully.

---

## 📊 Splunk Setup

### 1. Configure HTTP Event Collector (HEC)

```bash
# In Splunk Web Interface:
# 1. Go to Settings → Data Inputs → HTTP Event Collector
# 2. Click "New Token"
# 3. Name: AITTA Events
# 4. Source Type: aitta:test
# 5. Index: main (or your preferred index)
# 6. Copy the token value
```

### 2. Create Splunk Index (Optional)

```bash
# Create dedicated index for AITTA
| createdb index=aitta_events
```

### 3. Configure Search Permissions

Ensure your Splunk user has permissions to:
- Search all indexes (`search` capability)
- Access the HEC endpoint (`edit_tcp` capability)

### 4. Generate Sample Log Data

For testing, you can ingest sample logs:

```bash
# Send test event via HEC
curl -k https://your-splunk-server:8088/services/collector \
  -H "Authorization: Splunk YOUR_TOKEN" \
  -d '{"event": {"message": "Test error log", "host": "test-server-01", "level": "ERROR"}, "sourcetype": "aitta:test"}'
```

### 5. Test Splunk Connection

```bash
# Test Splunk integration
curl -X POST "http://localhost:8000/api/scan-and-alert?time_range=1h" \
  -H "X-API-Key: your-api-key"
```

Expected: Splunk logs retrieved and alerts processed.

---

## 🏗️ ServiceNow/CMDB Setup

### 1. Create Integration User

In ServiceNow:
1. Create dedicated user: `aitta_integration`
2. Assign roles: `incident_manager`, `cmdb_read`, `cmdb_write`
3. Generate personal access token

### 2. Configure Incident Table

Ensure your incident table has these fields:
- **short_description**: String (255 chars)
- **description**: String (4000 chars)
- **urgency**: Choice (1=High, 2=Medium, 3=Low)
- **impact**: Choice (1=High, 2=Medium, 3=Low)
- **assignment_group**: Reference to sys_user_group

### 3. Create Assignment Groups

```javascript
// In ServiceNow background script
var gr = new GlideRecord('sys_user_group');
gr.initialize();
gr.name = 'SRE Team';
gr.description = 'Site Reliability Engineering';
gr.insert();
```

### 4. Configure Business Rules (Optional)

Create business rules for incident routing:
- When urgency = 1 AND impact = 1 → Auto-assign to SRE Lead
- When short_description CONTAINS "critical" → Set VIP flag

### 5. Test ServiceNow Connection

```bash
# Test CMDB/ServiceNow integration
curl -X POST "http://localhost:8000/api/process-alert" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "alert_id": "servicenow-test-001",
    "severity": "Critical",
    "message": "Critical database connection failure",
    "host": "prod-db-01",
    "timestamp": "2025-11-30T12:00:00Z"
  }'
```

Expected: ServiceNow incident created successfully.

---

## 🐳 Docker Deployment

### 1. Build Docker Image

```bash
# Build the image
docker build -t Capstone-AITTA:latest .

# Run with environment variables
docker run -d \
  --name Capstone-AITTA \
  -p 8000:8000 \
  --env-file .env \
  Capstone-AITTA:latest
```

### 2. Docker Compose (Production)

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  Capstone-AITTA:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  database:
    image: postgres:15
    environment:
      POSTGRES_DB: aitta
      POSTGRES_USER: aitta
      POSTGRES_PASSWORD: your-db-password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### 3. Kubernetes Deployment

For production Kubernetes deployment:

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Check pod status
kubectl get pods -l app=Capstone-AITTA

# View logs
kubectl logs -l app=Capstone-AITTA
```

---

## 🧪 Testing & Validation

### 1. Health Check

```bash
curl http://localhost:8000/
# Expected: {"message": "AITTA API is running", ...}
```

### 2. API Documentation

```bash
# OpenAPI documentation
open http://localhost:8000/docs
```

### 3. Integration Tests

```bash
# Run all tests
python -m pytest test/ -v

# Test specific integration
python -m pytest test/test_mcp_jiraserver.py -v
python -m pytest test/test_mcp_splunkserver.py -v
python -m pytest test/test_mcp_cmdbserver.py -v
```

### 4. Load Testing

```bash
# Simple load test
for i in {1..10}; do
  curl -X POST "http://localhost:8000/api/process-alert" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your-api-key" \
    -d "{\"alert_id\": \"load-test-$i\", \"severity\": \"Medium\", \"message\": \"Load test alert $i\", \"host\": \"test-server-01\", \"timestamp\": \"2025-11-30T12:00:00Z\"}" &
done
```

### 5. Monitoring

```bash
# Check application logs
tail -f logs/Capstone-AITTA.log

# Monitor API metrics
curl http://localhost:8000/api/metrics
```

---

## 🔧 Troubleshooting

### Common Issues

#### Jira Connection Issues
```
Error: "Jira authentication failed"
Solution: Verify API token and email address
```

#### Splunk SSL Issues
```
Error: "SSL verification failed"
Solution: Set SPLUNK_VERIFY_SSL=false for testing
```

#### ServiceNow Permission Issues
```
Error: "Access denied"
Solution: Check user roles and table permissions
```

#### LLM API Issues
```
Error: "LLM service unavailable"
Solution: Verify API keys and switch to rule-based mode
```

### Mock Mode Configuration

For development without enterprise systems:

```bash
# In .env file
USE_MOCK_JIRA=true
USE_MOCK_SPLUNK=true
USE_MOCK_CMDB=true
```

### Debug Mode

Enable detailed logging:

```bash
# In .env file
LOG_LEVEL=DEBUG
```

---

## 📚 API Usage Examples

### Process Manual Alert

```bash
curl -X POST "http://localhost:8000/api/process-alert" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "alert_id": "alert-001",
    "severity": "High",
    "message": "Database connection pool exhausted",
    "host": "prod-db-01",
    "timestamp": "2025-11-30T12:00:00Z"
  }'
```

### Scan for Errors (24h)

```bash
curl -X POST "http://localhost:8000/api/scan-and-alert?time_range=24h" \
  -H "X-API-Key: your-api-key"
```

### View Metrics

```bash
curl "http://localhost:8000/api/metrics?range=7d"
```

### List Tickets

```bash
curl "http://localhost:8000/api/tickets?limit=10"
```

---

## 🔐 Security Best Practices

### 1. API Key Management
- Rotate API keys regularly
- Use strong, random keys
- Store securely (not in version control)

### 2. Network Security
- Use HTTPS in production
- Configure firewalls appropriately
- Limit API access to trusted networks

### 3. Data Protection
- Encrypt sensitive configuration
- Implement proper logging hygiene
- Follow GDPR/HIPAA requirements

### 4. Access Control
- Implement proper authentication
- Use role-based access control
- Audit all API access

---

## 🚀 Production Deployment Checklist

- [ ] Environment variables configured
- [ ] Enterprise system credentials set
- [ ] SSL certificates installed
- [ ] Database backup configured
- [ ] Monitoring and alerting set up
- [ ] Load balancer configured
- [ ] Backup and disaster recovery tested
- [ ] Security audit completed
- [ ] Documentation updated

---

## 📞 Support & Resources

- **GitHub Repository**: https://github.com/gauravprabhakar0404/Capstone-AITTA.git
- **API Documentation**: http://localhost:8000/docs (when running)
- **Issues & Support**: Create GitHub issues for technical support
- **Community**: Join discussions and contribute to the project

---

## 🎯 Next Steps

1. **Start with Mock Mode** for immediate testing
2. **Configure One System at a Time** (Jira → Splunk → ServiceNow)
3. **Test Integrations Thoroughly** before production deployment
4. **Monitor Performance** and adjust configurations as needed
5. **Scale Gradually** based on your organization's needs

Your AITTA installation is now ready to transform enterprise incident management! 🚀
