import json
import re
from docx import Document

def convert_docx_to_json(docx_path, json_path):
    # Load the DOCX file
    doc = Document(docx_path)
    
    questions = []
    
    # Process each paragraph in the document
    for para in doc.paragraphs:
        text = para.text.strip()
        
        # Skip empty lines
        if not text:
            continue
            
        # Remove number prefix using regex
        question = re.sub(r'^\d+\.\s*', '', text)
        
        if question:  # Only add if we have content after processing
            questions.append(question)
    
    # Create JSON structure
    data = {
        "meta": {
            "source": docx_path,
            "count": len(questions)
        },
        "questions": questions
    }
    
    # Save to JSON file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully converted {len(questions)} questions to {json_path}")

# Example usage:
convert_docx_to_json('C:\\Users\\heman\\Downloads\\Questions.docx', 'questions22.json')