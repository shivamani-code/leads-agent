import time
import asyncio
import pandas as pd
from playwright.sync_api import sync_playwright
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from playwright.async_api import async_playwright

# ================== CONFIG ==================

import os

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUBJECT = "Grow your business online 🚀"
EMAIL_BODY = """Hi [Business Name],

I noticed your business does not have a website.

We can help you get more customers and grow your business online 🚀

Let me know if you're interested!

Thanks
"""

FILE_NAME = "leads.xlsx"
CSV_BACKUP = "leads_backup.csv"

# ================== SCRAPER ==================


async def scrape(query):
    leads = []
    seen = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}")
        await page.wait_for_timeout(5000)

        # Scroll
        scroll_box = page.locator('div[role="feed"]')
        for _ in range(30):
            await scroll_box.evaluate("el => el.scrollTop = el.scrollHeight")
            await page.wait_for_timeout(2000)

        listings = page.locator('a.hfpxzc')
        count = await listings.count()
        print(f"🔍 Total listings found: {count}")

        for i in range(count):
            try:
                listings = page.locator('a.hfpxzc')
                await listings.nth(i).click()
                await page.wait_for_timeout(3000)

                # NAME
                try:
                    name = await page.locator('h1.DUwDvf').inner_text()
                except:
                    continue

                # PHONE
                phone = None
                try:
                    phone = await page.locator("//button[contains(@data-item-id,'phone')]").inner_text()
                except:
                    pass

                # WEBSITE
                website = None
                try:
                    website_el = page.locator("//a[contains(@data-item-id,'authority')]")
                    if await website_el.count() > 0:
                        website = True
                except:
                    pass

                # ONLY NO WEBSITE
                if website:
                    continue

                uid = str(name) + str(phone)
                if uid in seen:
                    continue
                seen.add(uid)

                print(f"✅ {i+1}. {name} | 📞 {phone}")

                leads.append({
                    "Business Name": name,
                    "Phone Number": phone,
                    "Email": None,
                    "Website": None
                })

            except Exception as e:
                print(f"⚠️ Skipped {i}: {e}")
                continue

        await browser.close()

    return leads
# ================== SAVE ==================

def save_data(data):
    df = pd.DataFrame(data)

    if not df.empty:
        df = df.drop_duplicates(subset=["Business Name", "Phone Number"])

    try:
        df.to_excel(FILE_NAME, index=False)
        print(f"✅ Excel saved: {FILE_NAME}")
    except Exception as e:
        print(f"❌ Excel error: {e}")

    try:
        df.to_csv(CSV_BACKUP, index=False)
        print("✅ CSV backup saved")
    except:
        pass

    return df

# ================== EMAIL ==================

def send_email(df):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL, PASSWORD)
    except Exception as e:
        print("❌ Email login failed:", e)
        return

    sent = 0

    for _, row in df.iterrows():
        email = row.get("Email")
        name = row.get("Business Name")

        if not email:
            continue

        msg = MIMEMultipart()
        msg['From'] = EMAIL
        msg['To'] = email
        msg['Subject'] = SUBJECT.replace("[Business Name]", str(name))

        body = EMAIL_BODY.replace("[Business Name]", str(name))
        msg.attach(MIMEText(body, 'plain'))

        try:
            server.send_message(msg)
            print(f"📧 Sent to {name}")
            sent += 1
            time.sleep(2)
        except:
            print(f"❌ Failed: {name}")

    server.quit()
    print(f"📨 Total emails sent: {sent}")

# ================== AUTOMATION ==================

async def run_automation(query):
    print(f"🚀 Running: {query}")

    data = await scrape(query)

    print(f"📊 Leads collected: {len(data)}")

    df = save_data(data)

    email_df = df[df["Email"].notna()]

    if not email_df.empty:
        send_email(email_df)

    return len(df)
# ================== TELEGRAM ==================

from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send query like:\nsalons in hyderabad\n\nCommands:\n/export\n/clear"
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    if query.lower() == "clear":
        if os.path.exists(FILE_NAME):
            os.remove(FILE_NAME)
        if os.path.exists(CSV_BACKUP):
            os.remove(CSV_BACKUP)
        await update.message.reply_text("🧹 Data cleared")
        return

    await update.message.reply_text(f"🚀 Running:\n{query}")

    try:
        count = await run_automation(query)
        await update.message.reply_text(f"✅ Done! {count} leads saved\nUse /export")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, "rb") as file:
            await update.message.reply_document(
                document=InputFile(file, filename=FILE_NAME)
            )
    else:
        await update.message.reply_text("⚠️ No data found")

def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("export", export_excel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("🤖 Telegram Bot Running...")
    app.run_polling()

# ================== START ==================

if __name__ == "__main__":
    start_bot()