import os
import fitz  # PyMuPDF
from flask import Flask, render_template, request, send_file, after_this_request
from PIL import Image, ImageOps
import tempfile

app = Flask(__name__)

def process_pdf_logic(input_path, output_path):
    """Core logic adapted from the original bot.py"""
    doc = fitz.open(input_path)
    processed_images = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # 1.5 zoom for quality/memory balance
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
    doc.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    # Create temporary paths
    temp_dir = tempfile.gettempdir()
    input_path = os.path.join(temp_dir, f"upload_{file.filename}")
    output_path = os.path.join(temp_dir, f"cleaned_{file.filename}")
    
    file.save(input_path)

    try:
        process_pdf_logic(input_path, output_path)
        
        @after_this_request
        def cleanup(response):
            try:
                os.remove(input_path)
                os.remove(output_path)
            except Exception as e:
                print(f"Error cleaning up: {e}")
            return response

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    # Bind to PORT for Heroku
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
