import os
import docx
import PyPDF2
import pandas as pd

# Function to extract text from a .docx file
def extract_text_from_docx(docx_file):
    doc = docx.Document(docx_file)
    return ' '.join([paragraph.text for paragraph in doc.paragraphs])

# Function to extract text from a .pdf file
def extract_text_from_pdf(pdf_file):
    with open(pdf_file, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text

# Function to process and extract relevant data from CV files
def process_cv(cv_path):
    _, ext = os.path.splitext(cv_path)
    if ext.lower() == '.docx':
        return extract_text_from_docx(cv_path)
    elif ext.lower() == '.pdf':
        return extract_text_from_pdf(cv_path)
    else:
        return ''

# Function to filter CVs based on job title, location, and keywords
def filter_cvs(cvs_folder, job_title, location, keywords):
    filtered_cvs = []
    for cv_file in os.listdir(cvs_folder):
        cv_path = os.path.join(cvs_folder, cv_file)
        cv_text = process_cv(cv_path).lower()
        
        # Check if all criteria are found in the CV text
        if (job_title.lower() in cv_text and
            location.lower() in cv_text and
            all(keyword.lower() in cv_text for keyword in keywords)):
            filtered_cvs.append({
                'file': cv_file,
                'job_title': job_title,
                'location': location,
                'keywords': ', '.join(keywords)
            })
    
    return pd.DataFrame(filtered_cvs)

# Function to display results in a structured format
def display_results(filtered_cvs):
    if filtered_cvs.empty:
        print("No CVs matched the search criteria.")
        return

    print(filtered_cvs.to_string(index=False))

# Example usage
if __name__ == "__main__":
    cvs_folder = 'C:\\Users\\Administrator\\Desktop\\SCV Porject\\CVs'
    job_title = 'IT Manager'
    location = 'Tel Aviv'
    keywords = ['Active Directory', 'GPO', 'CrowdStrike',]

    result = filter_cvs(cvs_folder, job_title, location, keywords)
    display_results(result)
