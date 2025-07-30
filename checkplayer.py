import json
import os
import requests
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

DB_FILE = "users.json"

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! برای ثبت Steam ID خودت از دستور زیر استفاده کن:\n"
        "`/setid <steam32_id>`\n"
        "مثال:\n/setid 123456789"
    )

async def setid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("فرمت درست نیست. مثال: /setid 123456789")
        return

    steam_id = context.args[0]
    if not steam_id.isdigit():
        await update.message.reply_text("Steam ID باید عددی باشد.")
        return

    user_id = str(update.message.from_user.id)
    users = load_users()
    users[user_id] = steam_id
    save_users(users)
    await update.message.reply_text(f"✅ Steam ID شما ثبت شد: {steam_id}")

def fetch_json(url):
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
    except:
        return None
    return None

def get_hero_name(hero_id):
    url = "https://api.opendota.com/api/constants/heroes"
    data = fetch_json(url)
    if not data:
        return "Unknown"
    for hero_key, hero_data in data.items():
        if hero_data.get("id") == hero_id:
            return hero_data.get("localized_name", "Unknown")
    return "Unknown"

def get_items_names(item_ids):
    url = "https://api.opendota.com/api/constants/items"
    data = fetch_json(url)
    if not data:
        return []
    names = []
    for item_id in item_ids:
        if item_id == 0:
            continue
        for key, item in data.items():
            if item.get("id") == item_id:
                names.append(item.get("dname", "Unknown"))
                break
    return names

def get_player_info_from_match(match_detail, player_id):
    players = match_detail.get("players", [])
    player_info = None
    for p in players:
        if p.get("account_id") == player_id:
            player_info = p
            break
    if not player_info:
        return None

    hero_id = player_info.get("hero_id")
    hero_name = get_hero_name(hero_id)

    item_ids = [
        player_info.get(f"item_{i}", 0) for i in range(6)
    ] + [
        player_info.get(f"backpack_{i}", 0) for i in range(3)
    ] + [player_info.get("item_neutral", 0)]

    items_names = get_items_names(item_ids)

    info = {
        "hero_name": hero_name,
        "kills": player_info.get("kills", 0),
        "deaths": player_info.get("deaths", 0),
        "assists": player_info.get("assists", 0),
        "hero_damage": player_info.get("hero_damage", 0),
        "tower_damage": player_info.get("tower_damage", 0),
        "last_hits": player_info.get("last_hits", 0),
        "hero_healing": player_info.get("hero_healing", 0),
        "items": items_names,
        "player_slot": player_info.get("player_slot"),
        "radiant_win": match_detail.get("radiant_win", False),
        "duration": match_detail.get("duration", 0),
        "match_id": match_detail.get("match_id")
    }
    return info

def check_common_matches(my_id: int, target_id: int):
    recent_matches_url = f"https://api.opendota.com/api/players/{my_id}/recentMatches?limit=20"
    recent_matches = fetch_json(recent_matches_url)
    if not recent_matches:
        return []

    common_matches = []

    for match in recent_matches:
        match_id = match.get("match_id")
        if not match_id:
            continue

        match_detail_url = f"https://api.opendota.com/api/matches/{match_id}"
        match_detail = fetch_json(match_detail_url)
        if not match_detail:
            continue

        players = match_detail.get("players", [])
        for player in players:
            if player.get("account_id") == target_id:
                common_matches.append(match_detail)
                break

    return common_matches

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("مثال درست: /check 123456789")
        return

    target_id_str = context.args[0]
    if not target_id_str.isdigit():
        await update.message.reply_text("Steam ID باید عددی باشد.")
        return

    target_id = int(target_id_str)
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text("❌ اول باید Steam ID خودتو با دستور /setid ثبت کنی.")
        return

    my_id = int(users[user_id])
    await update.message.reply_text("⏳ در حال بررسی بازی‌های مشترک، صبر کن...")

    matches = check_common_matches(my_id, target_id)

    if matches:
        keyboard = []

        for m in matches:
            match_id = m['match_id']

            # تشخیص تیم خودی و حریف
            players = m.get("players", [])
            my_team = None
            target_team = None
            for p in players:
                if p.get("account_id") == my_id:
                    my_team = "Radiant" if p.get("player_slot", 0) < 128 else "Dire"
                if p.get("account_id") == target_id:
                    target_team = "Radiant" if p.get("player_slot", 0) < 128 else "Dire"

            relation = "(unknown)"
            if my_team and target_team:
                relation = "(teammate)" if my_team == target_team else "(enemy)"

            callback_data = f"match:{match_id}:target:{target_id}"
            button_text = f"{match_id} {relation}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("بازی‌های مشترک شما:\nروی Match ID کلیک کن تا اطلاعات بیاد.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ توی ۲۰ بازی اخیرت با این بازیکن بازی نکردی.")

async def match_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    try:
        _, match_id_str, _, target_id_str = data.split(":")
        match_id = int(match_id_str)
        target_id = int(target_id_str)
    except Exception:
        await query.edit_message_text("داده نامعتبر دریافت شد.")
        return

    user_id = str(query.from_user.id)
    users = load_users()
    if user_id not in users:
        await query.edit_message_text("❌ اول Steam ID خودتو ثبت کن با /setid")
        return
    my_id = int(users[user_id])

    match_detail_url = f"https://api.opendota.com/api/matches/{match_id}"
    match_detail = fetch_json(match_detail_url)
    if not match_detail:
        await query.edit_message_text("❌ نتوانستم اطلاعات بازی را دریافت کنم.")
        return

    my_info = get_player_info_from_match(match_detail, my_id)
    target_info = get_player_info_from_match(match_detail, target_id)

    if not my_info or not target_info:
        await query.edit_message_text("❌ اطلاعات بازیکن‌ها پیدا نشد.")
        return

    def format_player_info(info):
        text = f"hero: {info['hero_name']}\n"
        text += f"kills: {info['kills']}  deaths: {info['deaths']}  assists: {info['assists']}\n"
        text += f"items: {', '.join(info['items']) if info['items'] else 'ندارد'}\n"
        text += f"hero damage  : {info['hero_damage']}\n"
        text += f"tower Damage: {info['tower_damage']}\n"
        text += f"Last Hits: {info['last_hits']}\n"
        text += f"Healing: {info['hero_healing']}\n"
        return text

    text = f"Match ID: {match_id}\n"
    text += "--------------------------\n"
    text += "🔹 اطلاعات شما:\n" + format_player_info(my_info)
    text += "--------------------------\n"
    text += "🔸 اطلاعات بازیکن هدف:\n" + format_player_info(target_info)
    text += "--------------------------\n"
    duration_min = int(my_info['duration'] / 60)
    text += f"مدت زمان بازی: {duration_min} دقیقه\n"
    radiant_win = my_info["radiant_win"]
    my_side = "Radiant" if my_info["player_slot"] < 128 else "Dire"
    did_win = (radiant_win and my_side == "Radiant") or (not radiant_win and my_side == "Dire")
    text += "نتیجه بازی: " + ("بردید 🎉" if did_win else "باختید 😢")

    await query.edit_message_text(text)

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "شروع بات"),
        BotCommand("setid", "ثبت Steam ID"),
        BotCommand("check", "چک کردن هم‌بازی")
    ])

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    TOKEN = "8496674130:AAGQeZI854ybAudt6-DLZFh9GrfW1Wl7yLg"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", setid))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CallbackQueryHandler(match_info_callback))

    app.post_init = set_commands

    print("🤖 بات داره اجرا میشه...")
    app.run_polling()
import json
import os
import requests
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

DB_FILE = "users.json"

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! برای ثبت Steam ID خودت از دستور زیر استفاده کن:\n"
        "`/setid <steam32_id>`\n"
        "مثال:\n/setid 123456789"
    )

async def setid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("فرمت درست نیست. مثال: /setid 123456789")
        return

    steam_id = context.args[0]
    if not steam_id.isdigit():
        await update.message.reply_text("Steam ID باید عددی باشد.")
        return

    user_id = str(update.message.from_user.id)
    users = load_users()
    users[user_id] = steam_id
    save_users(users)
    await update.message.reply_text(f"✅ Steam ID شما ثبت شد: {steam_id}")

def fetch_json(url):
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
    except:
        return None
    return None

def get_hero_name(hero_id):
    url = "https://api.opendota.com/api/constants/heroes"
    data = fetch_json(url)
    if not data:
        return "Unknown"
    for hero_key, hero_data in data.items():
        if hero_data.get("id") == hero_id:
            return hero_data.get("localized_name", "Unknown")
    return "Unknown"

def get_items_names(item_ids):
    url = "https://api.opendota.com/api/constants/items"
    data = fetch_json(url)
    if not data:
        return []
    names = []
    for item_id in item_ids:
        if item_id == 0:
            continue
        for key, item in data.items():
            if item.get("id") == item_id:
                names.append(item.get("dname", "Unknown"))
                break
    return names

def get_player_info_from_match(match_detail, player_id):
    players = match_detail.get("players", [])
    player_info = None
    for p in players:
        if p.get("account_id") == player_id:
            player_info = p
            break
    if not player_info:
        return None

    hero_id = player_info.get("hero_id")
    hero_name = get_hero_name(hero_id)

    item_ids = [
        player_info.get(f"item_{i}", 0) for i in range(6)
    ] + [
        player_info.get(f"backpack_{i}", 0) for i in range(3)
    ] + [player_info.get("item_neutral", 0)]

    items_names = get_items_names(item_ids)

    info = {
        "hero_name": hero_name,
        "kills": player_info.get("kills", 0),
        "deaths": player_info.get("deaths", 0),
        "assists": player_info.get("assists", 0),
        "hero_damage": player_info.get("hero_damage", 0),
        "tower_damage": player_info.get("tower_damage", 0),
        "last_hits": player_info.get("last_hits", 0),
        "hero_healing": player_info.get("hero_healing", 0),
        "items": items_names,
        "player_slot": player_info.get("player_slot"),
        "radiant_win": match_detail.get("radiant_win", False),
        "duration": match_detail.get("duration", 0),
        "match_id": match_detail.get("match_id")
    }
    return info

def check_common_matches(my_id: int, target_id: int):
    recent_matches_url = f"https://api.opendota.com/api/players/{my_id}/recentMatches?limit=20"
    recent_matches = fetch_json(recent_matches_url)
    if not recent_matches:
        return []

    common_matches = []

    for match in recent_matches:
        match_id = match.get("match_id")
        if not match_id:
            continue

        match_detail_url = f"https://api.opendota.com/api/matches/{match_id}"
        match_detail = fetch_json(match_detail_url)
        if not match_detail:
            continue

        players = match_detail.get("players", [])
        for player in players:
            if player.get("account_id") == target_id:
                common_matches.append(match_detail)
                break

    return common_matches

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("مثال درست: /check 123456789")
        return

    target_id_str = context.args[0]
    if not target_id_str.isdigit():
        await update.message.reply_text("Steam ID باید عددی باشد.")
        return

    target_id = int(target_id_str)
    user_id = str(update.message.from_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text("❌ اول باید Steam ID خودتو با دستور /setid ثبت کنی.")
        return

    my_id = int(users[user_id])
    await update.message.reply_text("⏳ در حال بررسی بازی‌های مشترک، صبر کن...")

    matches = check_common_matches(my_id, target_id)

    if matches:
        keyboard = []

        for m in matches:
            match_id = m['match_id']

            # تشخیص تیم خودی و حریف
            players = m.get("players", [])
            my_team = None
            target_team = None
            for p in players:
                if p.get("account_id") == my_id:
                    my_team = "Radiant" if p.get("player_slot", 0) < 128 else "Dire"
                if p.get("account_id") == target_id:
                    target_team = "Radiant" if p.get("player_slot", 0) < 128 else "Dire"

            relation = "(unknown)"
            if my_team and target_team:
                relation = "(teammate)" if my_team == target_team else "(enemy)"

            callback_data = f"match:{match_id}:target:{target_id}"
            button_text = f"{match_id} {relation}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("بازی‌های مشترک شما:\nروی Match ID کلیک کن تا اطلاعات بیاد.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ توی ۲۰ بازی اخیرت با این بازیکن بازی نکردی.")

async def match_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    try:
        _, match_id_str, _, target_id_str = data.split(":")
        match_id = int(match_id_str)
        target_id = int(target_id_str)
    except Exception:
        await query.edit_message_text("داده نامعتبر دریافت شد.")
        return

    user_id = str(query.from_user.id)
    users = load_users()
    if user_id not in users:
        await query.edit_message_text("❌ اول Steam ID خودتو ثبت کن با /setid")
        return
    my_id = int(users[user_id])

    match_detail_url = f"https://api.opendota.com/api/matches/{match_id}"
    match_detail = fetch_json(match_detail_url)
    if not match_detail:
        await query.edit_message_text("❌ نتوانستم اطلاعات بازی را دریافت کنم.")
        return

    my_info = get_player_info_from_match(match_detail, my_id)
    target_info = get_player_info_from_match(match_detail, target_id)

    if not my_info or not target_info:
        await query.edit_message_text("❌ اطلاعات بازیکن‌ها پیدا نشد.")
        return

    def format_player_info(info):
        text = f"hero: {info['hero_name']}\n"
        text += f"kills: {info['kills']}  deaths: {info['deaths']}  assists: {info['assists']}\n"
        text += f"items: {', '.join(info['items']) if info['items'] else 'ندارد'}\n"
        text += f"hero damage  : {info['hero_damage']}\n"
        text += f"tower Damage: {info['tower_damage']}\n"
        text += f"Last Hits: {info['last_hits']}\n"
        text += f"Healing: {info['hero_healing']}\n"
        return text

    text = f"Match ID: {match_id}\n"
    text += "--------------------------\n"
    text += "🔹 اطلاعات شما:\n" + format_player_info(my_info)
    text += "--------------------------\n"
    text += "🔸 اطلاعات بازیکن هدف:\n" + format_player_info(target_info)
    text += "--------------------------\n"
    duration_min = int(my_info['duration'] / 60)
    text += f"مدت زمان بازی: {duration_min} دقیقه\n"
    radiant_win = my_info["radiant_win"]
    my_side = "Radiant" if my_info["player_slot"] < 128 else "Dire"
    did_win = (radiant_win and my_side == "Radiant") or (not radiant_win and my_side == "Dire")
    text += "نتیجه بازی: " + ("بردید 🎉" if did_win else "باختید 😢")

    await query.edit_message_text(text)

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "شروع بات"),
        BotCommand("setid", "ثبت Steam ID"),
        BotCommand("check", "چک کردن هم‌بازی")
    ])

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    TOKEN = "BOT_TOKEN"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", setid))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CallbackQueryHandler(match_info_callback))

    app.post_init = set_commands

    print("🤖 BOT_RUNNIG...")
    app.run_polling()
