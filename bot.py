import os
import fitz  # PyMuPDF
from PIL import Image, ImageOps
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Use environment variable for security
TOKEN = os.environ.get('TELEGRAM_TOKEN')
DOWNLOAD_DIR = '/tmp'  # Heroku's temporary storage

async def process_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure a file was actually sent
    if not update.message.document:
        return

    file = await update.message.document.get_file()
    input_path = os.path.join(DOWNLOAD_DIR, f"in_{update.message.document.file_name}")
    output_path = os.path.join(DOWNLOAD_DIR, f"white_bg_{update.message.document.file_name}")

    status_msg = await update.message.reply_text("⏳ Downloading and processing...")
    await file.download_to_drive(input_path)

    try:
        doc = fitz.open(input_path)
        processed_images = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Use 1.5 or 2.0 zoom for clear printing without hitting Heroku memory limits
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Thresholding: Convert colors to White/Black
            gray_img = ImageOps.grayscale(img)
            binary_img = gray_img.point(lambda p: 255 if p > 160 else 0)
            processed_images.append(binary_img.convert("RGB"))

        if processed_images:
            processed_images[0].save(
                output_path, save_all=True, append_images=processed_images[1:]
            )
            await update.message.reply_document(document=open(output_path, 'rb'))
        
        await status_msg.delete()

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        if 'doc' in locals(): doc.close()
        for p in [input_path, output_path]:
            if os.path.exists(p): os.remove(p)

def main():
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable not set.")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.PDF, process_pdf))
    app.run_polling()

if __name__ == '__main__':
    main()
