import requests
import time
import threading
import json
import os
import re
from typing import Optional, Dict, Any, TypedDict, cast
from flask import Flask
from telegram.update import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ====== CONFIG FILE ======
CONFIG_FILE = "config.json"

class Config(TypedDict):
    x_user_id: Optional[str]
    x_username: Optional[str]
    telegram_channel: Optional[str]
    last_tweet_id: Optional[str]

def load_config() -> Config:
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return cast(Config, data)
    except:
        return {"x_user_id": None, "x_username": None, "telegram_channel": None, "last_tweet_id": None}

def save_config(cfg: Config) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

config: Config = load_config()

# ====== TOKENS FROM ENVIRONMENT ======
# Support for multiple X accounts (up to 5)
X_BEARER_TOKENS = []
for i in range(1, 6):  # X_BEARER_TOKEN_1 through X_BEARER_TOKEN_5
    token = os.getenv(f"X_BEARER_TOKEN_{i}")
    if token and token != "your_x_api_bearer_token":
        X_BEARER_TOKENS.append(token)

# Fallback to single token for backward compatibility
if not X_BEARER_TOKENS:
    single_token = os.getenv("X_BEARER_TOKEN", "your_x_api_bearer_token")
    if single_token != "your_x_api_bearer_token":
        X_BEARER_TOKENS.append(single_token)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "your_telegram_bot_token")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "123456789")
ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.strip() else 123456789   # your own Telegram user id (for security)

# Telegram login users - support multiple authorized users
AUTHORIZED_USERS = set()
if ADMIN_ID != 123456789:
    AUTHORIZED_USERS.add(ADMIN_ID)

CHECK_INTERVAL = 60
# Rate limit tracking for multiple accounts
import datetime
last_rate_limit_time = 0
current_wait_time = 0
current_token_index = 0  # Track which token we're currently using
token_rate_limits = {}  # Track rate limits per token

# Initialize rate limit tracking for each token
for i, token in enumerate(X_BEARER_TOKENS):
    token_rate_limits[i] = {'last_rate_limit': 0, 'wait_time': 0}
# ====================

# --- Flask keepalive server (for Replit + UptimeRobot) ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

# --- X API ---
def get_next_available_token():
    """Get the next available X token that isn't rate limited"""
    global current_token_index
    
    if not X_BEARER_TOKENS:
        print("No X Bearer tokens configured!")
        return None
        
    current_time = time.time()
    
    # Try all tokens starting from current index
    for i in range(len(X_BEARER_TOKENS)):
        token_idx = (current_token_index + i) % len(X_BEARER_TOKENS)
        token_info = token_rate_limits.get(token_idx, {'last_rate_limit': 0, 'wait_time': 0})
        
        # Check if this token is still rate limited
        if token_info['last_rate_limit'] == 0 or (current_time - token_info['last_rate_limit']) > token_info['wait_time']:
            current_token_index = token_idx
            return X_BEARER_TOKENS[token_idx]
    
    # All tokens are rate limited, return the one with the shortest remaining wait
    best_token_idx = 0
    shortest_wait = float('inf')
    
    for i, token in enumerate(X_BEARER_TOKENS):
        token_info = token_rate_limits.get(i, {'last_rate_limit': 0, 'wait_time': 0})
        remaining_wait = token_info['wait_time'] - (current_time - token_info['last_rate_limit'])
        if remaining_wait < shortest_wait:
            shortest_wait = remaining_wait
            best_token_idx = i
    
    current_token_index = best_token_idx
    return X_BEARER_TOKENS[best_token_idx]

def get_user_id_from_username(username: str):
    token = get_next_available_token()
    if not token:
        return None
        
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers).json()
        if "data" in response:
            return response["data"]["id"]
        else:
            print(f"Error getting user ID: {response}")
    except Exception as e:
        print(f"Error in get_user_id_from_username: {e}")
    return None

def get_latest_tweet(user_id):
    global last_rate_limit_time, current_wait_time, current_token_index
    
    token = get_next_available_token()
    if not token:
        print("No available X tokens!")
        return None, []
    
    url = (
        f"https://api.twitter.com/2/users/{user_id}/tweets"
        f"?max_results=5&expansions=attachments.media_keys"
        f"&media.fields=preview_image_url,url"
    )
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers)
        response_json = response.json()
        
        if response.status_code == 429:
            # Mark current token as rate limited
            current_time = time.time()
            token_rate_limits[current_token_index] = {
                'last_rate_limit': current_time,
                'wait_time': 900  # 15 minutes
            }
            print(f"Rate limited on token {current_token_index + 1}. Trying next token...")
            
            # Try the next token
            next_token = get_next_available_token()
            if next_token and next_token != token:
                print(f"Switched to token {current_token_index + 1}")
                return get_latest_tweet(user_id)  # Recursive call with new token
            else:
                last_rate_limit_time = current_time
                current_wait_time = 900
                print("All tokens are rate limited. Will wait before next request.")
                return None, []
        elif response.status_code != 200:
            print(f"X API error {response.status_code}: {response_json}")
            return None, []
        elif "data" in response_json:
            # Reset rate limit tracking on successful request
            last_rate_limit_time = 0
            current_wait_time = 0
            
            # Always return only the most recent tweet (first in the list)
            latest_tweet = response_json["data"][0]
            media_urls = []
            
            # ONLY get media that belongs specifically to THIS tweet
            if "attachments" in latest_tweet and "media_keys" in latest_tweet["attachments"]:
                current_tweet_media_keys = latest_tweet["attachments"]["media_keys"]
                
                if "includes" in response_json and "media" in response_json["includes"]:
                    for m in response_json["includes"]["media"]:
                        # Only include media that belongs to the current tweet
                        if m.get("media_key") in current_tweet_media_keys and "url" in m:
                            media_urls.append(m["url"])
            
            return latest_tweet, media_urls
        else:
            print(f"No tweet data: {response_json}")
            return None, []
    except Exception as e:
        print(f"Error in get_latest_tweet: {e}")
        return None, []

# --- Telegram posting ---
def post_text(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    try:
        response = requests.post(url, data=data)
        if not response.ok:
            print(f"Error posting text: {response.text}")
    except Exception as e:
        print(f"Error in post_text: {e}")

def post_photo(chat_id, photo_url, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "photo": photo_url, "caption": caption}
    try:
        response = requests.post(url, data=data)
        if not response.ok:
            print(f"Error posting photo: {response.text}")
    except Exception as e:
        print(f"Error in post_photo: {e}")

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "👋 Hi! Use:\n"
            "/setusername <username> → set X account\n"
            "/setchannel <@channel or id> → set Telegram channel\n"
            "/status → check current settings\n"
            "/testpost → send a test post to your channel\n"
            "/checknow → manually check for new tweets\n"
            "/ratelimit → check X API rate limit status\n"
            "/login → add yourself as authorized user\n"
            "/logout → remove yourself as authorized user"
        )

# Telegram login functionality
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    
    if user_id == ADMIN_ID:
        await update.message.reply_text("✅ You are already the admin!")
        return
        
    AUTHORIZED_USERS.add(user_id)
    await update.message.reply_text(
        f"✅ Welcome @{username}! You are now authorized to use this bot.\n"
        f"Your Telegram ID: {user_id}"
    )
    print(f"New user authorized: @{username} (ID: {user_id})")

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    
    if user_id == ADMIN_ID:
        await update.message.reply_text("❌ Admin cannot logout!")
        return
        
    if user_id in AUTHORIZED_USERS:
        AUTHORIZED_USERS.remove(user_id)
        await update.message.reply_text(
            f"✅ Goodbye @{username}! You have been logged out."
        )
        print(f"User logged out: @{username} (ID: {user_id})")
    else:
        await update.message.reply_text("ℹ️ You weren't logged in.")

def is_authorized(user_id):
    """Check if user is authorized to use the bot"""
    return user_id == ADMIN_ID or user_id in AUTHORIZED_USERS

async def set_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_authorized(update.effective_user.id):
        if update.message:
            await update.message.reply_text("❌ You are not authorized to use this command. Use /login first.")
        return
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /setusername <username>")
        return

    username = context.args[0].replace("@", "")
    user_id = get_user_id_from_username(username)

    if user_id:
        config["x_user_id"] = user_id
        config["x_username"] = username
        save_config(config)
        await update.message.reply_text(f"✅ X account set to @{username} (ID: {user_id})")
    else:
        await update.message.reply_text("❌ Could not find that username.")

async def set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_authorized(update.effective_user.id):
        if update.message:
            await update.message.reply_text("❌ You are not authorized to use this command. Use /login first.")
        return
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /setchannel <@channel or chat_id>")
        return
    config["telegram_channel"] = context.args[0]
    save_config(config)
    await update.message.reply_text(f"✅ Telegram channel set to {config['telegram_channel']}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    msg = "📊 Current Config:\n"
    msg += f"• X Username: @{config.get('x_username', '❌ Not set')}\n"
    msg += f"• X User ID: {config.get('x_user_id', '❌ Not set')}\n"
    msg += f"• Telegram Channel: {config.get('telegram_channel', '❌ Not set')}\n"
    msg += f"• Last Tweet ID: {config.get('last_tweet_id', '❌ None')}\n\n"
    
    # Show multiple X accounts info
    msg += f"🔑 X API Accounts: {len(X_BEARER_TOKENS)} configured\n"
    if X_BEARER_TOKENS:
        msg += f"• Current token: #{current_token_index + 1}\n"
        
        # Show rate limit status for each token
        current_time = time.time()
        for i, token in enumerate(X_BEARER_TOKENS):
            token_info = token_rate_limits.get(i, {'last_rate_limit': 0, 'wait_time': 0})
            if token_info['last_rate_limit'] == 0:
                status_emoji = "✅"
                status_text = "Available"
            else:
                remaining_wait = token_info['wait_time'] - (current_time - token_info['last_rate_limit'])
                if remaining_wait <= 0:
                    status_emoji = "✅"
                    status_text = "Available"
                else:
                    status_emoji = "⏳"
                    minutes = int(remaining_wait // 60)
                    seconds = int(remaining_wait % 60)
                    status_text = f"Rate limited ({minutes}m {seconds}s)"
            msg += f"  Token {i+1}: {status_emoji} {status_text}\n"
    
    # Show authorized users
    msg += f"\n👥 Authorized Users: {len(AUTHORIZED_USERS) + 1}\n"
    msg += f"• Admin ID: {ADMIN_ID}\n"
    if AUTHORIZED_USERS:
        for user_id in list(AUTHORIZED_USERS)[:5]:  # Show max 5 users
            msg += f"• User ID: {user_id}\n"
        if len(AUTHORIZED_USERS) > 5:
            msg += f"• ... and {len(AUTHORIZED_USERS) - 5} more\n"
    
    await update.message.reply_text(msg)

async def test_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_authorized(update.effective_user.id):
        if update.message:
            await update.message.reply_text("❌ You are not authorized to use this command. Use /login first.")
        return
    if not update.message:
        return
    if not config.get("telegram_channel"):
        await update.message.reply_text("❌ Please set a Telegram channel first with /setchannel")
        return
    
    # Send a test post with the new format
    test_text = "This is a test post from your Twitter-to-Telegram bot! 🚀"
    test_link = "https://x.com/example/status/123456789"
    test_account = "https://x.com/example"
    
    formatted_message = f"{test_text}\n\n🔗: {test_link}\n\nFollow My Account: {test_account}"
    
    post_text(config["telegram_channel"], formatted_message)
    await update.message.reply_text("✅ Test post sent to your channel!")

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_authorized(update.effective_user.id):
        if update.message:
            await update.message.reply_text("❌ You are not authorized to use this command. Use /login first.")
        return
    if not update.message:
        return
    
    if not config.get("x_user_id"):
        await update.message.reply_text("❌ Please set an X username first with /setusername")
        return
    if not config.get("telegram_channel"):
        await update.message.reply_text("❌ Please set a Telegram channel first with /setchannel")
        return
    
    await update.message.reply_text("🔍 Checking for new tweets...")
    
    try:
        tweet, media_urls = get_latest_tweet(config["x_user_id"])
        if tweet:
            tweet_id = tweet["id"]
            if tweet_id != config.get("last_tweet_id"):
                text = tweet.get("text", "")
                # Remove t.co links from the tweet text
                text = re.sub(r'https://t\.co/\w+', '', text).strip()
                link = f"https://x.com/{config['x_username']}/status/{tweet_id}"
                account_link = f"https://x.com/{config['x_username']}"
                
                formatted_message = f"{text}\n\n🔗: {link}\n\nFollow My Account: {account_link}"

                if media_urls:
                    post_photo(config["telegram_channel"], media_urls[0], formatted_message)
                    for extra in media_urls[1:]:
                        post_photo(config["telegram_channel"], extra)
                else:
                    post_text(config["telegram_channel"], formatted_message)

                config["last_tweet_id"] = tweet_id
                save_config(config)
                await update.message.reply_text(f"✅ Posted new tweet: {text[:50]}...")
            else:
                await update.message.reply_text("ℹ️ No new tweets found since last check")
        else:
            await update.message.reply_text("❌ Could not fetch tweets (may be rate limited)")
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking tweets: {str(e)}")

async def rate_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_authorized(update.effective_user.id):
        if update.message:
            await update.message.reply_text("❌ You are not authorized to use this command. Use /login first.")
        return
    if not update.message:
        return
    
    global last_rate_limit_time, current_wait_time
    
    if last_rate_limit_time == 0:
        await update.message.reply_text("✅ No rate limit detected. You can check for tweets now with /checknow")
    else:
        time_since_limit = time.time() - last_rate_limit_time
        remaining_wait = max(0, current_wait_time - time_since_limit)
        
        if remaining_wait > 0:
            minutes = int(remaining_wait // 60)
            seconds = int(remaining_wait % 60)
            if minutes > 0:
                wait_text = f"{minutes} minutes, {seconds} seconds"
            else:
                wait_text = f"{seconds} seconds"
            
            await update.message.reply_text(
                f"⏳ Rate limited by X API\n"
                f"Wait approximately: {wait_text}\n"
                f"Try /checknow after this time."
            )
        else:
            await update.message.reply_text("✅ Rate limit should be cleared. Try /checknow now!")

# --- Bot Loop ---
def bot_loop():
    global current_wait_time
    rate_limit_delay = CHECK_INTERVAL
    while True:
        try:
            if config["x_user_id"] and config["telegram_channel"]:
                tweet, media_urls = get_latest_tweet(config["x_user_id"])
                if tweet:
                    tweet_id = tweet["id"]
                    stored_last_tweet_id = config.get("last_tweet_id")
                    
                    # Only post if this is truly a NEW tweet (different ID from stored one)
                    if stored_last_tweet_id is None or tweet_id != stored_last_tweet_id:
                        text = tweet.get("text", "")
                        # Remove t.co links from the tweet text
                        text = re.sub(r'https://t\.co/\w+', '', text).strip()
                        link = f"https://x.com/{config['x_username']}/status/{tweet_id}"
                        account_link = f"https://x.com/{config['x_username']}"
                        
                        formatted_message = f"{text}\n\n🔗: {link}\n\nFollow My Account: {account_link}"

                        if media_urls:
                            post_photo(config["telegram_channel"], media_urls[0], formatted_message)
                            for extra in media_urls[1:]:
                                post_photo(config["telegram_channel"], extra)
                        else:
                            post_text(config["telegram_channel"], formatted_message)

                        # IMMEDIATELY update and save the last tweet ID to prevent duplicates
                        config["last_tweet_id"] = tweet_id
                        save_config(config)
                        print(f"Posted NEW tweet: {text[:40]}...")
                        
                        # Reset delay on successful post
                        rate_limit_delay = CHECK_INTERVAL
                    else:
                        # Same tweet as before - no action needed
                        rate_limit_delay = CHECK_INTERVAL
                elif tweet is None:
                    # Likely rate limited, increase delay
                    rate_limit_delay = min(rate_limit_delay * 2, 900)  # Max 15 minutes
                    current_wait_time = rate_limit_delay  # Track current wait time
                    print(f"Rate limited. Waiting {rate_limit_delay} seconds...")
        except Exception as e:
            print("Error in bot loop:", e)
            # On error, also increase delay
            rate_limit_delay = min(rate_limit_delay * 1.5, 900)
            current_wait_time = rate_limit_delay

        time.sleep(rate_limit_delay)

# --- Run Everything ---
if __name__ == "__main__":
    print("Starting Twitter-to-Telegram Bot...")
    print(f"X Bearer Tokens: {len(X_BEARER_TOKENS)} configured" if X_BEARER_TOKENS else "X Bearer Tokens: NOT SET")
    print(f"Telegram Token: {'Set' if TELEGRAM_TOKEN != 'your_telegram_bot_token' else 'NOT SET'}")
    print(f"Admin ID: {ADMIN_ID}")
    
    # Start Flask keepalive server
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=bot_loop, daemon=True).start()
    print("Bot loop and Flask server started...")
    
    # Validate Telegram token before starting bot
    if TELEGRAM_TOKEN == "your_telegram_bot_token" or not TELEGRAM_TOKEN or not TELEGRAM_TOKEN.strip():
        print("❌ WARNING: Invalid or missing Telegram token!")
        print("Please set TELEGRAM_TOKEN environment variable with a valid bot token from @BotFather")
        print("Bot will continue running tweet monitoring and Flask server, but Telegram commands will not work.")
        print("Flask server running on port 5000 - bot loop continues monitoring tweets")
        
        # Keep the process alive without Telegram bot
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("Bot stopped.")
    else:
        try:
            # Telegram command bot
            app_tg = Application.builder().token(TELEGRAM_TOKEN).build()
            app_tg.add_handler(CommandHandler("start", start))
            app_tg.add_handler(CommandHandler("setusername", set_username))
            app_tg.add_handler(CommandHandler("setchannel", set_channel))
            app_tg.add_handler(CommandHandler("status", status))
            app_tg.add_handler(CommandHandler("testpost", test_post))
            app_tg.add_handler(CommandHandler("checknow", check_now))
            app_tg.add_handler(CommandHandler("ratelimit", rate_limit))
            app_tg.add_handler(CommandHandler("login", login))
            app_tg.add_handler(CommandHandler("logout", logout))

            print("✅ Telegram bot initialized successfully!")
            print("Bot fully operational - Flask server on port 5000, Telegram commands active")
            app_tg.run_polling()
        except Exception as e:
            print(f"❌ Failed to start Telegram bot: {e}")
            print("Bot will continue running tweet monitoring and Flask server, but Telegram commands will not work.")
            print("Please check your Telegram token and try again.")
            
            # Keep the process alive without Telegram bot
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                print("Bot stopped.")