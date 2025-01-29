import os
import logging
from flask import Flask, render_template, request, jsonify
from google.cloud import vision
import json
from PIL import Image
import pdf2image
import tempfile
import io

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key_123")

# Initialize Google Cloud Vision client
try:
    credentials_json = os.environ.get('GOOGLE_CLOUD_CREDENTIALS')
    if credentials_json:
        logger.debug("Found Google Cloud credentials in environment")
        credentials_dict = json.loads(credentials_json)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(credentials_dict, f)
            credentials_path = f.name
            logger.debug(f"Saved credentials to temporary file: {credentials_path}")
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        vision_client = vision.ImageAnnotatorClient()
        logger.info("Successfully initialized Google Cloud Vision client")
    else:
        logger.error("Google Cloud credentials not found in environment")
        raise ValueError("Google Cloud credentials not found in environment")
except json.JSONDecodeError as je:
    logger.error(f"Invalid JSON in credentials: {str(je)}")
    vision_client = None
except Exception as e:
    logger.error(f"Failed to initialize Google Cloud Vision client: {str(e)}")
    vision_client = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg'}

def process_image_with_google_vision(image_path):
    """Extract text from image using Google Cloud Vision API"""
    try:
        if not vision_client:
            logger.error("Vision client not initialized, cannot process image")
            raise Exception("Google Cloud Vision client not initialized")

        logger.debug(f"Processing image with Google Vision: {image_path}")

        # Verify image can be opened
        try:
            with Image.open(image_path) as img:
                logger.debug(f"Successfully opened image: size={img.size}, mode={img.mode}")
        except Exception as e:
            logger.error(f"Failed to open image: {str(e)}")
            raise Exception("Invalid or corrupted image file")

        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()
            logger.debug(f"Successfully read image file of size: {len(content)} bytes")

        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)

        if response.error.message:
            logger.error(f"Google Vision API error: {response.error.message}")
            raise Exception(f"Google Vision API error: {response.error.message}")

        # Get the full text from the first annotation
        extracted_text = response.text_annotations[0].description if response.text_annotations else ""

        if not extracted_text:
            logger.warning("No text detected in the image")
            raise Exception("No text could be detected in the image")

        logger.info("Successfully extracted text")
        logger.debug(f"Extracted text length: {len(extracted_text)}")
        return extracted_text

    except Exception as e:
        logger.error(f"Google Vision API Error: {str(e)}")
        raise Exception(f"Error al procesar la imagen: {str(e)}")

def process_pdf(pdf_path):
    """Convert PDF to images and extract text using Google Cloud Vision"""
    try:
        logger.debug(f"Processing PDF: {pdf_path}")
        images = pdf2image.convert_from_path(pdf_path, dpi=300)
        logger.debug(f"Successfully converted PDF to {len(images)} images")

        text_results = []

        for i, image in enumerate(images):
            logger.debug(f"Processing page {i+1} of PDF")

            # Save image to temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
                image.save(temp_img.name, format='PNG')
                extracted_text = process_image_with_google_vision(temp_img.name)
                os.unlink(temp_img.name)

                if extracted_text:
                    text_results.append(extracted_text)
                    logger.debug(f"Successfully extracted text from page {i+1}")
                else:
                    logger.warning(f"No text extracted from page {i+1}")

        if not text_results:
            logger.warning("No text extracted from any PDF page")
            return None

        return '\n\n'.join(text_results)

    except Exception as e:
        logger.error(f"PDF Processing Error: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        return jsonify({'error': 'No se ha subido ningún archivo'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de archivo no válido'}), 400

    try:
        # Create temporary file
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        logger.debug(f"File saved to temporary path: {temp_path}")

        # Process file based on type
        try:
            if file.filename.lower().endswith('.pdf'):
                extracted_text = process_pdf(temp_path)
            else:
                extracted_text = process_image_with_google_vision(temp_path)

            if not extracted_text:
                raise Exception("No se pudo extraer texto del archivo")

        except Exception as process_error:
            logger.error(f"Processing error: {str(process_error)}")
            return jsonify({'error': str(process_error)}), 400
        finally:
            # Clean up temporary file
            os.remove(temp_path)
            os.rmdir(temp_dir)

        return render_template('results.html', extracted_text=extracted_text)

    except Exception as e:
        logger.error(f"Processing Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)