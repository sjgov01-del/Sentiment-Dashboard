import socket
import json
import websocket
import threading


class MassiveConnector:
    def __init__(self, api_key, ticker, on_trade, on_quote):
        self.api_key = api_key
        self.ticker = ticker
        self.on_trade = on_trade
        self.on_quote = on_quote
        self.ws = None
        self.running = False

    def connect(self):
        self.running = True

        def on_message(ws, message):
            data = json.loads(message)
            for event in data:
                ev = event.get('ev')
                if ev == 'Q':
                    self.on_quote(
                        bid=event.get('bp', 0),
                        ask=event.get('ap', 0)
                    )
                if ev == 'T':
                    self.on_trade(
                        price=event.get('p', 0),
                        size=event.get('s', 0),
                        ticker=event.get('sym', '')
                    )

        def on_open(ws):
            auth = {"action": "auth", "params": self.api_key}
            ws.send(json.dumps(auth))
            tickers = self.ticker.split(",")
            sub_params = ",".join([f"T.{t},Q.{t}" for t in tickers])
            subscribe = {"action": "subscribe", "params": sub_params}
            ws.send(json.dumps(subscribe))

        def on_error(ws, error):
            pass

        def on_close(ws, code, msg):
            pass

        def run():
            while self.running:
                try:
                    self.ws = websocket.WebSocketApp(
                        "wss://socket.massive.com/stocks",
                        on_message=on_message,
                        on_open=on_open,
                        on_error=on_error,
                        on_close=on_close
                    )
                    self.ws.run_forever(ping_interval=30, ping_timeout=10)
                except Exception:
                    pass
                threading.Event().wait(3)

        threading.Thread(target=run, daemon=True).start()

    def disconnect(self):
        self.running = False
        if self.ws:
            self.ws.close()
            self.ws = None


class DTNConnector:
    def __init__(self, ticker, on_trade, on_quote):
        self.ticker = ticker
        self.on_trade = on_trade
        self.on_quote = on_quote
        self.sock = None
        self.running = False

    def connect(self):
        self.running = True

        def run():
            while self.running:
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.connect(('127.0.0.1', 5009))
                    self.sock.sendall(b'S,SET PROTOCOL,5.2\r\n')
                    threading.Event().wait(2)
                    tickers = self.ticker.split(",")
                    for t in tickers:
                        msg = f'w{t.strip()}\r\n'
                        self.sock.sendall(msg.encode())
                    buffer = ''
                    while self.running:
                        data = self.sock.recv(4096).decode('latin-1')
                        if not data:
                            break
                        buffer += data
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            self.parse_message(line)
                except Exception:
                    threading.Event().wait(3)

        threading.Thread(target=run, daemon=True).start()

    def parse_message(self, line):
        try:
            if not line:
                return
            parts = line.split(',')
            msg_type = parts[0]
            if msg_type == 'Q':
                if len(parts) >= 10:
                    sym = parts[1]
                    price = float(parts[2]) if parts[2] else 0
                    size = int(float(parts[3])) if parts[3] else 0
                    bid = float(parts[7]) if parts[7] else 0
                    ask = float(parts[9]) if parts[9] else 0
                    if bid > 0:
                        self.on_quote(bid=bid, ask=ask)
                    if price > 0 and size > 0:
                        self.on_trade(price=price, size=size, ticker=sym)
        except Exception:
            pass

    def disconnect(self):
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None