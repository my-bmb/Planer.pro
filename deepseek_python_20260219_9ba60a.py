import os
import uuid
import cloudinary
import cloudinary.uploader
import cloudinary.api
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
import traceback

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
CORS(app)

# Initialize Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

class PlanManager:
    """Helper class to manage plan operations"""
    
    @staticmethod
    def create_plan(data):
        """Create a new plan in Supabase"""
        try:
            plan_id = str(uuid.uuid4())
            plan_data = {
                'id': plan_id,
                'title': data.get('title'),
                'photo': data.get('photo'),
                'created_at': datetime.utcnow().isoformat(),
                'content': data.get('content', []),
                'children': data.get('children', []),
                'progress': data.get('progress', 0),
                'level': data.get('level', 1),
                'parent_id': data.get('parentId'),
                'user_id': session.get('user_id', 'anonymous')
            }
            
            logger.info(f"Creating plan with data: {plan_data}")
            result = supabase.table('plans').insert(plan_data).execute()
            logger.info(f"Plan created: {plan_id}")
            return plan_data
        except Exception as e:
            logger.error(f"Error creating plan: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def get_plan(plan_id):
        """Get a plan by ID"""
        try:
            result = supabase.table('plans').select('*').eq('id', plan_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting plan {plan_id}: {str(e)}")
            return None

    @staticmethod
    def get_all_plans(user_id='anonymous'):
        """Get all plans for a user"""
        try:
            logger.info(f"Fetching all plans for user: {user_id}")
            result = supabase.table('plans').select('*').eq('user_id', user_id).execute()
            logger.info(f"Found {len(result.data)} plans")
            return result.data
        except Exception as e:
            logger.error(f"Error getting all plans: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    @staticmethod
    def update_plan(plan_id, data):
        """Update a plan"""
        try:
            data['updated_at'] = datetime.utcnow().isoformat()
            result = supabase.table('plans').update(data).eq('id', plan_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error updating plan {plan_id}: {str(e)}")
            return None

    @staticmethod
    def delete_plan(plan_id):
        """Delete a plan and all its children"""
        try:
            # Get all child plans recursively
            children = supabase.table('plans').select('id').eq('parent_id', plan_id).execute()
            for child in children.data:
                PlanManager.delete_plan(child['id'])
            
            # Delete the plan
            result = supabase.table('plans').delete().eq('id', plan_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting plan {plan_id}: {str(e)}")
            return False

class ContentManager:
    """Helper class to manage content operations"""
    
    @staticmethod
    def add_content(plan_id, content_item):
        """Add content to a plan"""
        try:
            # Get current plan
            plan = PlanManager.get_plan(plan_id)
            if not plan:
                return None
            
            # Initialize content array if needed
            if 'content' not in plan or not plan['content']:
                plan['content'] = []
            
            # Add new content
            content_item['id'] = content_item.get('id', str(uuid.uuid4()))
            content_item['created_at'] = datetime.utcnow().isoformat()
            plan['content'].append(content_item)
            
            # Update plan
            result = supabase.table('plans').update({
                'content': plan['content']
            }).eq('id', plan_id).execute()
            
            return content_item
        except Exception as e:
            logger.error(f"Error adding content to plan {plan_id}: {str(e)}")
            return None

    @staticmethod
    def update_content(plan_id, content_id, updated_data):
        """Update content in a plan"""
        try:
            plan = PlanManager.get_plan(plan_id)
            if not plan or 'content' not in plan:
                return None
            
            # Find and update content
            for i, item in enumerate(plan['content']):
                if item['id'] == content_id:
                    plan['content'][i].update(updated_data)
                    break
            
            # Update plan
            result = supabase.table('plans').update({
                'content': plan['content']
            }).eq('id', plan_id).execute()
            
            return updated_data
        except Exception as e:
            logger.error(f"Error updating content {content_id}: {str(e)}")
            return None

    @staticmethod
    def delete_content(plan_id, content_id):
        """Delete content from a plan"""
        try:
            plan = PlanManager.get_plan(plan_id)
            if not plan or 'content' not in plan:
                return False
            
            # Filter out the content
            plan['content'] = [item for item in plan['content'] if item['id'] != content_id]
            
            # Update plan
            supabase.table('plans').update({
                'content': plan['content']
            }).eq('id', plan_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error deleting content {content_id}: {str(e)}")
            return False

    @staticmethod
    def update_checklist_task(plan_id, content_id, task_index, completed):
        """Update checklist task completion"""
        try:
            plan = PlanManager.get_plan(plan_id)
            if not plan or 'content' not in plan:
                return False
            
            for item in plan['content']:
                if item['id'] == content_id and item['type'] == 'checkbox':
                    if 'data' in item and 'tasks' in item['data']:
                        if 0 <= task_index < len(item['data']['tasks']):
                            item['data']['tasks'][task_index]['completed'] = completed
                            
                            # Update XP if task completed
                            if completed:
                                xp_data = {
                                    'user_id': session.get('user_id', 'anonymous'),
                                    'xp_amount': 10,
                                    'action': 'task_completed',
                                    'timestamp': datetime.utcnow().isoformat()
                                }
                                supabase.table('user_xp').insert(xp_data).execute()
                            
                            break
            
            # Update plan
            supabase.table('plans').update({
                'content': plan['content']
            }).eq('id', plan_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error updating checklist task: {str(e)}")
            return False

class ImageManager:
    """Helper class to manage image operations with Cloudinary"""
    
    @staticmethod
    def upload_image(file):
        """Upload image to Cloudinary"""
        try:
            upload_result = cloudinary.uploader.upload(
                file,
                folder="life_dashboard",
                resource_type="auto",
                transformation=[
                    {'width': 1000, 'height': 1000, 'crop': 'limit'},
                    {'quality': 'auto'}
                ]
            )
            
            return {
                'url': upload_result['secure_url'],
                'public_id': upload_result['public_id'],
                'format': upload_result.get('format'),
                'bytes': upload_result.get('bytes'),
                'created_at': upload_result.get('created_at')
            }
        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            return None

    @staticmethod
    def upload_multiple_images(files):
        """Upload multiple images to Cloudinary"""
        results = []
        for file in files:
            if file and file.filename:
                result = ImageManager.upload_image(file)
                if result:
                    results.append(result)
        return results

    @staticmethod
    def delete_image(public_id):
        """Delete image from Cloudinary"""
        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get('result') == 'ok'
        except Exception as e:
            logger.error(f"Error deleting image {public_id}: {str(e)}")
            return False

# Routes

@app.route('/')
def index():
    """Render the main dashboard"""
    return render_template('index.html')

# Plan Routes

@app.route('/api/plans', methods=['GET'])
def get_plans():
    """Get all plans"""
    try:
        user_id = session.get('user_id', 'anonymous')
        plans = PlanManager.get_all_plans(user_id)
        return jsonify({'success': True, 'data': plans})
    except Exception as e:
        logger.error(f"Error in get_plans: {str(e)}")
        return jsonify({'success': False, 'error': str(e), 'data': []}), 200

@app.route('/api/plans', methods=['POST'])
def create_plan():
    """Create a new plan"""
    try:
        data = request.json
        plan = PlanManager.create_plan(data)
        if plan:
            return jsonify({'success': True, 'data': plan}), 201
        return jsonify({'success': False, 'error': 'Failed to create plan'}), 400
    except Exception as e:
        logger.error(f"Error in create_plan: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/plans/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    """Get a specific plan"""
    plan = PlanManager.get_plan(plan_id)
    if plan:
        return jsonify({'success': True, 'data': plan})
    return jsonify({'success': False, 'error': 'Plan not found'}), 404

@app.route('/api/plans/<plan_id>', methods=['PUT'])
def update_plan(plan_id):
    """Update a plan"""
    data = request.json
    plan = PlanManager.update_plan(plan_id, data)
    if plan:
        return jsonify({'success': True, 'data': plan})
    return jsonify({'success': False, 'error': 'Failed to update plan'}), 400

@app.route('/api/plans/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    """Delete a plan"""
    if PlanManager.delete_plan(plan_id):
        return jsonify({'success': True, 'message': 'Plan deleted'})
    return jsonify({'success': False, 'error': 'Failed to delete plan'}), 400

# Content Routes

@app.route('/api/plans/<plan_id>/content', methods=['POST'])
def add_content(plan_id):
    """Add content to a plan"""
    content_item = request.json
    result = ContentManager.add_content(plan_id, content_item)
    if result:
        return jsonify({'success': True, 'data': result}), 201
    return jsonify({'success': False, 'error': 'Failed to add content'}), 400

@app.route('/api/plans/<plan_id>/content/<content_id>', methods=['PUT'])
def update_content(plan_id, content_id):
    """Update content in a plan"""
    updated_data = request.json
    result = ContentManager.update_content(plan_id, content_id, updated_data)
    if result:
        return jsonify({'success': True, 'data': result})
    return jsonify({'success': False, 'error': 'Failed to update content'}), 400

@app.route('/api/plans/<plan_id>/content/<content_id>', methods=['DELETE'])
def delete_content(plan_id, content_id):
    """Delete content from a plan"""
    if ContentManager.delete_content(plan_id, content_id):
        return jsonify({'success': True, 'message': 'Content deleted'})
    return jsonify({'success': False, 'error': 'Failed to delete content'}), 400

@app.route('/api/plans/<plan_id>/checklist/<content_id>/task/<int:task_index>', methods=['PUT'])
def update_checklist_task(plan_id, content_id, task_index):
    """Update checklist task completion"""
    data = request.json
    completed = data.get('completed', False)
    
    if ContentManager.update_checklist_task(plan_id, content_id, task_index, completed):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to update task'}), 400

# Image Upload Routes

@app.route('/api/upload', methods=['POST'])
def upload_images():
    """Upload images to Cloudinary"""
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'success': False, 'error': 'No files selected'}), 400
    
    results = ImageManager.upload_multiple_images(files)
    
    if results:
        return jsonify({
            'success': True,
            'data': results,
            'message': f'Uploaded {len(results)} files successfully'
        })
    
    return jsonify({'success': False, 'error': 'Upload failed'}), 400

@app.route('/api/upload/single', methods=['POST'])
def upload_single_image():
    """Upload a single image"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    result = ImageManager.upload_image(file)
    
    if result:
        return jsonify({'success': True, 'data': result})
    
    return jsonify({'success': False, 'error': 'Upload failed'}), 400

@app.route('/api/delete-image/<public_id>', methods=['DELETE'])
def delete_image(public_id):
    """Delete image from Cloudinary"""
    if ImageManager.delete_image(public_id):
        return jsonify({'success': True, 'message': 'Image deleted'})
    return jsonify({'success': False, 'error': 'Failed to delete image'}), 400

# User Progress Routes

@app.route('/api/user/xp', methods=['GET'])
def get_user_xp():
    """Get user XP and level"""
    user_id = session.get('user_id', 'anonymous')
    
    try:
        # Get total XP
        xp_result = supabase.table('user_xp').select('xp_amount').eq('user_id', user_id).execute()
        total_xp = sum(item.get('xp_amount', 0) for item in xp_result.data)
        
        # Calculate level (simple formula: level = floor(xp/100) + 1)
        level = (total_xp // 100) + 1
        
        # Get achievements
        achievements_result = supabase.table('achievements').select('*').eq('user_id', user_id).execute()
        
        return jsonify({
            'success': True,
            'data': {
                'xp': total_xp,
                'level': level,
                'achievements': achievements_result.data or []
            }
        })
    except Exception as e:
        logger.error(f"Error getting user XP: {str(e)}")
        return jsonify({'success': False, 'error': str(e), 'data': {'xp': 0, 'level': 1, 'achievements': []}}), 200

# Health check
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

# Test database connection
@app.route('/api/test-db', methods=['GET'])
def test_db():
    """Test database connection"""
    try:
        result = supabase.table('plans').select('count', count='exact').execute()
        return jsonify({
            'success': True,
            'message': 'Database connected successfully',
            'count': result.count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))