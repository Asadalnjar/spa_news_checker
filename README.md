# SPA News Monitor with Grammar Check Integration

A Python-based automation script that continuously monitors the latest news items on the SPA (Saudi Press Agency) website and performs grammar and spelling checks via the ChatGPT API, sending real-time email alerts based on the results.

**🚀 Cloud-Ready**: Designed for 24/7 deployment on Render, Heroku, or any cloud platform with environment variable support.

## Features

- **Automated News Monitoring**: Crawls SPA news website every 20 minutes
- **Grammar & Spell Checking**: Uses OpenAI's ChatGPT API for content analysis
- **Email Notifications**: Sends real-time alerts with grammar check results
- **Duplicate Prevention**: Tracks processed articles to avoid rechecking
- **Continuous Operation**: Runs 24/7 with scheduled monitoring
- **Cloud-Ready**: Environment variable support for secure cloud deployment
- **Comprehensive Logging**: Detailed logs for monitoring and debugging

## Requirements

- Python 3.7 or higher
- OpenAI API key
- Email account with SMTP access (Gmail recommended)
- Internet connection

## Installation

### 🌐 Cloud Deployment (Recommended for 24/7 Operation)

For continuous 24/7 monitoring, deploy to a cloud platform:

**Quick Deploy to Render:**
1. Fork this repository to your GitHub
2. Sign up at [render.com](https://render.com)
3. Follow the [**Deployment Guide**](DEPLOYMENT.md)

**Other Cloud Platforms:**
- Heroku
- Railway
- Google Cloud Run
- AWS ECS

### 💻 Local Development Setup

1. **Clone or download the project files**
2. **Run the setup script**:
   ```bash
   python setup.py
   ```
   This will:
   - Install all required dependencies
   - Guide you through configuration setup
   - Validate your settings
   - Create service scripts

### Manual Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure the application**:
   - Edit [`config.json`](config.json:1) with your settings
   - Add your OpenAI API key
   - Configure email settings

## Configuration

### OpenAI API Setup

1. Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add it to [`config.json`](config.json:4):
   ```json
   "openai_api_key": "sk-your-api-key-here"
   ```

### Email Configuration

For Gmail (recommended):

1. **Enable 2-Factor Authentication** on your Google account
2. **Generate an App Password**:
   - Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and your device
   - Use the generated password in config
3. **Update [`config.json`](config.json:6)**:
   ```json
   "email": {
     "smtp_server": "smtp.gmail.com",
     "smtp_port": 587,
     "username": "your-email@gmail.com",
     "password": "your-app-password",
     "from_email": "your-email@gmail.com",
     "to_email": "recipient@gmail.com"
   }
   ```

### Configuration File Structure

```json
{
  "target_url": "https://www.spa.gov.sa/en/news/latest-news?page=4",
  "database_path": "news_monitor.db",
  "openai_api_key": "your-openai-api-key",
  "openai_model": "gpt-3.5-turbo",
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "from_email": "your-email@gmail.com",
    "to_email": "recipient@gmail.com"
  }
}
```

## Usage

### 🌐 Cloud Deployment

For 24/7 operation, see the [**Deployment Guide**](DEPLOYMENT.md) for step-by-step instructions to deploy on Render or other cloud platforms.

### 💻 Local Development

**Start the monitor**:
```bash
python main.py
```

The script will:
1. Run an initial check immediately
2. Schedule monitoring every 20 minutes
3. Continue running until stopped with Ctrl+C

### Email Notifications

You'll receive emails with the following format:

**For articles with no grammar issues**:
```
Subject: SPA News Grammar Check - News #1 - OK

News #1
Title: [Article Title]
Article Link: [URL]
Status: OK

Checked at: 2025-01-28 15:30:45
```

**For articles with grammar issues**:
```
Subject: SPA News Grammar Check - News #2 - Caution

News #2
Title: [Article Title]
Article Link: [URL]
Status: Caution

Mistakes Found:
- Grammar error in sentence 3: Subject-verb disagreement
- Spelling mistake: "recieve" should be "receive"

Checked at: 2025-01-28 15:32:15
```

## Monitoring and Logs

- **Log file**: [`spa_news_monitor.log`](spa_news_monitor.log:1)
- **Database**: [`news_monitor.db`](news_monitor.db:1) (SQLite database tracking processed articles)

### Log Levels

- **INFO**: Normal operations, article processing
- **WARNING**: Non-critical issues (e.g., content extraction failures)
- **ERROR**: Critical errors that don't stop the monitor
- **CRITICAL**: Fatal errors that stop the monitor

## Deployment Options

### 🌐 Cloud Deployment (Recommended)

**For 24/7 Operation:**
- **Render** - See [Deployment Guide](DEPLOYMENT.md)
- **Heroku** - With Scheduler add-on
- **Railway** - Simple deployment
- **Google Cloud Run** - Serverless option
- **AWS ECS** - Enterprise option

### 💻 Local Development

**Local Development:**
```bash
python main.py
```

**Background Service (Linux/macOS):**
```bash
nohup python main.py > monitor.log 2>&1 &
```

**Windows Service:**
Use the provided [`run_monitor.bat`](run_monitor.bat:1) script

## Troubleshooting

### Common Issues

1. **OpenAI API Errors**:
   - Check API key validity
   - Verify account has credits
   - Check rate limits

2. **Email Sending Failures**:
   - Verify SMTP settings
   - Check App Password for Gmail
   - Ensure 2FA is enabled

3. **Website Scraping Issues**:
   - SPA website structure may change
   - Check internet connectivity
   - Review HTML selectors in code

4. **Database Errors**:
   - Ensure write permissions
   - Check disk space
   - Verify SQLite installation

### Debug Mode

Enable detailed logging by modifying the logging level in [`main.py`](main.py:25):
```python
logging.basicConfig(level=logging.DEBUG)
```

## Customization

### Changing Check Interval

Modify the scheduler interval in [`main.py`](main.py:350):
```python
scheduler.add_job(
    func=self.process_news_articles,
    trigger=IntervalTrigger(minutes=30),  # Change from 20 to 30 minutes
    # ...
)
```

### Custom Grammar Prompts

Modify the grammar check prompt in [`main.py`](main.py:220):
```python
prompt = (
    "Your custom grammar checking instructions here. "
    "If there are no mistakes, reply: OK. "
    "If there are any mistakes, reply: Caution, and list all found mistakes."
)
```

### Different News Sources

Update the target URL and modify the HTML selectors in [`fetch_news_links()`](main.py:95) method.

## File Structure

```
spa_news_monitor/
├── main.py              # Main application script
├── config.json          # Configuration file (local development)
├── config.example.json  # Example configuration
├── requirements.txt     # Python dependencies
├── setup.py            # Setup and configuration script
├── test_monitor.py     # Test suite
├── README.md           # This documentation
├── DEPLOYMENT.md       # Cloud deployment guide
├── render.yaml         # Render deployment config
├── Dockerfile          # Docker container config
├── .gitignore          # Git ignore rules
├── run_monitor.bat     # Windows batch script
├── spa_news_monitor.log # Log file (created at runtime)
└── news_monitor.db     # SQLite database (created at runtime)
```

## API Costs

- **OpenAI API**: Approximately $0.002 per article (using gpt-3.5-turbo)
- **Daily estimate**: ~$0.10-0.50 depending on news volume
- **Monthly estimate**: ~$3-15

## Security Considerations

- Store API keys securely
- Use App Passwords for email
- Restrict file permissions on config files
- Consider using environment variables for sensitive data

## Quick Start Guide

### For 24/7 Cloud Deployment:
1. 📋 Fork this repository
2. 🔑 Get OpenAI API key
3. 📧 Set up Gmail App Password
4. 🚀 Deploy to Render using [Deployment Guide](DEPLOYMENT.md)
5. ✅ Monitor via email notifications

### For Local Testing:
1. 📥 Download/clone repository
2. ⚙️ Run `python setup.py`
3. 🧪 Run `python test_monitor.py`
4. ▶️ Run `python main.py`

## Support

For issues or questions:
1. Check the log files for error details
2. Verify configuration settings
3. Test individual components (email, API, scraping)
4. Review the troubleshooting section
5. See [Deployment Guide](DEPLOYMENT.md) for cloud-specific issues

## License

This project is provided as-is for educational and monitoring purposes.