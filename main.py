from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, MessageHandler, Filters, ConversationHandler, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging, time, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# =============== Health-порт для Render (Web Service на бесплатном плане) ===============
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def _run_health_server():
    port = int(os.environ.get("PORT", "10000"))  # Render сам задаёт PORT
    httpd = HTTPServer(("0.0.0.0", port), _HealthHandler)
    print(f"[health] listening on 0.0.0.0:{port}", flush=True)
    httpd.serve_forever()

# Запускаем в отдельном потоке, чтобы не мешать боту на polling
threading.Thread(target=_run_health_server, daemon=True).start()
# =======================================================================================

# (можно включить логи, если нужно)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

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
    # Нормализация: +380..., 380..., 0...
    if number.startswith('+'):
        pass
    elif number.startswith('38'):
        number = '+' + number
    elif number.startswith('0'):
        number = '+38' + number
    if number in ALLOWED_NUMBERS:
        update.message.reply_text("✅ Доступ разрешён. Отправьте ссылку с https://www.post4u.com.ua/:")
        return ASK_LINK
    update.message.reply_text("❌ Доступ запрещён.")
    return ConversationHandler.END

def _build_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,2200')
    driver = webdriver.Chrome(options=options)
    return driver

def parse_and_send(update, context):
    url = (update.message.text or "").strip()
    driver = _build_driver()
    try:
        driver.get(url)
        # Ждём контейнер (несколько возможных селекторов, чтобы не падать из-за мелких изменений)
        container = None
        selectors = [
            'div.entry.themeform',
            'main .entry.themeform',
            'div#content',
            'div.site-content',
            'article.post, article',
            'section.content, .post-content'
        ]
        last_err = None
        for sel in selectors:
            try:
                container = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                log.info(f"[parser] container by: {sel}")
                break
            except Exception as e:
                last_err = e
        if container is None:
            raise last_err or Exception("Не найден контейнер с постом")

        p_tags = container.find_elements(By.TAG_NAME, 'p')
        items = []
        i = 0
        while i < len(p_tags) - 1:
            try:
                a = p_tags[i].find_element(By.TAG_NAME, 'a')
                text = a.text.strip()
                link = a.get_attribute('href')
                img_url = p_tags[i+1].find_element(By.TAG_NAME, 'img').get_attribute('src')
                if text and link and img_url:
                    items.append((text, img_url, link))
                i += 2
            except Exception:
                i += 1

        for text, img_url, link in items:
            try:
                context.bot.send_photo(
                    chat_id=update.message.chat_id,
                    photo=img_url,
                    caption=f"{text}\n{link}"
                )
            except Exception as e:
                log.exception(f"[send] fail: {e}")
            time.sleep(0.5)

        update.message.reply_text(f'✅ Готово! Отправлено {len(items)} товаров.')
        return ConversationHandler.END
    except Exception as e:
        log.exception(f"[parse] fail: {e}")
        update.message.reply_text("❌ Не удалось спарсить. Проверь ссылку или пришли другую.")
        return ConversationHandler.END
    finally:
        try:
            driver.quit()
        except Exception:
            pass

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.all, request_contact)],
        states={
            ASK_PHONE: [MessageHandler(Filters.contact, verify_contact)],
            ASK_LINK: [MessageHandler(Filters.text & ~Filters.command, parse_and_send)]
        },
        fallbacks=[]
    ))
    # Ключевое: не тянуть старые апдейты после рестартов
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == '__main__':
    main()
