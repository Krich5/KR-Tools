from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from pywebpush import webpush, WebPushException
import json
import uuid
import os
import asyncio
import logging

WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")

VAPID_PRIVATE = "FTYj-ts2QY80KyCqL3BQssdi0JW0E1MdABzHdtQ5XXU"
VAPID_PUBLIC  = "BNiAo1vf0_8B4wg1jhZUwEFBv885FnYInGDhd0j-DPo-d6-7kxcful9t-Youyt-aVMSPOKBr4p7qY_hnX1L8fk4"
VAPID_EMAIL   = "mailto:krichardson@cxsol.com"

SUBS_FILE = Path("/app/data/push_subscriptions.json")

def load_subs() -> list:
    if SUBS_FILE.exists():
        try:
            return json.loads(SUBS_FILE.read_text())
        except Exception:
            pass
    return []

def save_subs(subs: list):
    SUBS_FILE.write_text(json.dumps(subs))

def send_push_all(payload: dict):
    subs = load_subs()
    print(f"[push] sending to {len(subs)} subscriber(s): {payload.get('title')}", flush=True)
    if not subs:
        return
    stale = []
    for sub in subs:
        try:
            r = webpush(
                subscription_info=sub,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims={"sub": VAPID_EMAIL},
            )
            print(f"[push] OK {r.status_code}", flush=True)
        except WebPushException as e:
            resp_text = e.response.text if e.response else "none"
            resp_code = e.response.status_code if e.response else 0
            print(f"[push] FAILED {resp_code}: {resp_text}", flush=True)
            if resp_code in (404, 410):
                stale.append(sub)
        except Exception as e:
            print(f"[push] ERROR {type(e).__name__}: {e}", flush=True)
    if stale:
        save_subs([s for s in subs if s not in stale])

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://kenleyr.com", "https://webhooks.kenleyr.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

DATA_FILE = Path("/app/data/storage.json")
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_storage() -> dict:
    if DATA_FILE.exists():
        try:
            raw = json.loads(DATA_FILE.read_text())
            return defaultdict(deque,
                               {k: deque(v) for k, v in raw.items()})
        except Exception:
            pass
    return defaultdict(deque)

def save_storage():
    DATA_FILE.write_text(json.dumps({k: list(v) for k, v in storage.items()}))

storage = load_storage()

HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Webhooks — kenleyr.com</title>
  <meta charset="UTF-8">
  <meta name="theme-color" content="#07101C">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      display: flex; flex-direction: column; height: 100vh;
      background: url('/static/gradient-background-dark.svg') center/cover no-repeat fixed #07101C;
      color: #e2e8f0;
    }
    #body-row { flex: 1; display: flex; overflow: hidden; }

    /* Resizers */
    .resizer {
      width: 5px; flex-shrink: 0; cursor: col-resize; position: relative;
      background: rgba(255,255,255,0.04); transition: background 0.15s; z-index: 5;
    }
    .resizer:hover, .resizer.dragging { background: rgba(74,222,128,0.3); }
    .resizer-btn { display: none; }

    /* Sidebar */
    #sidebar {
      width: 220px; flex-shrink: 0; display: flex; flex-direction: column;
      background: transparent; overflow: hidden; border: none;
      transition: width 0.18s ease;
    }
    #sidebar.sb-hidden { width: 0 !important; }
    #detail-panel.dp-hidden { flex: 0 0 0 !important; min-width: 0 !important; padding: 0 !important; overflow: hidden; }
    #sidebar-top {
      display: flex; align-items: center; justify-content: space-between;
      padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    #sidebar h1 {
      font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
      text-transform: uppercase;
      color: rgba(255,255,255,0.35);
    }
    #delete-selected-btn {
      display: none; background: rgba(248,113,113,0.15); border: 1px solid rgba(248,113,113,0.3);
      color: #f87171; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 11px; font-weight: 600;
    }
    #delete-selected-btn:hover { background: rgba(248,113,113,0.25); }
    #paths { flex: 1; overflow-y: auto; }
    .path-item {
      padding: 11px 16px; cursor: pointer;
      display: flex; align-items: center; gap: 8px;
      border-bottom: 1px solid rgba(255,255,255,0.04);
      transition: background 0.15s;
    }
    .path-item:hover { background: rgba(255,255,255,0.06); }
    .path-item.active {
      background: rgba(74, 222, 128, 0.08);
      border-left: 3px solid #4ade80;
    }
    .path-name { color: #e2e8f0; font-family: monospace; font-size: 13px; flex: 1; }
    .badge {
      background: #4ade80; color: #000;
      border-radius: 10px; padding: 2px 8px;
      font-size: 11px; font-weight: 700;
    }
    .delete-btn {
      background: none; border: none; color: rgba(255,255,255,0.25);
      cursor: pointer; font-size: 13px; padding: 0; line-height: 1; flex-shrink: 0;
    }
    .delete-btn:hover { color: #f87171; }
    .path-check { accent-color: #4ade80; width: 14px; height: 14px; cursor: pointer; flex-shrink: 0; }
    #empty-sidebar { padding: 20px 16px; color: rgba(255,255,255,0.3); font-size: 13px; line-height: 1.8; }
    #empty-sidebar code { color: #4ade80; font-size: 12px; }

    /* Header — full width top bar */
    #header {
      padding: 10px 16px; display: flex; align-items: center; gap: 8px;
      background: transparent; border-bottom: 1px solid rgba(255,255,255,0.08);
      flex-shrink: 0;
    }
    /* Main area */
    #main { flex: 1; display: flex; overflow: hidden; }
    #header h2 { font-size: 14px; font-weight: 600; color: #fff; }
    .url-label { font-family: monospace; font-size: 11px; color: rgba(255,255,255,0.35); }
    #copy-btn {
      background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12);
      color: rgba(255,255,255,0.6); padding: 4px 10px; border-radius: 6px;
      cursor: pointer; font-size: 11px; font-family: monospace; transition: all 0.15s;
    }
    #copy-btn:hover { background: rgba(255,255,255,0.12); color: #fff; }
    #copy-btn.copied { background: rgba(74,222,128,0.15); border-color: rgba(74,222,128,0.4); color: #4ade80; }
    .live-dot { width: 7px; height: 7px; background: #4ade80; border-radius: 50%; animation: pulse 2s infinite; flex-shrink: 0; }
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
    #flow-btn {
      margin-left: auto; border: 1px solid rgba(96,165,250,0.4);
      background: rgba(96,165,250,0.1); color: #60a5fa;
      padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600;
      transition: all 0.15s;
    }
    #flow-btn:hover { background: rgba(96,165,250,0.2); }
    #flow-btn.copied { border-color: rgba(74,222,128,0.4); background: rgba(74,222,128,0.1); color: #4ade80; }
    #clear-btn {
      border: 1px solid rgba(248,113,113,0.4);
      background: rgba(248,113,113,0.1); color: #f87171;
      padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; display: none;
    }
    #clear-btn:hover { background: rgba(248,113,113,0.2); }
    #sort-btn {
      background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12);
      color: rgba(255,255,255,0.5); padding: 4px 9px; border-radius: 6px;
      cursor: pointer; font-size: 11px; transition: all 0.15s;
    }
    #sort-btn:hover { background: rgba(255,255,255,0.12); color: #fff; }
    #pause-btn {
      background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12);
      color: rgba(255,255,255,0.5); padding: 4px 9px; border-radius: 6px;
      cursor: pointer; font-size: 11px; transition: all 0.15s; display: flex; align-items: center; gap: 5px;
    }
    #pause-btn:hover { background: rgba(255,255,255,0.12); color: #fff; }
    #pause-btn.paused { background: rgba(251,191,36,0.12); border-color: rgba(251,191,36,0.3); color: #fbbf24; }
    #pause-btn.paused:hover { background: rgba(251,191,36,0.2); }

    /* Split pane */
    #content { flex: 1; display: flex; overflow: hidden; }

    /* Feed list (left) */
    #feed-col {
      width: 360px; flex-shrink: 0; display: flex; flex-direction: column; border: none;
    }
    #feed-actions {
      display: none; align-items: center; gap: 8px; padding: 6px 12px;
      background: rgba(74,222,128,0.06); border-bottom: 1px solid rgba(74,222,128,0.12);
      flex-shrink: 0;
    }
    #feed-actions-count { font-size: 11px; color: rgba(255,255,255,0.45); flex: 1; }
    #feed-delete-btn {
      background: rgba(248,113,113,0.15); border: 1px solid rgba(248,113,113,0.3);
      color: #f87171; padding: 3px 10px; border-radius: 5px; cursor: pointer; font-size: 11px;
    }
    #feed-delete-btn:hover { background: rgba(248,113,113,0.28); }
    #feed-selall-btn {
      background: none; border: none; color: rgba(255,255,255,0.35);
      cursor: pointer; font-size: 11px; padding: 3px 6px;
    }
    #feed-selall-btn:hover { color: #fff; }
    #feed-list { flex: 1; overflow-y: auto; }
    .feed-item {
      padding: 10px 12px 10px 8px; cursor: pointer; position: relative;
      border-bottom: 1px solid rgba(255,255,255,0.05);
      transition: background 0.12s; display: flex; flex-direction: column; gap: 6px;
    }
    .feed-item:hover { background: rgba(255,255,255,0.05); }
    .feed-item.active { background: rgba(74,222,128,0.07); border-left: 3px solid #4ade80; padding-left: 5px; }
    .feed-item.fi-selected { background: rgba(74,222,128,0.04); }
    .feed-item-top { display: flex; align-items: center; gap: 6px; }
    .feed-check { width: 14px; height: 14px; cursor: pointer; flex-shrink: 0; accent-color: #4ade80; }
    .feed-time { font-size: 11px; color: rgba(255,255,255,0.3); margin-left: auto; }
    .feed-dismiss {
      background: none; border: none; color: rgba(255,255,255,0.2);
      cursor: pointer; font-size: 13px; line-height: 1; padding: 0 2px; flex-shrink: 0;
      opacity: 0; transition: opacity 0.12s, color 0.12s;
    }
    .feed-item:hover .feed-dismiss { opacity: 1; }
    .feed-dismiss:hover { color: #f87171; }
    .feed-preview { font-size: 12px; color: rgba(255,255,255,0.5); font-family: monospace; line-height: 1.7; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; padding-left: 20px; }
    .feed-empty { padding: 20px 14px; font-size: 13px; color: rgba(255,255,255,0.25); }

    /* Detail panel (right) */
    #detail-panel {
      flex: 1; overflow-y: auto; padding: 20px 24px;
    }
    #detail-empty {
      display: flex; flex-direction: column; align-items: center;
      justify-content: center; height: 100%;
      color: rgba(255,255,255,0.2); gap: 8px; font-size: 14px;
    }
    #detail-empty .hint { font-size: 12px; font-family: monospace; color: rgba(255,255,255,0.15); }

    /* Detail card */
    .detail-card { background: rgba(255,255,255,0.05); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; overflow: hidden; }
    .detail-header { padding: 12px 16px; display: flex; align-items: center; gap: 10px; background: rgba(255,255,255,0.04); border-bottom: 1px solid rgba(255,255,255,0.07); }
    .method { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; font-family: monospace; }
    .method.POST  { background: rgba(74,222,128,0.15); color: #4ade80; border: 1px solid rgba(74,222,128,0.3); }
    .method.GET   { background: rgba(96,165,250,0.15); color: #60a5fa; border: 1px solid rgba(96,165,250,0.3); }
    .method.PUT   { background: rgba(251,191,36,0.15); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
    .method.PATCH { background: rgba(192,132,252,0.15); color: #c084fc; border: 1px solid rgba(192,132,252,0.3); }
    .method.DELETE{ background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid rgba(248,113,113,0.3); }
    .timestamp { font-size: 12px; color: rgba(255,255,255,0.3); margin-left: auto; }
    .detail-body { padding: 18px; }
    .section-label { font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
    .fields-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .fields-table tr { border-bottom: 1px solid rgba(255,255,255,0.06); }
    .fields-table tr:last-child { border-bottom: none; }
    .fields-table td { padding: 9px 4px; vertical-align: top; }
    .field-key { color: rgba(255,255,255,0.4); font-weight: 600; white-space: nowrap; width: 1%; padding-right: 20px; font-family: monospace; }
    .field-val { color: #e2e8f0; font-family: monospace; word-break: break-all; }
    .field-val-wrap { display: flex; align-items: center; gap: 8px; }
    .copy-field-btn {
      background: none; border: none; color: rgba(255,255,255,0.2);
      cursor: pointer; padding: 2px 4px; border-radius: 4px;
      flex-shrink: 0; transition: all 0.15s; display: flex; align-items: center;
    }
    .copy-field-btn:hover { background: rgba(255,255,255,0.08); color: #4ade80; }
    .copy-field-btn.ok { color: #4ade80; }
    .pre-wrap { position: relative; }
    .copy-raw-btn {
      position: absolute; top: 8px; right: 8px;
      background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.14);
      color: rgba(255,255,255,0.5); padding: 5px 12px; border-radius: 7px;
      font-size: 12px; font-weight: 600; font-family: inherit;
      cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px;
    }
    .copy-raw-btn:hover { background: rgba(255,255,255,0.13); color: #fff; }
    .copy-raw-btn.ok { background: rgba(74,222,128,0.12); color: #4ade80; border-color: rgba(74,222,128,0.4); }
    pre { font-family: 'SF Mono', Monaco, monospace; font-size: 12px; background: rgba(0,0,0,0.3); color: #cdd6f4; padding: 12px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; border: 1px solid rgba(255,255,255,0.06); }
    .empty-body { color: rgba(255,255,255,0.25); font-size: 13px; font-style: italic; }
    .dismiss-btn {
      background: none; border: none; color: rgba(255,255,255,0.25);
      cursor: pointer; font-size: 16px; line-height: 1; padding: 0 0 0 4px; flex-shrink: 0;
    }
    .dismiss-btn:hover { color: #f87171; }

    /* ── Mobile: single-column drill-down ── */
    #mob-back { display: none; }
    @media (max-width: 768px) {
      body { height: 100dvh; }
      #header { padding: 10px 14px; gap: 8px; flex-wrap: nowrap; overflow: visible; }
      #header h2 { font-size: 14px; white-space: nowrap; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
      /* Hide non-essential buttons on mobile — keep pause + clear */
      #copy-btn, #sort-btn, #flow-btn { display: none !important; }
      #pause-btn, #clear-btn { font-size: 12px; padding: 5px 10px; }
      .resizer { display: none !important; }
      #body-row { position: relative; overflow: hidden; }
      #sidebar, #feed-col, #detail-panel {
        position: absolute; inset: 0; width: 100% !important; flex: none !important;
        transition: transform 0.28s cubic-bezier(0.4,0,0.2,1);
      }
      /* Default: show endpoints, hide others to the right */
      #sidebar    { transform: translateX(0); z-index: 3; }
      #feed-col   { transform: translateX(100%); z-index: 2; }
      #detail-panel { transform: translateX(200%); z-index: 1; overflow-y: auto; }

      /* States controlled by JS data-mobile attribute on #body-row */
      #body-row[data-mob="feed"] #sidebar     { transform: translateX(-100%); }
      #body-row[data-mob="feed"] #feed-col    { transform: translateX(0); }
      #body-row[data-mob="feed"] #detail-panel { transform: translateX(100%); }

      #body-row[data-mob="detail"] #sidebar    { transform: translateX(-100%); }
      #body-row[data-mob="detail"] #feed-col   { transform: translateX(-100%); }
      #body-row[data-mob="detail"] #detail-panel { transform: translateX(0); z-index: 4; }

      /* Back button */
      #mob-back {
        display: flex; align-items: center; gap: 6px;
        background: none; border: none; color: #60a5fa;
        font-size: 14px; font-weight: 600; cursor: pointer;
        padding: 10px 14px; flex-shrink: 0;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        width: 100%;
        -webkit-tap-highlight-color: transparent;
      }
      #mob-back svg { width: 16px; height: 16px; }
      #mob-back.hidden { display: none; }

      #detail-panel { padding: 0; }
      .detail-back-wrap { padding: 0; }
    }
  </style>
</head>
<body>
  <div id="header">
    <h2 id="header-title">Webhook Receiver</h2>
    <div class="live-dot"></div>
    <span id="header-url" class="url-label">Live</span>
    <button id="copy-btn" onclick="copyBase()">webhooks.kenleyr.com/</button>
    <button id="sort-btn" onclick="toggleSort()">↓ Newest</button>
    <button id="pause-btn" onclick="togglePause()">
      <svg width="10" height="12" viewBox="0 0 10 12" fill="currentColor"><rect x="0" y="0" width="3" height="12" rx="1"/><rect x="7" y="0" width="3" height="12" rx="1"/></svg>
      Live
    </button>
    <button id="flow-btn" onclick="copyFlowNode()" title="Copy Webex Flow Node">Flow Node</button>
    <button id="clear-btn" onclick="clearPath()">Clear</button>
  </div>
  <button id="mob-back" class="hidden" onclick="mobBack()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M15 18l-6-6 6-6"/></svg>
    <span id="mob-back-label">Endpoints</span>
  </button>
  <div id="body-row">
    <div id="sidebar">
      <div id="sidebar-top">
        <h1>Endpoints</h1>
        <button id="delete-selected-btn" onclick="deleteSelected()">Delete Selected</button>
      </div>
      <div id="paths">
        <div id="empty-sidebar">No requests yet.<br>POST to any path:<br><br>
          <code>webhooks.kenleyr.com/customer</code>
        </div>
      </div>
    </div>
    <div id="sb-resizer" class="resizer">
      <button class="resizer-btn" id="sb-toggle" title="Toggle sidebar">‹</button>
    </div>
    <div id="main">
      <div id="content">
        <div id="feed-col">
          <div id="feed-actions">
            <span id="feed-actions-count"></span>
            <button id="feed-selall-btn" onclick="toggleSelectAllFeed()">Select All</button>
            <button id="feed-delete-btn" onclick="deleteFeedSelected()">Delete</button>
          </div>
          <div id="feed-list">
            <div class="feed-empty">Select an endpoint</div>
          </div>
        </div>
        <div id="dp-resizer" class="resizer">
          <button class="resizer-btn" id="dp-toggle" title="Toggle detail panel">›</button>
        </div>
        <div id="detail-panel">
          <div id="detail-empty">
            <span>Select a request from the list</span>
            <span class="hint">New requests appear on the left</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const FLOW_NODE = `flowcontrol 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`;

    function copyFlowNode() {
      navigator.clipboard.writeText(FLOW_NODE).then(() => {
        const btn = document.getElementById('flow-btn');
        const orig = btn.textContent;
        btn.textContent = '✓ Copied';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 2000);
      });
    }

    let selectedPath = null;
    let selectedRequestId = null;
    let checkedPaths = new Set();
    let sortNewest = true;
    let paused = false;
    let requestMap = {};
    let selectedFeedIds = new Set();
    let lastCheckedFeedIdx = -1;
    let currentFeedOrder = [];

    const COPY_ICON  = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
    const CHECK_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
    const PAUSE_ICON = `<svg width="10" height="12" viewBox="0 0 10 12" fill="currentColor"><rect x="0" y="0" width="3" height="12" rx="1"/><rect x="7" y="0" width="3" height="12" rx="1"/></svg>`;
    const PLAY_ICON  = `<svg width="11" height="12" viewBox="0 0 11 12" fill="currentColor"><polygon points="0,0 11,6 0,12"/></svg>`;

    function formatTime(iso) { return new Date(iso).toLocaleString(); }
    function formatTimeShort(iso) {
      const d = new Date(iso);
      return d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
    }

    function bodyPreview(body) {
      if (!body) return '(empty)';
      if (typeof body === 'object') {
        const first = Object.entries(body)[0];
        return first ? `${first[0]}: ${first[1]}` : '{}';
      }
      return String(body).split('\\n')[0].slice(0, 60);
    }

    function toggleSort() {
      sortNewest = !sortNewest;
      document.getElementById('sort-btn').textContent = sortNewest ? '↓ Newest' : '↑ Oldest';
      loadRequests();
    }

    function togglePause() {
      paused = !paused;
      const btn = document.getElementById('pause-btn');
      btn.innerHTML = paused ? (PLAY_ICON + ' Paused') : (PAUSE_ICON + ' Live');
      paused ? btn.classList.add('paused') : btn.classList.remove('paused');
      if (!paused) { loadPaths(); if (selectedPath !== null) loadRequests(); }
    }

    function copyVal(btn, text) {
      const isLabeled = btn.classList.contains('copy-raw-btn');
      btn.innerHTML = isLabeled ? CHECK_ICON + ' Copied!' : CHECK_ICON;
      btn.classList.add('ok');
      setTimeout(() => {
        btn.innerHTML = isLabeled ? COPY_ICON + ' Copy' : COPY_ICON;
        btn.classList.remove('ok');
      }, 1800);
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text);
        } else {
          var ta = document.createElement('textarea');
          ta.value = text; ta.style.cssText = 'position:fixed;opacity:0';
          document.body.appendChild(ta); ta.select(); document.execCommand('copy');
          document.body.removeChild(ta);
        }
      } catch(e) {}
    }

    function copyBase() {
      var btn = document.getElementById('copy-btn');
      var url = 'https://' + btn.textContent.trim();
      var prev = btn.textContent;
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(function() { btn.textContent = prev; btn.classList.remove('copied'); }, 2000);
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url);
        } else {
          var ta = document.createElement('textarea');
          ta.value = url;
          ta.style.cssText = 'position:fixed;opacity:0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
      } catch(e) {}
    }

    function renderFeedList(reqs) {
      const feed = document.getElementById('feed-list');
      if (!reqs.length) { feed.innerHTML = '<div class="feed-empty">No requests yet.</div>'; updateFeedActionsBar(); return; }
      requestMap = {};
      reqs.forEach(r => requestMap[r.id] = r);
      const sorted = sortNewest ? [...reqs] : [...reqs].reverse();
      currentFeedOrder = sorted.map(r => r.id);
      feed.innerHTML = sorted.map((r, idx) => `
        <div class="feed-item ${r.id === selectedRequestId ? 'active' : ''} ${selectedFeedIds.has(r.id) ? 'fi-selected' : ''}" data-id="${r.id}" onclick="showDetailById('${r.id}')">
          <div class="feed-item-top">
            <input type="checkbox" class="feed-check" data-id="${r.id}" data-idx="${idx}" ${selectedFeedIds.has(r.id) ? 'checked' : ''}
              onclick="event.stopPropagation(); toggleFeedCheck('${r.id}', this.checked, ${idx}, event)">
            <span class="method ${r.method}">${r.method}</span>
            <span class="feed-time">${formatTimeShort(r.timestamp)}</span>
            <button class="feed-dismiss" onclick="event.stopPropagation(); dismissRequest('${r.id}')" title="Delete">✕</button>
          </div>
          <div class="feed-preview">${bodyPreview(r.body)}</div>
        </div>`).join('');
      updateFeedActionsBar();
    }

    function showDetailById(id) {
      const r = requestMap[id];
      if (!r) return;
      selectedRequestId = id;
      document.querySelectorAll('.feed-item').forEach(el => el.classList.remove('active'));
      const el = document.querySelector(`.feed-item[data-id="${id}"]`);
      if (el) el.classList.add('active');
      showDetail(r);
      if (window.innerWidth <= 768) {
        document.getElementById('body-row').dataset.mob = 'detail';
        const btn = document.getElementById('mob-back');
        btn.classList.remove('hidden');
        document.getElementById('mob-back-label').textContent = 'Feed';
      }
    }

    function toggleFeedCheck(id, checked, idx, event) {
      if (event.shiftKey && lastCheckedFeedIdx !== -1) {
        const start = Math.min(lastCheckedFeedIdx, idx);
        const end = Math.max(lastCheckedFeedIdx, idx);
        document.querySelectorAll('.feed-check').forEach(function(ch) {
          const ci = parseInt(ch.dataset.idx);
          if (ci >= start && ci <= end) {
            ch.checked = checked;
            const cid = ch.dataset.id;
            const item = ch.closest('.feed-item');
            if (checked) { selectedFeedIds.add(cid); if (item) item.classList.add('fi-selected'); }
            else { selectedFeedIds.delete(cid); if (item) item.classList.remove('fi-selected'); }
          }
        });
      } else {
        const item = document.querySelector(`.feed-item[data-id="${id}"]`);
        if (checked) { selectedFeedIds.add(id); if (item) item.classList.add('fi-selected'); }
        else { selectedFeedIds.delete(id); if (item) item.classList.remove('fi-selected'); }
        lastCheckedFeedIdx = idx;
      }
      updateFeedActionsBar();
    }

    function updateFeedActionsBar() {
      const bar = document.getElementById('feed-actions');
      const count = document.getElementById('feed-actions-count');
      const selAllBtn = document.getElementById('feed-selall-btn');
      const deleteBtn = document.getElementById('feed-delete-btn');
      const total = currentFeedOrder.length;
      if (selectedFeedIds.size > 0) {
        bar.style.display = 'flex';
        count.textContent = selectedFeedIds.size + ' selected';
        deleteBtn.textContent = 'Delete (' + selectedFeedIds.size + ')';
        selAllBtn.textContent = selectedFeedIds.size >= total ? 'Deselect All' : 'Select All';
      } else {
        bar.style.display = 'none';
      }
    }

    function toggleSelectAllFeed() {
      const total = currentFeedOrder.length;
      if (selectedFeedIds.size >= total) {
        selectedFeedIds.clear();
        document.querySelectorAll('.feed-check').forEach(function(ch) { ch.checked = false; });
        document.querySelectorAll('.feed-item').forEach(function(el) { el.classList.remove('fi-selected'); });
      } else {
        currentFeedOrder.forEach(function(id) { selectedFeedIds.add(id); });
        document.querySelectorAll('.feed-check').forEach(function(ch) { ch.checked = true; });
        document.querySelectorAll('.feed-item').forEach(function(el) { el.classList.add('fi-selected'); });
      }
      lastCheckedFeedIdx = -1;
      updateFeedActionsBar();
    }

    async function deleteFeedSelected() {
      if (!selectedFeedIds.size) return;
      const toDelete = [...selectedFeedIds];
      await Promise.all(toDelete.map(function(id) {
        return fetch('https://webhooks.kenleyr.com/_api/request/' + selectedPath, {
          method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id })
        });
      }));
      toDelete.forEach(function(id) {
        selectedFeedIds.delete(id);
        if (selectedRequestId === id) {
          selectedRequestId = null;
          document.getElementById('detail-panel').innerHTML = '<div id="detail-empty"><span>Select a request from the list</span><span class="hint">New requests appear on the left</span></div>';
        }
      });
      lastCheckedFeedIdx = -1;
      await loadRequests();
      loadPaths();
    }

    function escAttr(s) {
      return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;');
    }

    function showDetail(r) {
      const rawText = typeof r.body === 'object' ? JSON.stringify(r.body, null, 2) : (r.body != null ? String(r.body) : '');
      let bodyHtml = '<div class="empty-body">Empty body</div>';
      if (r.body) {
        if (typeof r.body === 'object') {
          const rows = Object.entries(r.body).map(([k, v]) => {
            const val = typeof v === 'object' ? JSON.stringify(v) : String(v);
            return `<tr>
              <td class="field-key">${k}</td>
              <td class="field-val"><div class="field-val-wrap">
                <span>${val}</span>
                <button class="copy-field-btn" data-copy="${escAttr(val)}" onclick="copyVal(this,this.dataset.copy)" title="Copy">${COPY_ICON}</button>
              </div></td></tr>`;
          }).join('');
          bodyHtml = `<table class="fields-table">${rows}</table>`;
        } else {
          bodyHtml = `<pre>${r.body}</pre>`;
        }
      }
      document.getElementById('detail-panel').innerHTML = `
        <div class="detail-card">
          <div class="detail-header">
            <span class="method ${r.method}">${r.method}</span>
            <span style="font-size:13px;color:rgba(255,255,255,0.5);font-family:monospace">/${selectedPath}</span>
            <span class="timestamp">${formatTime(r.timestamp)}</span>
            <button class="dismiss-btn" onclick="dismissRequest('${r.id}')" title="Dismiss">✕</button>
          </div>
          <div class="detail-body">
            <div class="section-label">Raw</div>
            <div class="pre-wrap">
              <pre>${rawText || '(empty)'}</pre>
              ${rawText ? `<button class="copy-raw-btn" data-copy="${escAttr(rawText)}" onclick="copyVal(this,this.dataset.copy)">${COPY_ICON} Copy</button>` : ''}
            </div>
            ${typeof r.body === 'object' && r.body ? `<div class="section-label" style="margin-top:14px">Parsed</div>${bodyHtml}` : ''}
            ${r.query ? `<div class="section-label" style="margin-top:14px">Query</div><pre>${r.query}</pre>` : ''}
          </div>
        </div>`;
    }

    async function loadPaths() {
      const res = await fetch('https://webhooks.kenleyr.com/_api/summary');
      const summary = await res.json();
      const paths = Object.keys(summary).sort();
      const container = document.getElementById('paths');
      if (!paths.length) {
        container.innerHTML = '<div id="empty-sidebar">No requests yet.<br>POST to any path:<br><br><code>webhooks.kenleyr.com/customer</code></div>';
        return;
      }
      container.innerHTML = paths.map(p => `
        <div class="path-item ${p === selectedPath ? 'active' : ''}" onclick="selectPath('${p}')">
          <input type="checkbox" class="path-check" ${checkedPaths.has(p) ? 'checked' : ''} onclick="event.stopPropagation(); toggleCheck('${p}', this.checked)">
          <span class="badge">${summary[p]}</span>
          <span class="path-name">${p}</span>
          <button class="delete-btn" onclick="event.stopPropagation(); deletePath('${p}')">✕</button>
        </div>`).join('');
      updateDeleteSelectedBtn();
    }

    async function loadRequests() {
      if (selectedPath === null || selectedPath === undefined) return;
      const res = await fetch(`https://webhooks.kenleyr.com/_api/requests/${selectedPath}`);
      const reqs = await res.json();
      renderFeedList(reqs);
      // Re-highlight active feed item
      document.querySelectorAll('.feed-item').forEach(el => {
        if (el.onclick && el.getAttribute('data-id') === selectedRequestId) el.classList.add('active');
      });
    }

    async function selectPath(path) {
      selectedPath = path;
      selectedRequestId = null;
      selectedFeedIds.clear();
      lastCheckedFeedIdx = -1;
      document.getElementById('header-title').textContent = '/' + path;
      document.getElementById('header-url').textContent = 'webhooks.kenleyr.com/' + path;
      document.getElementById('clear-btn').style.display = 'block';
      document.getElementById('copy-btn').textContent = 'webhooks.kenleyr.com/' + path;
      document.getElementById('detail-panel').innerHTML = '<div id="detail-empty"><span>Select a request from the list</span><span class="hint">New requests appear on the left</span></div>';
      await loadRequests();
      loadPaths();
      if (window.innerWidth <= 768) {
        document.getElementById('body-row').dataset.mob = 'feed';
        const btn = document.getElementById('mob-back');
        btn.classList.remove('hidden');
        document.getElementById('mob-back-label').textContent = 'Endpoints';
      }
    }

    function mobBack() {
      const row = document.getElementById('body-row');
      const btn = document.getElementById('mob-back');
      const state = row.dataset.mob;
      if (state === 'detail') {
        row.dataset.mob = 'feed';
        document.getElementById('mob-back-label').textContent = 'Endpoints';
      } else {
        delete row.dataset.mob;
        btn.classList.add('hidden');
      }
    }

    function resetMain() {
      document.getElementById('header-title').textContent = 'Webhook Receiver';
      document.getElementById('header-url').textContent = 'Live';
      document.getElementById('clear-btn').style.display = 'none';
      document.getElementById('copy-btn').textContent = 'webhooks.kenleyr.com/';
      document.getElementById('feed-list').innerHTML = '<div class="feed-empty">Select an endpoint</div>';
      document.getElementById('detail-panel').innerHTML = '<div id="detail-empty"><span>Select a request from the list</span><span class="hint">New requests appear on the left</span></div>';
    }

    async function clearPath() {
      if (selectedPath === null) return;
      await fetch(`https://webhooks.kenleyr.com/_api/clear/${encodeURIComponent(selectedPath)}`, { method: 'DELETE' });
      checkedPaths.delete(selectedPath);
      selectedPath = null; selectedRequestId = null;
      resetMain(); loadPaths();
    }

    async function deletePath(path) {
      await fetch(`https://webhooks.kenleyr.com/_api/clear/${encodeURIComponent(path)}`, { method: 'DELETE' });
      checkedPaths.delete(path);
      if (selectedPath === path) { selectedPath = null; selectedRequestId = null; resetMain(); }
      await loadPaths();
    }

    function toggleCheck(path, checked) {
      checked ? checkedPaths.add(path) : checkedPaths.delete(path);
      updateDeleteSelectedBtn();
    }

    function updateDeleteSelectedBtn() {
      const btn = document.getElementById('delete-selected-btn');
      if (checkedPaths.size > 0) { btn.style.display = 'block'; btn.textContent = `Delete (${checkedPaths.size})`; }
      else btn.style.display = 'none';
    }

    async function deleteSelected() {
      if (!checkedPaths.size) return;
      const toDelete = [...checkedPaths];
      await Promise.all(toDelete.map(p => fetch(`https://webhooks.kenleyr.com/_api/clear/${encodeURIComponent(p)}`, { method: 'DELETE' })));
      toDelete.forEach(p => {
        checkedPaths.delete(p);
        if (selectedPath === p) { selectedPath = null; selectedRequestId = null; resetMain(); }
      });
      await loadPaths();
    }

    async function dismissRequest(id) {
      await fetch(`https://webhooks.kenleyr.com/_api/request/${selectedPath}`, {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id })
      });
      if (selectedRequestId === id) {
        selectedRequestId = null;
        document.getElementById('detail-panel').innerHTML = '<div id="detail-empty"><span>Select a request from the list</span><span class="hint">New requests appear on the left</span></div>';
      }
      loadRequests(); loadPaths();
    }

    setInterval(async () => {
      if (paused) return;
      try {
        await loadPaths();
        if (selectedPath !== null) await loadRequests();
      } catch(e) {}
    }, 3000);
    loadPaths();

    // ── Resizable panels ──────────────────────────────────────────
    function initResizer(resizerId, panelId, minW, maxW) {
      var resizer = document.getElementById(resizerId);
      var panel   = document.getElementById(panelId);

      resizer.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('resizer-btn')) return;
        var startX = e.clientX;
        var startW = panel.offsetWidth;

        // Full-page overlay captures mouse even when moving fast
        var overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;cursor:col-resize;';
        document.body.appendChild(overlay);
        resizer.classList.add('dragging');

        overlay.addEventListener('mousemove', function(e2) {
          var w = Math.max(minW, Math.min(maxW, startW + (e2.clientX - startX)));
          panel.style.width = w + 'px';
          panel.style.flex  = '0 0 ' + w + 'px';
        });
        function cleanup() {
          resizer.classList.remove('dragging');
          if (overlay.parentNode) document.body.removeChild(overlay);
          window.removeEventListener('mouseup', cleanup);
        }
        window.addEventListener('mouseup', cleanup);

        e.preventDefault();
      });
    }

    initResizer('sb-resizer', 'sidebar', 120, 400);
    initResizer('dp-resizer', 'feed-col', 200, 700);
  </script>
</body>
</html>
"""


@app.get("/")
async def index():
    return HTMLResponse(HTML)


@app.get("/_api/vapid-key")
async def vapid_key():
    return {"key": VAPID_PUBLIC}


@app.post("/_api/push/subscribe")
async def push_subscribe(request: Request):
    sub = await request.json()
    subs = load_subs()
    # Avoid duplicates (match by endpoint)
    if not any(s.get("endpoint") == sub.get("endpoint") for s in subs):
        subs.append(sub)
        save_subs(subs)
    return {"status": "subscribed", "total": len(subs)}


@app.delete("/_api/push/unsubscribe")
async def push_unsubscribe(request: Request):
    sub = await request.json()
    subs = load_subs()
    subs = [s for s in subs if s.get("endpoint") != sub.get("endpoint")]
    save_subs(subs)
    return {"status": "unsubscribed"}


@app.get("/_api/summary")
async def summary():
    return {path: len(reqs) for path, reqs in storage.items()}


@app.get("/_api/requests/{path:path}")
async def get_requests(path: str):
    return list(storage.get(path, []))


@app.delete("/_api/clear/{path:path}")
async def clear_path(path: str):
    from urllib.parse import unquote
    path = unquote(path)
    if path in storage:
        del storage[path]
    save_storage()
    return {"status": "cleared"}


@app.delete("/_api/request/{path:path}")
async def delete_request(path: str, request: Request):
    body = await request.json()
    req_id = body.get("id")
    if path in storage:
        storage[path] = deque(
            (r for r in storage[path] if r["id"] != req_id)
        )
        if not storage[path]:
            del storage[path]
    save_storage()
    return {"status": "deleted"}


IGNORE_EXTENSIONS = {".js", ".css", ".png", ".ico", ".svg", ".jpg", ".jpeg", ".gif", ".woff", ".woff2", ".ttf", ".map", ".txt", ".php", ".asp", ".aspx", ".jsp", ".xml", ".zip", ".tar", ".gz", ".sql", ".bak", ".backup", ".old", ".orig", ".env", ".log", ".conf", ".config", ".cfg", ".ini", ".yaml", ".yml", ".toml"}
IGNORE_PATHS = {"favicon.ico", "favicon.png", "robots.txt", "sitemap.xml"}
IGNORE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def receive_webhook(path: str, request: Request, background_tasks: BackgroundTasks):
    from pathlib import PurePosixPath
    # Drop scanner/browser noise
    if request.method in IGNORE_METHODS:
        return JSONResponse({"error": "not found"}, status_code=404)
    if path.startswith("_") or path.startswith(".") or path in IGNORE_PATHS:
        return JSONResponse({"error": "not found"}, status_code=404)
    if PurePosixPath(path).suffix in IGNORE_EXTENSIONS:
        return JSONResponse({"error": "not found"}, status_code=404)

    # Token check — return 500 so scanners think the server is broken
    if WEBHOOK_TOKEN:
        provided = request.headers.get("token", "")
        if provided != WEBHOOK_TOKEN:
            return JSONResponse({"error": "internal server error"}, status_code=500)

    # Block root path
    if not path:
        return JSONResponse({"error": "internal server error"}, status_code=500)

    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes)
    except Exception:
        body = body_bytes.decode("utf-8", errors="replace") or None

    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "method": request.method,
        "headers": dict(request.headers),
        "body": body,
        "query": str(request.url.query) if request.url.query else None,
    }

    storage[path].appendleft(entry)
    save_storage()

    # Build a short message preview
    if isinstance(body, dict):
        preview = ", ".join(f"{k}: {v}" for k, v in list(body.items())[:2])
    elif isinstance(body, str) and body:
        preview = body
    else:
        preview = f"{request.method} request"
    preview = preview[:80] + ("…" if len(preview) > 80 else "")

    total = sum(len(v) for v in storage.values())
    background_tasks.add_task(send_push_all, {
        "title": f"Webhook: {path}",
        "body": f"Message: {preview}",
        "path": path,
        "badge": total,
    })

    return JSONResponse({"status": "Message Recieved"}, status_code=200)
