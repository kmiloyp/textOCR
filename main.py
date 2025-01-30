
import streamlit as st
from PIL import Image
import tempfile
import os
import logging
from google.cloud import vision
import pdf2image

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg'}

def process_image_with_google_vision(image_path):
    try:
        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        return response.text_annotations[0].description if response.text_annotations else ""
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
        return None

def process_pdf(pdf_path):
    try:
        images = pdf2image.convert_from_path(pdf_path)
        text_results = []
        for image in images:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp:
                image.save(temp.name, 'PNG')
                text = process_image_with_google_vision(temp.name)
                if text:
                    text_results.append(text)
                os.unlink(temp.name)
        return '\n\n'.join(text_results) if text_results else None
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return None

def main():
    st.title("OCR Document Processing")
    
    uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'png', 'jpg', 'jpeg'])
    
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(uploaded_file.getvalue())
            temp_path = temp_file.name
            
        try:
            if uploaded_file.type == "application/pdf":
                extracted_text = process_pdf(temp_path)
            else:
                extracted_text = process_image_with_google_vision(temp_path)
                
            if extracted_text:
                st.write("Extracted Text:")
                st.text_area("", extracted_text, height=300)
            else:
                st.error("No text could be extracted from the file")
                
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
        finally:
            os.unlink(temp_path)

if __name__ == '__main__':
    main()
