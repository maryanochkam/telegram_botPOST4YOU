from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, MessageHandler, Filters, ConversationHandler, CallbackContext
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging, time, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ====== ТВОИ ДАННЫЕ ======
TOKEN = '8080984044:AAGuSNyBDQ7VUb3t5yuCZnrbvRkOrO-sXwg'
ALLOWED_NUMBERS = ['+380675930528', '+380959312506']

ASK_PHONE, ASK_LINK = range(2)

# ====== ЛОГИ ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("post4u_bot")

# ====== ПРОСТОЙ HEALTH-СЕРВЕР ДЛЯ RENDER ======
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args, **kwargs):  # тишина в логах
        return

def start_health_server():
    try:
        srv = HTTPServer(("0.0.0.0", 10000), HealthHandler)
        log.info("[health] listening on 0.0.0.0:10000")
        srv.serve_forever()
    except Exception as e:
        log.error(f"Health server error: {e}")

# ====== БОТ ======
def request_contact(update: Update, context: CallbackContext):
    button = KeyboardButton("Поделиться контактом", request_contact=True)
    markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text("Поделитесь номером телефона:", reply_markup=markup)
    return ASK_PHONE

def normalize_msisdn(number: str) -> str:
    n = number.strip().replace(" ", "").replace("-", "")
    if n.startswith("+"):
        return n
    if n.startswith("38"):
        return "+" + n
    if n.startswith("0"):
        return "+38" + n
    return "+" + n  # на всякий

def verify_contact(update: Update, context: CallbackContext):
    try:
        number = normalize_msisdn(update.message.contact.phone_number)
        if number in ALLOWED_NUMBERS:
            update.message.reply_text("✅ Доступ разрешён. Пришлите ссылку с https://www.post4u.com.ua/")
            return ASK_LINK
        update.message.reply_text("❌ Доступ запрещён.")
        return ConversationHandler.END
    except Exception as e:
        log.error(f"Ошибка проверки контакта: {e}")
        update.message.reply_text("⚠️ Не смог прочитать контакт. Попробуйте ещё раз.")
        return ConversationHandler.END

def build_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,2000")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    # чуть агрессивнее ждать DOM
    driver.set_page_load_timeout(45)
    return driver

def extract_items_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    # разные варианты контейнера на Post4u
    container = soup.select_one("div.entry.themeform") \
        or soup.select_one("div.entry") \
        or soup.select_one("div.post") \
        or soup.select_one("#content") \
        or soup  # последний шанс — весь документ

    p_tags = container.find_all("p")
    items = []
    i = 0
    while i < len(p_tags) - 1:
        a = p_tags[i].find("a")
        img = p_tags[i+1].find("img") if i+1 < len(p_tags) else None
        if a and img:
            text = (a.get_text() or "").strip()
            link = a.get("href") or ""
            img_url = img.get("src") or img.get("data-src") or ""
            if text and link and img_url:
                items.append((text, img_url, link))
                i += 2
                continue
        i += 1
    return items

def parse_and_send(update: Update, context: CallbackContext):
    url = (update.message.text or "").strip()
    if not url.startswith("http"):
        update.message.reply_text("Нужна ссылка на страницу Post4u.")
        return ConversationHandler.END

    driver = None
    try:
        log.info(f"Парсим URL: {url}")
        driver = build_driver()
        driver.get(url)

        # ждём появления хоть какого-то контента на странице
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        # небольшой дожидатель скриптов/картинок
        time.sleep(2)

        items = extract_items_from_html(driver.page_source)

        # если 0 — попробуем чуть проскроллить (на всякий случай для ленивой подгрузки)
        if not items:
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
                items = extract_items_from_html(driver.page_source)
            except Exception:
                pass

        if not items:
            update.message.reply_text("⚠️ Не нашёл товары на странице. Разметка сайта могла измениться.")
            log.error("Парсер: 0 элементов. Контейнеры не найдены/не подошли.")
            return ConversationHandler.END

        sent = 0
        for text, img_url, link in items:
            try:
                context.bot.send_photo(
                    chat_id=update.message.chat_id,
                    photo=img_url,
                    caption=f"{text}\n{link}"
                )
                sent += 1
                time.sleep(0.5)
            except Exception as e:
                log.error(f"Не удалось отправить фото: {e}")

        update.message.reply_text(f"✅ Готово! Отправлено {sent} товаров.")
        return ConversationHandler.END

    except Exception as e:
        log.error(f"Ошибка при парсинге: {e}", exc_info=True)
        update.message.reply_text("❌ Ошибка при парсинге страницы. Проверь ссылку или пришлите другую.")
        return ConversationHandler.END
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def main():
    # health-порт для Render
    threading.Thread(target=start_health_server, daemon=True).start()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.all, request_contact)],
        states={
            ASK_PHONE: [MessageHandler(Filters.contact, verify_contact)],
            ASK_LINK:  [MessageHandler(Filters.text & ~Filters.command, parse_and_send)],
        },
        fallbacks=[]
    ))

    updater.start_polling(clean=True)  # сброс «висячих» апдейтов
    log.info("✅ Bot started (polling active).")
    updater.idle()

if __name__ == '__main__':
    main()
