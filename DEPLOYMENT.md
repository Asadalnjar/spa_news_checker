# Deployment Guide for Render

This guide explains how to deploy the SPA News Monitor to Render for 24/7 operation.

## Prerequisites

1. **GitHub Account** - To host your code
2. **Render Account** - Sign up at [render.com](https://render.com)
3. **OpenAI API Key** - Get from [OpenAI Platform](https://platform.openai.com/api-keys)
4. **Email Account** - Gmail with App Password recommended

## Step 1: Prepare Your Repository

### 1.1 Create GitHub Repository

1. Create a new repository on GitHub
2. Clone it locally or upload the project files
3. Ensure all files are committed and pushed

### 1.2 Required Files for Deployment

Make sure these files are in your repository:
- [`main.py`](main.py:1) - Main application
- [`requirements.txt`](requirements.txt:1) - Dependencies
- [`render.yaml`](render.yaml:1) - Render configuration
- [`Dockerfile`](Dockerfile:1) - Container configuration
- [`.gitignore`](.gitignore:1) - Git ignore rules

## Step 2: Set Up Email (Gmail)

### 2.1 Enable 2-Factor Authentication
1. Go to your Google Account settings
2. Enable 2-Factor Authentication

### 2.2 Generate App Password
1. Visit [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Select "Mail" and your device
3. Copy the generated 16-character password
4. Save this password - you'll need it for Render

## Step 3: Deploy to Render

### 3.1 Connect Repository

1. Log in to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub account
4. Select your repository
5. Choose "Deploy from a Git repository"

### 3.2 Configure Service

**Basic Settings:**
- **Name**: `spa-news-monitor`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`

**Advanced Settings:**
- **Plan**: Free (or Starter for better reliability)
- **Auto-Deploy**: Yes (recommended)

### 3.3 Set Environment Variables

In the Render dashboard, add these environment variables:

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `OPENAI_API_KEY` | `sk-proj-...` | Your OpenAI API key |
| `EMAIL_USERNAME` | `your.email@gmail.com` | Your Gmail address |
| `EMAIL_PASSWORD` | `abcd efgh ijkl mnop` | Gmail App Password (16 chars) |
| `EMAIL_FROM` | `your.email@gmail.com` | From email address |
| `EMAIL_TO` | `recipient@gmail.com` | Recipient email address |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP server (default) |
| `SMTP_PORT` | `587` | SMTP port (default) |
| `TARGET_URL` | `https://www.spa.gov.sa/en/news/latest-news?page=4` | Target URL (default) |
| `OPENAI_MODEL` | `gpt-3.5-turbo` | OpenAI model (default) |
| `CHECK_INTERVAL_MINUTES` | `20` | Check interval (default) |

### 3.4 Deploy

1. Click "Create Web Service"
2. Render will automatically build and deploy your application
3. Monitor the build logs for any errors

## Step 4: Verify Deployment

### 4.1 Check Logs

1. Go to your service dashboard on Render
2. Click on "Logs" tab
3. Look for these messages:
   ```
   SPA News Monitor initialized successfully
   Scheduler started. Monitoring will run every 20 minutes.
   ```

### 4.2 Test Email Notifications

The monitor will:
1. Run an initial check immediately after deployment
2. Send test emails if new articles are found
3. Continue monitoring every 20 minutes

## Step 5: Monitor and Maintain

### 5.1 Service Health

- **Render Dashboard**: Monitor service status and logs
- **Email Alerts**: You'll receive emails for each article processed
- **Logs**: Check for any errors or issues

### 5.2 Troubleshooting

**Common Issues:**

1. **Build Failures**:
   - Check [`requirements.txt`](requirements.txt:1) for correct dependencies
   - Verify Python version compatibility

2. **Environment Variable Errors**:
   - Double-check all required variables are set
   - Verify OpenAI API key is valid
   - Confirm Gmail App Password is correct

3. **Email Sending Issues**:
   - Ensure 2FA is enabled on Gmail
   - Verify App Password is 16 characters
   - Check SMTP settings

4. **Website Scraping Issues**:
   - SPA website structure may change
   - Check logs for HTTP errors
   - Verify target URL is accessible

### 5.3 Updating the Service

1. Push changes to your GitHub repository
2. Render will automatically redeploy (if auto-deploy is enabled)
3. Monitor logs during deployment

## Step 6: Cost Considerations

### Render Pricing

- **Free Tier**: 
  - 750 hours/month (enough for 24/7 operation)
  - Service sleeps after 15 minutes of inactivity
  - May cause delays in monitoring

- **Starter Plan ($7/month)**:
  - Always-on service
  - Better for reliable 24/7 monitoring
  - Recommended for production use

### OpenAI API Costs

- **gpt-3.5-turbo**: ~$0.002 per article
- **Estimated monthly cost**: $3-15 depending on news volume
- Monitor usage in OpenAI dashboard

## Step 7: Alternative Deployment Options

### 7.1 Using Docker

If you prefer Docker deployment:

1. Build the image:
   ```bash
   docker build -t spa-news-monitor .
   ```

2. Run with environment variables:
   ```bash
   docker run -d \
     -e OPENAI_API_KEY=your-key \
     -e EMAIL_USERNAME=your-email \
     -e EMAIL_PASSWORD=your-password \
     -e EMAIL_FROM=your-email \
     -e EMAIL_TO=recipient-email \
     spa-news-monitor
   ```

### 7.2 Other Cloud Platforms

The application can also be deployed to:
- **Heroku** (with Scheduler add-on)
- **Railway**
- **Google Cloud Run**
- **AWS ECS**
- **DigitalOcean App Platform**

## Security Best Practices

1. **Never commit sensitive data** to GitHub
2. **Use environment variables** for all secrets
3. **Regularly rotate API keys** and passwords
4. **Monitor logs** for suspicious activity
5. **Keep dependencies updated**

## Support

If you encounter issues:

1. Check the service logs on Render
2. Verify all environment variables are set correctly
3. Test individual components (email, API, scraping)
4. Review the troubleshooting section above

## Monitoring Success

You'll know the deployment is working when:

1. ✅ Service shows "Live" status on Render
2. ✅ Logs show regular monitoring activity
3. ✅ You receive email notifications for new articles
4. ✅ No error messages in the logs

The monitor will run continuously, checking for new articles every 20 minutes and sending email alerts with grammar check results.