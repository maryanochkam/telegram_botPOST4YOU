from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, MessageHandler, Filters, ConversationHandler, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import logging, time, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# =============== Health-порт для Render (нужно для бесплатного режима) ===============
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[health] listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()
# =====================================================================================

# Логи
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ======= ТВОИ ДАННЫЕ =======
TOKEN = '8080984044:AAGuSNyBDQ7VUb3t5yuCZnrbvRkOrO-sXwg'
ALLOWED_NUMBERS = ['+380675930528', '+380959312506']
ASK_PHONE, ASK_LINK = range(2)

# ==============================
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
    if not url.startswith("https://www.post4u.com.ua/"):
        update.message.reply_text("❗ Пожалуйста, отправьте ссылку именно с сайта https://www.post4u.com.ua/")
        return ConversationHandler.END

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(5)

    try:
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
            except:
                i += 1
        driver.quit()

        for text, img_url, link in items:
            context.bot.send_photo(chat_id=update.message.chat_id, photo=img_url, caption=f"{text}\n{link}")
            time.sleep(0.5)
        update.message.reply_text(f'✅ Готово! Отправлено {len(items)} товаров.')
    except Exception as e:
        logging.error(f"Ошибка при парсинге: {e}")
        update.message.reply_text("⚠️ Ошибка при обработке страницы.")
        driver.quit()
    return ConversationHandler.END

# ==============================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.all, request_contact)],
        states={
            ASK_PHONE: [MessageHandler(Filters.contact, verify_contact)],
            ASK_LINK: [MessageHandler(Filters.text, parse_and_send)]
        },
        fallbacks=[]
    ))

    # ✅ ВАЖНО: отключаем старые webhook и очищаем очередь
    updater.bot.delete_webhook(drop_pending_updates=True)
    updater.start_polling(drop_pending_updates=True)

    logging.info("✅ Bot started (polling active).")
    updater.idle()

if __name__ == '__main__':
    main()
