from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import cloudinary
import cloudinary.uploader
from supabase import create_client
import uuid
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Initialize Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Initialize Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

@app.route('/')
def index():
    return render_template('index.html')

# 📥 GET ALL PLANS
@app.route('/api/plans', methods=['GET'])
def get_plans():
    try:
        response = supabase.table('plans').select('*').order('created_at', desc=True).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 📤 SAVE PLAN (Create or Update)
@app.route('/api/plan', methods=['POST'])
def save_plan():
    try:
        data = request.json
        
        # Generate plan number if not exists
        if not data.get('plan_number'):
            count = supabase.table('plans').select('*', count='exact').execute()
            plan_number = str(len(count.data) + 1).zfill(3)
        else:
            plan_number = data.get('plan_number')
        
        plan_data = {
            'title': data.get('title', 'Untitled'),
            'photo_url': data.get('photo', None),
            'plan_number': plan_number,
            'tree_data': data.get('tree_data', {})
        }
        
        # Update if ID exists, else insert
        if data.get('id') and str(data.get('id')) != 'undefined':
            response = supabase.table('plans').update(plan_data).eq('id', data['id']).execute()
        else:
            response = supabase.table('plans').insert(plan_data).execute()
        
        return jsonify({'success': True, 'data': response.data[0] if response.data else {}})
    
    except Exception as e:
        print("Save error:", str(e))
        return jsonify({'error': str(e)}), 500

# 🗑️ DELETE PLAN
@app.route('/api/plan/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    try:
        supabase.table('plans').delete().eq('id', plan_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 📸 UPLOAD IMAGE TO CLOUDINARY
@app.route('/api/upload', methods=['POST'])
def upload_image():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder='life_dashboard',
            resource_type='auto'
        )
        
        return jsonify({
            'success': True,
            'url': upload_result['secure_url'],
            'public_id': upload_result['public_id']
        })
    
    except Exception as e:
        print("Upload error:", str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)