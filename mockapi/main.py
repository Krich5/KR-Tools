from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json, shutil

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kenleyr.com",
        "https://api.kenleyr.com",
        "https://automation.cxsol.com",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJ_DIR = DATA_DIR / "_proj"
PROJ_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ──────────────────────────────────────────────────────────────────

def resource_file(name: str) -> Path:
    return DATA_DIR / f"{name}.json"

def project_dir(name: str) -> Path:
    return PROJ_DIR / name

def proj_resource_file(project: str, resource: str) -> Path:
    return PROJ_DIR / project / f"{resource}.json"

def is_project(name: str) -> bool:
    return (PROJ_DIR / name).is_dir()

def valid_name(name: str) -> bool:
    return bool(name) and name.replace("-", "").replace("_", "").isalnum()

def list_resources() -> list[dict]:
    return [
        {"name": f.stem, "count": len(json.loads(f.read_text()))}
        for f in sorted(DATA_DIR.glob("*.json"))
    ]

def load_resource(name: str) -> list:
    f = resource_file(name)
    if not f.exists():
        raise HTTPException(404, f"Resource '{name}' not found")
    return json.loads(f.read_text())

def save_resource(name: str, records: list):
    resource_file(name).write_text(json.dumps(records, indent=2))

def load_proj_resource(project: str, resource: str) -> list:
    f = proj_resource_file(project, resource)
    if not f.exists():
        raise HTTPException(404, f"Resource '{resource}' not found")
    return json.loads(f.read_text())

# ── Static + UI ──────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    return HTMLResponse(HTML)

# ── Flat resources ───────────────────────────────────────────────────────────

@app.get("/_api/resources")
async def api_list_resources():
    return list_resources()

@app.post("/_api/resources")
async def api_create_resource(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not valid_name(name):
        raise HTTPException(400, "Invalid resource name")
    if resource_file(name).exists():
        raise HTTPException(409, "Resource already exists")
    save_resource(name, [])
    return {"name": name, "count": 0}

@app.patch("/_api/resources/{name}")
async def api_rename_resource(name: str, request: Request):
    body = await request.json()
    new_name = body.get("name", "").strip()
    if not valid_name(new_name):
        raise HTTPException(400, "Invalid resource name")
    old_file = resource_file(name)
    if not old_file.exists():
        raise HTTPException(404, "Resource not found")
    if resource_file(new_name).exists():
        raise HTTPException(409, "Name already taken")
    old_file.rename(resource_file(new_name))
    return {"name": new_name}

@app.delete("/_api/resources/{name}")
async def api_delete_resource(name: str):
    f = resource_file(name)
    if not f.exists():
        raise HTTPException(404, "Resource not found")
    f.unlink()
    return {"status": "deleted"}

@app.get("/_api/data/{resource}")
async def api_get_data(resource: str):
    f = resource_file(resource)
    return json.loads(f.read_text()) if f.exists() else []

@app.put("/_api/data/{resource}")
async def api_replace_data(resource: str, request: Request):
    f = resource_file(resource)
    if not f.exists():
        raise HTTPException(404, "Resource not found")
    records = await request.json()
    if not isinstance(records, list):
        raise HTTPException(400, "Body must be a JSON array")
    save_resource(resource, records)
    return {"count": len(records)}

# ── Projects ─────────────────────────────────────────────────────────────────

@app.get("/_api/projects")
async def api_list_projects():
    return [
        {"name": d.name, "resourceCount": len(list(d.glob("*.json")))}
        for d in sorted(PROJ_DIR.iterdir()) if d.is_dir()
    ]

@app.post("/_api/projects")
async def api_create_project(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not valid_name(name):
        raise HTTPException(400, "Invalid project name")
    d = project_dir(name)
    if d.exists():
        raise HTTPException(409, "Project already exists")
    d.mkdir(parents=True)
    return {"name": name, "resourceCount": 0}

@app.patch("/_api/projects/{project}")
async def api_rename_project(project: str, request: Request):
    body = await request.json()
    new_name = body.get("name", "").strip()
    if not valid_name(new_name):
        raise HTTPException(400, "Invalid project name")
    old_dir = project_dir(project)
    if not old_dir.exists():
        raise HTTPException(404, "Project not found")
    if project_dir(new_name).exists():
        raise HTTPException(409, "Name already taken")
    old_dir.rename(project_dir(new_name))
    return {"name": new_name}

@app.delete("/_api/projects/{project}")
async def api_delete_project(project: str):
    d = project_dir(project)
    if not d.exists():
        raise HTTPException(404, "Project not found")
    shutil.rmtree(d)
    return {"status": "deleted"}

@app.get("/_api/projects/{project}/resources")
async def api_list_proj_resources(project: str):
    d = project_dir(project)
    if not d.exists():
        raise HTTPException(404, "Project not found")
    return [
        {"name": f.stem, "count": len(json.loads(f.read_text()))}
        for f in sorted(d.glob("*.json"))
    ]

@app.post("/_api/projects/{project}/resources")
async def api_create_proj_resource(project: str, request: Request):
    d = project_dir(project)
    if not d.exists():
        raise HTTPException(404, "Project not found")
    body = await request.json()
    name = body.get("name", "").strip()
    if not valid_name(name):
        raise HTTPException(400, "Invalid resource name")
    f = d / f"{name}.json"
    if f.exists():
        raise HTTPException(409, "Resource already exists")
    f.write_text("[]")
    return {"name": name, "count": 0}

@app.patch("/_api/projects/{project}/resources/{name}")
async def api_rename_proj_resource(project: str, name: str, request: Request):
    body = await request.json()
    new_name = body.get("name", "").strip()
    if not valid_name(new_name):
        raise HTTPException(400, "Invalid resource name")
    old_file = proj_resource_file(project, name)
    if not old_file.exists():
        raise HTTPException(404, "Resource not found")
    if proj_resource_file(project, new_name).exists():
        raise HTTPException(409, "Name already taken")
    old_file.rename(proj_resource_file(project, new_name))
    return {"name": new_name}

@app.delete("/_api/projects/{project}/resources/{name}")
async def api_delete_proj_resource(project: str, name: str):
    f = proj_resource_file(project, name)
    if not f.exists():
        raise HTTPException(404, "Resource not found")
    f.unlink()
    return {"status": "deleted"}

@app.get("/_api/projects/{project}/data/{resource}")
async def api_get_proj_data(project: str, resource: str):
    f = proj_resource_file(project, resource)
    return json.loads(f.read_text()) if f.exists() else []

@app.put("/_api/projects/{project}/data/{resource}")
async def api_replace_proj_data(project: str, resource: str, request: Request):
    f = proj_resource_file(project, resource)
    if not f.exists():
        raise HTTPException(404, "Resource not found")
    records = await request.json()
    if not isinstance(records, list):
        raise HTTPException(400, "Body must be a JSON array")
    f.write_text(json.dumps(records, indent=2))
    return {"count": len(records)}

# ── REST CRUD (flat, 1-segment) ──────────────────────────────────────────────

@app.get("/{resource}")
async def list_records(resource: str, request: Request):
    if resource.startswith("_") or "." in resource:
        raise HTTPException(404)
    records = load_resource(resource)
    filters = dict(request.query_params)
    if filters:
        records = [r for r in records if all(str(r.get(k)) == v for k, v in filters.items())]
    return records

@app.post("/{resource}")
async def create_record(resource: str, request: Request):
    if resource.startswith("_"):
        raise HTTPException(404)
    f = resource_file(resource)
    if not f.exists():
        save_resource(resource, [])
    records = load_resource(resource)
    raw = await request.body()
    try:
        body = json.loads(raw)
        if not isinstance(body, dict):
            body = {"value": body}
    except (json.JSONDecodeError, ValueError):
        body = {"raw": raw.decode("utf-8", errors="replace")}
    body["id"] = str(len(records) + 1)
    records.append(body)
    save_resource(resource, records)
    return body

# ── REST CRUD (2-segment: /{project}/{resource} OR /{resource}/{id}) ─────────
# Disambiguated at runtime: if seg1 is a known project dir → project route

@app.get("/{seg1}/{seg2}")
async def two_seg_get(seg1: str, seg2: str, request: Request):
    if seg1.startswith("_") or "." in seg1:
        raise HTTPException(404)
    if is_project(seg1):
        f = proj_resource_file(seg1, seg2)
        if not f.exists():
            raise HTTPException(404, f"Resource '{seg2}' not found in project '{seg1}'")
        records = json.loads(f.read_text())
        filters = dict(request.query_params)
        if filters:
            records = [r for r in records if all(str(r.get(k)) == v for k, v in filters.items())]
        return records
    records = load_resource(seg1)
    for r in records:
        if str(r.get("id")) == seg2:
            return r
    raise HTTPException(404, "Record not found")

@app.post("/{seg1}/{seg2}")
async def two_seg_post(seg1: str, seg2: str, request: Request):
    if seg1.startswith("_"):
        raise HTTPException(404)
    # Auto-create the folder and resource if they don't exist
    d = project_dir(seg1)
    if not d.exists():
        d.mkdir(parents=True)
    f = proj_resource_file(seg1, seg2)
    if not f.exists():
        f.write_text("[]")
    records = json.loads(f.read_text())
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {"value": body}
    except Exception:
        raw = await request.body()
        body = {"raw": raw.decode("utf-8", errors="replace")}
    body["id"] = str(len(records) + 1)
    records.append(body)
    f.write_text(json.dumps(records, indent=2))
    return body

@app.put("/{seg1}/{seg2}")
async def two_seg_put(seg1: str, seg2: str, request: Request):
    if seg1.startswith("_") or is_project(seg1):
        raise HTTPException(404)
    records = load_resource(seg1)
    body = await request.json()
    for i, r in enumerate(records):
        if str(r.get("id")) == seg2:
            body["id"] = seg2
            records[i] = body
            save_resource(seg1, records)
            return body
    raise HTTPException(404, "Record not found")

@app.delete("/{seg1}/{seg2}")
async def two_seg_delete(seg1: str, seg2: str):
    if seg1.startswith("_") or is_project(seg1):
        raise HTTPException(404)
    records = load_resource(seg1)
    new_records = [r for r in records if str(r.get("id")) != seg2]
    if len(new_records) == len(records):
        raise HTTPException(404, "Record not found")
    save_resource(seg1, new_records)
    return {"status": "deleted"}

# ── REST CRUD (3-segment: /{project}/{resource}/{id}) ────────────────────────

@app.get("/{project}/{resource}/{record_id}")
async def get_proj_record(project: str, resource: str, record_id: str):
    if not is_project(project):
        raise HTTPException(404)
    records = load_proj_resource(project, resource)
    for r in records:
        if str(r.get("id")) == record_id:
            return r
    raise HTTPException(404, "Record not found")

@app.put("/{project}/{resource}/{record_id}")
async def update_proj_record(project: str, resource: str, record_id: str, request: Request):
    if not is_project(project):
        raise HTTPException(404)
    f = proj_resource_file(project, resource)
    if not f.exists():
        raise HTTPException(404)
    records = json.loads(f.read_text())
    body = await request.json()
    for i, r in enumerate(records):
        if str(r.get("id")) == record_id:
            body["id"] = record_id
            records[i] = body
            f.write_text(json.dumps(records, indent=2))
            return body
    raise HTTPException(404, "Record not found")

@app.delete("/{project}/{resource}/{record_id}")
async def delete_proj_record(project: str, resource: str, record_id: str):
    if not is_project(project):
        raise HTTPException(404)
    f = proj_resource_file(project, resource)
    if not f.exists():
        raise HTTPException(404)
    records = json.loads(f.read_text())
    new_records = [r for r in records if str(r.get("id")) != record_id]
    if len(new_records) == len(records):
        raise HTTPException(404, "Record not found")
    f.write_text(json.dumps(new_records, indent=2))
    return {"status": "deleted"}

# ── UI ───────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Mock API — kenleyr.com</title>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#07101C">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/one-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      display: flex; height: 100vh;
      background: url('/static/gradient-background-dark.svg') center/cover no-repeat fixed #07101C;
      color: #e2e8f0;
    }
    #sidebar {
      width: 260px; flex-shrink: 0; display: flex; flex-direction: column;
      background: transparent; border-right: 1px solid rgba(255,255,255,0.08);
    }
    #sidebar-header {
      padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.06);
      display: flex; align-items: center; gap: 6px; min-height: 52px;
    }
    #back-btn {
      display: none; background: none; border: none; color: rgba(255,255,255,0.4);
      cursor: pointer; font-size: 13px; padding: 4px 6px 4px 0; flex-shrink: 0;
    }
    #back-btn:hover { color: #fff; }
    #sidebar-title {
      font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
      color: rgba(255,255,255,0.35); flex: 1; min-width: 0; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap;
    }
    #sidebar-actions { display: flex; gap: 5px; align-items: center; flex-shrink: 0; }
    #delete-selected-res-btn {
      display: none; background: rgba(248,113,113,0.15); border: 1px solid rgba(248,113,113,0.3);
      color: #f87171; padding: 4px 8px; border-radius: 6px; cursor: pointer; font-size: 11px; font-weight: 600;
    }
    #delete-selected-res-btn:hover { background: rgba(248,113,113,0.25); }
    #new-project-btn {
      background: rgba(96,165,250,0.15); border: 1px solid rgba(96,165,250,0.3);
      color: #60a5fa; padding: 4px 8px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600;
    }
    #new-project-btn:hover { background: rgba(96,165,250,0.25); }
    #new-resource-btn {
      background: rgba(74,222,128,0.15); border: 1px solid rgba(74,222,128,0.3);
      color: #4ade80; padding: 4px 8px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600;
    }
    #new-resource-btn:hover { background: rgba(74,222,128,0.25); }
    #resources { flex: 1; overflow-y: auto; }
    .section-label {
      padding: 10px 16px 5px; font-size: 10px; font-weight: 700; letter-spacing: 1.2px;
      text-transform: uppercase; color: rgba(255,255,255,0.2);
    }
    .section-divider { border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 6px 0 2px; }
    .project-item {
      padding: 10px 16px; cursor: pointer; display: flex; align-items: center; gap: 8px;
      border-bottom: 1px solid rgba(255,255,255,0.04); transition: background 0.15s;
    }
    .project-item:hover { background: rgba(255,255,255,0.06); }
    .project-icon { font-size: 13px; flex-shrink: 0; }
    .resource-item {
      padding: 10px 16px; cursor: pointer; display: flex; align-items: center; gap: 8px;
      border-bottom: 1px solid rgba(255,255,255,0.04); transition: background 0.15s;
    }
    .resource-item:hover { background: rgba(255,255,255,0.06); }
    .resource-item.active { background: rgba(96,165,250,0.08); border-left: 3px solid #60a5fa; padding-left: 13px; }
    .item-name { color: #e2e8f0; font-family: monospace; font-size: 13px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .badge { background: #60a5fa; color: #000; border-radius: 10px; padding: 2px 7px; font-size: 11px; font-weight: 700; flex-shrink: 0; }
    .proj-badge { background: rgba(96,165,250,0.15); color: #60a5fa; border: 1px solid rgba(96,165,250,0.25); border-radius: 10px; padding: 2px 7px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
    .item-actions { display: flex; gap: 2px; flex-shrink: 0; opacity: 0; transition: opacity 0.15s; }
    .project-item:hover .item-actions, .resource-item:hover .item-actions { opacity: 1; }
    .res-btn { background: none; border: none; color: rgba(255,255,255,0.3); cursor: pointer; font-size: 12px; padding: 2px 5px; border-radius: 4px; }
    .res-btn:hover { color: #fff; background: rgba(255,255,255,0.08); }
    .res-btn.del:hover { color: #f87171; background: rgba(248,113,113,0.1); }
    .res-check { accent-color: #60a5fa; width: 14px; height: 14px; cursor: pointer; flex-shrink: 0; }
    #empty-sidebar { padding: 20px 16px; color: rgba(255,255,255,0.3); font-size: 13px; line-height: 1.9; }
    .copy-block-btn {
      position: absolute; top: 10px; right: 10px;
      background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.14);
      color: rgba(255,255,255,0.5); border-radius: 7px; padding: 5px 12px;
      font-size: 12px; font-weight: 600; font-family: inherit;
      cursor: pointer; display: flex; align-items: center; gap: 6px;
      transition: all 0.15s; -webkit-tap-highlight-color: transparent;
    }
    .copy-block-btn:hover { background: rgba(255,255,255,0.13); color: #fff; }
    .copy-block-btn.ok { background: rgba(74,222,128,0.12); border-color: rgba(74,222,128,0.4); color: #4ade80; }
    #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    #header {
      padding: 14px 24px; display: flex; align-items: center; gap: 10px;
      background: transparent; border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    #header h2 { font-size: 15px; font-weight: 600; color: #fff; }
    .url-label { font-family: monospace; font-size: 12px; color: rgba(255,255,255,0.35); cursor: pointer; }
    .url-label:hover { color: rgba(255,255,255,0.7); }
    .url-copied { color: #4ade80 !important; transition: color 0.15s; }
    .header-btns { margin-left: auto; display: flex; gap: 8px; align-items: center; }
    #view-data-btn {
      background: rgba(192,132,252,0.15); border: 1px solid rgba(192,132,252,0.3);
      color: #c084fc; padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; display: none;
    }
    #view-data-btn:hover { background: rgba(192,132,252,0.25); }
    .view-toggle {
      display: none; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
      border-radius: 8px; overflow: hidden;
    }
    .view-toggle button {
      background: none; border: none; color: rgba(255,255,255,0.4);
      padding: 5px 12px; cursor: pointer; font-size: 12px; font-weight: 600;
    }
    .view-toggle button.active { background: rgba(255,255,255,0.12); color: #fff; }
    #content { flex: 1; overflow-y: auto; padding: 20px 24px; }
    #no-selection { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: rgba(255,255,255,0.25); gap: 8px; }
    #no-selection .hint { font-size: 12px; font-family: monospace; color: rgba(255,255,255,0.2); }
    .table-wrap { background: rgba(255,255,255,0.04); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; overflow: hidden; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    thead { background: rgba(255,255,255,0.05); }
    th { padding: 10px 14px; text-align: left; font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 0.8px; border-bottom: 1px solid rgba(255,255,255,0.07); }
    td { padding: 11px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #e2e8f0; vertical-align: top; word-break: break-word; overflow-wrap: anywhere; white-space: normal; font-size: 13px; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(255,255,255,0.03); }
    .del-record-btn { background: none; border: none; color: rgba(255,255,255,0.2); cursor: pointer; font-size: 13px; }
    .del-record-btn:hover { color: #f87171; }
    .no-records { padding: 40px; text-align: center; color: rgba(255,255,255,0.25); font-size: 14px; }
    .endpoint-bar {
      margin-bottom: 16px; padding: 10px 14px;
      background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
      border-radius: 8px; font-family: monospace; font-size: 12px;
      color: rgba(255,255,255,0.4); display: flex; align-items: center; gap: 10px;
    }
    .endpoint-bar span { color: #60a5fa; cursor: pointer; }
    .endpoint-bar span:hover { color: #93c5fd; }
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 100; display: none; align-items: center; justify-content: center; }
    .modal { background: #0f1a2e; border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 32px; width: 620px; max-width: 95vw; }
    .modal h3 { font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 16px; }
    .modal label { font-size: 12px; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 6px; }
    .modal input, .modal textarea {
      width: 100%; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px; padding: 10px 12px; color: #e2e8f0; font-size: 14px; font-family: monospace;
      outline: none; resize: vertical;
    }
    .modal input:focus, .modal textarea:focus { border-color: rgba(96,165,250,0.5); }
    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
    .btn-cancel { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.1); color: rgba(255,255,255,0.5); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; }
    .btn-confirm { background: rgba(96,165,250,0.2); border: 1px solid rgba(96,165,250,0.4); color: #60a5fa; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }
    .btn-confirm:hover { background: rgba(96,165,250,0.3); }
    .form-group { margin-bottom: 14px; }

    /* ── Mobile: sliding sidebar → main ── */
    #mob-back { display: none; }
    @media (max-width: 768px) {
      body { position: relative; height: 100dvh; overflow: hidden; }
      #sidebar, #main {
        position: absolute; inset: 0; width: 100% !important;
        transition: transform 0.28s cubic-bezier(0.4,0,0.2,1);
      }
      #sidebar { transform: translateX(0); z-index: 2; }
      #main    { transform: translateX(100%); z-index: 1; display: flex; flex-direction: column; height: 100%; }
      body[data-mob="main"] #sidebar { transform: translateX(-100%); }
      body[data-mob="main"] #main    { transform: translateX(0); }
      #mob-back {
        display: flex; align-items: center; gap: 6px;
        background: none; border: none; border-bottom: 1px solid rgba(255,255,255,0.06);
        color: #60a5fa; font-size: 14px; font-weight: 600;
        padding: 10px 14px; width: 100%; cursor: pointer; flex-shrink: 0;
        -webkit-tap-highlight-color: transparent;
      }
      #mob-back svg { width: 16px; height: 16px; flex-shrink: 0; }
      #mob-back.hidden { display: none; }
      #header { padding: 10px 14px; }
      #header-url, #col-toggle-btn { display: none !important; }
      .view-toggle button { font-size: 12px; padding: 4px 10px; }
      #view-data-btn { font-size: 12px; padding: 5px 10px; }
    }
  </style>
</head>
<body>
  <div id="sidebar">
    <div id="sidebar-header">
      <button id="back-btn" onclick="exitProject()">← Back</button>
      <span id="sidebar-title">Workspace</span>
      <div id="sidebar-actions">
        <button id="delete-selected-res-btn" onclick="deleteSelectedResources()">Delete</button>
        <button id="new-project-btn" onclick="openNewProject()">+ Folder</button>
        <button id="new-resource-btn" onclick="openNewResource()">+ New</button>
      </div>
    </div>
    <div id="resources"></div>
  </div>

  <div id="main">
    <button id="mob-back" class="hidden" onclick="mobBack()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M15 18l-6-6 6-6"/></svg>
      <span id="mob-back-label">Resources</span>
    </button>
    <div id="header">
      <h2 id="header-title">Mock API</h2>
      <span id="header-url" class="url-label" onclick="copyUrl(this,'https://'+this.textContent.trim())" title="Click to copy">api.kenleyr.com</span>
      <div class="header-btns">
        <div class="view-toggle" id="view-toggle">
          <button id="btn-table" class="active" onclick="setView('table')">Table</button>
          <button id="btn-raw" onclick="setView('raw')">Raw</button>
        </div>
        <div style="position:relative">
          <button id="col-toggle-btn" onclick="toggleColDropdown()" style="display:none;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);color:rgba(255,255,255,0.5);padding:5px 12px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500">Columns ▾</button>
          <div id="col-dropdown" style="position:absolute;top:38px;right:0;display:none;background:#0f1a2e;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:8px;min-width:160px;z-index:50;max-height:300px;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,0.5)"></div>
        </div>
        <button id="view-data-btn" onclick="openViewData()">{ } Edit Data</button>
      </div>
    </div>
    <div id="content">
      <div id="no-selection">
        <span>Select a resource from the sidebar</span>
        <span class="hint">or create a new one to get started</span>
      </div>
    </div>
  </div>

  <!-- New Resource Modal -->
  <div class="modal-backdrop" id="modal-resource">
    <div class="modal">
      <h3 id="modal-resource-title">New Resource</h3>
      <div class="form-group">
        <label>Resource Name</label>
        <input id="resource-name-input" type="text" placeholder="e.g. Users, CallLogs, FeatureRequest" onkeydown="if(event.key==='Enter') confirmNewResource()">
      </div>
      <div class="modal-actions">
        <button class="btn-cancel" onclick="closeModal('modal-resource')">Cancel</button>
        <button class="btn-confirm" onclick="confirmNewResource()">Create</button>
      </div>
    </div>
  </div>

  <!-- New Project Modal -->
  <div class="modal-backdrop" id="modal-project">
    <div class="modal">
      <h3>New Folder</h3>
      <div class="form-group">
        <label>Folder Name</label>
        <input id="project-name-input" type="text" placeholder="e.g. HealthcareDemo, Dev_Kenley" onkeydown="if(event.key==='Enter') confirmNewProject()">
      </div>
      <div class="modal-actions">
        <button class="btn-cancel" onclick="closeModal('modal-project')">Cancel</button>
        <button class="btn-confirm" onclick="confirmNewProject()">Create</button>
      </div>
    </div>
  </div>

  <!-- Rename Modal (shared) -->
  <div class="modal-backdrop" id="modal-rename">
    <div class="modal">
      <h3 id="modal-rename-title">Rename</h3>
      <div class="form-group">
        <label>New Name</label>
        <input id="rename-input" type="text" onkeydown="if(event.key==='Enter') confirmRename()">
      </div>
      <div class="modal-actions">
        <button class="btn-cancel" onclick="closeModal('modal-rename')">Cancel</button>
        <button class="btn-confirm" onclick="confirmRename()">Rename</button>
      </div>
    </div>
  </div>

  <!-- View/Edit All Data Modal -->
  <div class="modal-backdrop" id="modal-data">
    <div class="modal" style="width:720px">
      <h3 id="modal-data-title">Resource Data</h3>
      <p style="font-size:12px;color:rgba(255,255,255,0.35);margin:6px 0 14px">Edit the full JSON array and click Update to save.</p>
      <div id="data-body-editor" style="border:1px solid rgba(255,255,255,0.1);border-radius:8px;overflow:hidden;font-size:13px;max-height:420px"></div>
      <div class="modal-actions">
        <button class="btn-cancel" onclick="closeModal('modal-data')">Close</button>
        <button class="btn-confirm" onclick="saveAllData()" style="background:rgba(192,132,252,0.2);border-color:rgba(192,132,252,0.4);color:#c084fc">Update</button>
      </div>
    </div>
  </div>

  <!-- View Record Modal -->
  <div class="modal-backdrop" id="modal-view">
    <div class="modal">
      <h3 id="modal-view-title">Record</h3>
      <pre id="modal-view-body" style="max-height:400px;overflow-y:auto;margin-top:4px;font-size:12px;color:#e2e8f0"></pre>
      <div class="modal-actions">
        <button class="btn-confirm" onclick="closeModal('modal-view')">Close</button>
      </div>
    </div>
  </div>

  <!-- Confirm Delete Modal -->
  <div class="modal-backdrop" id="modal-confirm">
    <div class="modal" style="width:420px">
      <h3 id="modal-confirm-title" style="color:#f87171">Confirm Delete</h3>
      <p id="modal-confirm-msg" style="margin-top:8px;font-size:14px;color:rgba(255,255,255,0.6);line-height:1.6"></p>
      <div class="modal-actions" style="margin-top:24px">
        <button class="btn-cancel" id="modal-confirm-cancel">Cancel</button>
        <button id="modal-confirm-ok" style="background:rgba(248,113,113,0.2);border:1px solid rgba(248,113,113,0.4);color:#f87171;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600">Delete</button>
      </div>
    </div>
  </div>

  <!-- Add Record Modal -->
  <div class="modal-backdrop" id="modal-record">
    <div class="modal">
      <h3>Add Record</h3>
      <div class="form-group">
        <label>JSON Body</label>
        <textarea id="record-body-input" rows="14" placeholder='{"name": "value"}'></textarea>
      </div>
      <div class="modal-actions">
        <button class="btn-cancel" onclick="closeModal('modal-record')">Cancel</button>
        <button class="btn-confirm" onclick="confirmAddRecord()">Save</button>
      </div>
    </div>
  </div>

  <script>
    const COPY_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
    function copyBlock(btn) {
      const text = document.getElementById('raw-pre')?.textContent || '';
      navigator.clipboard.writeText(text).catch(() => {});
      btn.innerHTML = COPY_SVG + ' Copied!';
      btn.classList.add('ok');
      setTimeout(() => { btn.innerHTML = COPY_SVG + ' Copy'; btn.classList.remove('ok'); }, 1800);
    }

    const BASE = 'https://api.kenleyr.com';
    let selectedResource = null;
    let currentProject = null;
    let allColumns = [];
    let hiddenColumns = new Set();
    let checkedResources = new Set();
    let viewMode = 'table';
    let renamingResource = null;
    let renamingProject = null;

    // ── View ──────────────────────────────────────────────────────────────────

    function setView(mode) {
      viewMode = mode;
      document.getElementById('btn-table').classList.toggle('active', mode === 'table');
      document.getElementById('btn-raw').classList.toggle('active', mode === 'raw');
      document.getElementById('col-toggle-btn').style.display = (mode === 'table' && selectedResource) ? 'block' : 'none';
      if (mode !== 'table') document.getElementById('col-dropdown').style.display = 'none';
      loadRecords();
    }

    // ── Sidebar ───────────────────────────────────────────────────────────────

    async function loadSidebar() {
      if (currentProject) {
        await loadProjectSidebar();
      } else {
        await loadRootSidebar();
      }
    }

    async function loadRootSidebar() {
      document.getElementById('back-btn').style.display = 'none';
      document.getElementById('sidebar-title').textContent = 'Workspace';
      document.getElementById('new-project-btn').style.display = '';

      const [projects, resources] = await Promise.all([
        fetch(`${BASE}/_api/projects`).then(r => r.json()),
        fetch(`${BASE}/_api/resources`).then(r => r.json()),
      ]);

      let html = '';

      if (projects.length) {
        html += '<div class="section-label">Folders</div>';
        html += projects.map(p => `
          <div class="project-item" onclick="enterProject('${esc(p.name)}')">
            <span class="project-icon">📁</span>
            <span class="item-name">${p.name}</span>
            <span class="proj-badge">${p.resourceCount}</span>
            <div class="item-actions">
              <button class="res-btn" onclick="event.stopPropagation();openRenameProject('${esc(p.name)}')" title="Rename">✎</button>
              <button class="res-btn del" onclick="event.stopPropagation();deleteProject('${esc(p.name)}')" title="Delete">✕</button>
            </div>
          </div>`).join('');
      }

      if (resources.length) {
        if (projects.length) html += '<hr class="section-divider">';
        html += '<div class="section-label">Resources</div>';
        html += resources.map(r => `
          <div class="resource-item ${r.name === selectedResource && !currentProject ? 'active' : ''}" onclick="selectResource('${esc(r.name)}')">
            <input type="checkbox" class="res-check" ${checkedResources.has(r.name) ? 'checked' : ''} onclick="event.stopPropagation();toggleCheckResource('${esc(r.name)}',this.checked)">
            <span class="badge">${r.count}</span>
            <span class="item-name">${r.name}</span>
            <div class="item-actions">
              <button class="res-btn" onclick="event.stopPropagation();openRename('${esc(r.name)}')" title="Rename">✎</button>
              <button class="res-btn del" onclick="event.stopPropagation();deleteResource('${esc(r.name)}')" title="Delete">✕</button>
            </div>
          </div>`).join('');
      }

      if (!projects.length && !resources.length) {
        html = '<div id="empty-sidebar">Nothing here yet.<br>Click <strong style="color:#4ade80">+ New</strong> for a resource<br>or <strong style="color:#60a5fa">+ Folder</strong> to group them.</div>';
      }

      document.getElementById('resources').innerHTML = html;
      updateDeleteBtn();
    }

    async function loadProjectSidebar() {
      document.getElementById('back-btn').style.display = 'inline';
      document.getElementById('sidebar-title').textContent = currentProject;
      document.getElementById('new-project-btn').style.display = 'none';

      const resources = await fetch(`${BASE}/_api/projects/${currentProject}/resources`).then(r => r.json());

      if (!resources.length) {
        document.getElementById('resources').innerHTML = '<div id="empty-sidebar">No resources yet.<br>Click <strong style="color:#4ade80">+ New</strong> to add one.</div>';
        return;
      }

      document.getElementById('resources').innerHTML = resources.map(r => `
        <div class="resource-item ${r.name === selectedResource ? 'active' : ''}" onclick="selectResource('${esc(r.name)}')">
          <span class="badge">${r.count}</span>
          <span class="item-name">${r.name}</span>
          <div class="item-actions">
            <button class="res-btn" onclick="event.stopPropagation();openRenameProjResource('${esc(r.name)}')" title="Rename">✎</button>
            <button class="res-btn del" onclick="event.stopPropagation();deleteProjResource('${esc(r.name)}')" title="Delete">✕</button>
          </div>
        </div>`).join('');
    }

    function enterProject(name) {
      currentProject = name;
      selectedResource = null;
      resetMain(`api.kenleyr.com/${name}`);
      loadSidebar();
    }

    function exitProject() {
      currentProject = null;
      selectedResource = null;
      resetMain('api.kenleyr.com');
      loadSidebar();
    }

    function resetMain(urlLabel) {
      document.getElementById('header-title').textContent = 'Mock API';
      document.getElementById('header-url').textContent = urlLabel;
      document.getElementById('view-data-btn').style.display = 'none';
      document.getElementById('view-toggle').style.display = 'none';
      document.getElementById('col-toggle-btn').style.display = 'none';
      document.getElementById('content').innerHTML = '<div id="no-selection"><span>Select a resource from the sidebar</span><span class="hint">or create a new one to get started</span></div>';
    }

    // ── Records ───────────────────────────────────────────────────────────────

    async function loadRecords() {
      if (!selectedResource) return;
      const url = currentProject
        ? `${BASE}/_api/projects/${currentProject}/data/${selectedResource}`
        : `${BASE}/_api/data/${selectedResource}`;
      const records = await fetch(url).then(r => r.json());
      const content = document.getElementById('content');
      const noSel = document.getElementById('no-selection');
      if (noSel) noSel.style.display = 'none';

      const path = currentProject ? `${currentProject}/${selectedResource}` : selectedResource;
      const fullUrl = `https://api.kenleyr.com/${path}`;
      const bar = `<div class="endpoint-bar">GET &nbsp;<span onclick="copyUrl(this,'${fullUrl}')" title="Click to copy">api.kenleyr.com/${path}</span></div>`;

      if (!records.length) {
        content.innerHTML = `${bar}<div class="table-wrap"><div class="no-records">No records yet. Use { } Edit Data to add entries.</div></div>`;
        return;
      }

      if (viewMode === 'raw') {
        content.innerHTML = `${bar}<div style="position:relative;margin:0 24px 24px">
          <button class="copy-block-btn" onclick="copyBlock(this)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            Copy
          </button>
          <pre id="raw-pre" style="background:rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px;font-size:12px;overflow:auto;max-height:calc(100vh - 160px)">${JSON.stringify(records, null, 2)}</pre>
        </div>`;
        return;
      }

      allColumns = [...new Set(records.flatMap(r => Object.keys(r)))];
      for (const c of hiddenColumns) { if (!allColumns.includes(c)) hiddenColumns.delete(c); }
      buildColDropdown();
      const vis = allColumns.filter(c => !hiddenColumns.has(c));
      const rows = records.map(r => `
        <tr onclick="viewRecord(${JSON.stringify(JSON.stringify(r))})" style="cursor:pointer">
          ${vis.map(c => `<td>${r[c] !== undefined ? (typeof r[c] === 'object' ? JSON.stringify(r[c]) : r[c]) : ''}</td>`).join('')}
          <td><button class="del-record-btn" onclick="event.stopPropagation();deleteRecord('${r.id}')">✕</button></td>
        </tr>`).join('');

      content.innerHTML = `${bar}<div class="table-wrap"><table>
        <thead><tr>${vis.map(c => `<th>${c}</th>`).join('')}<th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>`;
    }

    async function selectResource(name) {
      selectedResource = name;
      hiddenColumns = new Set();
      const path = currentProject ? `${currentProject}/${name}` : name;
      document.getElementById('header-title').textContent = name;
      document.getElementById('header-url').textContent = `api.kenleyr.com/${path}`;
      document.getElementById('view-data-btn').style.display = 'block';
      document.getElementById('view-toggle').style.display = 'flex';
      document.getElementById('col-toggle-btn').style.display = viewMode === 'table' ? 'block' : 'none';
      await loadRecords();
      loadSidebar();
      if (window.innerWidth <= 768) {
        document.body.dataset.mob = 'main';
        const btn = document.getElementById('mob-back');
        btn.classList.remove('hidden');
        document.getElementById('mob-back-label').textContent = currentProject ? currentProject : 'Resources';
      }
    }

    function mobBack() {
      delete document.body.dataset.mob;
      document.getElementById('mob-back').classList.add('hidden');
    }

    async function deleteRecord(id) {
      const url = currentProject
        ? `${BASE}/${currentProject}/${selectedResource}/${id}`
        : `${BASE}/${selectedResource}/${id}`;
      await fetch(url, { method: 'DELETE' });
      loadRecords();
      loadSidebar();
    }

    // ── Resource CRUD ─────────────────────────────────────────────────────────

    async function deleteResource(name) {
      if (!await confirmDialog(`Delete resource "${name}" and all its records?`)) return;
      await fetch(`${BASE}/_api/resources/${name}`, { method: 'DELETE' });
      checkedResources.delete(name);
      if (selectedResource === name) resetMain('api.kenleyr.com');
      loadSidebar();
    }

    async function deleteProjResource(name) {
      if (!await confirmDialog(`Delete resource "${name}" and all its records?`)) return;
      await fetch(`${BASE}/_api/projects/${currentProject}/resources/${name}`, { method: 'DELETE' });
      if (selectedResource === name) resetMain(`api.kenleyr.com/${currentProject}`);
      loadSidebar();
    }

    async function deleteProject(name) {
      if (!await confirmDialog(`Delete folder "${name}" and all its resources?`)) return;
      await fetch(`${BASE}/_api/projects/${name}`, { method: 'DELETE' });
      loadSidebar();
    }

    // ── Modals ────────────────────────────────────────────────────────────────

    function showModal(id) { document.getElementById(id).style.display = 'flex'; }
    function closeModal(id) { document.getElementById(id).style.display = 'none'; }

    function openNewResource() {
      document.getElementById('modal-resource-title').textContent =
        currentProject ? `New Resource in ${currentProject}` : 'New Resource';
      document.getElementById('resource-name-input').value = '';
      showModal('modal-resource');
      setTimeout(() => document.getElementById('resource-name-input').focus(), 50);
    }

    async function confirmNewResource() {
      const name = document.getElementById('resource-name-input').value.trim();
      if (!name) return;
      const url = currentProject
        ? `${BASE}/_api/projects/${currentProject}/resources`
        : `${BASE}/_api/resources`;
      const res = await fetch(url, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name}) });
      if (res.ok) { closeModal('modal-resource'); await loadSidebar(); selectResource(name); }
      else { const e = await res.json(); alert(e.detail || 'Error'); }
    }

    function openNewProject() {
      document.getElementById('project-name-input').value = '';
      showModal('modal-project');
      setTimeout(() => document.getElementById('project-name-input').focus(), 50);
    }

    async function confirmNewProject() {
      const name = document.getElementById('project-name-input').value.trim();
      if (!name) return;
      const res = await fetch(`${BASE}/_api/projects`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name}) });
      if (res.ok) { closeModal('modal-project'); await loadSidebar(); enterProject(name); }
      else { const e = await res.json(); alert(e.detail || 'Error'); }
    }

    function openRename(name) {
      renamingResource = name; renamingProject = null;
      document.getElementById('modal-rename-title').textContent = 'Rename Resource';
      document.getElementById('rename-input').value = name;
      showModal('modal-rename');
      setTimeout(() => document.getElementById('rename-input').select(), 50);
    }

    function openRenameProjResource(name) {
      renamingResource = name; renamingProject = currentProject;
      document.getElementById('modal-rename-title').textContent = 'Rename Resource';
      document.getElementById('rename-input').value = name;
      showModal('modal-rename');
      setTimeout(() => document.getElementById('rename-input').select(), 50);
    }

    function openRenameProject(name) {
      renamingResource = null; renamingProject = name;
      document.getElementById('modal-rename-title').textContent = 'Rename Folder';
      document.getElementById('rename-input').value = name;
      showModal('modal-rename');
      setTimeout(() => document.getElementById('rename-input').select(), 50);
    }

    async function confirmRename() {
      const newName = document.getElementById('rename-input').value.trim();
      closeModal('modal-rename');
      if (!newName) return;

      if (renamingResource && renamingProject) {
        const res = await fetch(`${BASE}/_api/projects/${renamingProject}/resources/${renamingResource}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: newName}) });
        if (res.ok) { if (selectedResource === renamingResource) { selectedResource = newName; } await loadSidebar(); }
        else { const e = await res.json(); alert(e.detail || 'Error'); }
      } else if (renamingResource) {
        const res = await fetch(`${BASE}/_api/resources/${renamingResource}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: newName}) });
        if (res.ok) { if (selectedResource === renamingResource) selectedResource = newName; await loadSidebar(); if (selectedResource === newName) selectResource(newName); }
        else { const e = await res.json(); alert(e.detail || 'Error'); }
      } else if (renamingProject) {
        const res = await fetch(`${BASE}/_api/projects/${renamingProject}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: newName}) });
        if (res.ok) { if (currentProject === renamingProject) currentProject = newName; await loadSidebar(); }
        else { const e = await res.json(); alert(e.detail || 'Error'); }
      }
    }

    let dataEditor = null;

    async function openViewData() {
      const url = currentProject
        ? `${BASE}/_api/projects/${currentProject}/data/${selectedResource}`
        : `${BASE}/_api/data/${selectedResource}`;
      const records = await fetch(url).then(r => r.json());
      document.getElementById('modal-data-title').textContent = `Data — ${selectedResource}`;
      showModal('modal-data');
      const container = document.getElementById('data-body-editor');
      if (!dataEditor) {
        dataEditor = CodeMirror(container, {
          mode: { name: 'javascript', json: true },
          theme: 'one-dark',
          lineNumbers: true,
          matchBrackets: true,
          autoCloseBrackets: true,
          lineWrapping: false,
          tabSize: 2,
          indentWithTabs: false,
          extraKeys: { 'Ctrl-Space': 'autocomplete' },
        });
        dataEditor.setSize('100%', '400px');
      }
      dataEditor.setValue(JSON.stringify(records, null, 2));
      setTimeout(() => dataEditor.refresh(), 50);
    }

    async function saveAllData() {
      let body;
      const raw = dataEditor ? dataEditor.getValue() : '';
      try {
        const parsed = JSON.parse(raw);
        body = Array.isArray(parsed) ? parsed : [parsed];
      } catch { alert('Invalid JSON'); return; }
      const url = currentProject
        ? `${BASE}/_api/projects/${currentProject}/data/${selectedResource}`
        : `${BASE}/_api/data/${selectedResource}`;
      await fetch(url, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
      closeModal('modal-data');
      loadRecords(); loadSidebar();
    }

    function viewRecord(jsonStr) {
      const record = JSON.parse(jsonStr);
      document.getElementById('modal-view-title').textContent = `Record #${record.id}`;
      document.getElementById('modal-view-body').textContent = JSON.stringify(record, null, 2);
      showModal('modal-view');
    }

    async function confirmAddRecord() {
      let body;
      try { body = JSON.parse(document.getElementById('record-body-input').value); }
      catch { alert('Invalid JSON'); return; }
      const url = currentProject ? `${BASE}/${currentProject}/${selectedResource}` : `${BASE}/${selectedResource}`;
      await fetch(url, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
      closeModal('modal-record');
      loadRecords(); loadSidebar();
    }

    // ── Multi-select (flat resources only) ───────────────────────────────────

    function toggleCheckResource(name, checked) {
      if (checked) checkedResources.add(name); else checkedResources.delete(name);
      updateDeleteBtn();
    }

    function updateDeleteBtn() {
      const btn = document.getElementById('delete-selected-res-btn');
      if (!currentProject && checkedResources.size > 0) {
        btn.style.display = 'block';
        btn.textContent = `Delete (${checkedResources.size})`;
      } else {
        btn.style.display = 'none';
      }
    }

    async function deleteSelectedResources() {
      if (!checkedResources.size) return;
      const toDelete = [...checkedResources];
      await Promise.all(toDelete.map(n => fetch(`${BASE}/_api/resources/${n}`, { method: 'DELETE' })));
      toDelete.forEach(n => { checkedResources.delete(n); if (selectedResource === n) resetMain('api.kenleyr.com'); });
      await loadSidebar();
    }

    // ── Column management ─────────────────────────────────────────────────────

    function toggleColDropdown() {
      const d = document.getElementById('col-dropdown');
      d.style.display = d.style.display === 'none' ? 'block' : 'none';
    }

    function buildColDropdown() {
      document.getElementById('col-dropdown').innerHTML = allColumns.map(c => `
        <label style="display:flex;align-items:center;gap:8px;padding:6px 8px;color:rgba(255,255,255,0.7);font-size:13px;cursor:pointer;border-radius:6px;white-space:nowrap" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background=''">
          <input type="checkbox" ${hiddenColumns.has(c) ? '' : 'checked'} onchange="toggleCol('${c}',this.checked)" style="accent-color:#60a5fa"> ${c}
        </label>`).join('');
    }

    function toggleCol(col, visible) {
      if (visible) hiddenColumns.delete(col); else hiddenColumns.add(col);
      loadRecords();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    function esc(s) { return s.replace(/'/g, "\\'"); }

    // ── Clipboard ─────────────────────────────────────────────────────────────

    function copyToClipboard(text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
      } else {
        fallbackCopy(text);
      }
    }

    function fallbackCopy(text) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }

    function copyUrl(el, url) {
      copyToClipboard(url);
      const prev = el.textContent;
      el.textContent = 'Copied!';
      el.style.color = '#4ade80';
      setTimeout(() => { el.textContent = prev; el.style.color = ''; }, 1800);
    }

    // ── Confirm dialog ────────────────────────────────────────────────────────

    function confirmDialog(message) {
      return new Promise(resolve => {
        document.getElementById('modal-confirm-msg').textContent = message;
        showModal('modal-confirm');
        const ok = document.getElementById('modal-confirm-ok');
        const cancel = document.getElementById('modal-confirm-cancel');
        function cleanup(result) {
          ok.replaceWith(ok.cloneNode(true));
          cancel.replaceWith(cancel.cloneNode(true));
          closeModal('modal-confirm');
          resolve(result);
        }
        document.getElementById('modal-confirm-ok').addEventListener('click', () => cleanup(true), { once: true });
        document.getElementById('modal-confirm-cancel').addEventListener('click', () => cleanup(false), { once: true });
      });
    }

    document.addEventListener('click', e => {
      const dd = document.getElementById('col-dropdown');
      const btn = document.getElementById('col-toggle-btn');
      if (dd && !dd.contains(e.target) && e.target !== btn) dd.style.display = 'none';
    });
    document.querySelectorAll('.modal-backdrop').forEach(m =>
      m.addEventListener('click', e => { if (e.target === m) closeModal(m.id); })
    );

    setInterval(async () => { await loadSidebar(); if (selectedResource) await loadRecords(); }, 3000);
    loadSidebar();
  </script>
</body>
</html>
"""
