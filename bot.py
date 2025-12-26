import os
import fitz  # PyMuPDF
import io
import gc
from flask import Flask, render_template, request, send_file, after_this_request, redirect, url_for
from PIL import Image, ImageOps
import tempfile

app = Flask(__name__)

# Standard A4 size in points
A4_WIDTH = 595
A4_HEIGHT = 842

def process_pdf_logic(input_path, output_path):
    """Whitens pages and merges 4 smaller pages onto one A4 sheet."""
    doc = fitz.open(input_path)
    new_doc = fitz.open()  # Target A4 PDF
    
    # Define the 4 slots on an A4 page (2x2 grid)
    # Slot size: ~297x421 points
    slots = [
        fitz.Rect(0, 0, A4_WIDTH/2, A4_HEIGHT/2),         # Top-Left
        fitz.Rect(A4_WIDTH/2, 0, A4_WIDTH, A4_HEIGHT/2),   # Top-Right
        fitz.Rect(0, A4_HEIGHT/2, A4_WIDTH/2, A4_HEIGHT),   # Bottom-Left
        fitz.Rect(A4_WIDTH/2, A4_HEIGHT/2, A4_WIDTH, A4_HEIGHT) # Bottom-Right
    ]

    current_a4_page = None
    
    for i in range(len(doc)):
        # 1. Whiten the background
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)) # Higher DPI for better quality
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        gray_img = ImageOps.grayscale(img)
        binary_img = gray_img.point(lambda p: 255 if p > 160 else 0)
        
        img_byte_arr = io.BytesIO()
        binary_img.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        # 2. Merge onto A4
        slot_index = i % 4
        if slot_index == 0:
            # Create a new A4 page every 4 input pages
            current_a4_page = new_doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
        
        # Insert the whitened image into the current slot
        current_a4_page.insert_image(slots[slot_index], stream=img_bytes)

        # Cleanup memory for current iteration
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
    input_path = os.path.join(temp_dir, f"in_{file.filename}")
    output_path = os.path.join(temp_dir, f"a4_merged_{file.filename}")
    
    file.save(input_path)

    try:
        process_pdf_logic(input_path, output_path)
        
        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(input_path): os.remove(input_path)
                if os.path.exists(output_path): os.remove(output_path)
            except Exception as e:
                print(f"Cleanup error: {e}")
            return response

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        return f"Conversion error: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
