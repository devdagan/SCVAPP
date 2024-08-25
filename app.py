import os
import csv
import docx
import PyPDF2
import pdfplumber
import zipfile
import io
import json
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, send_file, flash
from werkzeug.utils import secure_filename
import re
import datetime
from fuzzywuzzy import fuzz  # Add this line
from builtins import enumerate

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Folder to save uploaded CVs
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Allowed extensions for file uploads
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# Load job titles and cities from CSV files
job_titles = []
cities = []

with open('job_titles.csv', newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    job_titles = [row[0].strip().lower() for row in reader]

with open('cities.csv', newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    cities = [row[0].strip().lower() for row in reader]

def load_csv_data(filename):
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        return [row[0].strip() for row in reader]  # Remove .lower() to keep original capitalization

job_titles = load_csv_data('job_titles.csv')
cities = load_csv_data('cities.csv')


def load_candidates():
    try:
        with open('candidates.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_candidates(candidates):
    with open('candidates.json', 'w') as f:
        json.dump(candidates, f)

def load_searches():
    try:
        with open('searches.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_searches(searches):
    with open('searches.json', 'w') as f:
        json.dump(searches, f)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_docx(docx_file):
    doc = docx.Document(docx_file)
    return '\n'.join([paragraph.text for paragraph in doc.paragraphs])

def extract_text_from_pdf(pdf_file):
    text = ''
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text(layout=True) or ''
        
        # Clean up the extracted text
        lines = text.split('\n')
        cleaned_lines = [re.sub(r'\s+', ' ', line).strip() for line in lines if line.strip()]
        text = '\n'.join(cleaned_lines)
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    
    return text

def normalize_text(text):
    # Normalize the text by converting to lowercase, removing punctuation, and collapsing spaces
    return re.sub(r'[^a-zA-Z0-9\s]', '', text.lower()).strip()

def normalize_city_name(city_name):
    # Remove special characters, digits, and normalize spaces
    city_name = re.sub(r'[^a-zA-Z\s]', '', city_name)  # Remove special characters
    city_name = re.sub(r'\s+', ' ', city_name).strip()  # Normalize spaces
    return city_name.lower()

def fuzzy_match(string, options, threshold=80):
    for option in options:
        if fuzz.ratio(string.lower(), option.lower()) >= threshold:
            return True
    return False

def build_city_patterns(city_list):
    # Build a regex pattern for each city considering the normalized versions
    city_patterns = {}
    for city in city_list:
        normalized_city = normalize_city_name(city)
        city_variants = [
            normalized_city,
            normalized_city.replace(' ', '-'),  # Handle dash variations
            normalized_city.replace('-', ' '),
        ]
        pattern = '|'.join(re.escape(variant) for variant in city_variants)
        city_patterns[city] = re.compile(r'\b(' + pattern + r')\b', re.IGNORECASE)
    return city_patterns

def build_job_title_patterns(job_list):
    # Build a regex pattern for each job title considering common variants
    job_patterns = {}
    for job in job_list:
        job_variants = [
            job,
            job.replace(' ', ''),
            job.replace('-', ' '),
            job.replace('\'', '')
        ]
        pattern = '|'.join(re.escape(variant) for variant in job_variants)
        job_patterns[job] = re.compile(r'\b(' + pattern + r')\b', re.IGNORECASE)
    return job_patterns

city_patterns = build_city_patterns(cities)
job_patterns = build_job_title_patterns(job_titles)


def load_job_titles():
    with open('job_titles.csv', 'r', encoding='utf-8') as file:
        return [line.strip() for line in file]

job_titles = load_job_titles()

def is_reversed(text):
    return sum(1 for c in text if '\u0590' <= c <= '\u05FF') > len(text) / 2

def reverse_text(text):
    return text[::-1]

def extract_info(text):
    print("\n--- Starting extraction ---")
    print(f"Full text:\n{text}\n")
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    normalized_text = ' '.join(lines)
    
    print("Normalized text lines:")
    for i, line in enumerate(lines[:10]):
        print(f"{i+1}: {line}")
    print()

    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    email = emails[0] if emails else "Not found"
    print(f"Extracted email: {email}")

    def find_pattern(pattern, lines, reverse=False):
        for line in lines:
            if reverse:
                line = line[::-1]
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1), reverse
        return "", False

    def find_exact_job_title(line):
        for job_title in sorted(job_titles, key=len, reverse=True):
            if job_title.lower() in line.lower():
                return job_title
        return None

    def find_job_title(lines):
        for line in lines[:5]:  # Check first 5 lines for job titles
            exact_title = find_exact_job_title(line)
            if exact_title:
                return exact_title
            for job_title in sorted(job_titles, key=len, reverse=True):
                if fuzz.partial_ratio(job_title.lower(), line.lower()) > 90:
                    return job_title
        return "Not Found"

    def find_location(lines):
        for line in lines:
            for city in cities:
                if city.lower() in line.lower():
                    return city
        return "Not Found"

    # Job title extraction
    job_title = find_job_title(lines)

    # Location extraction
    location = find_location(lines)

    print(f"\nFinal extracted job title: {job_title}")
    print(f"Final extracted location: {location}")

    print("--- Extraction complete ---\n")

    return {
        'email': email,
        'job_title': job_title,
        'location': location or "Not Found",
        'full_text': normalized_text
    }

def match_keywords(cv_text, keywords):
    matched_keywords = []
    for keyword in keywords:
        if keyword.lower() in cv_text.lower():
            matched_keywords.append(keyword)
    return matched_keywords

def search_candidates(job_title, location, keywords):
    matched_candidates = []
    for candidate in candidates:
        cv_text = candidate['full_text']
        job_title_match = job_title.lower() in candidate['job_title'].lower()
        location_match = location.lower() in candidate['location'].lower()
        matched_keywords = match_keywords(cv_text, keywords)
        keywords_match = bool(matched_keywords)
        
        if job_title_match and location_match and keywords_match:
            candidate['matched_keywords'] = ', '.join(matched_keywords) if matched_keywords else 'N/A'
            matched_candidates.append(candidate)
        elif job_title_match and location_match:
            candidate['matched_keywords'] = 'N/A'
            matched_candidates.append(candidate)
            
    return matched_candidates


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/all_candidates', methods=['GET', 'POST'])
def all_candidates():
    if request.method == 'POST':
        candidates = load_candidates()
        skipped_files = []

        files = request.files.getlist('candidateFiles')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                text = ""
                if filename.endswith('.docx'):
                    text = extract_text_from_docx(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    file_type = 'docx'
                elif filename.endswith('.pdf'):
                    text = extract_text_from_pdf(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    file_type = 'pdf'

                if text and text != "Text extraction failed.":
                    extracted_info = extract_info(text)
                    if any(candidate['email'] == extracted_info['email'] for candidate in candidates):
                        skipped_files.append(filename)
                        continue

                    candidates.append({
                        'email': extracted_info['email'],
                        'job_title': extracted_info['job_title'],
                        'location': extracted_info['location'],
                        'upload_date': datetime.date.today().strftime('%d-%m-%Y'),
                        'source': 'Manual Upload',
                        'cv_file': filename,
                        'file_type': file_type,
                        'full_text': extracted_info['full_text']  # Store the full text
                    })
                else:
                    print(f"Failed to extract text from {filename}")
        
        save_candidates(candidates)
        if skipped_files:
            flash(f"The following files were skipped because their emails already exist: {', '.join(skipped_files)}")
        
        return redirect(url_for('all_candidates'))

    candidates = load_candidates()
    return render_template('all_candidates.html', candidates=candidates)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download_selected_cvs', methods=['POST'])
def download_selected_cvs():
    selected_files = request.form.getlist('selected[]')

    if not selected_files:
        flash('No CVs selected for download.')
        return redirect(url_for('all_candidates'))

    if len(selected_files) == 1:
        # Download a single file directly
        filename = selected_files[0]
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        return send_file(filepath, as_attachment=True)

    else:
        # Create a ZIP file in memory for multiple files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for filename in selected_files:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                zip_file.write(filepath, filename)

        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name='selected_cvs.zip', mimetype='application/zip')

@app.route('/delete_selected_searches', methods=['POST'])
def delete_selected_searches():
    searches = load_searches()
    selected_searches = request.form.getlist('selected[]')

    if not selected_searches:
        flash('No searches selected for deletion.')
        return redirect(url_for('previous_search'))

    searches = [s for s in searches if s['search_name'] not in selected_searches]
    save_searches(searches)
    
    flash(f'Successfully deleted selected searches.')
    return redirect(url_for('previous_search'))

# ... (keep all previous imports and code)

@app.route('/new_search', methods=['GET', 'POST'])
def new_search():
    if request.method == 'POST':
        searches = load_searches()
        search_name = request.form.get('search_name', '')
        job_title = request.form.get('job_title', '').strip()
        location = request.form.get('location', '').strip()
        keywords = request.form.get('keywords', '').strip()

        if not search_name:
            flash('Search name is required.')
            return redirect(url_for('new_search'))

        search_data = {
            'search_name': search_name,
            'job_title': job_title,
            'location': location,
            'keywords': keywords,
            'date': datetime.date.today().strftime('%d-%m-%Y')
        }

        # If any of the optional fields are empty, ensure they are set to None or an empty string
        search_data['job_title'] = job_title if job_title else None
        search_data['location'] = location if location else None
        search_data['keywords'] = keywords if keywords else None

        searches.append(search_data)
        save_searches(searches)
        flash(f'Search {search_name} created successfully.')
        return redirect(url_for('previous_search'))

    # Pass both cities and job titles to the template
    return render_template('new_search.html', cities=cities, job_titles=job_titles)




@app.route('/previous_search', methods=['GET', 'POST'])
def previous_search():
    searches = load_searches()

    if request.method == 'POST':
        selected_searches = request.form.getlist('selected[]')

        if not selected_searches:
            flash('No searches selected for deletion.')
            return redirect(url_for('previous_search'))

        searches = [s for s in searches if s['search_name'] not in selected_searches]
        save_searches(searches)
        flash(f'Successfully deleted selected searches.')
        return redirect(url_for('previous_search'))

    return render_template('previous_search.html', searches=enumerate(searches, 1))

@app.route('/delete_selected_cvs', methods=['POST'])
def delete_selected_cvs():
    selected_files = request.form.getlist('selected[]')

    if not selected_files:
        flash('No CVs selected for deletion.')
        return redirect(url_for('all_candidates'))

    candidates = load_candidates()
    for filename in selected_files:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        # Also remove from candidates list
        candidates = [c for c in candidates if c['cv_file'] != filename]

    save_candidates(candidates)
    flash(f'Successfully deleted selected CVs.')
    return redirect(url_for('all_candidates'))

@app.route('/search_results/<search_name>')
def search_results(search_name):
    searches = load_searches()
    candidates = load_candidates()
    search = next((s for s in searches if s['search_name'] == search_name), None)
    if not search:
        flash('Search not found.')
        return redirect(url_for('previous_search'))

    filtered_candidates = []
    for candidate in candidates:
        # Only perform matching if the respective field is not empty
        job_title_match = fuzzy_match(search['job_title'], [candidate['job_title']], threshold=70) if search['job_title'] else True
        location_match = fuzzy_match(search['location'], [candidate['location']], threshold=70) if search['location'] else True
        
        # New logic for keywords match
        keywords = [kw.strip().lower() for kw in search['keywords'].split(',') if kw.strip()] if search['keywords'] else []
        matched_keywords = [kw for kw in keywords if kw in candidate['full_text'].lower()]
        keywords_match = len(matched_keywords) == len(keywords) if keywords else True  # All keywords must match

        if job_title_match and location_match and keywords_match:
            candidate['matched_keywords'] = ', '.join(matched_keywords) if matched_keywords else 'N/A'
            filtered_candidates.append(candidate)
        
        # Debug logging
        print(f"Candidate: {candidate['email']}")
        print(f"Job Title: {candidate['job_title']}")
        print(f"Location: {candidate['location']}")
        print(f"Job Title Match: {job_title_match}")
        print(f"Location Match: {location_match}")
        print(f"Keywords Match: {keywords_match}")
        print(f"Matched Keywords: {matched_keywords}")
        print("---")

    return render_template('search_results.html', search=search, candidates=filtered_candidates, enumerate=enumerate)



if __name__ == '__main__':
    app.run(debug=True)