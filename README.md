# AI Insurance Claims Fulfillment Automation System

An intelligent system that automates the processing of insurance claims by monitoring email communications, validating users, and processing claims using Large Language Models (LLM).

## 🌟 Key Features

- **Intelligent Email Filtering**: Uses LLM (AWS Bedrock) to identify and filter insurance-related communications
- **Automated Claims Processing**: Processes claims automatically with LLM-based assessment
- **User Validation**: Validates users against a registration system via FastAPI
- **Attachment Management**: Processes and stores email attachments securely
- **MongoDB Integration**: Persistent storage of claims and processing data
- **Microservices Architecture**: Modular design with separate services for different functionalities
- **Real-time Monitoring**: Continuous monitoring of email inbox with intelligent processing

## 🏗️ System Architecture

The system consists of several microservices:

1. **User Validator API** (Port 8000)
   - Validates user registration status
   - Manages user policy information

2. **Mail Service API** (Port 8001)
   - Handles email communications
   - Sends notifications and responses

3. **Fulfillment API** (Port 8002)
   - Processes claims fulfillment
   - Manages claim status and updates

4. **Main System Components**
   - `mail_monitor.py`: Core email monitoring system
   - `fulfillment_processor.py`: Claims processing engine
   - `mongodb_manager.py`: Database operations manager

## 🚀 Getting Started

### Prerequisites

1. Python 3.x
2. MongoDB
3. AWS Bedrock access (for LLM functionality)
4. Gmail account with App Password configured

### Environment Setup

Create a `.env` file in the root directory with the following variables:

```env
EMAIL_USERNAME=your.email@gmail.com
EMAIL_APP_PASSWORD=your-gmail-app-password
FASTAPI_BASE_URL=http://localhost:8000
MAIL_SERVICE_URL=http://localhost:8001
LOCAL_ATTACHMENTS_FOLDER=attachments
```

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create necessary directories:
   ```bash
   mkdir attachments
   mkdir prompts
   ```

## 🔄 Running the System

1. Start all services using the startup script:
   ```bash
   python start_system.py
   ```

This will:
- Start all API services
- Initialize MongoDB connections
- Begin email monitoring
- Start the claims processing system

## 📁 Project Structure

```
├── apis/
│   ├── fulfillment_api.py
│   ├── mail_service.py
│   └── user_validator.py
├── prompts/
│   ├── fulfillment_pending_email.txt
│   ├── fulfillment_requirements.txt
│   ├── fulfillment_system_prompt.txt
│   ├── user_not_found_email.txt
│   └── user_not_found_fallback.txt
├── attachments/
│   └── CLAIM_*/              # Claim-specific attachment folders
├── mail_monitor.py
├── fulfillment_processor.py
├── mongodb_manager.py
├── start_system.py
└── test_mongodb_connection.py
```

## 🔄 System Flow

1. **Email Monitoring**
   - Continuously monitors Gmail inbox
   - Uses LLM to filter insurance-related emails
   - Creates unique claim IDs for processing

2. **User Validation**
   - Validates sender email against registration system
   - Sends rejection emails for unregistered users
   - Retrieves user policy information

3. **Claims Processing**
   - Analyzes claim content using LLM
   - Processes attachments and stores them securely
   - Generates fulfillment assessments

4. **Communication**
   - Sends automated responses
   - Manages claim status notifications
   - Handles communication with users

## 🛠️ Development

### Adding New Features

1. Create new API endpoints in respective service files
2. Update prompt templates in `/prompts` directory
3. Modify MongoDB schemas as needed
4. Update email templates for new scenarios

### Testing

Run MongoDB connection test:
```bash
python test_mongodb_connection.py
```

## 📝 Logging

The system provides comprehensive logging with emoji indicators:
- ✅ Success operations
- ❌ Errors and failures
- 📧 Email operations
- 🤖 LLM operations
- 🔍 System checks

## 🔒 Security

- Uses Gmail App Passwords for secure email access
- Implements secure attachment handling
- Validates user authentication
- Stores sensitive data in environment variables

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
