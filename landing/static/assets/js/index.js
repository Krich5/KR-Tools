const FRAMES = ['webhooks', 'mockapi', 'sftp'];

function showPanel(name) {
  document.getElementById('home-view').classList.add('hidden');
  FRAMES.forEach(id => {
    document.getElementById('frame-' + id).classList.remove('active');
    document.getElementById('tab-'   + id).classList.remove('active');
  });
  document.getElementById('tab-home').classList.remove('active');
  document.getElementById('frame-' + name).classList.add('active');
  document.getElementById('tab-'   + name).classList.add('active');
}

function goHome() {
  FRAMES.forEach(id => {
    document.getElementById('frame-' + id).classList.remove('active');
    document.getElementById('tab-'   + id).classList.remove('active');
  });
  document.getElementById('home-view').classList.remove('hidden');
  document.getElementById('tab-home').classList.add('active');
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
