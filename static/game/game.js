document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('connect');
  const msgs = document.getElementById('messages');
  btn?.addEventListener('click', () => {
    const code = 'demo';
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${proto}://${window.location.host}/ws/game/${code}/`;
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      msgs.innerHTML += '<div>Connected</div>';
      ws.send(JSON.stringify({type: 'hello', payload: 'hi from client'}));
    }
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      msgs.innerHTML += `<div>${JSON.stringify(data)}</div>`;
    }
    ws.onclose = () => msgs.innerHTML += '<div>Disconnected</div>';
  });
});
