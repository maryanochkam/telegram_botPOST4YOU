from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, MessageHandler, Filters, ConversationHandler, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import logging, time

TOKEN = '8080984044:AAHFO5lM_KULdtFjc56Aq2NgGtzLRm_sapo'
ALLOWED_NUMBERS = ['+380675930528', '+380959312506']
ASK_PHONE, ASK_LINK = range(2)

def request_contact(update, context):
    button = KeyboardButton("Поделиться контактом", request_contact=True)
    markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text("Поделитесь номером телефона:", reply_markup=markup)
    return ASK_PHONE

def verify_contact(update, context):
    number = update.message.contact.phone_number
    if number.startswith('38'): number = '+' + number
    elif number.startswith('0'): number = '+38' + number
    if number in ALLOWED_NUMBERS:
        update.message.reply_text("✅ Доступ разрешён. Отправьте ссылку с https://www.post4u.com.ua/:")
        return ASK_LINK
    update.message.reply_text("❌ Доступ запрещён.")
    return ConversationHandler.END

def parse_and_send(update, context):
    url = update.message.text.strip()
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(5)
    container = driver.find_element(By.CSS_SELECTOR, 'div.entry.themeform')
    p_tags = container.find_elements(By.TAG_NAME, 'p')
    items = []
    i = 0
    while i < len(p_tags) - 1:
        try:
            text = p_tags[i].find_element(By.TAG_NAME, 'a').text.strip()
            link = p_tags[i].find_element(By.TAG_NAME, 'a').get_attribute('href')
            img_url = p_tags[i+1].find_element(By.TAG_NAME, 'img').get_attribute('src')
            items.append((text, img_url, link))
            i += 2
        except: i += 1
    driver.quit()
    for text, img_url, link in items:
        context.bot.send_photo(chat_id=update.message.chat_id, photo=img_url, caption=f"{text}\n{link}")
        time.sleep(0.5)
    update.message.reply_text(f'✅ Готово! Отправлено {len(items)} товаров.')
    return ConversationHandler.END

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.all, request_contact)],
        states={ASK_PHONE: [MessageHandler(Filters.contact, verify_contact)], ASK_LINK: [MessageHandler(Filters.text, parse_and_send)]},
        fallbacks=[]
    ))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__': main()
