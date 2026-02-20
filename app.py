import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize Supabase
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_ANON_KEY')
)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# ==================== Helper Functions ====================

def delete_item_and_children(item_id):
    """Recursively delete item and all children using PostgreSQL function"""
    try:
        supabase.rpc('delete_item_recursive', {'item_id': item_id}).execute()
        return True
    except Exception as e:
        print(f"Error deleting item: {e}")
        return False

# ==================== API Routes ====================

@app.route('/')
def index():
    """Serve the main application"""
    return render_template('index.html')

# ===== Plans API =====

@app.route('/api/plans', methods=['GET'])
def get_plans():
    """Get all plans"""
    try:
        response = supabase.table('plans')\
            .select('*')\
            .order('created_at', desc=True)\
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plans', methods=['POST'])
def create_plan():
    """Create a new plan"""
    try:
        data = request.json
        new_plan = {
            'title': data.get('title'),
            'description': data.get('description', ''),
            'photo_url': data.get('photo_url'),
            'photo_public_id': data.get('photo_public_id')
        }
        
        response = supabase.table('plans').insert(new_plan).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plans/<plan_id>', methods=['PUT'])
def update_plan(plan_id):
    """Update a plan"""
    try:
        data = request.json
        update_data = {
            'title': data.get('title'),
            'description': data.get('description', ''),
            'photo_url': data.get('photo_url'),
            'photo_public_id': data.get('photo_public_id')
        }
        
        response = supabase.table('plans')\
            .update(update_data)\
            .eq('id', plan_id)\
            .execute()
        
        return jsonify(response.data[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plans/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    """Delete a plan (cascades to all items)"""
    try:
        supabase.table('plans').delete().eq('id', plan_id).execute()
        return jsonify({'message': 'Plan deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== Items API =====

@app.route('/api/items/<plan_id>', methods=['GET'])
def get_items(plan_id):
    """Get all items for a plan as FLAT list (critical for frontend tree building)"""
    try:
        response = supabase.table('items')\
            .select('*')\
            .eq('plan_id', plan_id)\
            .order('position')\
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items', methods=['POST'])
def create_item():
    """Create a new item"""
    try:
        data = request.json
        
        # Get max position for ordering within same parent
        position_response = supabase.table('items')\
            .select('position')\
            .eq('plan_id', data.get('plan_id'))\
            .eq('parent_id', data.get('parent_id'))\
            .order('position', desc=True)\
            .limit(1)\
            .execute()
        
        max_position = position_response.data[0]['position'] if position_response.data else -1
        position = max_position + 1
        
        new_item = {
            'plan_id': data.get('plan_id'),
            'parent_id': data.get('parent_id'),
            'title': data.get('title'),
            'description': data.get('description', ''),
            'type': data.get('type', 'content'),
            'content_data': data.get('content_data', {}),
            'position': position
        }
        
        response = supabase.table('items').insert(new_item).execute()
        return jsonify(response.data[0]), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/<item_id>', methods=['PUT'])
def update_item(item_id):
    """Update an item"""
    try:
        data = request.json
        update_data = {
            'title': data.get('title'),
            'description': data.get('description', ''),
            'content_data': data.get('content_data', {})
        }
        
        response = supabase.table('items')\
            .update(update_data)\
            .eq('id', item_id)\
            .execute()
        
        return jsonify(response.data[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Delete an item and all its children recursively"""
    try:
        success = delete_item_and_children(item_id)
        if success:
            return jsonify({'message': 'Item and children deleted successfully'})
        else:
            return jsonify({'error': 'Failed to delete item'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/reorder', methods=['POST'])
def reorder_items():
    """Bulk update item positions"""
    try:
        items = request.json.get('items', [])
        
        for item in items:
            supabase.table('items')\
                .update({'position': item['position']})\
                .eq('id', item['id'])\
                .execute()
        
        return jsonify({'message': 'Items reordered successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== Upload API =====

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload file to Cloudinary"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder='life-dashboard',
            resource_type='auto'
        )
        
        # Get item_id if provided
        item_id = request.form.get('item_id')
        
        # Save to attachments table if item_id is provided
        if item_id:
            attachment = {
                'item_id': item_id,
                'file_url': upload_result['secure_url'],
                'public_id': upload_result['public_id'],
                'file_name': file.filename,
                'file_type': upload_result['resource_type'],
                'type': 'image' if upload_result['resource_type'] == 'image' else 'document'
            }
            supabase.table('attachments').insert(attachment).execute()
        
        return jsonify({
            'url': upload_result['secure_url'],
            'public_id': upload_result['public_id'],
            'format': upload_result.get('format'),
            'resource_type': upload_result['resource_type']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/attachments/<item_id>', methods=['GET'])
def get_attachments(item_id):
    """Get all attachments for an item"""
    try:
        response = supabase.table('attachments')\
            .select('*')\
            .eq('item_id', item_id)\
            .order('created_at')\
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)