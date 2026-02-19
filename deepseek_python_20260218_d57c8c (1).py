from flask import Flask, render_template, request, jsonify, session
from supabase import create_client, Client
import cloudinary
import cloudinary.uploader
import cloudinary.api
from datetime import datetime
import os
from dotenv import load_dotenv
import uuid
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Get port from environment variable (Render sets this automatically)
port = int(os.environ.get('PORT', 5000))

# Supabase Configuration
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/plans', methods=['GET'])
def get_plans():
    """Get all plans for the current session"""
    try:
        # Get session ID or create new one
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Fetch plans from Supabase
        response = supabase.table('plans')\
            .select('*')\
            .eq('session_id', session['session_id'])\
            .order('created_at')\
            .execute()
        
        # Parse content JSON
        plans = []
        for plan in response.data:
            plan['content'] = json.loads(plan['content']) if plan['content'] else []
            plan['children'] = json.loads(plan['children']) if plan['children'] else []
            plans.append(plan)
        
        return jsonify({'success': True, 'plans': plans})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans', methods=['POST'])
def create_plan():
    """Create a new plan"""
    try:
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        data = request.json
        plan_id = data.get('id', int(datetime.now().timestamp() * 1000))
        
        # Upload photo to Cloudinary if present
        photo_url = None
        if data.get('photo'):
            try:
                upload_result = cloudinary.uploader.upload(
                    data['photo'],
                    folder=f"plans/{session['session_id']}",
                    public_id=str(plan_id)
                )
                photo_url = upload_result['secure_url']
            except Exception as e:
                print(f"Cloudinary upload error: {e}")
        
        plan_data = {
            'id': plan_id,
            'session_id': session['session_id'],
            'title': data['title'],
            'photo': photo_url,
            'content': json.dumps([]),
            'children': json.dumps([]),
            'progress': 0,
            'level': 1,
            'parent_id': None,
            'created_at': datetime.now().isoformat()
        }
        
        response = supabase.table('plans').insert(plan_data).execute()
        
        if response.data:
            plan = response.data[0]
            plan['content'] = []
            plan['children'] = []
            return jsonify({'success': True, 'plan': plan})
        else:
            return jsonify({'success': False, 'error': 'Failed to create plan'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<int:plan_id>', methods=['PUT'])
def update_plan(plan_id):
    """Update an existing plan"""
    try:
        data = request.json
        
        # Check if photo needs to be uploaded
        photo_url = data.get('photo')
        if data.get('photo') and data['photo'].startswith('data:image'):
            try:
                upload_result = cloudinary.uploader.upload(
                    data['photo'],
                    folder=f"plans/{session['session_id']}",
                    public_id=str(plan_id),
                    overwrite=True
                )
                photo_url = upload_result['secure_url']
            except Exception as e:
                print(f"Cloudinary upload error: {e}")
        
        update_data = {
            'title': data['title'],
            'photo': photo_url
        }
        
        response = supabase.table('plans')\
            .update(update_data)\
            .eq('id', plan_id)\
            .eq('session_id', session.get('session_id'))\
            .execute()
        
        if response.data:
            return jsonify({'success': True, 'plan': response.data[0]})
        else:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<int:plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    """Delete a plan and all its children"""
    try:
        # Get all child plans recursively
        def get_all_child_ids(parent_id):
            response = supabase.table('plans')\
                .select('id')\
                .eq('parent_id', parent_id)\
                .eq('session_id', session.get('session_id'))\
                .execute()
            
            child_ids = [p['id'] for p in response.data]
            for child_id in child_ids[:]:
                child_ids.extend(get_all_child_ids(child_id))
            return child_ids
        
        child_ids = get_all_child_ids(plan_id)
        all_ids = [plan_id] + child_ids
        
        # Delete images from Cloudinary
        for pid in all_ids:
            try:
                cloudinary.uploader.destroy(f"plans/{session['session_id']}/{pid}")
            except:
                pass
        
        # Delete from Supabase
        response = supabase.table('plans')\
            .delete()\
            .in_('id', all_ids)\
            .eq('session_id', session.get('session_id'))\
            .execute()
        
        return jsonify({'success': True, 'deleted': len(all_ids)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<int:plan_id>/content', methods=['GET'])
def get_plan_content(plan_id):
    """Get content of a specific plan"""
    try:
        response = supabase.table('plans')\
            .select('content, children')\
            .eq('id', plan_id)\
            .eq('session_id', session.get('session_id'))\
            .execute()
        
        if response.data:
            content = json.loads(response.data[0]['content']) if response.data[0]['content'] else []
            children = json.loads(response.data[0]['children']) if response.data[0]['children'] else []
            return jsonify({'success': True, 'content': content, 'children': children})
        else:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<int:plan_id>/content', methods=['POST'])
def add_plan_content(plan_id):
    """Add content to a plan"""
    try:
        # Get current plan
        response = supabase.table('plans')\
            .select('content, children')\
            .eq('id', plan_id)\
            .eq('session_id', session.get('session_id'))\
            .execute()
        
        if not response.data:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        current_content = json.loads(response.data[0]['content']) if response.data[0]['content'] else []
        current_children = json.loads(response.data[0]['children']) if response.data[0]['children'] else []
        
        data = request.json
        new_item = {
            'id': data.get('id', int(datetime.now().timestamp() * 1000)),
            'type': data['type'],
            'data': data['data'],
            'created_at': datetime.now().isoformat()
        }
        
        # FIXED: Only create sub-plan if explicitly requested
        # Default is to NOT create sub-plan (treat model as content only)
        if data['type'] == 'model' and data.get('create_subplan', False):
            sub_plan_id = new_item['id']
            current_children.append(sub_plan_id)
            
            # Create sub-plan
            sub_plan_data = {
                'id': sub_plan_id,
                'session_id': session['session_id'],
                'title': data['data'].get('title', 'New Model'),
                'photo': data['data'].get('photo'),
                'content': json.dumps([]),
                'children': json.dumps([]),
                'progress': 0,
                'level': data.get('level', 2),
                'parent_id': plan_id,
                'created_at': datetime.now().isoformat()
            }
            
            supabase.table('plans').insert(sub_plan_data).execute()
            print(f"Created sub-plan: {sub_plan_id} with title: {data['data'].get('title')}")
        
        # Handle photo upload for photo type
        if data['type'] == 'photo' and data['data'].get('images'):
            for img in data['data']['images']:
                if img.get('preview', '').startswith('data:image'):
                    try:
                        upload_result = cloudinary.uploader.upload(
                            img['preview'],
                            folder=f"plans/{session['session_id']}/{plan_id}",
                            public_id=f"photo_{int(datetime.now().timestamp() * 1000)}"
                        )
                        img['preview'] = upload_result['secure_url']
                        img['cloudinary_id'] = upload_result['public_id']
                    except Exception as e:
                        print(f"Cloudinary upload error: {e}")
        
        current_content.append(new_item)
        
        # Update plan
        update_data = {
            'content': json.dumps(current_content),
            'children': json.dumps(current_children)
        }
        
        supabase.table('plans')\
            .update(update_data)\
            .eq('id', plan_id)\
            .execute()
        
        return jsonify({'success': True, 'item': new_item})
        
    except Exception as e:
        print(f"Error adding content: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<int:plan_id>/content/<int:content_id>', methods=['PUT'])
def update_plan_content(plan_id, content_id):
    """Update specific content item"""
    try:
        response = supabase.table('plans')\
            .select('content')\
            .eq('id', plan_id)\
            .eq('session_id', session.get('session_id'))\
            .execute()
        
        if not response.data:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        content = json.loads(response.data[0]['content']) if response.data[0]['content'] else []
        data = request.json
        
        # Find and update content
        for item in content:
            if item['id'] == content_id:
                item['data'] = data['data']
                break
        
        # Update in database
        supabase.table('plans')\
            .update({'content': json.dumps(content)})\
            .eq('id', plan_id)\
            .execute()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/plans/<int:plan_id>/content/<int:content_id>', methods=['DELETE'])
def delete_plan_content(plan_id, content_id):
    """Delete specific content item"""
    try:
        response = supabase.table('plans')\
            .select('content')\
            .eq('id', plan_id)\
            .eq('session_id', session.get('session_id'))\
            .execute()
        
        if not response.data:
            return jsonify({'success': False, 'error': 'Plan not found'}), 404
        
        content = json.loads(response.data[0]['content']) if response.data[0]['content'] else []
        
        # Find item to delete (for photos, delete from Cloudinary)
        for item in content:
            if item['id'] == content_id and item['type'] == 'photo':
                if item['data'].get('images'):
                    for img in item['data']['images']:
                        if img.get('cloudinary_id'):
                            try:
                                cloudinary.uploader.destroy(img['cloudinary_id'])
                            except:
                                pass
                break
        
        # Remove from content
        content = [item for item in content if item['id'] != content_id]
        
        # Update in database
        supabase.table('plans')\
            .update({'content': json.dumps(content)})\
            .eq('id', plan_id)\
            .execute()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a single file to Cloudinary"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        plan_id = request.form.get('plan_id', 'temp')
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file,
            folder=f"plans/{session.get('session_id', 'temp')}/{plan_id}",
            resource_type="auto"
        )
        
        return jsonify({
            'success': True,
            'url': upload_result['secure_url'],
            'public_id': upload_result['public_id'],
            'format': upload_result['format'],
            'bytes': upload_result['bytes']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Bind to 0.0.0.0 to make it accessible externally
    app.run(host='0.0.0.0', port=port, debug=True)