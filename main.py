import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from datetime import timedelta
import pytz
import threading
import telegram
from telegram.ext import CommandHandler, Application
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import MessageHandler, filters
import json
import asyncio
import os

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
user_id = os.environ.get('TELEGRAM_USER_ID')
dining_halls = ['Stern Dining', 'Wilbur Dining', 'Arrillaga Family Dining Commons']
SUBSCRIPTIONS_FILE = 'subscriptions.json'

def send_telegram_message(bot_token, chat_id, message):
    """
    Send a message to a Telegram chat.
    
    :param bot_token: Your Telegram bot token
    :param chat_id: The chat ID to send the message to
    :param message: The message to send
    :return: True if the message was sent successfully, False otherwise
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent successfully to chat_id: {chat_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False

def process_telegram_message(message):
    """
    Process a received Telegram message.
    
    :param message: The received message as a dictionary
    """
    try:
        chat_id = message['message']['chat']['id']
        text = message['message']['text']
        
        logger.info(f"Received message: '{text}' from chat_id: {chat_id}")
        
        if text.lower() == '/start':
            welcome_message = "Welcome to the Stanford Dining Hall Menu Bot! Here are the available commands:\n\n" \
                              "/menu - Get today's menu\n" \
                              "/tomorrow - Get tomorrow's menu\n" \
                              "/help - Show this help message"
            send_telegram_message(bot_token, chat_id, welcome_message)
        
        elif text.lower() == '/menu':
            today = datetime.now(pytz.timezone('US/Pacific'))
            date = today.strftime('%m/%-d/%Y - %A')
            send_menus_for_date(chat_id, date)
        
        elif text.lower() == '/tomorrow':
            tomorrow = datetime.now(pytz.timezone('US/Pacific')) + timedelta(days=1)
            date = tomorrow.strftime('%m/%-d/%Y - %A')
            send_menus_for_date(chat_id, date)
        
        elif text.lower() == '/help':
            help_message = "Available commands:\n" \
                           "/menu - Get today's menu\n" \
                           "/tomorrow - Get tomorrow's menu\n" \
                           "/help - Show this help message"
            send_telegram_message(bot_token, chat_id, help_message)
        
        else:
            send_telegram_message(bot_token, chat_id, "I'm sorry, I don't understand that command. Type /help for a list of available commands.")

    except KeyError as e:
        logger.error(f"Error processing message: {e}")

def send_menus_for_date(chat_id, date):
    """
    Send menus for all dining halls for a specific date.
    
    :param chat_id: The chat ID to send the messages to
    :param date: The date for which to send menus
    """
    logger.info(f"Sending menus for date: {date} to chat_id: {chat_id}")
    meal = 'Lunch'  # You might want to make this dynamic based on the current time
    for dining_hall in dining_halls:
        menu = get_menu(dining_hall, date, meal)
        message = f"Menu for *{dining_hall}* on {date} for {meal}:\n"
        for item, info in menu.items():
            message += f"{item}\n"
        send_telegram_message(bot_token, chat_id, message)

# Function to get the menu
def get_menu(dining_hall, date, meal):
    logger.info(f"Getting menu for {dining_hall} on {date} for {meal}")
    # Set up Chrome options (optional, e.g., to run headless)
    chrome_options = Options()
    # Uncomment the next line to run in headless mode
    chrome_options.add_argument("--headless")

    # Initialize the WebDriver for Chrome
    #service = Service()  # You can specify the path to chromedriver here if needed
    driver = webdriver.Chrome(options=chrome_options)
    # Alternatively, specify the path to chromedriver if it's not in your PATH
    # driver = webdriver.Chrome(executable_path='/path/to/chromedriver', options=chrome_options)

    try:
        # Navigate to the page
        driver.get('https://rdeapps.stanford.edu/dininghallmenu/')

        # Wait for the page to load
        time.sleep(2)

        # Select the dining hall
        select_location = Select(driver.find_element(By.ID, 'MainContent_lstLocations'))
        select_location.select_by_visible_text(dining_hall)

        # Select the date
        select_date = Select(driver.find_element(By.ID, 'MainContent_lstDay'))
        # Print available date options
        date_options = select_date.options
        print("Available dates:")
        for option in date_options:
            print(f"  - {option.text}")
        print()

        # Get closest date from these options
        
        select_date.select_by_visible_text(date)  # Date format: MM/DD/YYYY

        # Select the meal type
        select_meal = Select(driver.find_element(By.ID, 'MainContent_lstMealType'))
        select_meal.select_by_visible_text(meal)

        # Click the "Get Menu" button
        #get_menu_button = driver.find_element(By.ID, 'MainContent_btnGetMenu')
        #get_menu_button.click()

        # Wait for the menu to load
        time.sleep(2)

        # Extract the menu items
        # The menu is organized by categories; we'll extract categories and items
        menu = {}

        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Find all menu items
        menu_items = soup.find_all('div', class_='clsMenuItem')

        # Extract text from each menu item
        for item in menu_items:
            item_name = item.find('span', class_='clsLabel_Name').text.strip()
            menu[item_name] = {}

            # Extract ingredients if available
            ingredients_span = item.find('span', class_='clsLabel_Ingredients')
            if ingredients_span:
                ingredients = ingredients_span.text.strip().replace('Ingredients:', '').strip()
                menu[item_name]['ingredients'] = ingredients

            # Extract allergens if available
            allergens_span = item.find('span', class_='clsLabel_Allergens')
            if allergens_span:
                allergens = allergens_span.text.strip().replace('Allergens:', '').strip()
                menu[item_name]['allergens'] = allergens

            # Extract dietary icons
            icons = item.find_all('img', class_='clsLabel_IconImage')
            dietary_info = [icon['title'] for icon in icons]
            if dietary_info:
                menu[item_name]['dietary_info'] = dietary_info
        return menu

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Close the browser
        driver.quit()

def pretty_print_menu(menu):
    for item, info in menu.items():
        print(f"Item: {item}")
        if 'ingredients' in info:
            print(f"  Ingredients: {info['ingredients']}")
        if 'allergens' in info:
            print(f"  Allergens: {info['allergens']}")
        if 'dietary_info' in info:
            print(f"  Dietary Info: {', '.join(info['dietary_info'])}")
        print()

def get_formatted_date(days_offset=0):
    """Get formatted date string for today or a future day."""
    date = datetime.now(pytz.timezone('US/Pacific')) + timedelta(days=days_offset)
    return date.strftime('%m/%-d/%Y - %A')

async def send_menu_message(update, context, date):
    """Send menu messages for all dining halls on a specific date."""
    logger.info(f"Sending menu message for date: {date}")
    meal = 'Lunch'  # You might want to make this dynamic based on the current time
    for dining_hall in dining_halls:
        menu = get_menu(dining_hall, date, meal)
        message = f"Menu for *{dining_hall}* on {date} for {meal}:\n"
        message += "\n".join(menu.keys())
        await update.message.reply_text(message, parse_mode='Markdown')
    return True

async def start(update, context):
    logger.info(f"Start command received from user: {update.effective_user.id}")
    await update.message.reply_text("Welcome to the Stanford Dining Hall Menu Bot! Here are the available commands:\n\n"
                              "/menu - Get today's menu\n"
                              "/tomorrow - Get tomorrow's menu\n"
                              "/help - Show this help message")
    return True

async def menu(update, context):
    logger.info(f"Menu command received from user: {update.effective_user.id}")
    date = get_formatted_date()
    await send_menu_message(update, context, date)
    return True

async def tomorrow(update, context):
    logger.info(f"Tomorrow command received from user: {update.effective_user.id}")
    date = get_formatted_date(days_offset=1)
    await send_menu_message(update, context, date)
    return True

async def help(update, context):
    logger.info(f"Help command received from user: {update.effective_user.id}")
    await update.message.reply_text(
        "Welcome to the Stanford Dining Hall Menu Bot! Here are the available commands:\n\n"
        "/menu - Get today's menu for all dining halls\n"
        "/tomorrow - Get tomorrow's menu for all dining halls\n"
        "/dininghalls - List available dining halls\n"
        "/subscribe - Subscribe to daily menu updates\n"
        "/unsubscribe - Unsubscribe from daily menu updates\n"
        "/help - Show this help message"
    )
    return True

def load_subscriptions():
    try:
        with open(SUBSCRIPTIONS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_subscriptions(subscriptions):
    with open(SUBSCRIPTIONS_FILE, 'w') as f:
        json.dump(subscriptions, f)

async def subscribe(update, context):
    user_id = str(update.effective_user.id)
    subscriptions = load_subscriptions()
    
    if user_id in subscriptions:
        await update.message.reply_text("You are already subscribed to daily menu updates.")
    else:
        subscriptions[user_id] = True
        save_subscriptions(subscriptions)
        await update.message.reply_text("You have successfully subscribed to daily menu updates.")
    
    logger.info(f"User {user_id} subscribed to daily menu updates")
    return True

async def unsubscribe(update, context):
    user_id = str(update.effective_user.id)
    subscriptions = load_subscriptions()
    
    if user_id in subscriptions:
        del subscriptions[user_id]
        save_subscriptions(subscriptions)
        await update.message.reply_text("You have successfully unsubscribed from daily menu updates.")
    else:
        await update.message.reply_text("You are not currently subscribed to daily menu updates.")
    
    logger.info(f"User {user_id} unsubscribed from daily menu updates")
    return True

# Modify the send_daily_menu function to send menus to all subscribed users
async def send_daily_menu(context):
    """Send daily menu to all subscribed users."""
    logger.info("Sending daily menu to subscribed users")
    date = get_formatted_date()
    meal = 'Lunch'
    subscriptions = load_subscriptions()
    
    for user_id in subscriptions:
        for dining_hall in dining_halls:
            menu = get_menu(dining_hall, date, meal)
            message = f"Menu for *{dining_hall}* on {date} for {meal}:\n"
            message += "\n".join(menu.keys())
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
    
    logger.info(f"Daily menu sent at {datetime.now(pytz.timezone('US/Pacific')).strftime('%Y-%m-%d %H:%M:%S')} PT")
    return True


async def schedule_daily_menu(context):
    """Schedule the daily menu to be sent at 9:00 AM PT."""
    logger.info("Starting daily menu scheduler")
    while True:
        now = datetime.now(pytz.timezone('US/Pacific'))
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        
        time_to_sleep = (next_run - now).total_seconds()
        logger.info(f"Sleeping until {next_run.strftime('%Y-%m-%d %H:%M:%S')} PT")
        await asyncio.sleep(time_to_sleep)
        
        await send_daily_menu(context)

def get_available_dining_halls():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get('https://rdeapps.stanford.edu/dininghallmenu/')
        time.sleep(2)
        
        select_location = Select(driver.find_element(By.ID, 'MainContent_lstLocations'))
        return [option.text for option in select_location.options if option.text != 'Select Location']
    except Exception as e:
        logger.error(f"Error getting available dining halls: {e}")
        return []
    finally:
        driver.quit()

async def handle_message(update, context):
    if context.user_data.get('awaiting_dininghall'):
        selected_hall = update.message.text
        available_halls = get_available_dining_halls()
        
        if selected_hall in available_halls:
            context.user_data['awaiting_dininghall'] = False
            date = get_formatted_date()
            meal = 'Lunch'  # You might want to make this dynamic based on the current time
            menu = get_menu(selected_hall, date, meal)
            message = f"Menu for *{selected_hall}* on {date} for {meal}:\n"
            message += "\n".join(menu.keys())
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("Invalid selection. Please choose a dining hall from the list.")
    else:
        await update.message.reply_text("I'm sorry, I don't understand that command. Type /help for a list of available commands.")

async def dininghalls(update, context):
    logger.info(f"Dininghalls command received from user: {update.effective_user.id}")
    available_halls = get_available_dining_halls()
    
    if available_halls:
        message = "Available dining halls:\n\n" + "\n".join(f"• {hall}" for hall in available_halls)
        keyboard = [[hall] for hall in available_halls]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text(message, reply_markup=reply_markup)
        context.user_data['awaiting_dininghall'] = True
    else:
        await update.message.reply_text("Sorry, I couldn't retrieve the list of dining halls at the moment. Please try again later.")
    return True

if __name__ == "__main__":
    # Start the Telegram bot
    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('menu', menu))
    application.add_handler(CommandHandler('tomorrow', tomorrow))
    application.add_handler(CommandHandler('help', help))
    application.add_handler(CommandHandler('dininghalls', dininghalls))
    application.add_handler(CommandHandler('subscribe', subscribe))
    application.add_handler(CommandHandler('unsubscribe', unsubscribe))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    #application.add_error_handler(error_handler)
    
    # Inline query handler
    #application.add_handler(InlineQueryHandler(inline_query))
    
    # Callback query handler
    #application.add_handler(CallbackQueryHandler(button))
    
    # Start the daily menu scheduler in a separate thread
    threading.Thread(target=lambda: asyncio.run(schedule_daily_menu(application)), daemon=True).start()

    # Run the bot in the main thread
    logger.info("Starting Telegram bot")
    application.run_polling()