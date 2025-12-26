import os
import fitz  # PyMuPDF
from PIL import Image, ImageOps
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Environment variables
TOKEN = os.environ.get('TELEGRAM_TOKEN')
# You must set this in Heroku Config Vars (e.g., https://your-app-name.herokuapp.com)
HEROKU_APP_URL = os.environ.get('HEROKU_APP_URL')
DOWNLOAD_DIR = '/tmp' 

async def process_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        return

    file = await update.message.document.get_file()
    # Clean the filename for safety
    safe_name = "".join([c for c in update.message.document.file_name if c.isalnum() or c in "._-"])
    input_path = os.path.join(DOWNLOAD_DIR, f"in_{safe_name}")
    output_path = os.path.join(DOWNLOAD_DIR, f"white_bg_{safe_name}")

    status_msg = await update.message.reply_text("⏳ Processing your PDF. This may take a moment...")
    await file.download_to_drive(input_path)

    try:
        doc = fitz.open(input_path)
        processed_images = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # 1.5 zoom provides good print quality while staying within Heroku's 512MB RAM limit
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Thresholding logic: convert background colors to white
            gray_img = ImageOps.grayscale(img)
            binary_img = gray_img.point(lambda p: 255 if p > 160 else 0)
            processed_images.append(binary_img.convert("RGB"))

        if processed_images:
            processed_images[0].save(
                output_path, save_all=True, append_images=processed_images[1:]
            )
            with open(output_path, 'rb') as f:
                await update.message.reply_document(document=f)
        
        await status_msg.delete()

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        if 'doc' in locals(): doc.close()
        for p in [input_path, output_path]:
            if os.path.exists(p): os.remove(p)

def main():
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN not set.")
        return
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.PDF, process_pdf))
    
    # Heroku assigns a dynamic port
    PORT = int(os.environ.get('PORT', 8443))

    if HEROKU_APP_URL:
        # Use Webhooks (Required for 'web' dynos on Heroku)
        print(f"Starting Webhook on port {PORT}...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{HEROKU_APP_URL}/{TOKEN}"
        )
    else:
        # Fallback to Polling if no URL is provided (for local testing)
        print("Starting Polling...")
        app.run_polling()

if __name__ == '__main__':
    main()
