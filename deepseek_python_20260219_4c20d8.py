import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, session
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize Supabase
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# ========== Database Setup ==========
def get_table_info():
    """Get table info from Supabase"""
    try:
        # Try to query the table to see what columns exist
        response = supabase.table('plans').select('*').limit(1).execute()
        if response.data and len(response.data) > 0:
            print("✅ Table 'plans' exists with columns:", list(response.data[0].keys()))
            return True
        else:
            print("⚠️ Table 'plans' exists but is empty")
            return True
    except Exception as e:
        print(f"❌ Error accessing table: {e}")
        return False

# ========== Helper Functions ==========
def generate_id():
    """Generate unique ID"""
    return str(uuid.uuid4())

def get_user_id():
    """Get or create user session ID"""
    if 'user_id' not in session:
        session['user_id'] = generate_id()
    return session['user_id']

def upload_to_cloudinary(file, folder='plans'):
    """Upload file to Cloudinary"""
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type='auto',
            transformation=[
                {'width': 800, 'height': 800, 'crop': 'limit'},
                {'quality': 'auto'}
            ]
        )
        return {
            'public_id': result['public_id'],
            'url': result['secure_url'],
            'format': result.get('format', ''),
            'resource_type': result['resource_type']
        }
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

def delete_from_cloudinary(public_id):
    """Delete file from Cloudinary"""
    try:
        cloudinary.uploader.destroy(public_id)
        return True
    except Exception as e:
        print(f"Cloudinary delete error: {e}")
        return False

# ========== Routes ==========
@app.route('/')
def index():
    """Render main dashboard"""
    # Check database connection
    get_table_info()
    return render_template('index.html')

# ===== Plan CRUD Operations =====
@app.route('/api/plans', methods=['GET'])
def get_plans():
    """Get all plans for current user"""
    try:
        user_id = get_user_id()
        print(f"Fetching plans for user: {user_id}")
        
        response = supabase.table('plans')\
            .select('*')\
            .is_('parent_id', 'null')\
            .eq('user_id', user_id)\
            .order('created_at')\
            .execute()
        
        print(f"Found {len(response.data)} plans")
        
        # Convert to list and ensure proper JSON parsing
        plans = []
        for item in response.data:
            item['content'] = json.loads(item['content']) if isinstance(item['content'], str) else item.get('content', [])
            item['children'] = json.loads(item['children']) if isinstance(item['children'], str) else item.get('children', [])
            plans.append(item)
        
        return jsonify({'success': True, 'data': plans})
    except Exception as e:
        print(f"Error in get_plans: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans', methods=['POST'])
def create_plan():
    """Create new plan"""
    try:
        data = request.json
        user_id = get_user_id()
        
        print(f"Creating plan for user: {user_id}")
        
        plan_data = {
            'id': generate_id(),
            'user_id': user_id,
            'title': data.get('title', 'New Plan'),
            'photo': data.get('photo'),
            'created_at': datetime.now().isoformat(),
            'content': json.dumps([]),
            'children': json.dumps([]),
            'progress': 0,
            'level': 1,
            'parent_id': None
        }
        
        print(f"Inserting plan data: {plan_data}")
        
        response = supabase.table('plans').insert(plan_data).execute()
        
        if response.data and len(response.data) > 0:
            new_plan = response.data[0]
            new_plan['content'] = json.loads(new_plan['content'])
            new_plan['children'] = json.loads(new_plan['children'])
            print(f"Plan created successfully: {new_plan['id']}")
            return jsonify({'success': True, 'data': new_plan})
        else:
            print("Failed to create plan: No data returned")
            return jsonify({'success': False, 'error': 'Failed to create plan'}), 500
            
    except Exception as e:
        print(f"Error in create_plan: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    """Get single plan by ID"""
    try:
        user_id = get_user_id()
        response = supabase.table('plans')\
            .select('*')\
            .eq('id', plan_id)\
            .eq('user_id', user_id)\
            .execute()
        
        if response.data and len(response.data) > 0:
            plan = response.data[0]
            plan['content'] = json.loads(plan['content']) if isinstance(plan['content'], str) else plan.get('content', [])
            plan['children'] = json.loads(plan['children']) if isinstance(plan['children'], str) else plan.get('children', [])
            return jsonify({'success': True, 'data': plan})
        else:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<plan_id>', methods=['PUT'])
def update_plan(plan_id):
    """Update plan"""
    try:
        data = request.json
        user_id = get_user_id()
        
        update_data = {
            'title': data.get('title'),
            'photo': data.get('photo'),
            'updated_at': datetime.now().isoformat()
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        response = supabase.table('plans')\
            .update(update_data)\
            .eq('id', plan_id)\
            .eq('user_id', user_id)\
            .execute()
        
        if response.data and len(response.data) > 0:
            updated_plan = response.data[0]
            updated_plan['content'] = json.loads(updated_plan['content']) if isinstance(updated_plan['content'], str) else updated_plan.get('content', [])
            updated_plan['children'] = json.loads(updated_plan['children']) if isinstance(updated_plan['children'], str) else updated_plan.get('children', [])
            return jsonify({'success': True, 'data': updated_plan})
        else:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    """Delete plan and all children"""
    try:
        user_id = get_user_id()
        
        # Get plan to delete its photos from Cloudinary
        plan_response = supabase.table('plans')\
            .select('photo,content')\
            .eq('id', plan_id)\
            .eq('user_id', user_id)\
            .execute()
        
        if plan_response.data and len(plan_response.data) > 0:
            plan = plan_response.data[0]
            
            # Delete main plan photo from Cloudinary
            if plan.get('photo') and 'cloudinary' in plan['photo']:
                public_id = extract_public_id(plan['photo'])
                if public_id:
                    delete_from_cloudinary(public_id)
            
            # Delete all child plans and their photos recursively
            delete_child_plans_recursive(plan_id, user_id)
        
        # Delete the plan
        response = supabase.table('plans')\
            .delete()\
            .eq('id', plan_id)\
            .eq('user_id', user_id)\
            .execute()
        
        return jsonify({'success': True, 'data': response.data})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def delete_child_plans_recursive(parent_id, user_id):
    """Recursively delete all child plans"""
    try:
        # Get all children
        children = supabase.table('plans')\
            .select('id,photo,content')\
            .eq('parent_id', parent_id)\
            .eq('user_id', user_id)\
            .execute()
        
        for child in children.data:
            # Delete child's photo
            if child.get('photo') and 'cloudinary' in child['photo']:
                public_id = extract_public_id(child['photo'])
                if public_id:
                    delete_from_cloudinary(public_id)
            
            # Recursively delete grandchildren
            delete_child_plans_recursive(child['id'], user_id)
        
        # Delete all children
        supabase.table('plans')\
            .delete()\
            .eq('parent_id', parent_id)\
            .eq('user_id', user_id)\
            .execute()
            
    except Exception as e:
        print(f"Error deleting child plans: {e}")

# ===== Content Management =====
@app.route('/api/plans/<plan_id>/content', methods=['PUT'])
def update_plan_content(plan_id):
    """Update plan content array"""
    try:
        data = request.json
        content = data.get('content', [])
        user_id = get_user_id()
        
        response = supabase.table('plans')\
            .update({
                'content': json.dumps(content),
                'updated_at': datetime.now().isoformat()
            })\
            .eq('id', plan_id)\
            .eq('user_id', user_id)\
            .execute()
        
        if response.data and len(response.data) > 0:
            updated_plan = response.data[0]
            updated_plan['content'] = json.loads(updated_plan['content'])
            return jsonify({'success': True, 'data': updated_plan})
        else:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<plan_id>/progress', methods=['PUT'])
def update_plan_progress(plan_id):
    """Update plan progress"""
    try:
        data = request.json
        progress = data.get('progress', 0)
        user_id = get_user_id()
        
        response = supabase.table('plans')\
            .update({
                'progress': progress,
                'updated_at': datetime.now().isoformat()
            })\
            .eq('id', plan_id)\
            .eq('user_id', user_id)\
            .execute()
        
        return jsonify({'success': True, 'data': response.data})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== Sub-plan (Model) Management =====
@app.route('/api/plans/<parent_id>/subplans', methods=['POST'])
def create_subplan(parent_id):
    """Create a sub-plan (model) under a parent plan"""
    try:
        data = request.json
        user_id = get_user_id()
        
        # Verify parent exists
        parent_check = supabase.table('plans')\
            .select('level')\
            .eq('id', parent_id)\
            .eq('user_id', user_id)\
            .execute()
        
        if not parent_check.data or len(parent_check.data) == 0:
            return jsonify({'success': False, 'error': 'Parent plan not found'}), 404
        
        parent_level = parent_check.data[0]['level']
        
        subplan_data = {
            'id': generate_id(),
            'user_id': user_id,
            'title': data.get('title', 'New Model'),
            'photo': data.get('photo'),
            'created_at': datetime.now().isoformat(),
            'content': json.dumps([]),
            'children': json.dumps([]),
            'progress': 0,
            'level': parent_level + 1,
            'parent_id': parent_id
        }
        
        response = supabase.table('plans').insert(subplan_data).execute()
        
        if response.data and len(response.data) > 0:
            new_subplan = response.data[0]
            
            # Update parent's children array
            parent = supabase.table('plans')\
                .select('children')\
                .eq('id', parent_id)\
                .execute()
            
            if parent.data and len(parent.data) > 0:
                children = json.loads(parent.data[0]['children']) if isinstance(parent.data[0]['children'], str) else parent.data[0].get('children', [])
                children.append(new_subplan['id'])
                
                supabase.table('plans')\
                    .update({'children': json.dumps(children)})\
                    .eq('id', parent_id)\
                    .execute()
            
            new_subplan['content'] = json.loads(new_subplan['content'])
            new_subplan['children'] = json.loads(new_subplan['children'])
            return jsonify({'success': True, 'data': new_subplan})
        else:
            return jsonify({'success': False, 'error': 'Failed to create subplan'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<plan_id>/subplans', methods=['GET'])
def get_subplans(plan_id):
    """Get all sub-plans of a plan"""
    try:
        user_id = get_user_id()
        response = supabase.table('plans')\
            .select('*')\
            .eq('parent_id', plan_id)\
            .eq('user_id', user_id)\
            .order('created_at')\
            .execute()
        
        subplans = []
        for item in response.data:
            item['content'] = json.loads(item['content']) if isinstance(item['content'], str) else item.get('content', [])
            item['children'] = json.loads(item['children']) if isinstance(item['children'], str) else item.get('children', [])
            subplans.append(item)
        
        return jsonify({'success': True, 'data': subplans})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== Photo Upload Routes =====
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload file to Cloudinary"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Upload to Cloudinary
        result = upload_to_cloudinary(file)
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'url': result['url'],
                    'public_id': result['public_id'],
                    'name': file.filename
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Upload failed'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload/multiple', methods=['POST'])
def upload_multiple_files():
    """Upload multiple files to Cloudinary"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        results = []
        
        for file in files:
            if file.filename:
                result = upload_to_cloudinary(file)
                if result:
                    results.append({
                        'url': result['url'],
                        'public_id': result['public_id'],
                        'name': file.filename
                    })
        
        return jsonify({
            'success': True,
            'data': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete', methods=['POST'])
def delete_file():
    """Delete file from Cloudinary"""
    try:
        data = request.json
        public_id = data.get('public_id')
        
        if not public_id:
            return jsonify({'success': False, 'error': 'No public_id provided'}), 400
        
        result = delete_from_cloudinary(public_id)
        
        return jsonify({'success': result})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== Helper Routes =====
@app.route('/api/user/session', methods=['GET'])
def get_user_session():
    """Get or create user session"""
    return jsonify({
        'success': True,
        'data': {
            'user_id': get_user_id()
        }
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

# ===== Utility Functions =====
def extract_public_id(cloudinary_url):
    """Extract public_id from Cloudinary URL"""
    try:
        # Example URL: https://res.cloudinary.com/cloud_name/image/upload/v1234567890/folder/public_id.jpg
        parts = cloudinary_url.split('/')
        # Find 'upload' in parts and get the next part after version
        for i, part in enumerate(parts):
            if part == 'upload' and i + 2 < len(parts):
                # Skip version number (v1234567890)
                version_part = parts[i + 1]
                if version_part.startswith('v'):
                    public_id_with_ext = parts[i + 2]
                    # Remove file extension
                    public_id = '.'.join(public_id_with_ext.split('.')[:-1])
                    return public_id
        return None
    except:
        return None

# ===== Initialize =====
with app.app_context():
    get_table_info()

# ===== Run the app =====
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)