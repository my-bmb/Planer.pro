from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import cloudinary
import cloudinary.uploader
from supabase import create_client, Client  # <-- Yeh line fix

load_dotenv()

app = Flask(__name__)

# Initialize Supabase
supabase: Client = create_client(  # <-- Type hint optional
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/plans', methods=['GET'])
def get_plans():
    try:
        response = supabase.table('plans').select('*').execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plan', methods=['POST'])
def save_plan():
    try:
        data = request.json
        plan_data = {
            'title': data.get('title', 'Untitled'),
            'photo_url': data.get('photo', None),
            'tree_data': data.get('tree_data', {})
        }
        
        if data.get('id') and str(data.get('id')) != 'undefined':
            response = supabase.table('plans').update(plan_data).eq('id', data['id']).execute()
        else:
            response = supabase.table('plans').insert(plan_data).execute()
        
        return jsonify({'success': True, 'data': response.data[0] if response.data else {}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plan/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    try:
        supabase.table('plans').delete().eq('id', plan_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_image():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file'}), 400
        
        file = request.files['file']
        upload_result = cloudinary.uploader.upload(file, folder='life_dashboard')
        
        return jsonify({
            'success': True,
            'url': upload_result['secure_url']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)