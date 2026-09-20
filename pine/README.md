# TradingView → Icarus Bridge alert

Paste `ALERT_TEMPLATE.json` into a **strategy** alert on THE PULSE OF ICARUS
(Order fills **and** alert() function calls). Replace `YOUR_WEBHOOK_SECRET`
with the value in your `.env`.

Numerics are quoted on purpose: an empty TradingView placeholder would
otherwise produce invalid JSON. `meta` is `key=value;key=value` because
TradingView does not escape quotes inside `{{strategy.order.alert_message}}`.

The webhook URL is the public tunnel printed by `icarus-bridge serve`
(`https://….ngrok.io/webhook` or cloudflared).

This is **Brain A** (Pine → Alpaca paper, NQ1! mapped to QQQ). It does not
feed the Python engine. A CME data pack on the chart improves Brain A’s
display; it does not stream bars into `icarus_engine`. See [DATA.md](../DATA.md).
