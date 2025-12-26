import os
import fitz  # PyMuPDF
import io
import gc
from flask import Flask, render_template, request, send_file, after_this_request, redirect, url_for
from PIL import Image, ImageOps
import tempfile

app = Flask(__name__)

def process_pdf_logic(input_path, output_path):
    """Processes PDF page-by-page to keep memory usage low."""
    doc = fitz.open(input_path)
    new_doc = fitz.open()  # Create a new empty PDF

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # matrix=1.0 is standard quality. Increase to 1.2 if text is blurry, 
        # but 1.0 is safest for Heroku memory limits.
        pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Background Removal Logic
        gray_img = ImageOps.grayscale(img)
        binary_img = gray_img.point(lambda p: 255 if p > 160 else 0)
        
        # Convert processed image to bytes
        img_byte_arr = io.BytesIO()
        binary_img.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        # Create new page in output PDF and insert the processed image
        new_page = new_doc.new_page(width=pix.width, height=pix.height)
        new_page.insert_image(new_page.rect, stream=img_bytes)

        # Explicitly clear memory for this page
        img_byte_arr.close()
        del pix, img, gray_img, binary_img, img_bytes
        gc.collect()

    new_doc.save(output_path)
    new_doc.close()
    doc.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['GET', 'POST'])
def convert():
    if request.method == 'GET':
        return redirect(url_for('index'))
    
    if 'file' not in request.files:
        return "No file uploaded", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    temp_dir = tempfile.gettempdir()
    input_path = os.path.join(temp_dir, f"upload_{file.filename}")
    output_path = os.path.join(temp_dir, f"cleaned_{file.filename}")
    
    file.save(input_path)

    try:
        process_pdf_logic(input_path, output_path)
        
        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(input_path): os.remove(input_path)
                if os.path.exists(output_path): os.remove(output_path)
            except Exception as e:
                print(f"Error cleaning up: {e}")
            return response

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
