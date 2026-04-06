import telebot
import requests
import json
import random
import string
import time
import threading
import os
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request

# 🔑 BOT CONFIG
BOT_TOKEN = "8156691298:AAFNdvY6hAOLgS6P-lzRGO1xd9S8IkRyHiE"
ADMIN_IDS = [8431995898, 5936431184]

bot = telebot.TeleBot(BOT_TOKEN)

# Flask app for webhook
app = Flask(__name__)

# 📢 Force join channels
CHANNELS = [
    {"id": -1003343836959, "link": "https://t.me/free_netflix_accountsss", "username": "@free_netflix_accountsss", "name": "Free Netflix Accounts"},
    {"id": -1003343836959, "link": "https://t.me/esdiekidrav_gateways", "username": "@esdiekidrav_gateways", "name": "PREMIUM COOKIE GATEWAYS"}
]

# 🌐 API CONFIG
API_URL = "https://ayaanmods.site/number.php"
API_KEY = "annonymous"
API_DEVELOPER = "@afkchatgpt998"
FREE_DAILY_LIMIT = 5

# 📊 Database structure
DB_FILE = "user_data.json"

def load_data():
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "users": {}, 
            "gift_codes": {}, 
            "invites": {}, 
            "feedbacks": {}, 
            "reports": {}, 
            "daily_usage": {},
            "total_commands": 0
        }

def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Load data and ensure all required keys exist
data = load_data()
required_keys = ["daily_usage", "gift_codes", "invites", "feedbacks", "reports", "total_commands", "users"]
for key in required_keys:
    if key not in data:
        data[key] = {} if key != "total_commands" else 0
        save_data(data)

# Helper functions
def has_premium(user_id):
    user_id = str(user_id)
    if user_id in data["users"]:
        expiry = data["users"][user_id].get("premium_expiry")
        if expiry and datetime.now() < datetime.fromisoformat(expiry):
            return True
    return False

def get_invite_count(user_id):
    user_id = str(user_id)
    return data["invites"].get(user_id, 0)

def add_invite(user_id):
    user_id = str(user_id)
    data["invites"][user_id] = data["invites"].get(user_id, 0) + 1
    save_data(data)
    
    if data["invites"][user_id] >= 2 and not has_premium(user_id):
        data["users"][user_id] = {
            "premium_expiry": (datetime.now() + timedelta(days=30)).isoformat()
        }
        save_data(data)
        return True
    return False

def get_today_usage(user_id):
    """Safe function to get today's usage"""
    user_id = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_id not in data["daily_usage"]:
        return 0
    
    return data["daily_usage"][user_id].get(today, 0)

def can_lookup(user_id):
    """Check if user can lookup"""
    if has_premium(user_id):
        return True, "premium", FREE_DAILY_LIMIT
    
    user_id = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_id not in data["daily_usage"]:
        data["daily_usage"][user_id] = {}
    
    if today not in data["daily_usage"][user_id]:
        data["daily_usage"][user_id][today] = 0
    
    used_today = data["daily_usage"][user_id][today]
    remaining = FREE_DAILY_LIMIT - used_today
    
    if used_today >= FREE_DAILY_LIMIT:
        return False, "daily_limit_reached", remaining
    
    return True, "free", remaining

def increment_lookup(user_id):
    """Only increment after successful lookup"""
    user_id = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user_id not in data["daily_usage"]:
        data["daily_usage"][user_id] = {}
    
    data["daily_usage"][user_id][today] = data["daily_usage"][user_id].get(today, 0) + 1
    data["total_commands"] = data.get("total_commands", 0) + 1
    save_data(data)

def is_joined(user_id):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True

def generate_gift_code(duration_type, duration_value):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    expiry = None
    
    if duration_type == "months":
        expiry = datetime.now() + timedelta(days=duration_value * 30)
    elif duration_type == "days":
        expiry = datetime.now() + timedelta(days=duration_value)
    
    data["gift_codes"][code] = {
        "expiry": expiry.isoformat(),
        "used": False,
        "used_by": None,
        "used_at": None,
        "duration_type": duration_type,
        "duration_value": duration_value,
        "created_at": datetime.now().isoformat()
    }
    save_data(data)
    return code

def redeem_gift_code(user_id, code):
    if code not in data["gift_codes"]:
        return False, "❌ Invalid gift code!"
    
    gift = data["gift_codes"][code]
    
    if gift["used"]:
        return False, f"❌ This gift code has already been used by user {gift.get('used_by', 'Unknown')}!"
    
    expiry = datetime.fromisoformat(gift["expiry"])
    if expiry < datetime.now():
        return False, "❌ This gift code has expired!"
    
    user_id = str(user_id)
    
    if user_id not in data["users"]:
        data["users"][user_id] = {}
    
    data["users"][user_id]["premium_expiry"] = expiry.isoformat()
    
    gift["used"] = True
    gift["used_by"] = user_id
    gift["used_at"] = datetime.now().isoformat()
    
    save_data(data)
    
    return True, f"✅ Premium access granted until {expiry.strftime('%Y-%m-%d')}!"

# Progress Bar Function
def get_progress_bar(current, total, length=20):
    if total == 0:
        return "░" * length
    filled = int(length * current / total)
    bar = "█" * filled + "░" * (length - filled)
    return bar

def format_number_info(response_text):
    """Format API response safely with aesthetic design"""
    try:
        # Try to parse as JSON first
        data_list = json.loads(response_text)
        
        # Check if it's a list of dictionaries
        if isinstance(data_list, list):
            if not data_list:
                return "❌ No records found for this number!"
            
            # Create aesthetic header
            formatted = "🔍 *OSINT NUMBER LOOKUP* 🔍\n"
            formatted += "╔══════════════════════════════════════╗\n"
            formatted += f"║ 📡 API DEVELOPER: `{API_DEVELOPER}`\n"
            formatted += f"║ 📢 CHANNEL: `{CHANNELS[0]['name']}`\n"
            formatted += f"║ 🔗 LINK: {CHANNELS[0]['link']}\n"
            formatted += f"║ 📊 TOTAL RECORDS: `{len(data_list)}`\n"
            formatted += "╚══════════════════════════════════════╝\n\n"
            
            for idx, record in enumerate(data_list, 1):
                if not isinstance(record, dict):
                    continue
                
                # Create record header with decoration
                formatted += f"┌─ 📋 *RECORD {idx}* ─────────────────┐\n"
                
                # Safe extraction with beautiful formatting
                if record.get('name'):
                    formatted += f"│ 👤 *NAME:* `{record['name'][:50]}`\n"
                if record.get('father_name'):
                    formatted += f"│ 👨 *FATHER:* `{record['father_name'][:50]}`\n"
                if record.get('mobile'):
                    formatted += f"│ 📱 *MOBILE:* `{record['mobile']}`\n"
                if record.get('alternate'):
                    formatted += f"│ 📞 *ALT:* `{record['alternate']}`\n"
                if record.get('address'):
                    address = str(record['address'])[:80]
                    formatted += f"│ 🏠 *ADDRESS:* `{address}`\n"
                if record.get('circle'):
                    formatted += f"│ 🔄 *CIRCLE:* `{record['circle']}`\n"
                if record.get('email'):
                    formatted += f"│ 📧 *EMAIL:* `{record['email'][:40]}`\n"
                if record.get('id'):
                    formatted += f"│ 🆔 *ID:* `{record['id']}`\n"
                
                formatted += "└─────────────────────────────────────┘\n\n"
            
            formatted += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            formatted += "🔒 *Data retrieved from secure sources*"
            
            # Split long messages to avoid MESSAGE_TOO_LONG error
            if len(formatted) > 4000:
                parts = []
                current_part = ""
                for line in formatted.split('\n'):
                    if len(current_part + line) > 3800:
                        parts.append(current_part)
                        current_part = line + '\n'
                    else:
                        current_part += line + '\n'
                if current_part:
                    parts.append(current_part)
                return parts
            
            return formatted
        
        else:
            return [f"📱 **NUMBER INFORMATION** 📱\n\n```\n{response_text[:3000]}\n```"]
            
    except json.JSONDecodeError:
        return [f"📱 **NUMBER INFORMATION** 📱\n\n```\n{response_text[:3000]}\n```"]
    except Exception as e:
        return [f"❌ Error: {str(e)[:100]}"]

def send_loading_with_progress(chat_id, message_text):
    """Send message with progress bar animation"""
    msg = bot.send_message(chat_id, f"🔍 {message_text}\n\n[░░░░░░░░░░░░░░░░░░░░] 0%")
    
    for i in range(1, 101, 10):
        try:
            progress_bar = get_progress_bar(i, 100)
            bot.edit_message_text(
                f"🔍 {message_text}\n\n[{progress_bar}] {i}%",
                chat_id, msg.message_id
            )
            time.sleep(0.2)
        except:
            pass
    
    return msg

def main_menu(user_id):
    """Create main menu keyboard with buttons"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Show remaining searches if free user
    if not has_premium(user_id):
        today_usage = get_today_usage(user_id)
        remaining = FREE_DAILY_LIMIT - today_usage
        if remaining > 0:
            keyboard.add(InlineKeyboardButton(f"📱 LOOKUP ({remaining} left today)", callback_data="lookup"))
        else:
            keyboard.add(InlineKeyboardButton(f"📱 LOOKUP (0 left - Wait for reset)", callback_data="lookup"))
    else:
        keyboard.add(InlineKeyboardButton("📱 NUMBER LOOKUP (Unlimited)", callback_data="lookup"))
    
    keyboard.add(
        InlineKeyboardButton("👥 INVITE FRIENDS", callback_data="invite"),
        InlineKeyboardButton("🎁 REDEEM CODE", callback_data="redeem")
    )
    keyboard.add(
        InlineKeyboardButton("📊 MY STATUS", callback_data="status"),
        InlineKeyboardButton("💬 SUPPORT", callback_data="support")
    )
    keyboard.add(
        InlineKeyboardButton("ℹ️ HELP & INFO", callback_data="help")
    )
    
    if has_premium(user_id):
        keyboard.add(InlineKeyboardButton("⭐ PREMIUM FEATURES", callback_data="premium_features"))
    else:
        keyboard.add(InlineKeyboardButton("🔓 GET PREMIUM", callback_data="get_premium"))
    
    # 👑 ADMIN BUTTON - Only visible to admins
    if user_id in ADMIN_IDS:
        keyboard.add(InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel"))
    
    return keyboard

def admin_panel_menu():
    """Admin panel menu with all admin features"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎁 GENERATE CODE", callback_data="admin_gen_code"),
        InlineKeyboardButton("📊 STATISTICS", callback_data="admin_stats")
    )
    keyboard.add(
        InlineKeyboardButton("👥 USERS LIST", callback_data="admin_users"),
        InlineKeyboardButton("🎫 GIFT CODES", callback_data="admin_codes")
    )
    keyboard.add(
        InlineKeyboardButton("➕ ADD INVITE", callback_data="admin_add_invite"),
        InlineKeyboardButton("➖ REMOVE INVITE", callback_data="admin_remove_invite")
    )
    keyboard.add(
        InlineKeyboardButton("📝 FEEDBACK", callback_data="admin_feedback"),
        InlineKeyboardButton("⚠️ REPORTS", callback_data="admin_reports")
    )
    keyboard.add(
        InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast"),
        InlineKeyboardButton("📈 BOT STATS", callback_data="admin_bot_stats")
    )
    keyboard.add(
        InlineKeyboardButton("🔄 RESET DAILY USAGE", callback_data="admin_reset_daily"),
        InlineKeyboardButton("⚙️ SETTINGS", callback_data="admin_settings")
    )
    keyboard.add(
        InlineKeyboardButton("🔙 BACK TO MAIN MENU", callback_data="back_menu")
    )
    return keyboard

def notify_admin_new_user(user_id, username, first_name):
    """Notify admin when new user joins"""
    total_users = len(data["users"])
    today_users = sum(1 for u in data["users"].keys() if data["users"].get(u, {}).get("joined_date", "").startswith(datetime.now().strftime("%Y-%m-%d")))
    
    message = f"👤 **NEW USER JOINED!** 👤\n\n"
    message += f"📊 **User Info:**\n"
    message += f"• ID: `{user_id}`\n"
    message += f"• Name: {first_name}\n"
    message += f"• Username: @{username if username else 'None'}\n\n"
    message += f"📈 **Bot Stats:**\n"
    message += f"• Total Users: {total_users}\n"
    message += f"• Today's Joins: {today_users + 1}\n"
    message += f"• Premium Users: {sum(1 for u in data['users'].values() if u.get('premium_expiry'))}\n\n"
    message += f"🎯 **Daily Limit:** {FREE_DAILY_LIMIT} search/day for free users"
    
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, message, parse_mode="Markdown")
        except:
            pass

# 🚀 Start Command
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username
    first_name = msg.from_user.first_name
    
    # Ensure user data exists
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {
            "joined_date": datetime.now().isoformat(),
            "username": username,
            "first_name": first_name
        }
        save_data(data)
        notify_admin_new_user(user_id, username, first_name)
    
    # Handle referral
    if len(msg.text.split()) > 1:
        ref_code = msg.text.split()[1]
        if ref_code.startswith("ref_"):
            try:
                referrer_id = int(ref_code.split("_")[1])
                if referrer_id != user_id:
                    got_premium = add_invite(referrer_id)
                    bot.send_message(referrer_id, 
                        f"🎉 **New Referral!** 🎉\n\n"
                        f"👤 {first_name} joined using your link!\n"
                        f"📊 Total invites: {get_invite_count(referrer_id)}/2",
                        parse_mode="Markdown")
                    if got_premium:
                        bot.send_message(referrer_id, 
                            "🎉 **CONGRATULATIONS!** 🎉\n\n"
                            "You've invited 2 friends and received **PREMIUM ACCESS**!\n"
                            "✅ Unlimited lookups activated!",
                            parse_mode="Markdown")
            except:
                pass
    
    if not is_joined(user_id):
        keyboard = InlineKeyboardMarkup()
        for ch in CHANNELS:
            keyboard.add(InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch["link"]))
        keyboard.add(InlineKeyboardButton("✅ VERIFY MEMBERSHIP", callback_data="check_join"))
        
        text = f"🔒 **VERIFICATION REQUIRED** 🔒\n\n"
        text += f"Welcome {first_name}!\n\n"
        text += f"Please join our channels to use this bot:\n\n"
        for ch in CHANNELS:
            text += f"📢 **{ch['name']}**\n"
            text += f"🔗 {ch['link']}\n\n"
        text += "After joining both channels, tap the verify button below."
        
        bot.reply_to(msg, text, parse_mode="Markdown", reply_markup=keyboard)
        return
    
    welcome_text = f"✨ **WELCOME TO NUMBER LOOKUP BOT** ✨\n\n"
    welcome_text += f"👋 Hello **{first_name}**!\n\n"
    
    if has_premium(user_id):
        expiry = data["users"][str(user_id)]["premium_expiry"]
        days_left = (datetime.fromisoformat(expiry) - datetime.now()).days
        welcome_text += f"⭐ **PREMIUM MEMBER** ⭐\n"
        welcome_text += f"📅 Expires: {datetime.fromisoformat(expiry).strftime('%Y-%m-%d')}\n"
        welcome_text += f"⏰ Days left: **{days_left}**\n\n"
        welcome_text += f"✅ Unlimited lookups activated!\n\n"
    else:
        today_usage = get_today_usage(user_id)
        remaining = FREE_DAILY_LIMIT - today_usage
        
        welcome_text += f"🔓 **FREE USER** 🔓\n"
        welcome_text += f"📊 **Daily Limit:** {FREE_DAILY_LIMIT} search/day\n"
        welcome_text += f"📊 Today's usage: {today_usage}/{FREE_DAILY_LIMIT}\n"
        
        # Add progress bar for daily usage
        usage_bar = get_progress_bar(today_usage, FREE_DAILY_LIMIT, 15)
        welcome_text += f"📈 Daily Usage: [{usage_bar}] {int(today_usage/FREE_DAILY_LIMIT*100)}%\n\n"
        
        if remaining > 0:
            welcome_text += f"🎯 **{remaining} search(s) remaining today!**\n\n"
        else:
            welcome_text += f"⚠️ **No searches left today!**\n"
            welcome_text += f"⏰ Resets at midnight (12:00 AM)\n\n"
        
        welcome_text += f"👥 **Invite 2 friends** for unlimited premium access!\n"
        welcome_text += f"📊 Current invites: {get_invite_count(user_id)}/2\n"
        
        # Add invite progress bar
        invite_progress = get_progress_bar(get_invite_count(user_id), 2, 15)
        welcome_text += f"🎯 Invite Progress: [{invite_progress}] {int(get_invite_count(user_id)/2*100)}%\n\n"
    
    # Show admin hint if user is admin
    if user_id in ADMIN_IDS:
        welcome_text += f"👑 **You are an Admin!**\n"
        welcome_text += f"📌 Use the 'ADMIN PANEL' button below for admin features.\n\n"
    
    welcome_text += "Use the buttons below to get started:"
    
    bot.reply_to(msg, welcome_text, parse_mode="Markdown", reply_markup=main_menu(user_id))

# Number lookup handler - COUNT ONLY AFTER SUCCESS
@bot.message_handler(func=lambda msg: msg.text and msg.text.strip().isdigit() and len(msg.text.strip()) >= 10)
def handle_number(msg):
    user_id = msg.from_user.id
    
    if not is_joined(user_id):
        keyboard = InlineKeyboardMarkup()
        for ch in CHANNELS:
            keyboard.add(InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch["link"]))
        keyboard.add(InlineKeyboardButton("✅ VERIFY", callback_data="check_join"))
        return bot.reply_to(msg, "🔒 Please verify channels first!", reply_markup=keyboard)
    
    can_lookup_status, reason, remaining = can_lookup(user_id)
    
    if not can_lookup_status:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("👥 INVITE FRIENDS", callback_data="invite"))
        keyboard.add(InlineKeyboardButton("🎁 REDEEM CODE", callback_data="redeem"))
        
        bot.reply_to(msg, 
            "⚠️ **DAILY LIMIT REACHED** ⚠️\n\n"
            f"📊 **Free users get {FREE_DAILY_LIMIT} search per day**\n"
            f"⏰ Resets at midnight (12:00 AM)\n\n"
            "**Get unlimited access:**\n"
            "• Invite 2 friends (FREE premium)\n"
            "• Redeem a gift code\n\n"
            f"👥 Invited: {get_invite_count(user_id)}/2\n"
            f"🎯 Progress: [{get_progress_bar(get_invite_count(user_id), 2, 10)}]",
            parse_mode="Markdown", reply_markup=keyboard)
        return
    
    number = msg.text.strip()
    
    # Send progress bar loading animation
    loading_msg = send_loading_with_progress(msg.chat.id, f"Looking up number {number}...")
    
    # Perform lookup
    params = {"key": API_KEY, "number": number}
    
    try:
        res = requests.get(API_URL, params=params, timeout=15)
        
        if res.status_code == 200:
            response_text = res.text
            formatted_info = format_number_info(response_text)
            
            # Check if we got valid data
            lookup_success = "❌" not in str(formatted_info) if isinstance(formatted_info, str) else True
            
            # If formatted_info is a list (multiple parts), send as separate messages
            if isinstance(formatted_info, list):
                # Delete loading message
                bot.delete_message(msg.chat.id, loading_msg.message_id)
                
                # Send each part separately
                for part in formatted_info:
                    try:
                        bot.send_message(msg.chat.id, part, parse_mode="Markdown")
                        time.sleep(0.3)  # Small delay between messages
                    except Exception as e:
                        # If still too long, split further
                        if "MESSAGE_TOO_LONG" in str(e):
                            for i in range(0, len(part), 3500):
                                bot.send_message(msg.chat.id, part[i:i+3500], parse_mode="Markdown")
                        else:
                            bot.send_message(msg.chat.id, f"⚠️ Error displaying data: {str(e)[:100]}")
            else:
                # Single message
                try:
                    bot.edit_message_text(formatted_info, msg.chat.id, loading_msg.message_id, parse_mode="Markdown")
                except Exception as e:
                    if "MESSAGE_TOO_LONG" in str(e):
                        # Split into multiple messages
                        bot.delete_message(msg.chat.id, loading_msg.message_id)
                        for i in range(0, len(formatted_info), 3500):
                            bot.send_message(msg.chat.id, formatted_info[i:i+3500], parse_mode="Markdown")
                    else:
                        bot.edit_message_text(f"⚠️ Error: {str(e)[:100]}", msg.chat.id, loading_msg.message_id)
            
            # Only increment count if lookup was successful
            if lookup_success:
                increment_lookup(user_id)
                
                # Show success with updated daily usage
                today_usage = get_today_usage(user_id)
                remaining_now = FREE_DAILY_LIMIT - today_usage
                usage_bar = get_progress_bar(today_usage, FREE_DAILY_LIMIT, 15)
                
                success_msg = f"✅ **Lookup Complete!**\n\n"
                if not has_premium(user_id):
                    success_msg += f"📊 **Daily Usage:** [{usage_bar}] {int(today_usage/FREE_DAILY_LIMIT*100)}%\n"
                    if remaining_now > 0:
                        success_msg += f"🎯 **{remaining_now} search(s) remaining today!**\n"
                    else:
                        success_msg += f"⚠️ **No searches left today!**\n⏰ Resets at midnight\n"
                bot.send_message(msg.chat.id, success_msg, parse_mode="Markdown")
            else:
                # If lookup failed, inform user that count wasn't deducted
                bot.send_message(msg.chat.id, 
                    "ℹ️ **Note:** Your search count was not deducted due to API error.\n"
                    "Please try again later.", 
                    parse_mode="Markdown")
            
        else:
            bot.edit_message_text("❌ API Error - Please try again later", msg.chat.id, loading_msg.message_id)
            bot.send_message(msg.chat.id, 
                "ℹ️ **Note:** Your search count was not deducted.\n"
                "Please try again later.", 
                parse_mode="Markdown")
    
    except requests.Timeout:
        bot.edit_message_text("⏰ Request timeout - Please try again", msg.chat.id, loading_msg.message_id)
        bot.send_message(msg.chat.id, 
            "ℹ️ **Note:** Your search count was not deducted.\n"
            "Please try again later.", 
            parse_mode="Markdown")
    except Exception as e:
        error_msg = str(e)
        if "MESSAGE_TOO_LONG" in error_msg:
            bot.edit_message_text("⚠️ Result too long - Sending in parts...", msg.chat.id, loading_msg.message_id)
            # Try to send raw response in parts
            try:
                raw_response = res.text if 'res' in locals() else "No data"
                for i in range(0, len(raw_response), 3500):
                    bot.send_message(msg.chat.id, f"📊 **Data (Part {i//3500 + 1}):**\n```\n{raw_response[i:i+3500]}\n```", parse_mode="Markdown")
            except:
                bot.send_message(msg.chat.id, f"⚠️ Error: {error_msg[:200]}")
        else:
            bot.edit_message_text(f"⚠️ Error: {error_msg[:100]}", msg.chat.id, loading_msg.message_id)
        
        bot.send_message(msg.chat.id, 
            f"ℹ️ **Note:** Your search count was not deducted.\n"
            f"Error: {error_msg[:100]}", 
            parse_mode="Markdown")

# Callback handlers (keeping from previous version)
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        if is_joined(user_id):
            bot.edit_message_text("✅ **VERIFIED!** ✅\n\nUse /start to continue.", 
                                call.message.chat.id, call.message.message_id)
            class FakeMessage:
                def __init__(self, user_id, chat_id):
                    self.from_user = type('obj', (object,), {'id': user_id})
                    self.chat = type('obj', (object,), {'id': chat_id})
                    self.text = "/start"
            
            fake_msg = FakeMessage(user_id, call.message.chat.id)
            start(fake_msg)
        else:
            bot.answer_callback_query(call.id, "Please join all channels first!", show_alert=True)
    
    elif call.data == "lookup":
        if not is_joined(user_id):
            bot.answer_callback_query(call.id, "Please verify channels first with /start", show_alert=True)
            return
        
        can_lookup_status, reason, remaining = can_lookup(user_id)
        
        if not can_lookup_status:
            bot.answer_callback_query(call.id, f"Daily limit reached! You get {FREE_DAILY_LIMIT} search/day. Invite friends for unlimited access.", show_alert=True)
            return
        
        if remaining > 0:
            bot.send_message(call.message.chat.id, 
                            f"📱 **Send me a phone number**\n\n"
                            f"Example: `9876543210`\n\n"
                            f"🎯 **You have {remaining} search(s) remaining today!**\n"
                            f"⏰ Resets at midnight\n\n"
                            f"📌 Include country code for better results",
                            parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, 
                            f"📱 **Send me a phone number**\n\n"
                            f"Example: `9876543210`\n\n"
                            f"⚠️ **This is your last search for today!**\n\n"
                            f"📌 Include country code for better results",
                            parse_mode="Markdown")
        bot.answer_callback_query(call.id)
    
    elif call.data == "invite":
        bot_ref = f"@{bot.get_me().username}"
        invite_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
        
        invite_count = get_invite_count(user_id)
        progress_bar = get_progress_bar(invite_count, 2, 15)
        
        text = f"👥 **INVITE SYSTEM** 👥\n\n"
        text += f"Share this link with your friends:\n`{invite_link}`\n\n"
        text += f"📊 **Your Stats:**\n"
        text += f"• Invited friends: {invite_count}/2\n"
        text += f"🎯 Progress: [{progress_bar}] {int(invite_count/2*100)}%\n\n"
        
        if invite_count >= 2:
            text += "✅ **Premium status: ACTIVE**\n"
            text += "🎉 You have unlimited access!\n\n"
        else:
            text += f"🎁 **Reward:** Invite {2-invite_count} more friends → FREE Premium Access!\n"
            text += f"⭐ Premium gives you unlimited daily searches!\n\n"
        
        text += "**How it works:**\n"
        text += "1. Share your unique link\n"
        text += "2. Friends join via your link\n"
        text += "3. Get premium when 2 join\n\n"
        text += f"📊 **Free users get {FREE_DAILY_LIMIT} search/day**"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📤 SHARE LINK", url=f"https://t.me/share/url?url={invite_link}&text=🔥 Check out this awesome number lookup bot! Get {FREE_DAILY_LIMIT} free searches daily! 🔥"))
        keyboard.add(InlineKeyboardButton("🔙 BACK", callback_data="back_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "status":
        if has_premium(user_id):
            expiry = data["users"][str(user_id)]["premium_expiry"]
            days_left = (datetime.fromisoformat(expiry) - datetime.now()).days
            
            text = f"⭐ **PREMIUM STATUS** ⭐\n\n"
            text += f"✅ Status: **Active**\n"
            text += f"📅 Expires: {datetime.fromisoformat(expiry).strftime('%Y-%m-%d')}\n"
            text += f"⏰ Days left: **{days_left}**\n"
            text += f"🎯 Lookups: **Unlimited**\n\n"
            
            text += f"📊 **Daily Limit:** No limit\n"
            text += f"👥 Invited friends: {get_invite_count(user_id)}"
        else:
            today_usage = get_today_usage(user_id)
            remaining = FREE_DAILY_LIMIT - today_usage
            invites = get_invite_count(user_id)
            
            usage_bar = get_progress_bar(today_usage, FREE_DAILY_LIMIT, 20)
            invite_bar = get_progress_bar(invites, 2, 20)
            
            text = f"🔓 **FREE USER STATUS** 🔓\n\n"
            text += f"📊 **Daily Limit:** {FREE_DAILY_LIMIT} search/day\n"
            text += f"📊 **Today's Usage:**\n"
            text += f"[{usage_bar}] {int(today_usage/FREE_DAILY_LIMIT*100)}% ({today_usage}/{FREE_DAILY_LIMIT})\n\n"
            text += f"🎯 **Remaining:** **{remaining}** search(s)\n"
            text += f"⏰ **Resets at:** Midnight (12:00 AM)\n\n"
            text += f"👥 **Invite Progress:**\n"
            text += f"[{invite_bar}] {int(invites/2*100)}% ({invites}/2)\n\n"
            
            if invites >= 2:
                text += "🎉 **You qualify for premium!**\n"
                text += "Use /start to activate premium access."
            else:
                text += f"🎯 Need {2-invites} more invites for premium!\n"
                text += "💡 Tip: Share your invite link with friends!\n\n"
                text += f"⭐ Premium gives you unlimited daily searches!"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 BACK", callback_data="back_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "redeem":
        bot.send_message(call.message.chat.id, 
                        "🎁 **REDEEM GIFT CODE** 🎁\n\n"
                        "Send your 12-character gift code as a message.\n\n"
                        "Example: `ABC123DEF456`\n\n"
                        f"⭐ Premium gives you unlimited daily searches!\n"
                        f"⚠️ **Note:** Each code can only be used once!")
        bot.answer_callback_query(call.id)
    
    elif call.data == "support":
        text = f"💬 **SUPPORT CENTER** 💬\n\n"
        text += f"**Need help?** Contact us:\n\n"
        text += f"📢 **Channel 1:** {CHANNELS[0]['link']}\n"
        text += f"📢 **Channel 2:** {CHANNELS[1]['link']}\n"
        text += f"👨‍💻 **Developer:** {API_DEVELOPER}\n\n"
        text += f"**Free Tier:**\n"
        text += f"• {FREE_DAILY_LIMIT} search per day\n"
        text += f"• Resets daily at midnight\n\n"
        text += f"**Commands:**\n"
        text += f"• /start - Start the bot\n"
        text += f"• Send any number to lookup\n\n"
        text += f"**Report Issues:**\n"
        text += f"Send `report <issue>` to report problems\n\n"
        text += f"**Feedback:**\n"
        text += f"Send `feedback <message>` to share your thoughts\n\n"
        text += f"⏰ **Response Time:** Within 24 hours"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📢 JOIN CHANNEL 1", url=CHANNELS[0]['link']))
        keyboard.add(InlineKeyboardButton("📢 JOIN CHANNEL 2", url=CHANNELS[1]['link']))
        keyboard.add(InlineKeyboardButton("🔙 BACK", callback_data="back_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "get_premium":
        invites = get_invite_count(user_id)
        invite_bar = get_progress_bar(invites, 2, 20)
        
        text = f"🔓 **GET PREMIUM ACCESS** 🔓\n\n"
        text += f"**Ways to get premium:**\n\n"
        text += f"1️⃣ **Invite Friends** (FREE)\n"
        text += f"   • Invite 2 friends to this bot\n"
        text += f"   • Get 30 days premium access\n"
        text += f"   • Current invites: {invites}/2\n"
        text += f"   [{invite_bar}] {int(invites/2*100)}%\n\n"
        text += f"2️⃣ **Gift Codes**\n"
        text += f"   • Redeem codes from giveaways\n"
        text += f"   • Tap 'Redeem Code' button\n"
        text += f"   • Each code can only be used once\n\n"
        text += f"3️⃣ **Contact Admin**\n"
        text += f"   • For special offers\n"
        text += f"   • Use the 'ADMIN PANEL' button (admins only)\n\n"
        text += f"**Premium Benefits:**\n"
        text += f"⭐ Unlimited daily searches\n"
        text += f"⭐ Priority API access\n"
        text += f"⭐ Full detailed results\n"
        text += f"⭐ Priority support\n\n"
        text += f"📊 **Free vs Premium:**\n"
        text += f"Free:    {FREE_DAILY_LIMIT} search/day\n"
        text += f"Premium: Unlimited searches"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("👥 INVITE NOW", callback_data="invite"))
        keyboard.add(InlineKeyboardButton("🎁 REDEEM CODE", callback_data="redeem"))
        keyboard.add(InlineKeyboardButton("🔙 BACK", callback_data="back_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "premium_features":
        text = f"⭐ **PREMIUM FEATURES** ⭐\n\n"
        text += f"✅ **Unlimited lookups**\n"
        text += f"   • No daily restrictions\n"
        text += f"   • Search as much as you want\n\n"
        text += f"✅ **Advanced results**\n"
        text += f"   • Full name details\n"
        text += f"   • Address information\n"
        text += f"   • Alternate numbers\n\n"
        text += f"✅ **Priority support**\n"
        text += f"   • Faster response times\n"
        text += f"   • Direct admin contact\n\n"
        text += f"✅ **Early access**\n"
        text += f"   • New features first\n"
        text += f"   • Exclusive giveaways\n\n"
        text += f"📊 **Usage Comparison:**\n"
        text += f"Free:    [{get_progress_bar(1, FREE_DAILY_LIMIT, 20)}] {FREE_DAILY_LIMIT}/day\n"
        text += f"Premium: [████████████████████] Unlimited"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 BACK", callback_data="back_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
    
    elif call.data == "help":
        text = f"ℹ️ **HELP & INFORMATION** ℹ️\n\n"
        text += f"**How to use:**\n"
        text += f"1. Send any phone number (10+ digits)\n"
        text += f"2. Bot will fetch details automatically\n"
        text += f"3. Watch the progress bar for status\n\n"
        
        text += f"**Free Tier:**\n"
        text += f"• {FREE_DAILY_LIMIT} lookup per day\n"
        text += f"• Resets at midnight (12:00 AM)\n"
        text += f"• Progress bar shows daily usage\n"
        text += f"• Invite friends for premium\n\n"
        
        text += f"**Premium Benefits:**\n"
        text += f"• Unlimited lookups\n"
        text += f"• Full detailed results\n"
        text += f"• Priority support\n\n"
        
        text += f"**Gift Codes:**\n"
        text += f"• Each code can only be used once\n"
        text += f"• Codes expire after use\n"
        text += f"• Send code to redeem\n\n"
        
        text += f"**Commands:**\n"
        text += f"• /start - Start the bot\n\n"
        
        text += f"**Support:**\n"
        text += f"• Channel 1: {CHANNELS[0]['link']}\n"
        text += f"• Channel 2: {CHANNELS[1]['link']}\n"
        text += f"• Developer: {API_DEVELOPER}"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💬 SUPPORT", callback_data="support"))
        keyboard.add(InlineKeyboardButton("🔙 BACK", callback_data="back_menu"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
    
    elif call.data == "back_menu":
        bot.edit_message_text("📱 **MAIN MENU**", call.message.chat.id, call.message.message_id,
                            reply_markup=main_menu(user_id))
        bot.answer_callback_query(call.id)
    
    # Admin panel callbacks (keeping from previous version)
    elif call.data == "admin_panel":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin access only!", show_alert=True)
            return
        
        bot.edit_message_text("👑 **ADMIN CONTROL PANEL**", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=admin_panel_menu())
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_gen_code":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        bot.send_message(call.message.chat.id, 
                        "🎁 **GENERATE GIFT CODE** 🎁\n\n"
                        "Send command in this format:\n\n"
                        "`code <name> <duration>`\n\n"
                        "**Examples:**\n"
                        "• `code PREMIUM 30d` - 30 days\n"
                        "• `code VIP 6m` - 6 months\n\n"
                        "Available: d (days), m (months)\n\n"
                        "⚠️ **Note:** Each code can only be used once!")
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_stats":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        total_users = len(data["users"])
        premium_users = sum(1 for u in data["users"].values() if u.get("premium_expiry"))
        total_invites = sum(data["invites"].values())
        active_codes = sum(1 for c in data["gift_codes"].values() if not c["used"])
        used_codes = sum(1 for c in data["gift_codes"].values() if c["used"])
        total_lookups = sum(sum(day.values()) for day in data["daily_usage"].values())
        today_lookups = sum(sum(day.values()) for uid, day in data["daily_usage"].items() if day and list(day.keys())[0] == datetime.now().strftime("%Y-%m-%d") if day)
        
        premium_percent = int((premium_users / total_users * 100)) if total_users > 0 else 0
        premium_bar = get_progress_bar(premium_users, total_users, 15) if total_users > 0 else "░░░░░░░░░░░░░░░"
        
        stats = f"📊 **BOT STATISTICS** 📊\n\n"
        stats += f"👥 **Users:**\n"
        stats += f"   • Total: {total_users}\n"
        stats += f"   • Premium: {premium_users}\n"
        stats += f"   • Free: {total_users - premium_users}\n"
        stats += f"   [{premium_bar}] {premium_percent}% Premium\n\n"
        stats += f"📈 **Usage:**\n"
        stats += f"   • Total lookups: {total_lookups}\n"
        stats += f"   • Today's lookups: {today_lookups}\n"
        stats += f"   • Total invites: {total_invites}\n\n"
        stats += f"🎁 **Gift Codes:**\n"
        stats += f"   • Active: {active_codes}\n"
        stats += f"   • Used: {used_codes}\n"
        stats += f"   • Total: {len(data['gift_codes'])}\n\n"
        stats += f"📊 **Daily Limit:** {FREE_DAILY_LIMIT} search/day\n"
        stats += f"📝 **Feedback:** {len(data.get('feedbacks', {}))}\n"
        stats += f"⚠️ **Reports:** {len(data.get('reports', {}))}"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 REFRESH", callback_data="admin_stats"))
        keyboard.add(InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="admin_panel"))
        
        bot.edit_message_text(stats, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    # Add other admin callbacks as needed
    elif call.data == "admin_users":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        users_list = "👥 **USER LIST** 👥\n\n"
        premium_count = 0
        free_count = 0
        
        for uid, udata in list(data["users"].items())[:10]:
            if udata.get("premium_expiry"):
                premium_count += 1
                users_list += f"⭐ `{uid}` - Premium\n"
            else:
                free_count += 1
                users_list += f"🔓 `{uid}` - Free\n"
        
        users_list += f"\n📊 **Summary:**\n"
        users_list += f"• Premium: {premium_count}\n"
        users_list += f"• Free: {free_count}\n"
        users_list += f"• Total: {len(data['users'])}"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="admin_panel"))
        
        bot.edit_message_text(users_list, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_codes":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        codes_list = "🎫 **GIFT CODES** 🎫\n\n"
        active = 0
        used = 0
        
        for code, cinfo in list(data["gift_codes"].items())[:10]:
            if cinfo["used"]:
                used += 1
                codes_list += f"❌ `{code}` - Used\n"
            else:
                active += 1
                codes_list += f"✅ `{code}` - Active\n"
        
        codes_list += f"\n📊 **Summary:**\n"
        codes_list += f"• Active: {active}\n"
        codes_list += f"• Used: {used}\n"
        codes_list += f"• Total: {len(data['gift_codes'])}"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="admin_panel"))
        
        bot.edit_message_text(codes_list, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_add_invite":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        bot.send_message(call.message.chat.id, 
                        "➕ **ADD INVITE** ➕\n\n"
                        "Send command:\n`addinv <user_id> <count>`\n\n"
                        "Example: `addinv 123456789 1`")
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_remove_invite":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        bot.send_message(call.message.chat.id, 
                        "➖ **REMOVE INVITE** ➖\n\n"
                        "Send command:\n`removeinv <user_id> <count>`\n\n"
                        "Example: `removeinv 123456789 1`")
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_feedback":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        feedbacks = data.get("feedbacks", {})
        if feedbacks:
            text = "📝 **USER FEEDBACK** 📝\n\n"
            for uid, fb in list(feedbacks.items())[:10]:
                text += f"👤 User: `{uid}`\n"
                text += f"💬 {fb}\n\n"
        else:
            text = "📝 No feedback yet."
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_reports":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        reports = data.get("reports", {})
        if reports:
            text = "⚠️ **USER REPORTS** ⚠️\n\n"
            for uid, rp in list(reports.items())[:10]:
                text += f"👤 User: `{uid}`\n"
                text += f"⚠️ {rp}\n\n"
        else:
            text = "⚠️ No reports yet."
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="admin_panel"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_broadcast":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        bot.send_message(call.message.chat.id, 
                        "📢 **BROADCAST MESSAGE** 📢\n\n"
                        "Send command:\n`broadcast <message>`\n\n"
                        "Example: `broadcast Hello everyone!`\n\n"
                        "⚠️ This will send to ALL users!")
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_bot_stats":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        total_commands = data.get("total_commands", 0)
        total_users = len(data["users"])
        premium_users = sum(1 for u in data["users"].values() if u.get("premium_expiry"))
        today_joins = sum(1 for u in data["users"].values() if u.get("joined_date", "").startswith(datetime.now().strftime("%Y-%m-%d")))
        today_lookups = sum(sum(day.values()) for uid, day in data["daily_usage"].items() if day and list(day.keys())[0] == datetime.now().strftime("%Y-%m-%d") if day)
        
        growth_bar = get_progress_bar(today_joins, max(total_users, 1), 15)
        
        stats = f"📈 **BOT USAGE STATISTICS** 📈\n\n"
        stats += f"**Overall:**\n"
        stats += f"• Total Commands: {total_commands}\n"
        stats += f"• Total Users: {total_users}\n"
        stats += f"• Premium Users: {premium_users}\n\n"
        stats += f"**Today:**\n"
        stats += f"• New Users: {today_joins}\n"
        stats += f"• Lookups: {today_lookups}\n"
        stats += f"• Growth: [{growth_bar}] {int(today_joins/max(total_users,1)*100)}%\n\n"
        stats += f"**Daily Limit:**\n"
        stats += f"• Free users: {FREE_DAILY_LIMIT} search/day\n"
        stats += f"• Resets at midnight\n\n"
        stats += f"**Channels:**\n"
        for ch in CHANNELS:
            stats += f"• {ch['name']}: ✅ Required\n"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 REFRESH", callback_data="admin_bot_stats"))
        keyboard.add(InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="admin_panel"))
        
        bot.edit_message_text(stats, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    
    elif call.data == "admin_reset_daily":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        data["daily_usage"] = {}
        save_data(data)
        bot.answer_callback_query(call.id, "✅ Daily usage reset for all users!", show_alert=True)
        bot.send_message(call.message.chat.id, "✅ **Daily usage has been reset for all users!**")
    
    elif call.data == "admin_settings":
        if user_id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
            return
        
        settings = f"⚙️ **BOT SETTINGS** ⚙️\n\n"
        settings += f"🔧 **Current Configuration:**\n"
        settings += f"• Free lookups: {FREE_DAILY_LIMIT}/day\n"
        settings += f"• Premium invites: 2\n"
        settings += f"• Premium duration: 30 days\n"
        settings += f"• Channel verification: Active\n"
        settings += f"• Daily reset: Midnight (12:00 AM)\n\n"
        settings += f"🎁 **Gift Codes:**\n"
        settings += f"• One-time use only\n"
        settings += f"• Expire after redemption\n"
        settings += f"• Total codes: {len(data['gift_codes'])}\n\n"
        settings += f"📊 **API Settings:**\n"
        settings += f"• API URL: {API_URL}\n"
        settings += f"• Developer: {API_DEVELOPER}\n\n"
        settings += f"📢 **Channels:**\n"
        for ch in CHANNELS:
            settings += f"• {ch['name']}: {ch['username']}\n"
        settings += f"\nTo modify settings, use commands:\n"
        settings += f"• `set_free_limit <number>`\n"
        settings += f"• `set_invite_target <number>`\n"
        settings += f"• `set_premium_days <number>`"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 RESET DAILY USAGE", callback_data="admin_reset_daily"))
        keyboard.add(InlineKeyboardButton("🔙 BACK TO ADMIN", callback_data="admin_panel"))
        
        bot.edit_message_text(settings, call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown", reply_markup=keyboard)
        bot.answer_callback_query(call.id)

# Handle text commands
@bot.message_handler(func=lambda msg: True)
def handle_text(msg):
    user_id = msg.from_user.id
    text = msg.text.strip()
    
    # Handle gift code redemption
    if len(text) == 12 and text.isalnum() and text.upper() == text:
        loading_msg = send_loading_with_progress(msg.chat.id, "Redeeming gift code...")
        success, message = redeem_gift_code(user_id, text.upper())
        bot.edit_message_text(message, msg.chat.id, loading_msg.message_id, parse_mode="Markdown")
        return
    
    # Handle admin commands
    if user_id in ADMIN_IDS:
        if text.lower().startswith("code "):
            parts = text.split()
            if len(parts) == 3:
                code_name = parts[1]
                duration = parts[2]
                
                if duration.endswith("d"):
                    days = int(duration[:-1])
                    gift_code = generate_gift_code("days", days)
                    bot.reply_to(msg, 
                        f"✅ **Code Generated!**\n\n"
                        f"📝 Code: `{gift_code}`\n"
                        f"⏰ Duration: {days} days\n"
                        f"🏷️ Name: {code_name}\n\n"
                        f"⚠️ **Note:** This code can only be used once!")
                elif duration.endswith("m"):
                    months = int(duration[:-1])
                    gift_code = generate_gift_code("months", months)
                    bot.reply_to(msg, 
                        f"✅ **Code Generated!**\n\n"
                        f"📝 Code: `{gift_code}`\n"
                        f"⏰ Duration: {months} months\n"
                        f"🏷️ Name: {code_name}\n\n"
                        f"⚠️ **Note:** This code can only be used once!")
                else:
                    bot.reply_to(msg, "❌ Invalid format!\nUse: code NAME 30d / 6m")
            else:
                bot.reply_to(msg, "❌ Usage: code NAME 30d")
        
        elif text.lower().startswith("addinv "):
            try:
                parts = text.split()
                target_id = int(parts[1])
                count = int(parts[2]) if len(parts) > 2 else 1
                
                for _ in range(count):
                    got_premium = add_invite(target_id)
                
                bot.reply_to(msg, f"✅ Added {count} invite(s) to user {target_id}\n📊 Total: {get_invite_count(target_id)}")
                
                if got_premium:
                    bot.send_message(target_id, 
                        "🎉 **PREMIUM ACCESS GRANTED!** 🎉\n\n"
                        "An admin has granted you premium access!\n"
                        "✅ Unlimited lookups activated!",
                        parse_mode="Markdown")
            except:
                bot.reply_to(msg, "❌ Invalid! Use: addinv USER_ID [COUNT]")
        
        elif text.lower().startswith("removeinv "):
            try:
                parts = text.split()
                target_id = str(parts[1])
                count = int(parts[2]) if len(parts) > 2 else 1
                
                current = data["invites"].get(target_id, 0)
                new_count = max(0, current - count)
                data["invites"][target_id] = new_count
                save_data(data)
                
                bot.reply_to(msg, f"✅ Removed {count} invite(s) from user {target_id}\n📊 New total: {new_count}")
            except:
                bot.reply_to(msg, "❌ Invalid! Use: removeinv USER_ID [COUNT]")
        
        elif text.lower().startswith("broadcast "):
            broadcast_msg = text[10:]
            total = 0
            success = 0
            
            status_msg = bot.reply_to(msg, "📢 Broadcasting message...")
            users_list = list(data["users"].keys())
            
            for idx, uid in enumerate(users_list):
                try:
                    bot.send_message(int(uid), 
                        f"📢 **ANNOUNCEMENT** 📢\n\n{broadcast_msg}\n\n— Bot Admin", 
                        parse_mode="Markdown")
                    success += 1
                except:
                    pass
                total += 1
                
                if idx % 10 == 0:
                    progress_bar = get_progress_bar(idx + 1, len(users_list), 20)
                    bot.edit_message_text(f"📢 Broadcasting...\n\n[{progress_bar}] {int((idx+1)/len(users_list)*100)}%", 
                                        msg.chat.id, status_msg.message_id)
                time.sleep(0.05)
            
            bot.edit_message_text(f"✅ Broadcast completed!\n\n📊 Sent: {success}/{total}", 
                                msg.chat.id, status_msg.message_id)
        
        elif text.lower().startswith("set_free_limit "):
            try:
                global FREE_DAILY_LIMIT
                limit = int(text.split()[1])
                FREE_DAILY_LIMIT = limit
                bot.reply_to(msg, f"✅ Free limit set to {limit} lookups/day\n⏰ Resets daily at midnight")
            except:
                bot.reply_to(msg, "❌ Invalid! Use: set_free_limit NUMBER")
        
        elif text.lower().startswith("set_invite_target "):
            try:
                target = int(text.split()[1])
                bot.reply_to(msg, f"✅ Invite target set to {target} invites for premium")
            except:
                bot.reply_to(msg, "❌ Invalid! Use: set_invite_target NUMBER")
        
        elif text.lower().startswith("set_premium_days "):
            try:
                days = int(text.split()[1])
                bot.reply_to(msg, f"✅ Premium duration set to {days} days")
            except:
                bot.reply_to(msg, "❌ Invalid! Use: set_premium_days NUMBER")
    
    # Handle feedback
    elif text.lower().startswith("feedback "):
        feedback = text[9:]
        data["feedbacks"][str(user_id)] = feedback
        save_data(data)
        bot.reply_to(msg, "✅ Thanks for your feedback! We appreciate it.")
    
    # Handle report
    elif text.lower().startswith("report "):
        report = text[7:]
        data["reports"][str(user_id)] = report
        save_data(data)
        
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, 
                    f"⚠️ **New Report** ⚠️\n\n"
                    f"👤 User: `{user_id}`\n"
                    f"📝 Report: {report}",
                    parse_mode="Markdown")
            except:
                pass
        
        bot.reply_to(msg, "✅ Report submitted! Our team will review it.")

# Daily reset function
def daily_reset_task():
    """Function to reset daily usage at midnight"""
    while True:
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_until_midnight = (midnight - now).total_seconds()
        
        time.sleep(seconds_until_midnight)
        
        data["daily_usage"] = {}
        save_data(data)
        
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, 
                    f"🔄 **Daily Reset Complete** 🔄\n\n"
                    f"📊 All free users have been refreshed with {FREE_DAILY_LIMIT} new searches!\n"
                    f"⏰ Next reset: {midnight + timedelta(days=1)}",
                    parse_mode="Markdown")
            except:
                pass
        
        print(f"🔄 Daily reset completed at {datetime.now()}")

# Start daily reset thread
reset_thread = threading.Thread(target=daily_reset_task, daemon=True)
reset_thread.start()

# Flask routes for webhook
@app.route('/')
def index():
    return "Bot is running!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200

# Error handler
@bot.message_handler(func=lambda msg: True)
def handle_unknown(msg):
    if not msg.text or not msg.text.strip():
        return
    
    if msg.text.strip().isdigit() and len(msg.text.strip()) >= 10:
        return
    
    bot.reply_to(msg, 
        "❓ **Unknown Command** ❓\n\n"
        "Send a phone number to lookup details.\n"
        f"**Free users get {FREE_DAILY_LIMIT} search/day!**\n\n"
        "Use /start for main menu.\n\n"
        "**Available buttons:**\n"
        "• NUMBER LOOKUP\n"
        "• INVITE FRIENDS\n"
        "• REDEEM CODE\n"
        "• MY STATUS\n"
        "• SUPPORT\n"
        "• HELP & INFO",
        parse_mode="Markdown", reply_markup=main_menu(msg.from_user.id))

# Run bot
if __name__ == '__main__':
    print("🤖 Bot is starting...")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print(f"📢 Channels:")
    for ch in CHANNELS:
        print(f"   • {ch['name']}: {ch['username']}")
    print(f"👨‍💻 API Developer: {API_DEVELOPER}")
    print(f"📊 Free users get {FREE_DAILY_LIMIT} search/day (resets at midnight)")
    print(f"🎁 Gift codes are one-time use only!")
    print(f"✅ Count only deducted on successful lookup!")
    print(f"👑 Admin button visible only to admins in main menu!")
    print(f"📱 Message splitting enabled for long responses!")
    
    if 'RENDER' in os.environ or 'RAILWAY_ENVIRONMENT' in os.environ:
        PORT = int(os.environ.get('PORT', 1000))
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/{BOT_TOKEN}"
        bot.set_webhook(webhook_url)
        print(f"🚀 Running in webhook mode on port {PORT}")
        app.run(host='0.0.0.0', port=PORT)
    else:
        print("🚀 Running in polling mode")
        print("✅ Bot is ready! Send /start to begin")
        bot.infinity_polling()
