import os
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
from werkzeug.utils import secure_filename
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all routes

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'pdf', 'doc', 'docx', 'txt'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'your_supabase_url')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'your_supabase_key')

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def generate_uuid():
    """Generate a UUID string"""
    return str(uuid.uuid4())

# ==================== PLAN ROUTES ====================

@app.route('/plans', methods=['GET'])
def get_plans():
    """Get all plans"""
    try:
        data = supabase.table("plans").select("*").order("created_at", desc=True).execute()
        return jsonify(data.data), 200
    except Exception as e:
        logger.error(f"Error fetching plans: {e}")
        return jsonify([]), 200  # Return empty array if table doesn't exist

@app.route('/plans', methods=['POST'])
def create_plan():
    """Create a new plan"""
    try:
        data = request.json
        new_plan = {
            "id": generate_uuid(),
            "title": data.get('title'),
            "photo": data.get('photo'),
            "created_at": datetime.now().isoformat(),
            "progress": 0,
            "content": []
        }
        
        res = supabase.table("plans").insert(new_plan).execute()
        return jsonify(res.data[0]), 201
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/plans/<plan_id>', methods=['PUT'])
def update_plan(plan_id):
    """Update a plan"""
    try:
        data = request.json
        res = supabase.table("plans").update(data).eq("id", plan_id).execute()
        return jsonify(res.data[0]), 200
    except Exception as e:
        logger.error(f"Error updating plan: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/plans/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    """Delete a plan"""
    try:
        supabase.table("plans").delete().eq("id", plan_id).execute()
        return jsonify({"message": "Plan deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error deleting plan: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== MODEL ROUTES ====================

@app.route('/models/<plan_id>', methods=['GET'])
def get_models(plan_id):
    """Get all models for a plan"""
    try:
        data = supabase.table("models").select("*").eq("plan_id", plan_id).order("created_at", desc=True).execute()
        return jsonify(data.data), 200
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return jsonify([]), 200  # Return empty array if table doesn't exist

@app.route('/models', methods=['POST'])
def create_model():
    """Create a new model (sub-plan)"""
    try:
        data = request.json
        
        # Determine level based on parent
        level = 1
        if data.get('parent_model_id'):
            # Get parent model to determine level
            parent = supabase.table("models").select("level").eq("id", data.get('parent_model_id')).execute()
            if parent.data:
                level = parent.data[0].get('level', 1) + 1
        
        new_model = {
            "id": generate_uuid(),
            "title": data.get('title'),
            "description": data.get('description'),
            "photo": data.get('photo'),
            "plan_id": data.get('plan_id'),
            "parent_model_id": data.get('parent_model_id'),
            "created_at": datetime.now().isoformat(),
            "progress": 0,
            "level": level,
            "content": []
        }
        
        res = supabase.table("models").insert(new_model).execute()
        return jsonify(res.data[0]), 201
    except Exception as e:
        logger.error(f"Error creating model: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/models/<model_id>', methods=['PUT'])
def update_model(model_id):
    """Update a model"""
    try:
        data = request.json
        res = supabase.table("models").update(data).eq("id", model_id).execute()
        return jsonify(res.data[0]), 200
    except Exception as e:
        logger.error(f"Error updating model: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/models/<model_id>', methods=['DELETE'])
def delete_model(model_id):
    """Delete a model and all its children"""
    try:
        # Delete all child models recursively (cascade should handle this if set in DB)
        supabase.table("models").delete().eq("id", model_id).execute()
        return jsonify({"message": "Model deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error deleting model: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== CHECKLIST ROUTES ====================

@app.route('/checklists', methods=['POST'])
def create_checklist():
    """Create a new checklist"""
    try:
        new_checklist = {
            "id": generate_uuid(),
            "title": request.json.get('title'),
            "model_id": request.json.get('model_id'),
            "created_at": datetime.now().isoformat()
        }
        
        res = supabase.table("checklists").insert(new_checklist).execute()
        return jsonify(res.data[0]), 201
    except Exception as e:
        logger.error(f"Error creating checklist: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/checklists/<model_id>', methods=['GET'])
def get_checklists(model_id):
    """Get all checklists for a model"""
    try:
        data = supabase.table("checklists").select("*").eq("model_id", model_id).execute()
        return jsonify(data.data), 200
    except Exception as e:
        logger.error(f"Error fetching checklists: {e}")
        return jsonify([]), 200

# ==================== TASK ROUTES ====================

@app.route('/tasks', methods=['POST'])
def create_task():
    """Create a new task"""
    try:
        data = request.json
        new_task = {
            "id": generate_uuid(),
            "checklist_id": data.get('checklist_id'),
            "text": data.get('text'),
            "completed": data.get('completed', False),
            "order": data.get('order', 0),
            "created_at": datetime.now().isoformat()
        }
        
        res = supabase.table("tasks").insert(new_task).execute()
        return jsonify(res.data[0]), 201
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/tasks/<checklist_id>', methods=['GET'])
def get_tasks(checklist_id):
    """Get all tasks for a checklist"""
    try:
        data = supabase.table("tasks").select("*").eq("checklist_id", checklist_id).order("order").execute()
        return jsonify(data.data), 200
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return jsonify([]), 200

@app.route('/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    """Update a task"""
    try:
        data = request.json
        res = supabase.table("tasks").update(data).eq("id", task_id).execute()
        return jsonify(res.data[0]), 200
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    try:
        supabase.table("tasks").delete().eq("id", task_id).execute()
        return jsonify({"message": "Task deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== UPLOAD ROUTES ====================

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload a file"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if file and allowed_file(file.filename):
            # Secure the filename and generate unique name
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{generate_uuid()}.{file_ext}"
            
            # Save file locally
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # In production, you might want to upload to cloud storage (S3, etc.)
            # For now, we'll return a local URL
            file_url = f"/uploads/{unique_filename}"
            
            # Save upload record to database
            upload_data = {
                "id": generate_uuid(),
                "filename": filename,
                "url": file_url,
                "model_id": request.form.get('model_id'),
                "plan_id": request.form.get('plan_id'),
                "created_at": datetime.now().isoformat()
            }
            
            try:
                supabase.table("uploads").insert(upload_data).execute()
            except Exception as db_error:
                logger.warning(f"Could not save upload record: {db_error}")
            
            return jsonify({
                "url": file_url,
                "filename": filename,
                "message": "File uploaded successfully"
            }), 200
        else:
            return jsonify({"error": "File type not allowed"}), 400
            
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>', methods=['GET'])
def get_upload(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==================== CONTENT ROUTES ====================

@app.route('/content/<model_id>', methods=['GET'])
def get_content(model_id):
    """Get content for a model"""
    try:
        # Get model content
        model = supabase.table("models").select("content").eq("id", model_id).execute()
        if model.data:
            return jsonify(model.data[0].get('content', [])), 200
        return jsonify([]), 200
    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        return jsonify([]), 200

@app.route('/content/<model_id>', methods=['PUT'])
def update_content(model_id):
    """Update content for a model"""
    try:
        data = request.json
        res = supabase.table("models").update({"content": data.get('content', [])}).eq("id", model_id).execute()
        return jsonify(res.data[0]), 200
    except Exception as e:
        logger.error(f"Error updating content: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== PROGRESS ROUTES ====================

@app.route('/progress/<model_id>', methods=['PUT'])
def update_progress(model_id):
    """Update progress for a model"""
    try:
        data = request.json
        progress = data.get('progress', 0)
        
        # Update model progress
        res = supabase.table("models").update({"progress": progress}).eq("id", model_id).execute()
        
        # If this model has a parent, update parent progress recursively
        if res.data and res.data[0].get('parent_model_id'):
            parent_id = res.data[0].get('parent_model_id')
            self.update_parent_progress(parent_id)
        
        return jsonify(res.data[0]), 200
    except Exception as e:
        logger.error(f"Error updating progress: {e}")
        return jsonify({"error": str(e)}), 500

def update_parent_progress(parent_id):
    """Helper function to update parent progress based on children"""
    try:
        # Get all children
        children = supabase.table("models").select("progress").eq("parent_model_id", parent_id).execute()
        
        if children.data:
            # Calculate average progress
            total_progress = sum(child.get('progress', 0) for child in children.data)
            avg_progress = total_progress // len(children.data) if children.data else 0
            
            # Update parent
            supabase.table("models").update({"progress": avg_progress}).eq("id", parent_id).execute()
            
            # Recursively update grandparent
            parent = supabase.table("models").select("parent_model_id").eq("id", parent_id).execute()
            if parent.data and parent.data[0].get('parent_model_id'):
                self.update_parent_progress(parent.data[0].get('parent_model_id'))
                
    except Exception as e:
        logger.error(f"Error updating parent progress: {e}")

# ==================== HEALTH CHECK ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
