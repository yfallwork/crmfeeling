import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    # threaded=True es imprescindible: sin esto, el servidor atiende una sola
    # petición a la vez y una llamada lenta (p. ej. el webhook de WooCommerce
    # aprobando un pedido, que puede tardar hasta 20s hablando con su API)
    # bloquea también el escáner de entradas mientras tanto.
    app.run(debug=True, port=5000, threaded=True)
