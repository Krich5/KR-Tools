from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from pathlib import Path
import secrets, time, os
import bcrypt

app = FastAPI()

AUTH_USER = os.environ.get("AUTH_USER", "")
AUTH_PASS_HASH = os.environ.get("AUTH_PASS_HASH", "")
SESSIONS: dict[str, float] = {}
COOKIE = "kr_sess"
SESSION_DAYS = 7


def new_session() -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = time.time() + SESSION_DAYS * 86400
    return token


def valid(token: str | None) -> bool:
    if not token:
        return False
    exp = SESSIONS.get(token)
    return bool(exp and time.time() < exp)


STATIC = Path("/app/static")
PAGES = STATIC / "pages"
LEGACY_ALIASES = {
    "index.html": PAGES / "index.html",
    "styles.css": STATIC / "assets" / "css" / "styles.css",
    "css/styles.css": STATIC / "assets" / "css" / "styles.css",
    "js/index.js": STATIC / "assets" / "js" / "index.js",
    "js/webex/home.js": STATIC / "assets" / "js" / "webex" / "home.js",
    "icon-192.png": STATIC / "assets" / "images" / "icon-192.png",
    "icon-512.png": STATIC / "assets" / "images" / "icon-512.png",
}


@app.get("/login")
def login_page(bad: str = ""):
    return HTMLResponse(login_html(bool(bad)))


@app.post("/login")
def login_post(username: str = Form(...), password: str = Form(...)):
    if username == AUTH_USER and bcrypt.checkpw(password.encode(), AUTH_PASS_HASH.encode()):
        token = new_session()
        r = RedirectResponse("/", status_code=302)
        r.set_cookie(
            COOKIE,
            token,
            max_age=SESSION_DAYS * 86400,
            httponly=True,
            samesite="lax"
        )
        return r
    return HTMLResponse(login_html(True), status_code=401)


@app.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=302)
    r.delete_cookie(COOKIE)
    return r


# Public assets needed for PWA installability
PUBLIC = {
    "sw.js",
    "manifest.json",
    "favicon.ico",
    "icon-192.png",
    "icon-512.png",
    "assets/images/icon-192.png",
    "assets/images/icon-512.png",
    "assets/images/kr-logo.png",
    "assets/css/styles.css",
    "assets/js/index.js",
    "gradient-background-dark.svg",
    "apple-touch-icon.png",
}


@app.get("/")
def root(request: Request):
    if not valid(request.cookies.get(COOKIE)):
        return RedirectResponse("/login")
    return FileResponse(PAGES / "index.html")


@app.get("/{path:path}")
def serve(request: Request, path: str):
    legacy_target = LEGACY_ALIASES.get(path)

    # Allow public assets without auth
    if path in PUBLIC:
        target = STATIC / path
        if target.is_file():
            return FileResponse(target)
        if legacy_target and legacy_target.is_file():
            return FileResponse(legacy_target)
        return RedirectResponse("/login")

    # Require auth for everything else
    if not valid(request.cookies.get(COOKIE)):
        return RedirectResponse("/login")

    target = STATIC / path
    page_target = PAGES / path

    # Serve file if it exists
    if target.is_file():
        return FileResponse(target)
    if page_target.is_file():
        return FileResponse(page_target)
    if legacy_target and legacy_target.is_file():
        return FileResponse(legacy_target)

    # 🔴 KEY FIX: do NOT fall back to index.html
    # This prevents iframe infinite loops
    raise HTTPException(status_code=404, detail="File not found")


def login_html(error: bool) -> str:
    err_block = """
      <div class="err-msg">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        Incorrect username or password
      </div>""" if error else ""

    return f"""<!DOCTYPE html>
<html>
<head>
  <title>KR Tools</title>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#07101C">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ height: 100%; background: #07101C; }}
    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      min-height: 100%; min-height: 100dvh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #07101C;
      color: #e2e8f0;
      overflow-x: hidden;
    }}
    .bg {{ position: fixed; inset: 0; width: 100%; height: 100%; z-index: 0; }}
    input:-webkit-autofill,
    input:-webkit-autofill:hover,
    input:-webkit-autofill:focus {{
      -webkit-box-shadow: 0 0 0px 1000px rgba(59,123,245,0.08) inset !important;
      -webkit-text-fill-color: #e2e8f0 !important;
      caret-color: #e2e8f0;
    }}

    @keyframes fade-up {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}

    .wrap {{
      position: relative;
      z-index: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
      max-width: 400px;
      padding: 0 24px;
      animation: fade-up 0.5s ease both;
    }}

    /* Logo section */
    .logo-wrap {{
      margin-bottom: 36px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .logo-img {{
      width: 130px;
      height: auto;
    }}
    .logo-title {{
      margin-top: 18px;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 5px;
      text-transform: uppercase;
      color: rgba(255,255,255,0.25);
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .logo-title span {{ display: block; height: 1px; width: 32px; }}
    .logo-title span:first-child {{ background: linear-gradient(90deg, transparent, rgba(59,123,245,0.6)); }}
    .logo-title span:last-child  {{ background: linear-gradient(270deg, transparent, rgba(74,222,128,0.6)); }}

    /* Card */
    .card {{
      width: 100%;
      background: rgba(255,255,255,0.04);
      backdrop-filter: blur(32px);
      -webkit-backdrop-filter: blur(32px);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 20px;
      padding: 32px;
      box-shadow:
        0 40px 100px rgba(0,0,0,0.5),
        inset 0 1px 0 rgba(255,255,255,0.06);
    }}

    .err-msg {{
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(248,113,113,0.08);
      border: 1px solid rgba(248,113,113,0.2);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 13px;
      color: #f87171;
      margin-bottom: 16px;
    }}

    .field {{
      position: relative;
      margin-bottom: 12px;
    }}
    .field svg {{
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      color: rgba(255,255,255,0.25);
      pointer-events: none;
    }}
    input {{
      width: 100%;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 11px;
      padding: 13px 16px 13px 42px;
      color: #e2e8f0;
      font-size: 14px;
      font-family: inherit;
      outline: none;
      transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
    }}
    input::placeholder {{ color: rgba(255,255,255,0.25); }}
    input:focus {{
      border-color: rgba(59,123,245,0.45);
      background: rgba(59,123,245,0.05);
      box-shadow: 0 0 0 3px rgba(59,123,245,0.08);
    }}

    button {{
      width: 100%;
      padding: 14px;
      margin-top: 6px;
      background: linear-gradient(135deg, rgba(59,123,245,0.3) 0%, rgba(74,222,128,0.2) 100%);
      border: 1px solid rgba(59,123,245,0.35);
      border-radius: 11px;
      color: #fff;
      font-size: 14px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: all 0.2s;
      letter-spacing: 0.3px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    button:hover {{
      background: linear-gradient(135deg, rgba(59,123,245,0.45) 0%, rgba(74,222,128,0.3) 100%);
      border-color: rgba(59,123,245,0.55);
      transform: translateY(-1px);
      box-shadow: 0 8px 32px rgba(59,123,245,0.25);
    }}
    button:active {{ transform: translateY(0); box-shadow: none; }}
  </style>
</head>
<body>
  <svg class="bg" viewBox="0 0 1440 920" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
    <rect width="1440" height="920" fill="#07101C"/>
    <rect width="1440" height="920" fill="url(#lg0)" fill-opacity="0.8"/>
    <rect width="1440" height="920" fill="url(#lg1)" fill-opacity="0.6"/>
    <rect width="1440" height="920" fill="url(#lg2)" fill-opacity="0.8"/>
    <rect width="1440" height="920" fill="url(#lg3)" fill-opacity="0.15"/>
    <defs>
      <radialGradient id="lg0" cx="0" cy="0" r="1" gradientTransform="matrix(225.5 425 -642.246 254.148 34.5 48)" gradientUnits="userSpaceOnUse"><stop stop-color="#A52C2C"/><stop offset="1" stop-opacity="0"/></radialGradient>
      <radialGradient id="lg1" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(269.5 -108.5) rotate(78.1068) scale(327.531 512.657)"><stop stop-color="#7C03F6"/><stop offset="1" stop-color="#493260" stop-opacity="0"/></radialGradient>
      <radialGradient id="lg2" cx="0" cy="0" r="1" gradientTransform="matrix(21.5 736 -1128.69 100.749 698.5 -134.5)" gradientUnits="userSpaceOnUse"><stop stop-color="#21417C"/><stop offset="0.1" stop-color="#1D6ADB" stop-opacity="0.83"/><stop offset="0.46" stop-color="#1170CF" stop-opacity="0.2"/><stop offset="0.81" stop-opacity="0.1"/></radialGradient>
      <radialGradient id="lg3" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(69.5 886) rotate(-19.5711) scale(1491.15 2333.97)"><stop stop-color="#75006F"/><stop offset="0.48" stop-color="#FF00F2" stop-opacity="0"/></radialGradient>
    </defs>
    <g stroke="#3B7BF5" stroke-width="1" fill="none" opacity="0.12">
      <path d="M 0,400 H 200 V 500 H 320 V 600 H 150 V 700"/>
      <circle cx="200" cy="500" r="3" fill="#3B7BF5"/>
      <circle cx="320" cy="600" r="2.5" fill="#3B7BF5"/>
    </g>
    <g stroke="#4ade80" stroke-width="1" fill="none" opacity="0.12">
      <path d="M 1440,400 H 1240 V 500 H 1120 V 600 H 1290 V 700"/>
      <circle cx="1240" cy="500" r="3" fill="#4ade80"/>
      <circle cx="1120" cy="600" r="2.5" fill="#4ade80"/>
    </g>
  </svg>

  <div class="wrap">
    <div class="logo-wrap">
      <img src="/assets/images/kr-logo.png" alt="KR Tools" class="logo-img">
      <div class="logo-title">
        <span></span>KR TOOLS<span></span>
      </div>
    </div>

    <div class="card">
      {err_block}
      <form method="POST" action="/login">
        <div class="field">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          <input type="text" name="username" placeholder="Username" required autocomplete="username">
        </div>
        <div class="field">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          <input type="password" name="password" placeholder="Password" required autocomplete="current-password">
        </div>
        <button type="submit">
          Sign In
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
      </form>
    </div>
  </div>
</body>
</html>"""
