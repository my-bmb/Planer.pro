from flask import Flask, request, jsonify, render_template
from supabase import create_client
from dotenv import load_dotenv
import cloudinary.uploader
import os

load_dotenv()

app = Flask(__name__)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- PLANS ----------------

@app.route("/plans", methods=["GET"])
def get_plans():
    data = supabase.table("plans").select("*").execute()
    return jsonify(data.data)

@app.route("/plans", methods=["POST"])
def create_plan():
    data = request.json
    res = supabase.table("plans").insert(data).execute()
    return jsonify(res.data)


# ---------------- MODELS ----------------

@app.route("/models/<plan_id>")
def get_models(plan_id):
    data = supabase.table("models").select("*").eq("plan_id", plan_id).execute()
    return jsonify(data.data)

@app.route("/models", methods=["POST"])
def create_model():
    data = request.json
    res = supabase.table("models").insert(data).execute()
    return jsonify(res.data)


# ---------------- CHECKLIST ----------------

@app.route("/checklists", methods=["POST"])
def create_checklist():
    data = request.json
    res = supabase.table("checklists").insert(data).execute()
    return jsonify(res.data)


# ---------------- TASKS ----------------

@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.json
    res = supabase.table("tasks").insert(data).execute()
    return jsonify(res.data)


# ---------------- IMAGE UPLOAD ----------------

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    result = cloudinary.uploader.upload(file)
    return jsonify({"url": result["secure_url"]})


if __name__ == "__main__":
    app.run(debug=True)
