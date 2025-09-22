# Twitter to Telegram Bot

A powerful bot that monitors Twitter/X accounts and automatically forwards new tweets to Telegram channels with support for multiple developer accounts and user authentication.

## 🚀 Features

- **Multi-Account Support**: Configure up to 5 X developer accounts to avoid rate limits
- **Automatic Token Rotation**: Smart switching between accounts when rate limits are hit
- **Telegram Login System**: Multiple users can authenticate and use the bot
- **Rate Limit Protection**: Intelligent handling of API limits with exponential backoff
- **Media Support**: Forwards images and media from tweets
- **Real-time Monitoring**: Continuous tweet monitoring with configurable intervals
- **Admin Controls**: Secure command system with user authorization

## 🛠️ Setup

### Environment Variables

Set these in your Replit Secrets tab:

#### X/Twitter API (Required - at least 1, up to 5)
```
X_BEARER_TOKEN_1=your_first_bearer_token
X_BEARER_TOKEN_2=your_second_bearer_token
X_BEARER_TOKEN_3=your_third_bearer_token
X_BEARER_TOKEN_4=your_fourth_bearer_token
X_BEARER_TOKEN_5=your_fifth_bearer_token
```

#### Telegram Configuration (Required)
```
TELEGRAM_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id
```

### Getting API Keys

#### X/Twitter Bearer Token
1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a developer account and app
3. Navigate to "Keys and Tokens"
4. Copy the Bearer Token

#### Telegram Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Use `/newbot` command
3. Follow setup instructions
4. Copy the provided token

#### Your Telegram User ID
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. Copy the user ID number

## 🎮 Usage

### Bot Commands

- `/start` - Show available commands
- `/login` - Authorize yourself to use the bot
- `/logout` - Remove your authorization
- `/setusername @username` - Set X account to monitor
- `/setchannel @channel` - Set Telegram channel for posts
- `/status` - Show current configuration and token status
- `/testpost` - Send a test post to your channel
- `/checknow` - Manually check for new tweets
- `/ratelimit` - Check API rate limit status

### Setup Workflow

1. Set up all environment variables in Replit Secrets
2. Start the bot (it runs automatically)
3. Message your bot on Telegram
4. Use `/setusername @targetaccount` to set which X account to monitor
5. Use `/setchannel @yourchannel` to set where tweets should be posted
6. The bot will automatically start monitoring and posting new tweets

## 🔧 Technical Details

### Architecture
- **Python Flask**: Web server for health checks and uptime monitoring
- **Multi-threading**: Separate threads for bot loop and web server
- **Token Rotation**: Automatic switching between X accounts to avoid rate limits
- **State Management**: Persistent configuration with JSON storage
- **Error Handling**: Graceful degradation when APIs are unavailable

### Rate Limit Handling
- Per-token rate limit tracking
- Automatic token rotation when limits are hit
- Exponential backoff with maximum 15-minute delays
- Smart recovery when limits reset

### Security Features
- Admin-only sensitive commands
- User authentication system with login/logout
- Environment variable protection for API keys
- Telegram user ID verification

## 📦 Dependencies

- `python-telegram-bot` - Telegram bot functionality
- `requests` - HTTP requests for X API
- `flask` - Web server for health checks

## 🚀 Deployment

This bot is optimized for Replit deployment with:
- Automatic dependency management
- Environment variable configuration
- Health check endpoint on port 5000
- Automatic restarts and uptime monitoring

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

---

**Note**: This bot requires valid API keys from both X/Twitter and Telegram to function properly. Make sure to follow the terms of service for both platforms.